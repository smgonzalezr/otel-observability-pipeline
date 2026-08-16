"""
Fase 4. Mide el costo de la instrumentacion.

Corre el mismo escenario dos veces, una sin OTel y otra con OTel, y compara
latencia, CPU y memoria. La carga la genera este mismo script para no depender
de k6, aunque el repositorio incluye load_test.js para repetir la prueba con
k6 en un entorno real.

Reglas de la medicion:
  - La latencia se mide desde el cliente, no dentro del servicio. Medir con el
    instrumento que se esta evaluando daria un resultado sesgado.
  - Se descartan los primeros segundos de calentamiento.
  - CPU y memoria se leen de los procesos con psutil, sumando los dos servicios.
  - Cada escenario se repite y se reporta la mediana.

uso:
    python run_benchmark.py --usuarios 50 --duracion 300 --repeticiones 3
"""

import argparse
import json
import os
import signal
import statistics
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import psutil
import requests

RAIZ = Path(__file__).resolve().parent.parent
PY = os.getenv("PY", sys.executable)
URL_A = "http://localhost:8001/checkout"
SESION = requests.Session()
SESION.trust_env = False  # ignora proxies del entorno para trafico local

SKUS = [f"SKU-{1000 + i}" for i in range(50)]
CLIENTES = [f"cli-{i:03d}" for i in range(60)]


# --------------------------------------------------------- ciclo de vida

def _lanzar(cmd, entorno, log):
    limpio = {k: v for k, v in os.environ.items()
              if k.lower() not in ("all_proxy", "http_proxy", "https_proxy", "grpc_proxy")}
    limpio.update(entorno)
    limpio["NO_PROXY"] = "localhost,127.0.0.1"
    limpio["no_proxy"] = "localhost,127.0.0.1"
    return subprocess.Popen(cmd, env=limpio, stdout=open(log, "w"), stderr=subprocess.STDOUT)


def levantar(otel: bool):
    """
    Arranca los dos servicios y, si aplica, el collector.

    Devuelve (procesos_app, procesos_infra). Se separan a proposito: el costo
    del collector es infraestructura compartida y no debe sumarse al costo de
    la aplicacion, que es lo que mide la Fase 4.
    """
    for f in ("/tmp/service_a.db", "/tmp/service_b.db"):
        Path(f).unlink(missing_ok=True)

    infra, app = [], []
    base = {"OTEL_ENABLED": "true" if otel else "false",
            "OTEL_EXPORTER_OTLP_ENDPOINT": "http://localhost:4317",
            "OTEL_SAMPLE_RATIO": os.getenv("OTEL_SAMPLE_RATIO", "1.0"),
            "DEPLOYMENT_ENV": "benchmark"}

    if otel:
        infra.append(_lanzar([PY, str(RAIZ / "benchmark" / "collector_stub.py")],
                             base, "/tmp/bench_collector.log"))
        time.sleep(2)

    app.append(_lanzar(
        [PY, str(RAIZ / "services" / "service-b" / "app.py")],
        {**base, "OTEL_SERVICE_NAME": "service-b", "PORT": "8002", "METRICS_PORT": "9465"},
        "/tmp/bench_b.log"))
    app.append(_lanzar(
        [PY, str(RAIZ / "services" / "service-a" / "app.py")],
        {**base, "OTEL_SERVICE_NAME": "service-a", "PORT": "8001",
         "METRICS_PORT": "9464", "SERVICE_B_URL": "http://localhost:8002"},
        "/tmp/bench_a.log"))

    esperar_salud()
    return app, infra


def esperar_salud(intentos=40):
    for _ in range(intentos):
        try:
            a = SESION.get("http://localhost:8001/health", timeout=1)
            b = SESION.get("http://localhost:8002/health", timeout=1)
            if a.ok and b.ok:
                return
        except Exception:
            pass
        time.sleep(0.5)
    raise RuntimeError("los servicios no respondieron a tiempo")


def apagar(procesos):
    for p in procesos:
        try:
            p.send_signal(signal.SIGTERM)
        except Exception:
            pass
    for p in procesos:
        try:
            p.wait(timeout=8)
        except Exception:
            p.kill()
    time.sleep(1)


