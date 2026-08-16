"""
Arranque unico de telemetria para los dos servicios.

Deja los tres pilares listos:
  trazas   -> OTLP gRPC hacia el OTel Collector
  metricas -> endpoint /metrics en formato Prometheus
  logs     -> JSON por salida estandar, con trace_id y span_id en cada linea

La variable OTEL_ENABLED apaga todo. Se usa para medir la linea base del
benchmark de la Fase 4 sin tocar el codigo de negocio.
"""

import json
import logging
import os
import sys
import time

# ---------------------------------------------------------------- utilidades


def _flag(nombre: str, por_defecto: str = "true") -> bool:
    return os.getenv(nombre, por_defecto).strip().lower() in ("1", "true", "yes", "on")


OTEL_ENABLED = _flag("OTEL_ENABLED")
SERVICE_NAME = os.getenv("OTEL_SERVICE_NAME", "servicio-sin-nombre")
SERVICE_VERSION = os.getenv("SERVICE_VERSION", "1.0.0")
ENVIRONMENT = os.getenv("DEPLOYMENT_ENV", "local")
OTLP_ENDPOINT = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")
METRICS_PORT = int(os.getenv("METRICS_PORT", "9464"))


# ------------------------------------------------------------- logs en JSON


def _contexto_actual():
    """Lee trace_id y span_id del span activo. Devuelve ("", "") si no hay."""
    if not OTEL_ENABLED:
        return "", ""
    try:
        from opentelemetry import trace

        ctx = trace.get_current_span().get_span_context()
        if ctx.is_valid:
            return format(ctx.trace_id, "032x"), format(ctx.span_id, "016x")
    except Exception:
        pass
    return "", ""


class FormatoJSON(logging.Formatter):
    """
    Escribe cada linea de log como un objeto JSON e incrusta el contexto de
    la traza activa. Ese trace_id es el que despues sirve de pivote en
    Grafana para saltar del log a la traza.
    """

    def format(self, record: logging.LogRecord) -> str:
        linea = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(record.created))
            + f".{int(record.msecs):03d}Z",
            "severity": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "service.name": SERVICE_NAME,
            "service.version": SERVICE_VERSION,
            "deployment.environment.name": ENVIRONMENT,
        }

        # LoggingInstrumentor inyecta estos campos cuando hay traza activa.
        # Si por version del paquete no llegan, se leen del span en curso.
        trace_id = getattr(record, "otelTraceID", None)
        span_id = getattr(record, "otelSpanID", None)
        if not trace_id or trace_id in ("0", "0" * 32):
            trace_id, span_id = _contexto_actual()

        if trace_id and trace_id != "0" * 32:
            linea["trace_id"] = trace_id
            linea["span_id"] = span_id
            # Formato que entiende Cloud Logging para enlazar con Cloud Trace.
            proyecto = os.getenv("GCP_PROJECT_ID")
            if proyecto:
                linea["logging.googleapis.com/trace"] = (
                    f"projects/{proyecto}/traces/{trace_id}"
                )
                linea["logging.googleapis.com/spanId"] = span_id

        for clave, valor in getattr(record, "extra_fields", {}).items():
            linea[clave] = valor

        if record.exc_info:
            linea["exception"] = self.formatException(record.exc_info)

        return json.dumps(linea, ensure_ascii=False)


def configurar_logs() -> logging.Logger:
    manejador = logging.StreamHandler(sys.stdout)
    manejador.setFormatter(FormatoJSON())

    raiz = logging.getLogger()
    raiz.handlers.clear()
    raiz.addHandler(manejador)
    raiz.setLevel(logging.INFO)

    logging.getLogger("uvicorn.access").disabled = True
    return logging.getLogger(SERVICE_NAME)


def log_con_campos(logger: logging.Logger, nivel: str, mensaje: str, **campos):
    """Escribe un log con atributos de negocio adicionales."""
    getattr(logger, nivel)(mensaje, extra={"extra_fields": campos})


# -------------------------------------------------------- trazas y metricas

_estado = {"tracer": None, "meter": None, "listo": False}


