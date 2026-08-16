"""
service-a: recibe la peticion de compra, consulta su base de datos y llama
a service-b para reservar inventario.

Es el servicio de entrada, o sea el que crea el trace_id que despues viaja
por toda la cadena.
"""

import os
import random
import sqlite3
import sys
import time
import uuid

import httpx
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

SERVICE_B_URL = os.getenv("SERVICE_B_URL", "http://localhost:8002")
DB_PATH = os.getenv("DB_PATH", "/tmp/service_a.db")

app = FastAPI(title="service-a", version="1.0.0")
logger = configurar_logs()
tracer, meter = iniciar_telemetria()
instrumentar_app(app)

cliente = httpx.Client(timeout=5.0)


# ------------------------------------------------------ metricas de negocio

if OTEL_ENABLED:
    contador_pedidos = meter.create_counter(
        "ecommerce.orders.created",
        unit="{pedido}",
        description="Pedidos creados por service-a",
    )
    contador_fallos = meter.create_counter(
        "ecommerce.orders.failed",
        unit="{pedido}",
        description="Pedidos que no se pudieron completar",
    )
    histograma_checkout = meter.create_histogram(
        "ecommerce.checkout.duration",
        unit="s",
        description="Duracion del flujo de compra completo",
    )
    histograma_monto = meter.create_histogram(
        "ecommerce.order.amount",
        unit="{moneda}",
        description="Monto de los pedidos creados",
    )
else:  # objetos vacios para la corrida sin instrumentacion
    class _Nada:
        def add(self, *a, **k):
            pass

        def record(self, *a, **k):
            pass

    contador_pedidos = contador_fallos = histograma_checkout = histograma_monto = _Nada()


# --------------------------------------------------------------- base de datos


def preparar_bd():
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute(
        """CREATE TABLE IF NOT EXISTS clientes (
               id TEXT PRIMARY KEY,
               nombre TEXT,
               tier TEXT,
               descuento REAL)"""
    )
    cur.execute(
        """CREATE TABLE IF NOT EXISTS pedidos (
               id TEXT PRIMARY KEY,
               cliente_id TEXT,
               monto REAL,
               estado TEXT,
               creado_en REAL)"""
    )
    filas = cur.execute("SELECT COUNT(*) FROM clientes").fetchone()[0]
    if filas == 0:
        cur.executemany(
            "INSERT INTO clientes VALUES (?,?,?,?)",
            [
                (f"cli-{i:03d}", f"Cliente {i}", tier, desc)
                for i, (tier, desc) in enumerate(
                    [("gold", 0.10), ("silver", 0.05), ("basic", 0.0)] * 20
                )
            ],
        )
    con.commit()
    cur.close()
    con.close()


preparar_bd()


# ------------------------------------------------------------------ modelos


class PeticionCompra(BaseModel):
    cliente_id: str = "cli-001"
    sku: str = "SKU-1001"
    cantidad: int = 1
    precio_unitario: float = 25000.0


# ----------------------------------------------------------- logica de negocio


def calcular_total(precio: float, cantidad: int, descuento: float) -> float:
    """
    Span propio. La auto instrumentacion no puede ver esto porque no pasa
    por HTTP ni por la base de datos, es calculo puro de negocio.
    """
    with tracer.start_as_current_span("calcular_total_pedido") as span:
        bruto = precio * cantidad
        total = round(bruto * (1 - descuento), 2)
        span.set_attribute("ecommerce.order.subtotal", bruto)
        span.set_attribute("ecommerce.order.discount_rate", descuento)
        span.set_attribute("ecommerce.order.total_amount", total)
        span.set_attribute("ecommerce.order.currency", "COP")
        span.set_attribute("ecommerce.cart.item_count", cantidad)
        return total


def buscar_cliente(cliente_id: str):
    """La consulta la instrumenta sqlite3 de forma automatica."""
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    fila = cur.execute(
        "SELECT id, nombre, tier, descuento FROM clientes WHERE id = ?", (cliente_id,)
    ).fetchone()
    cur.close()
    con.close()
    return fila


def guardar_pedido(pedido_id, cliente_id, monto, estado):
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute(
        "INSERT INTO pedidos VALUES (?,?,?,?,?)",
        (pedido_id, cliente_id, monto, estado, time.time()),
    )
    con.commit()
    cur.close()
    con.close()


# --------------------------------------------------------------- endpoints


@app.get("/health")
def salud():
    return {"status": "ok", "service": "service-a"}