# ------------------------------------------------------------ recursos

def procesos_de_servicios(procesos):
    salida = []
    for p in procesos:
        try:
            pr = psutil.Process(p.pid)
            salida.append(pr)
            pr.cpu_percent(None)  # primera lectura, se descarta
        except Exception:
            pass
    return salida


def muestrear_recursos(procs):
    cpu = 0.0
    rss = 0.0
    for pr in procs:
        try:
            cpu += pr.cpu_percent(None)
            rss += pr.memory_info().rss / (1024 * 1024)
        except Exception:
            pass
    return cpu, rss


# ------------------------------------------------------------ la carga

def una_peticion(i: int):
    cuerpo = {
        "cliente_id": CLIENTES[i % len(CLIENTES)],
        "sku": SKUS[i % len(SKUS)],
        "cantidad": (i % 3) + 1,
        "precio_unitario": 15000.0 + (i % 20) * 1000,
    }
    t0 = time.perf_counter()
    try:
        r = SESION.post(URL_A, json=cuerpo, timeout=10)
        ok = r.status_code == 200
    except Exception:
        ok = False
    return (time.perf_counter() - t0) * 1000.0, ok


def correr_carga(procs, procs_infra, usuarios: int, duracion: int, calentamiento: int):
    latencias, errores, muestras, muestras_infra = [], 0, [], []
    inicio = time.time()
    contador = [0]

    def trabajador():
        nonlocal errores
        while time.time() - inicio < duracion:
            i = contador[0]
            contador[0] += 1
            ms, ok = una_peticion(i)
            if time.time() - inicio >= calentamiento:
                latencias.append(ms)
                if not ok:
                    errores += 1

    with ThreadPoolExecutor(max_workers=usuarios) as pool:
        futuros = [pool.submit(trabajador) for _ in range(usuarios)]
        while time.time() - inicio < duracion:
            time.sleep(2)
            if time.time() - inicio >= calentamiento:
                muestras.append(muestrear_recursos(procs))
                if procs_infra:
                    muestras_infra.append(muestrear_recursos(procs_infra))
        for f in futuros:
            f.result()

    return latencias, errores, muestras, muestras_infra


def percentil(datos, p):
    if not datos:
        return 0.0
    orden = sorted(datos)
    k = (len(orden) - 1) * (p / 100.0)
    bajo, alto = int(k), min(int(k) + 1, len(orden) - 1)
    return orden[bajo] + (orden[alto] - orden[bajo]) * (k - bajo)


# ----------------------------------------------------------- escenario

