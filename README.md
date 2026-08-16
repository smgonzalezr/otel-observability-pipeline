# Pipeline de observabilidad end to end con OpenTelemetry

Dos microservicios instrumentados con el SDK de OpenTelemetry, un Collector
desplegado en GCP y en AWS, y los tres pilares unidos por `trace_id`.

El repositorio incluye el codigo, la configuracion del Collector, la
infraestructura como codigo, un benchmark que se ejecuta de verdad y un
reporte tecnico con los resultados medidos.

---

## Que hay aqui

```
.
├── services/
│   ├── common/telemetry.py      arranque unico de trazas, metricas y logs
│   ├── service-a/               recibe la compra, llama a service-b
│   └── service-b/               reserva inventario
├── collector/
│   ├── otel-collector-gcp.yaml    receivers, processors, exporters para GCP
│   ├── otel-collector-aws.yaml    lo mismo para AWS
│   └── otel-collector-local.yaml  para docker compose
├── iac/
│   ├── terraform/gcp/           GKE, Workload Identity, Jaeger, Grafana
│   ├── terraform/aws/           ECS Fargate, X-Ray, CloudWatch, SSM
│   ├── helm/otel-collector/     chart propio, DaemonSet o Deployment
│   └── k8s/servicios.yaml       manifiestos de los dos servicios
├── benchmark/
│   ├── load_test.js             prueba de carga con k6, 50 usuarios, 5 min
│   ├── run_benchmark.py         version que corre sin dependencias externas
│   ├── collector_stub.py        receptor OTLP en memoria para medir
│   └── results/                 resultados en JSON
├── dashboards/
│   ├── grafana-observabilidad.json   dashboard de 6 paneles mas correlacion
│   ├── grafana-datasources.yml       enlace de log a traza por trace_id
│   ├── prometheus.yml
│   └── promtail.yml
├── docs/
│   ├── Informe_Actividad_4_SMGR_EICH_20260816.pdf      el entregable escrito
│   ├── evidencia/               traza, logs y metricas capturados de verdad
│   └── figuras/                 las cuatro figuras, en PNG, SVG y draw.io
└── docker-compose.yaml          stack completo en local
```

---

## Arranque rapido en local

Necesita Docker y Docker Compose.

```bash
docker compose up -d --build
```

Espere un minuto y genere trafico:

```bash
curl -X POST localhost:8001/checkout \
  -H 'Content-Type: application/json' \
  -d '{"cliente_id":"cli-001","sku":"SKU-1001","cantidad":2,"precio_unitario":25000}'
```

La respuesta trae el `trace_id`. Con ese valor puede recorrer los tres pilares:

| Que quiere ver | Donde |
|---|---|
| La traza completa | http://localhost:16686 y busque el trace_id |
| Las metricas crudas | http://localhost:9464/metrics y http://localhost:9090 |
| El dashboard | http://localhost:3000 (admin / admin), carpeta Observabilidad |
| Los logs de esa traza | Grafana, Explore, Loki, `{container="service-a"} \| json \| trace_id="..."` |

