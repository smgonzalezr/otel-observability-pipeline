"""
service-b: reserva inventario. Lo llama service-a por HTTP.

No crea un trace_id nuevo. Lee la cabecera traceparent que envia service-a y
continua la misma traza, que es lo que permite ver los dos servicios en un
solo diagrama de Jaeger.
"""

import os
import random
import sqlite3
import sys
import time
import uuid

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# Busca el modulo compartido tanto en el repo como dentro del contenedor.
for _ruta in (
    os.path.join(os.path.dirname(__file__), "..", "common"),
    os.path.join(os.path.dirname(__file__), "common"),
):
    if os.path.isdir(_ruta):
        sys.path.insert(0, _ruta)

from telemetry import (  # noqa: E402
    OTEL_ENABLED,
    configurar_logs,
    iniciar_telemetria,
    instrumentar_app,
    log_con_campos,
    trace_id_actual,
)

DB_PATH = os.getenv("DB_PATH", "/tmp/service_b.db")
LATENCIA_BASE_MS = float(os.getenv("LATENCIA_BASE_MS", "4"))

app = FastAPI(title="service-b", version="1.0.0")
logger = configurar_logs()
tracer, meter = iniciar_telemetria()
instrumentar_app(app)


# ------------------------------------------------------ metricas de negocio

if OTEL_ENABLED:
    contador_reservas = meter.create_counter(
        "inventory.reservations",
        unit="{reserva}",
        description="Reservas de inventario procesadas",
    )
    histograma_reserva = meter.create_histogram(
        "inventory.reserve.duration",
        unit="s",
        description="Duracion de la reserva de inventario",
    )
    medidor_stock = meter.create_up_down_counter(
        "inventory.stock.level",
        unit="{unidad}",
        description="Movimiento de existencias",
    )
else:
    class _Nada:
        def add(self, *a, **k):
            pass

        def record(self, *a, **k):
            pass

    contador_reservas = histograma_reserva = medidor_stock = _Nada()


# --------------------------------------------------------------- base de datos


def preparar_bd():
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute(
        """CREATE TABLE IF NOT EXISTS inventario (
               sku TEXT PRIMARY KEY,
               nombre TEXT,
               existencias INTEGER,
               bodega TEXT)"""
    )
    cur.execute(
        """CREATE TABLE IF NOT EXISTS reservas (
               id TEXT PRIMARY KEY,
               sku TEXT,
               cantidad INTEGER,
               pedido_id TEXT,
               creada_en REAL)"""
    )
    filas = cur.execute("SELECT COUNT(*) FROM inventario").fetchone()[0]
    if filas == 0:
        cur.executemany(
            "INSERT INTO inventario VALUES (?,?,?,?)",
            [
                (f"SKU-{1000 + i}", f"Producto {i}", 100000, f"bodega-{i % 3 + 1}")
                for i in range(50)
            ],
        )
    con.commit()
    cur.close()
    con.close()


preparar_bd()


class PeticionReserva(BaseModel):
    sku: str
    cantidad: int
    pedido_id: str


def verificar_existencias(sku: str):
    """Span propio sobre la regla de negocio, mas la consulta automatica."""
    with tracer.start_as_current_span("verificar_existencias") as span:
        span.set_attribute("ecommerce.inventory.sku", sku)
        con = sqlite3.connect(DB_PATH)
        cur = con.cursor()
        fila = cur.execute(
            "SELECT sku, nombre, existencias, bodega FROM inventario WHERE sku = ?", (sku,)
        ).fetchone()
        cur.close()
        con.close()
        if fila:
            span.set_attribute("ecommerce.inventory.available", fila[2])
            span.set_attribute("ecommerce.inventory.warehouse_id", fila[3])
        return fila


def aplicar_reserva(sku: str, cantidad: int, pedido_id: str) -> str:
    with tracer.start_as_current_span("aplicar_reserva") as span:
        reserva_id = f"rsv-{uuid.uuid4().hex[:10]}"
        con = sqlite3.connect(DB_PATH)
        cur = con.cursor()
        cur.execute(
            "UPDATE inventario SET existencias = existencias - ? WHERE sku = ?",
            (cantidad, sku),
        )
        cur.execute(
            "INSERT INTO reservas VALUES (?,?,?,?,?)",
            (reserva_id, sku, cantidad, pedido_id, time.time()),
        )
        con.commit()
        cur.close()
        con.close()
        span.set_attribute("ecommerce.reservation.id", reserva_id)
        return reserva_id


@app.get("/health")
def salud():
    return {"status": "ok", "service": "service-b"}


@app.post("/inventory/reserve")
def reservar(peticion: PeticionReserva):
    inicio = time.perf_counter()

    with tracer.start_as_current_span("reservar_inventario") as span:
        span.set_attribute("ecommerce.inventory.sku", peticion.sku)
        span.set_attribute("ecommerce.order.id", peticion.pedido_id)
        span.set_attribute("ecommerce.cart.item_count", peticion.cantidad)

        log_con_campos(
            logger,
            "info",
            "reserva solicitada",
            **{
                "ecommerce.inventory.sku": peticion.sku,
                "ecommerce.order.id": peticion.pedido_id,
            },
        )

        # Simula el tiempo de una consulta a un sistema externo de bodegas.
        time.sleep(LATENCIA_BASE_MS / 1000.0)

        articulo = verificar_existencias(peticion.sku)
        if articulo is None:
            contador_reservas.add(1, {"resultado": "sku_no_existe"})
            span.set_attribute("error.type", "sku_no_existe")
            log_con_campos(logger, "error", "sku desconocido", **{"ecommerce.inventory.sku": peticion.sku})
            raise HTTPException(status_code=404, detail="sku no existe")

        _, nombre, existencias, bodega = articulo

        if existencias < peticion.cantidad:
            contador_reservas.add(1, {"resultado": "sin_stock", "bodega": bodega})
            span.set_attribute("ecommerce.inventory.result", "sin_stock")
            log_con_campos(
                logger,
                "warning",
                "existencias insuficientes",
                **{
                    "ecommerce.inventory.sku": peticion.sku,
                    "ecommerce.inventory.available": existencias,
                },
            )
            return {"reservado": False, "motivo": "sin_stock", "trace_id": trace_id_actual()}

        reserva_id = aplicar_reserva(peticion.sku, peticion.cantidad, peticion.pedido_id)

        duracion = time.perf_counter() - inicio
        atributos = {"resultado": "ok", "bodega": bodega}
        contador_reservas.add(1, atributos)
        histograma_reserva.record(duracion, atributos)
        medidor_stock.add(-peticion.cantidad, {"sku": peticion.sku, "bodega": bodega})

        span.set_attribute("ecommerce.inventory.result", "reservado")

        log_con_campos(
            logger,
            "info",
            "reserva confirmada",
            **{
                "ecommerce.reservation.id": reserva_id,
                "ecommerce.inventory.sku": peticion.sku,
                "ecommerce.inventory.warehouse_id": bodega,
                "duration_ms": round(duracion * 1000, 2),
            },
        )

        return {
            "reservado": True,
            "reserva_id": reserva_id,
            "producto": nombre,
            "bodega": bodega,
            "trace_id": trace_id_actual(),
        }


@app.get("/inventory/{sku}")
def consultar(sku: str):
    articulo = verificar_existencias(sku)
    if articulo is None:
        raise HTTPException(status_code=404, detail="sku no existe")
    return {"sku": articulo[0], "nombre": articulo[1], "existencias": articulo[2], "bodega": articulo[3]}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8002")), log_level="warning")