def escenario(nombre: str, otel: bool, usuarios: int, duracion: int, calentamiento: int):
    print(f"  levantando servicios (OTEL={otel}) ...", flush=True)
    app, infra = levantar(otel)
    procs_app = procesos_de_servicios(app)
    procs_infra = procesos_de_servicios(infra)
    time.sleep(1)

    print(f"  aplicando carga: {usuarios} usuarios por {duracion}s ...", flush=True)
    latencias, errores, muestras, muestras_infra = correr_carga(
        procs_app, procs_infra, usuarios, duracion, calentamiento)

    spans = 0
    if otel:
        try:
            time.sleep(6)  # deja que el BatchSpanProcessor vacie la cola
            spans = SESION.get("http://localhost:4319/stats", timeout=5).json()["spans_totales"]
        except Exception:
            pass

    apagar(app + infra)

    cpus = [c for c, _ in muestras] or [0]
    rss = [m for _, m in muestras] or [0]
    cpus_i = [c for c, _ in muestras_infra] or [0]
    rss_i = [m for _, m in muestras_infra] or [0]
    total = len(latencias)

    return {
        "escenario": nombre,
        "otel": otel,
        "peticiones": total,
        "errores": errores,
        "rps": round(total / max(duracion - calentamiento, 1), 1),
        "lat_media_ms": round(statistics.fmean(latencias), 2) if latencias else 0,
        "lat_p50_ms": round(percentil(latencias, 50), 2),
        "lat_p95_ms": round(percentil(latencias, 95), 2),
        "lat_p99_ms": round(percentil(latencias, 99), 2),
        "cpu_media_pct": round(statistics.fmean(cpus), 1),
        "cpu_max_pct": round(max(cpus), 1),
        "mem_media_mb": round(statistics.fmean(rss), 1),
        "mem_max_mb": round(max(rss), 1),
        "spans_exportados": spans,
        "collector_cpu_pct": round(statistics.fmean(cpus_i), 1),
        "collector_mem_mb": round(statistics.fmean(rss_i), 1),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--usuarios", type=int, default=50)
    ap.add_argument("--duracion", type=int, default=300)
    ap.add_argument("--calentamiento", type=int, default=30)
    ap.add_argument("--repeticiones", type=int, default=3)
    ap.add_argument("--salida", default=str(RAIZ / "benchmark" / "results" / "benchmark_results.json"))
    ap.add_argument("--solo", choices=["sin", "con"], default=None,
                    help="corre un solo escenario y lo agrega a un archivo jsonl")
    ap.add_argument("--jsonl", default=str(RAIZ / "benchmark" / "results" / "corridas.jsonl"))
    ap.add_argument("--etiqueta", default="")
    args = ap.parse_args()

    # Modo por escenario. Util cuando el entorno limita el tiempo por corrida.
    if args.solo:
        otel = args.solo == "con"
        nombre = "con OTel" if otel else "sin instrumentacion"
        r = escenario(nombre, otel, args.usuarios, args.duracion, args.calentamiento)
        r.update(etiqueta=args.etiqueta, usuarios=args.usuarios, duracion=args.duracion)
        Path(args.jsonl).parent.mkdir(parents=True, exist_ok=True)
        with open(args.jsonl, "a") as fh:
            fh.write(json.dumps(r, ensure_ascii=False) + chr(10))
        print(json.dumps(r, indent=2, ensure_ascii=False))
        return

    corridas = []
    for r in range(1, args.repeticiones + 1):
        print(f"\n== repeticion {r} de {args.repeticiones} ==", flush=True)
        print(" [1/2] sin instrumentacion", flush=True)
        corridas.append({**escenario("sin instrumentacion", False, args.usuarios,
                                     args.duracion, args.calentamiento), "repeticion": r})
        print(" [2/2] con instrumentacion OTel", flush=True)
        corridas.append({**escenario("con OTel", True, args.usuarios,
                                     args.duracion, args.calentamiento), "repeticion": r})

    def mediana(otel, campo):
        vals = [c[campo] for c in corridas if c["otel"] is otel]
        return round(statistics.median(vals), 2)

    campos = ["peticiones", "rps", "lat_media_ms", "lat_p50_ms", "lat_p95_ms",
              "lat_p99_ms", "cpu_media_pct", "mem_media_mb"]
    resumen = {c: {"sin_otel": mediana(False, c), "con_otel": mediana(True, c)} for c in campos}
    for c, v in resumen.items():
        base = v["sin_otel"]
        v["delta_abs"] = round(v["con_otel"] - base, 2)
        v["delta_pct"] = round((v["con_otel"] - base) / base * 100, 1) if base else 0.0

    salida = {
        "configuracion": vars(args),
        "entorno": {
            "cpus": psutil.cpu_count(),
            "memoria_total_mb": round(psutil.virtual_memory().total / 1024 / 1024),
            "python": sys.version.split()[0],
        },
        "corridas": corridas,
        "resumen": resumen,
    }

    Path(args.salida).parent.mkdir(parents=True, exist_ok=True)
    Path(args.salida).write_text(json.dumps(salida, indent=2, ensure_ascii=False))
    print(f"\nresultados en {args.salida}")

    print(f"\n{'metrica':<18}{'sin OTel':>12}{'con OTel':>12}{'delta':>12}{'delta %':>10}")
    print("-" * 64)
    for c, v in resumen.items():
        print(f"{c:<18}{v['sin_otel']:>12}{v['con_otel']:>12}{v['delta_abs']:>12}{v['delta_pct']:>9}%")


if __name__ == "__main__":
    main()
