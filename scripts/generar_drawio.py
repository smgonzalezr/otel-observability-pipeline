"""
Genera las figuras 1 y 3 en formato draw.io para poder editarlas.

Salida:
  docs/figuras/fig1_arquitectura.drawio
  docs/figuras/fig3_correlacion.drawio

Los archivos quedan en XML sin comprimir, asi que se abren en
https://app.diagrams.net, en la aplicacion de escritorio o en la extension de
VS Code, y ademas se pueden leer y comparar en un control de versiones.

Las cajas van anidadas dentro de su contenedor. Mover un contenedor mueve todo
su contenido, y las coordenadas de los hijos son relativas al padre.
"""

import xml.etree.ElementTree as ET
from pathlib import Path
from xml.dom import minidom

RAIZ = Path(__file__).resolve().parent.parent
SALIDA = RAIZ / "docs" / "figuras"
SALIDA.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------- paleta

AZUL = "#4285f4"
AZUL_F = "#eef4ff"
NARANJA = "#ff9900"
NARANJA_F = "#fff3e0"
MORADO = "#7a5cc4"
MORADO_F = "#f6f4fb"
VERDE = "#2e9e63"
VERDE_F = "#f2faf5"
ROJO = "#c0392b"
ROJO_F = "#fdeceb"
GRIS = "#9a9a9a"
GRIS_F = "#fafafa"
AMBAR = "#e8a33d"
AMBAR_F = "#fff6e5"

# ------------------------------------------------------------- utilidades


class Lienzo:
    """Acumula celdas de draw.io y las escribe como XML."""

    def __init__(self, nombre, ancho=1600, alto=920):
        self.nombre = nombre
        self.ancho = ancho
        self.alto = alto
        self.celdas = []
        self._n = 0

    def _id(self, prefijo="c"):
        self._n += 1
        return f"{prefijo}{self._n}"

    def caja(self, x, y, w, h, valor="", estilo="", padre="1", ident=None):
        ident = ident or self._id()
        self.celdas.append(
            {"id": ident, "value": valor, "style": estilo, "parent": padre,
             "x": x, "y": y, "w": w, "h": h, "tipo": "vertex"}
        )
        return ident

    def texto(self, x, y, w, h, valor, padre="1", tam=11, negrita=False,
              color="#333333", alineacion="left", ident=None):
        estilo = (
            f"text;html=1;strokeColor=none;fillColor=none;align={alineacion};"
            f"verticalAlign=top;whiteSpace=wrap;overflow=hidden;"
            f"fontSize={tam};fontColor={color};"
            f"fontStyle={1 if negrita else 0}"
        )
        return self.caja(x, y, w, h, valor, estilo, padre, ident)

    def flecha(self, origen, destino, valor="", color="#0b6ea8", grosor=2,
               punteada=False, estilo_extra=""):
        ident = self._id("f")
        estilo = (
            f"edgeStyle=orthogonalEdgeStyle;rounded=1;html=1;"
            f"strokeColor={color};strokeWidth={grosor};endArrow=block;endFill=1;"
            f"fontSize=10;fontColor={color};"
            f"{'dashed=1;' if punteada else 'dashed=0;'}{estilo_extra}"
        )
        self.celdas.append(
            {"id": ident, "value": valor, "style": estilo, "parent": "1",
             "origen": origen, "destino": destino, "tipo": "edge"}
        )
        return ident

    def escribir(self, ruta):
        mxfile = ET.Element("mxfile", {
            "host": "app.diagrams.net",
            "type": "device",
            "agent": "generar_drawio.py",
        })
        diagrama = ET.SubElement(mxfile, "diagram", {"name": self.nombre, "id": "d1"})
        modelo = ET.SubElement(diagrama, "mxGraphModel", {
            "dx": "1400", "dy": "900", "grid": "1", "gridSize": "10",
            "guides": "1", "tooltips": "1", "connect": "1", "arrows": "1",
            "fold": "1", "page": "1", "pageScale": "1",
            "pageWidth": str(self.ancho), "pageHeight": str(self.alto),
            "math": "0", "shadow": "0",
        })
        raiz = ET.SubElement(modelo, "root")
        ET.SubElement(raiz, "mxCell", {"id": "0"})
        ET.SubElement(raiz, "mxCell", {"id": "1", "parent": "0"})

        for c in self.celdas:
            if c["tipo"] == "vertex":
                celda = ET.SubElement(raiz, "mxCell", {
                    "id": c["id"], "value": c["value"], "style": c["style"],
                    "parent": c["parent"], "vertex": "1",
                })
                ET.SubElement(celda, "mxGeometry", {
                    "x": str(c["x"]), "y": str(c["y"]),
                    "width": str(c["w"]), "height": str(c["h"]),
                    "as": "geometry",
                })
            else:
                celda = ET.SubElement(raiz, "mxCell", {
                    "id": c["id"], "value": c["value"], "style": c["style"],
                    "parent": c["parent"], "edge": "1",
                    "source": c["origen"], "target": c["destino"],
                })
                ET.SubElement(celda, "mxGeometry", {"relative": "1", "as": "geometry"})

        crudo = ET.tostring(mxfile, encoding="unicode")
        bonito = minidom.parseString(crudo).toprettyxml(indent="  ")
        bonito = "\n".join(l for l in bonito.split("\n") if l.strip())
        Path(ruta).write_text(bonito, encoding="utf-8")
        print(f"  {Path(ruta).name}  ({len(self.celdas)} celdas)")