def iniciar_telemetria(app=None):
    """
    Deja lista la telemetria y devuelve (tracer, meter).

    Cuando OTEL_ENABLED es false devuelve objetos que no hacen nada, para que
    el codigo de negocio sea identico en los dos escenarios del benchmark.
    """
    if _estado["listo"]:
        return _estado["tracer"], _estado["meter"]

    from opentelemetry import metrics, trace

    if not OTEL_ENABLED:
        _estado.update(
            tracer=trace.get_tracer(SERVICE_NAME),
            meter=metrics.get_meter(SERVICE_NAME),
            listo=True,
        )
        return _estado["tracer"], _estado["meter"]

    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.exporter.prometheus import PrometheusMetricReader
    from opentelemetry.propagate import set_global_textmap
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.sdk.trace.sampling import (
        ALWAYS_ON,
        ParentBased,
        TraceIdRatioBased,
    )
    from opentelemetry.trace.propagation.tracecontext import (
        TraceContextTextMapPropagator,
    )

    # Atributos de recurso comunes a las tres senales. Son la llave que une
    # una metrica, un log y una traza con el mismo servicio.
    recurso = Resource.create(
        {
            "service.name": SERVICE_NAME,
            "service.version": SERVICE_VERSION,
            "service.namespace": "demo-observabilidad",
            "deployment.environment.name": ENVIRONMENT,
            "cloud.provider": os.getenv("CLOUD_PROVIDER", "local"),
            "cloud.region": os.getenv("CLOUD_REGION", "local"),
        }
    )

    # --- trazas
    # OTEL_SAMPLE_RATIO controla el muestreo de cabecera. 1.0 conserva todo.
    # Bajarlo es la palanca directa para reducir el costo de instrumentacion.
    razon = float(os.getenv("OTEL_SAMPLE_RATIO", "1.0"))
    if razon >= 1.0:
        muestreador = ParentBased(ALWAYS_ON)
    else:
        muestreador = ParentBased(TraceIdRatioBased(razon))

    proveedor_trazas = TracerProvider(resource=recurso, sampler=muestreador)
    proveedor_trazas.add_span_processor(
        BatchSpanProcessor(
            OTLPSpanExporter(endpoint=OTLP_ENDPOINT, insecure=True),
            max_queue_size=2048,
            max_export_batch_size=512,
            schedule_delay_millis=5000,
        )
    )
    trace.set_tracer_provider(proveedor_trazas)

    # W3C TraceContext es el formato de propagacion. Sin esto el trace_id
    # no sobrevive el salto de service-a a service-b.
    set_global_textmap(TraceContextTextMapPropagator())

    # --- metricas
    lector = PrometheusMetricReader()
    metrics.set_meter_provider(MeterProvider(resource=recurso, metric_readers=[lector]))

    from prometheus_client import start_http_server

    try:
        start_http_server(METRICS_PORT)
    except OSError:
        pass  # el puerto ya lo abrio otro worker

    # --- auto instrumentacion
    from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
    from opentelemetry.instrumentation.logging import LoggingInstrumentor
    from opentelemetry.instrumentation.sqlite3 import SQLite3Instrumentor

    # inject_trace_context agrega otelTraceID y otelSpanID a cada LogRecord
    # sin cambiar el formato, que aqui lo controla FormatoJSON.
    LoggingInstrumentor().instrument(
        set_logging_format=False, inject_trace_context=True
    )
    HTTPXClientInstrumentor().instrument()
    SQLite3Instrumentor().instrument()

    if app is not None:
        instrumentar_app(app)

    _estado.update(
        tracer=trace.get_tracer(SERVICE_NAME, SERVICE_VERSION),
        meter=metrics.get_meter(SERVICE_NAME, SERVICE_VERSION),
        listo=True,
    )
    return _estado["tracer"], _estado["meter"]


def instrumentar_app(app):
    """Aplica la auto instrumentacion de FastAPI a una app ya creada."""
    if not OTEL_ENABLED:
        return
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

    FastAPIInstrumentor.instrument_app(app, excluded_urls="health,metrics")


def trace_id_actual() -> str:
    """Devuelve el trace_id activo en hexadecimal, o cadena vacia."""
    from opentelemetry import trace

    contexto = trace.get_current_span().get_span_context()
    if contexto.is_valid:
        return format(contexto.trace_id, "032x")
    return ""
