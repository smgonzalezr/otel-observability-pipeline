"""
Collector minimo en memoria, solo para el banco de pruebas.

En produccion aqui va el OpenTelemetry Collector real, con la configuracion
que esta en collector/otel-collector-gcp.yaml y collector/otel-collector-aws.yaml.
Este archivo existe porque el benchmark necesita un receptor OTLP de verdad,
para que la medicion incluya el costo de serializar y enviar los spans.

Recibe OTLP por gRPC en el puerto 4317, guarda los spans en memoria y expone
un pequeno servidor HTTP para consultarlos.
"""

import json
import threading
from concurrent import futures
from http.server import BaseHTTPRequestHandler, HTTPServer

import grpc
from opentelemetry.proto.collector.trace.v1 import trace_service_pb2, trace_service_pb2_grpc

SPANS = []
CANDADO = threading.Lock()


def _hex(b: bytes) -> str:
    return b.hex()


def _valor(v):
    campo = v.WhichOneof("value")
    if campo is None:
        return None
    if campo == "array_value":
        return [_valor(x) for x in v.array_value.values]
    return getattr(v, campo)


class ServicioTrazas(trace_service_pb2_grpc.TraceServiceServicer):
    def Export(self, request, context):
        recibidos = []
        for rs in request.resource_spans:
            recurso = {kv.key: _valor(kv.value) for kv in rs.resource.attributes}
            for ss in rs.scope_spans:
                for s in ss.spans:
                    recibidos.append(
                        {
                            "trace_id": _hex(s.trace_id),
                            "span_id": _hex(s.span_id),
                            "parent_span_id": _hex(s.parent_span_id),
                            "name": s.name,
                            "kind": s.kind,
                            "start": s.start_time_unix_nano,
                            "end": s.end_time_unix_nano,
                            "duration_ms": (s.end_time_unix_nano - s.start_time_unix_nano) / 1e6,
                            "service.name": recurso.get("service.name"),
                            "attributes": {kv.key: _valor(kv.value) for kv in s.attributes},
                            "status": s.status.code,
                        }
                    )
        with CANDADO:
            SPANS.extend(recibidos)
        return trace_service_pb2.ExportTraceServiceResponse()


class ManejadorHTTP(BaseHTTPRequestHandler):
    def do_GET(self):
        with CANDADO:
            copia = list(SPANS)

        if self.path.startswith("/spans"):
            cuerpo = json.dumps(copia).encode()
        elif self.path.startswith("/stats"):
            trazas = {}
            for s in copia:
                trazas.setdefault(s["trace_id"], []).append(s)
            multi = sum(
                1
                for spans in trazas.values()
                if len({s["service.name"] for s in spans}) > 1
            )
            cuerpo = json.dumps(
                {
                    "spans_totales": len(copia),
                    "trazas_totales": len(trazas),
                    "trazas_con_dos_servicios": multi,
                    "servicios": sorted({s["service.name"] for s in copia if s["service.name"]}),
                    "nombres_de_span": sorted({s["name"] for s in copia}),
                }
            ).encode()
        elif self.path.startswith("/reset"):
            with CANDADO:
                SPANS.clear()
            cuerpo = b'{"ok":true}'
        else:
            cuerpo = b'{"endpoints":["/spans","/stats","/reset"]}'

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(cuerpo)))
        self.end_headers()
        self.wfile.write(cuerpo)

    def log_message(self, *a):
        pass


def main(puerto_grpc: int = 4317, puerto_http: int = 4319):
    servidor = grpc.server(futures.ThreadPoolExecutor(max_workers=4))
    trace_service_pb2_grpc.add_TraceServiceServicer_to_server(ServicioTrazas(), servidor)
    servidor.add_insecure_port(f"0.0.0.0:{puerto_grpc}")
    servidor.start()

    http = HTTPServer(("0.0.0.0", puerto_http), ManejadorHTTP)
    threading.Thread(target=http.serve_forever, daemon=True).start()

    print(f"collector stub escuchando OTLP/gRPC en {puerto_grpc} y consultas en {puerto_http}", flush=True)
    servidor.wait_for_termination()


if __name__ == "__main__":
    main()