Sin Docker tambien funciona:

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r services/service-a/requirements.txt
./scripts/run_local.sh on
```

---

## Fase 1. Instrumentacion

Todo el arranque de telemetria vive en `services/common/telemetry.py`. El codigo
de negocio no sabe que existe OpenTelemetry, salvo cuando abre un span propio.

**Auto instrumentacion.** Cubre lo que es igual en todos los servicios:

- `FastAPIInstrumentor` para el HTTP de entrada
- `HTTPXClientInstrumentor` para el HTTP de salida, y es quien inyecta la cabecera `traceparent`
- `SQLite3Instrumentor` para las consultas a la base de datos
- `LoggingInstrumentor` con `inject_trace_context=True` para que cada log lleve el `trace_id`

**Spans propios.** Cubren lo que solo el equipo conoce:

| Servicio | Span | Que representa |
|---|---|---|
| service-a | `flujo_checkout` | el flujo de compra completo |
| service-a | `calcular_total_pedido` | el descuento por tier del cliente |
| service-a | `reservar_inventario_remoto` | la dependencia con service-b |
| service-b | `reservar_inventario` | la reserva completa |
| service-b | `verificar_existencias` | la regla de disponibilidad |
| service-b | `aplicar_reserva` | el descuento de existencias |

**Los tres pilares.**

- Trazas por OTLP gRPC al Collector, puerto 4317.
- Metricas en `/metrics` del puerto 9464, en formato Prometheus. Incluye
  `ecommerce_orders_created_total`, `ecommerce_checkout_duration_seconds`,
  `inventory_reservations_total` y `inventory_stock_level`.
- Logs en JSON por salida estandar, con `trace_id`, `span_id` y atributos de
  negocio en cada linea.

Variables que controlan el comportamiento:

| Variable | Para que sirve |
|---|---|
| `OTEL_ENABLED` | apaga toda la telemetria, se usa en la linea base del benchmark |
| `OTEL_SAMPLE_RATIO` | muestreo de cabecera, 1.0 conserva todo |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | a donde salen las trazas |
| `METRICS_PORT` | puerto del endpoint de Prometheus |
| `GCP_PROJECT_ID` | activa el campo que enlaza logs con Cloud Trace |

---

## Fase 2. Collector

La misma estructura en las dos nubes. Solo cambian los exporters.

| | GCP | AWS |
|---|---|---|
| Despliegue | DaemonSet en GKE | sidecar en la task de ECS Fargate |
| Trazas | `otlp/jaeger`, `googlecloud` | `awsxray`, `otlp/tempo`, `otlp/jaeger` |
| Metricas | `prometheus`, `googlemanagedprometheus` | `prometheus`, `awsemf` |
| Logs | `googlecloud` | `awscloudwatchlogs` |
| Configuracion | ConfigMap creado por Terraform | Parametro de SSM creado por Terraform |
| Identidad | Workload Identity | rol IAM de la tarea |

En los dos casos el orden de los procesadores es el mismo: `memory_limiter`
primero para proteger el proceso, los procesadores de contexto en el medio y
`batch` siempre al final.

El conector `spanmetrics` se ejecuta sobre el cien por ciento de los spans y
produce las metricas de tasa, error y duracion que alimentan los SLI. Asi los
indicadores no dependen de cuantas trazas se guarden.

Validar antes de desplegar:

```bash
docker run --rm -v $(pwd)/collector:/c otel/opentelemetry-collector-contrib:0.113.0 \
  validate --config=/c/otel-collector-gcp.yaml
```

---

## Fase 3. Despliegue

### GCP

```bash
cd iac/terraform/gcp
cp terraform.tfvars.example terraform.tfvars   # ponga su project_id
terraform init && terraform apply
$(terraform output -raw comando_credenciales)
kubectl apply -f ../../k8s/servicios.yaml
helm upgrade --install otel ../../helm/otel-collector \
  -n observability -f ../../helm/otel-collector/values-gcp.yaml
```

### AWS

```bash
cd iac/terraform/aws
cp terraform.tfvars.example terraform.tfvars   # ponga las imagenes de ECR
terraform init && terraform apply
```

El Collector viaja como sidecar dentro de la task definition, asi que no hay
que desplegarlo aparte.

---

## Fase 4. Benchmark

Con k6, que es lo que pide la actividad:

```bash
cd benchmark
OTEL_ENABLED=false ../scripts/run_local.sh off
k6 run -e ESCENARIO=sin_otel -e USUARIOS=50 load_test.js