def contenedor(fill, stroke, tam=15):
    return (
        f"rounded=1;whiteSpace=wrap;html=1;fillColor={fill};strokeColor={stroke};"
        f"strokeWidth=2;verticalAlign=top;align=center;fontSize={tam};fontStyle=1;"
        f"fontColor={stroke};arcSize=6;spacingTop=4;container=1;collapsible=0;"
    )


def tarjeta(fill, stroke, tam=11, alineacion="left"):
    return (
        f"rounded=1;whiteSpace=wrap;html=1;fillColor={fill};strokeColor={stroke};"
        f"verticalAlign=top;align={alineacion};fontSize={tam};arcSize=8;"
        f"spacingLeft=8;spacingTop=4;spacingRight=6;fontColor=#333333;"
    )


# ==================================================== FIGURA 1: pipeline

def figura_uno():
    L = Lienzo("Figura 1. Pipeline de observabilidad", 1600, 920)

    L.texto(20, 12, 900, 24,
            "Pipeline de observabilidad end to end con OpenTelemetry",
            tam=18, negrita=True, color="#111111")
    L.texto(20, 38, 1100, 20,
            "service-a &#8594; service-b  &#183;  GCP GKE y AWS ECS Fargate  &#183; "
            "trazas, metricas y logs unidos por trace_id",
            tam=12, color="#555555")

    # ---------------------------------------------------------- FASE 1
    f1 = L.caja(20, 70, 340, 800, "FASE 1. Aplicacion + OTel SDK",
                contenedor("#f4f8fb", "#1a5fb4", 15), ident="fase1")

    sa = L.caja(16, 34, 308, 236, "service-a (Python, FastAPI)",
                contenedor("#ffffff", AZUL, 13), padre=f1, ident="service_a")
    L.texto(12, 30, 284, 18, "POST /checkout", padre=sa, tam=11)
    L.caja(12, 52, 284, 84,
           "<b>Auto instrumentacion</b><br>"
           "FastAPIInstrumentor (HTTP servidor)<br>"
           "HTTPXClientInstrumentor (HTTP cliente)<br>"
           "SQLite3Instrumentor (base de datos)",
           tarjeta(AZUL_F, AZUL, 10), padre=sa)
    L.caja(12, 144, 284, 76,
           "<b>Spans propios de negocio</b><br>"
           "flujo_checkout<br>calcular_total_pedido<br>reservar_inventario_remoto",
           tarjeta(AMBAR_F, AMBAR, 10), padre=sa)

    sb = L.caja(16, 288, 308, 224, "service-b (Python, FastAPI)",
                contenedor("#ffffff", NARANJA, 13), padre=f1, ident="service_b")
    L.texto(12, 30, 284, 18, "POST /inventory/reserve", padre=sb, tam=11)
    L.caja(12, 52, 284, 68,
           "<b>Auto instrumentacion</b><br>"
           "FastAPI + SQLite3<br>lee la cabecera traceparent entrante",
           tarjeta(NARANJA_F, NARANJA, 10), padre=sb)
    L.caja(12, 128, 284, 80,
           "<b>Spans propios de negocio</b><br>"
           "reservar_inventario<br>verificar_existencias<br>aplicar_reserva",
           tarjeta(AMBAR_F, AMBAR, 10), padre=sb)

    pilares = L.caja(16, 530, 308, 250, "Los tres pilares que emite el SDK",
                     contenedor("#ffffff", VERDE, 13), padre=f1)
    L.caja(12, 34, 284, 60,
           "<b>Trazas</b><br>OTLP/gRPC al Collector, puerto 4317<br>"
           "Sampler: ParentBased(AlwaysOn)",
           tarjeta("#ffffff", "#cccccc", 10), padre=pilares)
    L.caja(12, 100, 284, 72,
           "<b>Metricas</b><br>PrometheusMetricReader en :9464/metrics<br>"
           "ecommerce.orders.created<br>ecommerce.checkout.duration",
           tarjeta("#ffffff", "#cccccc", 10), padre=pilares)
    L.caja(12, 178, 284, 60,
           "<b>Logs</b><br>JSON por salida estandar<br>"
           "cada linea lleva trace_id y span_id",
           tarjeta("#ffffff", "#cccccc", 10), padre=pilares)

    # ---------------------------------------------------------- FASE 2
    f2 = L.caja(392, 70, 380, 800,
                "FASE 2. OpenTelemetry Collector",
                contenedor(MORADO_F, "#4b338f", 15), ident="fase2")
    L.texto(14, 26, 352, 18,
            "GCP: DaemonSet en GKE  &#183;  AWS: sidecar en ECS Fargate",
            padre=f2, tam=10, color="#4b338f", alineacion="center")

    rec = L.caja(16, 50, 348, 130, "receivers",
                 contenedor("#ffffff", MORADO, 13), padre=f2, ident="receivers")
    L.texto(12, 30, 324, 92,
            "otlp / grpc &#8594; 0.0.0.0:4317<br>"
            "otlp / http &#8594; 0.0.0.0:4318<br>"
            "prometheus/self (metricas internas 8888)<br>"
            "<i>awsecscontainermetrics solo en ECS</i>",
            padre=rec, tam=10.5)

    pro = L.caja(16, 194, 348, 156, "processors (el orden importa)",
                 contenedor("#ffffff", MORADO, 13), padre=f2)
    L.texto(12, 30, 324, 118,
            "1. memory_limiter (limit_mib 512)<br>"
            "2. k8sattributes / resourcedetection<br>"
            "3. resource (cloud.provider, environment)<br>"
            "4. batch (timeout 5s, size 1024)<br><br>"
            "<i>memory_limiter primero, batch siempre al final</i>",
            padre=pro, tam=10.5)

    con = L.caja(16, 364, 348, 120, "connectors",
                 contenedor("#ffffff", MORADO, 13), padre=f2, ident="connectors")
    L.texto(12, 30, 324, 84,
            "<b>spanmetrics</b><br>"
            "deriva tasa, error y duracion desde los spans<br>"
            "alimenta los SLI 1, 2 y 3 del dashboard<br>"
            "<font color='#c0392b'>se ejecuta sobre el 100% de los spans</font>",
            padre=con, tam=10.5)

    exp = L.caja(16, 498, 348, 176, "exporters",
                 contenedor("#ffffff", MORADO, 13), padre=f2, ident="exporters")
    L.texto(12, 30, 324, 140,
            "<b><font color='#1a5fb4'>en GCP</font></b><br>"
            "otlp/jaeger &#183; googlecloud<br>"
            "googlemanagedprometheus &#183; prometheus (8889)<br><br>"
            "<b><font color='#b06a00'>en AWS</font></b><br>"
            "awsxray &#183; otlp/tempo &#183; otlp/jaeger<br>"
            "awsemf &#183; awscloudwatchlogs &#183; prometheus<br>"
            "<i>Es lo unico que cambia entre las dos nubes.</i>",
            padre=exp, tam=10.5)

    L.caja(16, 688, 348, 96,
           "<b>Configuracion versionada</b><br>"
           "GCP: ConfigMap desde collector/otel-collector-gcp.yaml<br>"
           "AWS: SSM Parameter desde otel-collector-aws.yaml<br>"
           "<i>Los dos los crea Terraform con file(), no a mano.</i>",
           tarjeta("#f0ecf9", MORADO, 10) + "dashed=1;", padre=f2)

    # ---------------------------------------------------------- FASE 3
    f3 = L.caja(804, 70, 776, 800, "FASE 3. Backends y visualizacion",
                contenedor(VERDE_F, "#1f6b41", 15), ident="fase3")

    # Las tres salidas se apilan a la izquierda para que las flechas que vienen
    # del Collector entren derecho, sin cruzar por encima de otras cajas.
    tz = L.caja(16, 36, 380, 230, "TRAZAS",
                contenedor("#ffffff", VERDE, 13), padre=f3, ident="trazas")
    L.texto(12, 34, 356, 184,
            "<b><font color='#1a5fb4'>Jaeger UI (GCP)</font></b><br>"
            "vista de cascada de los 20 spans<br><br>"
            "<b><font color='#b06a00'>AWS X-Ray o Tempo (AWS)</font></b><br>"
            "mismo trace_id en las dos nubes<br><br>"
            "<b>Verificacion de propagacion</b><br>"
            "una traza, dos servicios, 20 spans<br>"
            "los spans de service-b cuelgan de los de service-a",
            padre=tz, tam=10.5)

    mt = L.caja(16, 280, 380, 230, "METRICAS",
                contenedor("#ffffff", VERDE, 13), padre=f3, ident="metricas")
    L.texto(12, 34, 356, 184,
            "<b>Prometheus + Grafana</b><br>"
            "raspa el endpoint 8889 del Collector<br>"
            "y el 9464 de cada servicio<br><br>"
            "<b>Dashboard de 6 paneles</b><br>"
            "4 SLI: rps, error, latencia, negocio<br>"
            "1 panel de CPU y memoria<br>"
            "1 panel de errores del Collector<br><br>"
            "<i>dashboards/grafana-observabilidad.json</i>",
            padre=mt, tam=10.5)

    lg = L.caja(16, 524, 380, 250, "LOGS y CORRELACION",
                contenedor("#ffffff", VERDE, 13), padre=f3, ident="logs")
    L.texto(12, 34, 356, 204,
            "<b>Destino</b><br>"
            "GCP: Cloud Logging &#183; AWS: CloudWatch Logs &#183; local: Loki<br><br>"
            "<b>Pivote: el campo trace_id de cada linea JSON</b><br>"
            "Grafana lo convierte en un enlace con derivedFields, asi que desde un "
            "log se abre la traza y desde una traza se filtran sus logs.<br><br>"
            "En GCP el campo logging.googleapis.com/trace hace lo mismo sin "
            "configurar nada.",
            padre=lg, tam=10.5)

    # ------------------------------------------------------------- FASE 4
    ov = L.caja(412, 36, 348, 738, "FASE 4. Analisis de overhead (medido)",
                contenedor("#fdf6f2", "#8a4a1e", 14), padre=f3)
    L.texto(14, 36, 320, 70,
            "Escenario: 2 repeticiones, 8 usuarios concurrentes, 60 s por corrida, "
            "mediana.<br><br>"
            "La latencia se mide desde el cliente, nunca con el instrumento evaluado.",
            padre=ov, tam=10.5)

    L.texto(14, 122, 320, 18,
            "<b>metrica&#160;&#160;&#160;&#160;&#160;&#160;&#160;&#160;&#160;&#160;"
            "&#160;&#160;&#160;sin OTel&#160;&#160;&#160;&#160;&#160;con OTel&#160;"
            "&#160;&#160;&#160;&#160;cambio</b>", padre=ov, tam=10.5)

    filas = [
        ("Latencia p50 (ms)", "19,77", "30,77", "+55,6 %"),
        ("Latencia p99 (ms)", "155,20", "159,36", "+2,7 %"),
        ("Throughput (rps)", "268,2", "197,3", "-26,5 %"),
        ("CPU 2 servicios (%)", "111,2", "155,6", "+39,9 %"),
        ("Memoria RSS (MB)", "96,6", "150,3", "+55,6 %"),
    ]
    for i, (nom, a, b, c) in enumerate(filas):
        y = 150 + i * 26
        L.texto(14, y, 124, 18, nom, padre=ov, tam=10.5)
        L.texto(140, y, 60, 18, a, padre=ov, tam=10.5, color="#444444")
        L.texto(204, y, 60, 18, b, padre=ov, tam=10.5, color="#444444")
        L.texto(266, y, 68, 18, c, padre=ov, tam=10.5, color=ROJO, negrita=True)

    L.caja(14, 296, 320, 150,
           "<b>La palanca que sirve</b><br><br>"
           "Cada peticion produce 20 spans. El costo no lo genera el agente sino "
           "ese volumen.<br><br>"
           "Con muestreo de cabecera al 10 % los spans bajan 88,3 % y el throughput "
           "sube de 197 a 220 rps.<br><br>"
           "La memoria casi no baja: cargar el SDK es un costo fijo.",
           tarjeta("#ffffff", "#c58f6e", 10), padre=ov)

    L.caja(14, 462, 320, 128,
           "<b>Lo que sigue</b><br><br>"
           "Mover la decision al Collector con muestreo de cola, que conserva el "
           "100 % de los errores porque decide con la traza ya completa.<br><br>"
           "Los SLI no se afectan: salen de spanmetrics, antes del muestreo.",
           tarjeta("#ffffff", "#c58f6e", 10), padre=ov)

    L.texto(14, 606, 320, 116,
            "<i>Datos en benchmark/results/benchmark_results.json. Se reproducen con "
            "<b>make benchmark</b>.</i>",
            padre=ov, tam=10, color="#777777")

    # ------------------------------------------------------------ flechas
    L.flecha("service_a", "receivers", "OTLP")
    L.flecha("service_b", "receivers", "OTLP")
    L.flecha("service_a", "service_b", "HTTP con traceparent",
             color="#777777", grosor=2, punteada=True,
             estilo_extra="exitX=1;exitY=0.85;exitDx=0;exitDy=0;"
                          "entryX=1;entryY=0.15;entryDx=0;entryDy=0;")
    lado = ("exitX=1;exitY=0.5;exitDx=0;exitDy=0;"
            "entryX=0;entryY=0.5;entryDx=0;entryDy=0;")
    L.flecha("exporters", "trazas", estilo_extra=lado)
    L.flecha("exporters", "metricas", estilo_extra=lado)
    L.flecha("exporters", "logs", estilo_extra=lado)

    L.escribir(SALIDA / "fig1_arquitectura.drawio")