@app.post("/checkout")
def checkout(peticion: PeticionCompra):
    inicio = time.perf_counter()
    pedido_id = f"ord-{uuid.uuid4().hex[:12]}"

    # Span que envuelve todo el flujo de negocio.
    with tracer.start_as_current_span("flujo_checkout") as span:
        span.set_attribute("ecommerce.order.id", pedido_id)
        span.set_attribute("ecommerce.checkout.step", "payment")
        span.set_attribute("enduser.id", peticion.cliente_id)

        log_con_campos(
            logger,
            "info",
            "checkout iniciado",
            **{
                "ecommerce.order.id": pedido_id,
                "ecommerce.checkout.step": "cart",
                "event.name": "ecommerce.checkout.started",
            },
        )

        cliente = buscar_cliente(peticion.cliente_id)
        if cliente is None:
            contador_fallos.add(1, {"motivo": "cliente_no_existe"})
            span.set_attribute("error.type", "cliente_no_existe")
            log_con_campos(
                logger, "error", "cliente no encontrado", **{"enduser.id": peticion.cliente_id}
            )
            raise HTTPException(status_code=404, detail="cliente no encontrado")

        _, nombre, tier, descuento = cliente
        span.set_attribute("ecommerce.customer.tier", tier)

        total = calcular_total(peticion.precio_unitario, peticion.cantidad, descuento)

        # Llamada a service-b. httpx instrumentado inyecta la cabecera
        # traceparent, que es lo que mantiene un solo trace_id.
        with tracer.start_as_current_span("reservar_inventario_remoto") as span_rpc:
            span_rpc.set_attribute("peer.service", "service-b")
            try:
                respuesta = cliente_http_reserva(peticion.sku, peticion.cantidad, pedido_id)
            except httpx.HTTPError as exc:
                contador_fallos.add(1, {"motivo": "service_b_no_responde"})
                span.set_attribute("error.type", type(exc).__name__)
                log_con_campos(
                    logger, "error", "service-b no respondio", **{"error.type": type(exc).__name__}
                )
                raise HTTPException(status_code=503, detail="inventario no disponible")

        if not respuesta.get("reservado", False):
            guardar_pedido(pedido_id, peticion.cliente_id, total, "rechazado")
            contador_fallos.add(1, {"motivo": "sin_inventario"})
            span.set_attribute("ecommerce.payment.result", "declined")
            log_con_campos(
                logger,
                "warning",
                "pedido rechazado por falta de inventario",
                **{
                    "ecommerce.order.id": pedido_id,
                    "ecommerce.inventory.sku": peticion.sku,
                    "event.name": "ecommerce.order.cancelled",
                },
            )
            raise HTTPException(status_code=409, detail="sin inventario")

        guardar_pedido(pedido_id, peticion.cliente_id, total, "confirmado")

        duracion = time.perf_counter() - inicio
        atributos = {"tier": tier, "sku": peticion.sku}
        contador_pedidos.add(1, atributos)
        histograma_checkout.record(duracion, atributos)
        histograma_monto.record(total, atributos)

        span.set_attribute("ecommerce.payment.result", "authorized")
        span.set_attribute("ecommerce.checkout.step", "order_submit")

        log_con_campos(
            logger,
            "info",
            "pedido confirmado",
            **{
                "ecommerce.order.id": pedido_id,
                "ecommerce.order.total_amount": total,
                "ecommerce.customer.tier": tier,
                "duration_ms": round(duracion * 1000, 2),
                "event.name": "ecommerce.order.created",
            },
        )

        return {
            "pedido_id": pedido_id,
            "cliente": nombre,
            "tier": tier,
            "total": total,
            "reserva": respuesta.get("reserva_id"),
            "trace_id": trace_id_actual(),
            "duracion_ms": round(duracion * 1000, 2),
        }


def cliente_http_reserva(sku: str, cantidad: int, pedido_id: str) -> dict:
    respuesta = cliente.post(
        f"{SERVICE_B_URL}/inventory/reserve",
        json={"sku": sku, "cantidad": cantidad, "pedido_id": pedido_id},
    )
    respuesta.raise_for_status()
    return respuesta.json()


@app.get("/orders/{pedido_id}")
def consultar_pedido(pedido_id: str):
    with tracer.start_as_current_span("consultar_pedido") as span:
        span.set_attribute("ecommerce.order.id", pedido_id)
        con = sqlite3.connect(DB_PATH)
        cur = con.cursor()
        fila = cur.execute(
            "SELECT id, cliente_id, monto, estado FROM pedidos WHERE id = ?", (pedido_id,)
        ).fetchone()
        cur.close()
        con.close()
        if fila is None:
            raise HTTPException(status_code=404, detail="pedido no encontrado")
        return {"pedido_id": fila[0], "cliente_id": fila[1], "monto": fila[2], "estado": fila[3]}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8001")), log_level="warning")