OTEL_ENABLED=true ../scripts/run_local.sh on
k6 run -e ESCENARIO=con_otel -e USUARIOS=50 load_test.js
```

Sin instalar k6, el script en Python hace lo mismo:

```bash
python benchmark/run_benchmark.py --usuarios 50 --duracion 300 --repeticiones 3
```

Los resultados quedan en `benchmark/results/benchmark_results.json`.

### Lo que salio en las mediciones

Dos repeticiones, 8 usuarios concurrentes, 60 segundos por corrida, mediana.
La latencia se mide desde el cliente, nunca con el instrumento evaluado.

| Metrica | Sin OTel | Con OTel | Cambio | Con muestreo 10% |
|---|---|---|---|---|
| Latencia p50 | 19,77 ms | 30,77 ms | +55,6 % | 26,92 ms |
| Latencia p95 | 79,41 ms | 92,57 ms | +16,6 % | 87,57 ms |
| Latencia p99 | 155,20 ms | 159,36 ms | +2,7 % | 153,65 ms |
| Throughput | 268,2 rps | 197,3 rps | -26,5 % | 219,6 rps |
| CPU (dos servicios) | 111,2 % | 155,6 % | +39,9 % | 144,7 % |
| Memoria RSS | 96,6 MB | 150,3 MB | +55,6 % | 149,3 MB |

El Collector consumio aparte 4,2 % de un nucleo y 285 MB.

Con 50 usuarios el costo sube: el p50 crece 60,1 % y el throughput cae 34,1 %.
Es de esperar, porque la instrumentacion compite por la misma CPU que ya esta
saturada.

La causa del costo no es el agente sino el volumen: cada peticion genera cerca
de 20 spans. Bajar el muestreo de cabecera al 10 % reduce los spans un 88,3 % y
recupera 23 peticiones por segundo. La memoria casi no baja, porque cargar el
SDK es un costo fijo.

---

## Como se verifica la correlacion

1. Llame a `/checkout` y guarde el `trace_id` que devuelve.
2. Busquelo en Jaeger. Debe aparecer una sola traza con 20 spans y los dos servicios.
3. En Grafana Explore, consulte Loki filtrando por ese `trace_id`. Deben salir
   cinco lineas, tres de service-a y dos de service-b.
4. Haga clic en el enlace TraceID de cualquier linea. Debe abrir la misma traza.

La evidencia de una corrida real esta en `docs/evidencia/`.

---

## Notas sobre el entorno de medicion

El benchmark se ejecuto en un contenedor de 4 vCPU y 3,9 GB de RAM, con el
generador de carga en la misma maquina. Por eso las latencias absolutas
incluyen la competencia por CPU entre el generador y los servicios. Las
comparaciones entre escenarios siguen siendo validas porque las dos corridas
sufren la misma condicion.

En lugar del Collector completo, el benchmark usa `collector_stub.py`, un
receptor OTLP en memoria. Recibe los spans por gRPC de verdad, asi que la
medicion incluye el costo de serializar y enviar, que es lo que interesa.

---

## Regenerar los documentos

Las dos versiones del reporte leen las mismas cifras de
`benchmark/results/benchmark_results.json`, asi que nunca se separan de lo que
se midio. Si vuelve a correr el benchmark, regenere los documentos:

```bash
make figuras        # rehace las figuras 2 y 4 con los datos nuevos
make drawio         # regenera las figuras 1 y 3 en formato draw.io
make reporte        # PDF
make reporte-docx   # DOCX con normas APA 7
```

Las figuras 1 y 3 tambien estan en `.drawio`, en XML sin comprimir. Se abren en
https://app.diagrams.net, en la aplicacion de escritorio o con la extension de
VS Code, y al ser texto plano se pueden comparar en el control de versiones.
Las cajas van anidadas dentro de su contenedor, asi que mover una fase mueve
todo su contenido.

El DOCX sigue APA 7: Times New Roman 12, interlineado doble, margenes de una
pulgada, numero de pagina arriba a la derecha, portada y resumen con palabras
clave, encabezados de tres niveles, tablas sin lineas verticales con su numero
y titulo, figuras con nota, y referencias con sangria francesa.

---

## Fuentes

- OpenTelemetry Python SDK. https://opentelemetry-python.readthedocs.io/
- OpenTelemetry Collector. https://opentelemetry.io/docs/collector/
- Jaeger Architecture. https://www.jaegertracing.io/docs/architecture/
- Grafana, enlace entre trazas, logs y metricas. https://grafana.com/docs/grafana/latest/explore/trace-integration/
- k6. https://k6.io/docs/
- W3C Trace Context. https://www.w3.org/TR/trace-context/