# ================================================ FIGURA 3: correlacion

def figura_tres():
    L = Lienzo("Figura 3. Correlacion por trace_id", 1480, 900)

    L.texto(30, 14, 1000, 24,
            "Correlacion entre los tres pilares usando trace_id como pivote",
            tam=18, negrita=True, color="#111111")
    L.texto(30, 40, 1200, 20,
            "Una sola peticion de compra, capturada en el entorno de pruebas. "
            "Los tres bloques comparten el mismo identificador.",
            tam=11.5, color="#555555")

    # -------------------------------------------------------- el pivote
    piv = L.caja(400, 74, 680, 64,
                 "<b>trace_id</b><br>"
                 "<font style='font-family: Consolas, monospace; font-size: 14px'>"
                 "aef4e2c82298fb222f881f25b2383bd3</font>",
                 "rounded=1;whiteSpace=wrap;html=1;fillColor=" + ROJO_F +
                 ";strokeColor=" + ROJO + ";strokeWidth=3;align=center;"
                 "verticalAlign=middle;fontSize=13;fontColor=#8b2520;arcSize=10;",
                 ident="pivote")

    # ---------------------------------------------------------- 1. LOGS
    c1 = L.caja(30, 190, 430, 480, "1. LOGS estructurados",
                contenedor("#f4f8fb", "#1a5fb4", 15), ident="col_logs")
    L.texto(14, 26, 402, 16, "salida estandar en JSON, sin campos libres",
            padre=c1, tam=10, color="#555555", alineacion="center")

    L.caja(14, 50, 402, 122,
           "<font style='font-family: Consolas, monospace; font-size: 10px'>"
           "{\"timestamp\": \"...\", \"severity\": \"INFO\",<br>"
           "&#160;\"message\": \"checkout iniciado\",<br>"
           "&#160;\"service.name\": \"service-a\",<br>"
           "<font color='#c0392b'>&#160;\"trace_id\": \"aef4e2c822...83bd3\",</font><br>"
           "<font color='#c0392b'>&#160;\"span_id\": \"b36bf8543506e168\",</font><br>"
           "&#160;\"ecommerce.order.id\": \"ord-10dc0f85abb5\"}</font>",
           tarjeta("#ffffff", "#b9cfe6", 10), padre=c1)

    L.caja(14, 186, 402, 132,
           "<b>Las 5 lineas de esta peticion</b><br><br>"
           "service-a&#160;&#160; checkout iniciado<br>"
           "service-a&#160;&#160; HTTP Request: POST /inventory/reserve<br>"
           "service-b&#160;&#160; reserva solicitada<br>"
           "service-b&#160;&#160; reserva confirmada<br>"
           "service-a&#160;&#160; pedido confirmado<br><br>"
           "<i>Los dos servicios, un solo trace_id.</i>",
           tarjeta("#ffffff", "#b9cfe6", 10), padre=c1)

    L.caja(14, 332, 402, 122,
           "<b>Como se logra</b><br><br>"
           "LoggingInstrumentor con inject_trace_context agrega otelTraceID a cada "
           "LogRecord y el formateador propio lo escribe como trace_id.<br><br>"
           "<i>En GCP se agrega ademas logging.googleapis.com/trace</i>",
           tarjeta(AZUL_F, AZUL, 10) + "dashed=1;", padre=c1)

    # -------------------------------------------------------- 2. TRAZAS
    c2 = L.caja(500, 190, 430, 480, "2. TRAZAS distribuidas",
                contenedor(MORADO_F, "#4b338f", 15), ident="col_trazas")
    L.texto(14, 26, 402, 16, "20 spans, 2 servicios, 37,97 ms",
            padre=c2, tam=10, color="#555555", alineacion="center")

    casc = L.caja(14, 50, 402, 190, "",
                  tarjeta("#ffffff", "#c6b9e0", 10), padre=c2)
    # (nombre, nivel, ancho de barra, desplazamiento) a escala sobre 200 px
    # que equivalen a los 37,97 ms que dura la traza completa.
    barras = [
        ("POST /checkout", 0, 200, 0, AZUL),
        ("&#8735; flujo_checkout", 1, 134, 29, AZUL),
        ("&#8735; SELECT clientes", 2, 3, 32, AZUL),
        ("&#8735; calcular_total_pedido", 2, 2, 38, AZUL),
        ("&#8735; reservar_inventario_remoto", 2, 112, 44, AZUL),
        ("&#8735; POST /inventory/reserve", 3, 92, 56, NARANJA),
        ("&#8735; reservar_inventario", 4, 40, 78, NARANJA),
        ("&#8735; verificar / aplicar_reserva", 5, 20, 88, NARANJA),
    ]
    for i, (nom, nivel, ancho, desp, color) in enumerate(barras):
        y = 8 + i * 22
        L.texto(6 + nivel * 9, y, 190, 16, nom, padre=casc, tam=9.5)
        L.caja(196 + desp, y + 2, ancho, 11, "",
               f"rounded=1;html=1;fillColor={color};strokeColor=none;arcSize=40;",
               padre=casc)

    L.caja(14, 252, 402, 116,
           "<b>Atributos del span de negocio</b><br>"
           "<font style='font-family: Consolas, monospace; font-size: 10px'>"
           "ecommerce.order.id = ord-10dc0f85abb5<br>"
           "ecommerce.customer.tier = silver<br>"
           "ecommerce.payment.result = authorized<br>"
           "ecommerce.checkout.step = order_submit<br>"
           "enduser.id = cli-007</font>",
           tarjeta("#ffffff", "#c6b9e0", 10), padre=c2)

    L.caja(14, 380, 402, 86,
           "<b>Como se logra</b><br><br>"
           "service-a envia la cabecera traceparent del W3C y service-b la lee, "
           "asi que no crea una traza nueva.<br>"
           "<i>TraceContextTextMapPropagator + HTTPXClientInstrumentor</i>",
           tarjeta("#f0ecf9", MORADO, 10) + "dashed=1;", padre=c2)

    # ------------------------------------------------------ 3. METRICAS
    c3 = L.caja(970, 190, 480, 480, "3. METRICAS",
                contenedor(VERDE_F, "#1f6b41", 15), ident="col_metricas")
    L.texto(14, 26, 452, 16, "formato Prometheus en :9464/metrics",
            padre=c3, tam=10, color="#555555", alineacion="center")

    L.caja(14, 50, 452, 140,
           "<b>De negocio, escritas a mano</b><br>"
           "<font style='font-family: Consolas, monospace; font-size: 10px'>"
           "ecommerce_orders_created_total<br>"
           "ecommerce_checkout_duration_seconds<br>"
           "ecommerce_order_amount<br>"
           "inventory_reservations_total<br>"
           "inventory_reserve_duration_seconds<br>"
           "inventory_stock_level</font><br>"
           "<i>37 series verificadas en el endpoint</i>",
           tarjeta("#ffffff", "#a8d6bd", 10), padre=c3)

    L.caja(14, 204, 452, 106,
           "<b>Derivadas de los spans por el Collector</b><br>"
           "<font style='font-family: Consolas, monospace; font-size: 10px'>"
           "otel_demo_calls_total<br>"
           "otel_demo_duration_milliseconds_bucket</font><br><br>"
           "Salen del conector spanmetrics, o sea del 100% de los spans. "
           "Alimentan los SLI.",
           tarjeta("#ffffff", "#a8d6bd", 10), padre=c3)

    L.caja(14, 324, 452, 132,
           "<b>El puente hacia las trazas</b><br><br>"
           "Las metricas no llevan trace_id porque serian de cardinalidad infinita. "
           "El enlace se hace por dos vias:<br>"
           "&#8226; atributos de recurso comunes (service.name)<br>"
           "&#8226; exemplars, que si guardan un trace_id de ejemplo",
           tarjeta("#eaf6ef", VERDE, 10) + "dashed=1;", padre=c3)

    # -------------------------------------------- recorrido de una alerta
    flujo = L.caja(30, 700, 1420, 170,
                   "Como se usa en la practica: el recorrido de una alerta",
                   contenedor(GRIS_F, "#666666", 13), ident="flujo")

    pasos = [
        ("1. Salta una alerta",
         "El panel de latencia p99 supera el umbral. Viene de metricas, que se calculan sobre todo.",
         VERDE, "p1"),
        ("2. Abre un ejemplo",
         "El exemplar del histograma lleva a una traza concreta de las que superaron el umbral.",
         MORADO, "p2"),
        ("3. Ve donde se fue el tiempo",
         "La cascada muestra que el 56% del tiempo esta en la llamada a service-b.",
         MORADO, "p3"),
        ("4. Lee los logs de esa traza",
         "Un clic filtra los logs por trace_id y muestra las 5 lineas de esa peticion.",
         AZUL, "p4"),
        ("5. Causa identificada",
         "Sin cambiar de herramienta ni buscar a mano por marca de tiempo.",
         ROJO, "p5"),
    ]
    for i, (titulo, cuerpo, color, ident) in enumerate(pasos):
        L.caja(16 + i * 282, 36, 250, 110,
               f"<b>{titulo}</b><br><br>{cuerpo}",
               tarjeta("#ffffff" if color != ROJO else ROJO_F, color, 10),
               padre=flujo, ident=ident)
    horizontal = ("exitX=1;exitY=0.5;exitDx=0;exitDy=0;"
                  "entryX=0;entryY=0.5;entryDx=0;entryDy=0;")
    for a, b in (("p1", "p2"), ("p2", "p3"), ("p3", "p4"), ("p4", "p5")):
        L.flecha(a, b, "", color=ROJO, grosor=2, estilo_extra=horizontal)

    # Los tres pilares cuelgan del pivote: sale por abajo y entra por arriba.
    vertical = ("exitX=0.5;exitY=1;exitDx=0;exitDy=0;"
                "entryX=0.5;entryY=0;entryDx=0;entryDy=0;")
    L.flecha("pivote", "col_logs", "", color=ROJO, grosor=2, estilo_extra=vertical)
    L.flecha("pivote", "col_trazas", "", color=ROJO, grosor=2, estilo_extra=vertical)
    L.flecha("pivote", "col_metricas", "", color=ROJO, grosor=2, estilo_extra=vertical)

    L.escribir(SALIDA / "fig3_correlacion.drawio")


if __name__ == "__main__":
    print("generando diagramas editables en formato draw.io:")
    figura_uno()
    figura_tres()
    print("\nSe abren en https://app.diagrams.net, en la app de escritorio "
          "o con la extension de VS Code.")
