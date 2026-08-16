#!/usr/bin/env bash
# Levanta el stub del collector y los dos servicios en local.
#   uso: ./run_local.sh <on|off>   (on = con instrumentacion OTel)
set -u

MODO="${1:-on}"
REPO="$(cd "$(dirname "$0")/.." && pwd)"
PY="${PY:-python3}"

# En entornos con proxy hay que dejar fuera el trafico local.
unset ALL_PROXY all_proxy HTTP_PROXY HTTPS_PROXY http_proxy https_proxy grpc_proxy
export NO_PROXY=localhost,127.0.0.1
export no_proxy=localhost,127.0.0.1

if [ "$MODO" = "on" ]; then
  export OTEL_ENABLED=true
else
  export OTEL_ENABLED=false
fi

export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
export DEPLOYMENT_ENV=local

rm -f /tmp/service_a.db /tmp/service_b.db

if [ "$OTEL_ENABLED" = "true" ]; then
  "$PY" "$REPO/benchmark/collector_stub.py" > /tmp/collector.log 2>&1 &
  echo $! > /tmp/pid_collector
  sleep 2
fi

OTEL_SERVICE_NAME=service-b PORT=8002 METRICS_PORT=9465 \
  "$PY" "$REPO/services/service-b/app.py" > /tmp/service_b.log 2>&1 &
echo $! > /tmp/pid_b

OTEL_SERVICE_NAME=service-a PORT=8001 METRICS_PORT=9464 \
  SERVICE_B_URL=http://localhost:8002 \
  "$PY" "$REPO/services/service-a/app.py" > /tmp/service_a.log 2>&1 &
echo $! > /tmp/pid_a

sleep 6
echo "servicios arriba (OTEL_ENABLED=$OTEL_ENABLED)"
