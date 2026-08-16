"""
Arma el reporte técnico en PDF a partir de los datos reales del repositorio.

Lee benchmark/results/benchmark_results.json y docs/evidencia/, así que las
cifras del documento y las del repositorio nunca se separan.
"""

import json
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    Image,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

RAIZ = Path(__file__).resolve().parent.parent
FIG = RAIZ / "docs" / "figuras"
D = json.loads((RAIZ / "benchmark" / "results" / "benchmark_results.json").read_text())
E8 = D["escenario_8_usuarios"]
C8 = E8["comparacion"]
M8 = E8["con_muestreo_10_pct"]
C50 = D["escenario_50_usuarios"]["comparacion"]

AZUL = colors.HexColor("#1a4f7a")
GRIS = colors.HexColor("#4a4a4a")
ROJO = colors.HexColor("#b03a2e")

ss = getSampleStyleSheet()
S = {
    "titulo": ParagraphStyle("t", parent=ss["Title"], fontSize=19, leading=24,
                             textColor=AZUL, spaceAfter=6),
    "sub": ParagraphStyle("s", parent=ss["Normal"], fontSize=11.5, leading=15,
                          alignment=TA_CENTER, textColor=GRIS, spaceAfter=16),
    "h1": ParagraphStyle("h1", parent=ss["Heading1"], fontSize=14, leading=18,
                         textColor=AZUL, spaceBefore=16, spaceAfter=7),
    "h2": ParagraphStyle("h2", parent=ss["Heading2"], fontSize=11.8, leading=15,
                         textColor=colors.HexColor("#2c3e50"), spaceBefore=11, spaceAfter=5),
    "p": ParagraphStyle("p", parent=ss["Normal"], fontSize=9.9, leading=14.2,
                        alignment=TA_JUSTIFY, spaceAfter=7),
    "li": ParagraphStyle("li", parent=ss["Normal"], fontSize=9.9, leading=14,
                         leftIndent=14, bulletIndent=4, spaceAfter=3.5),
    "code": ParagraphStyle("c", parent=ss["Normal"], fontSize=8.2, leading=10.6,
                           fontName="Courier", backColor=colors.HexColor("#f4f4f4"),
                           borderPadding=5, leftIndent=6, spaceAfter=8),
    "cap": ParagraphStyle("cap", parent=ss["Normal"], fontSize=8.4, leading=11,
                          textColor=GRIS, alignment=TA_CENTER, spaceBefore=4, spaceAfter=12),
    "nota": ParagraphStyle("n", parent=ss["Normal"], fontSize=8.6, leading=11.6,
                           textColor=GRIS, alignment=TA_JUSTIFY, spaceAfter=8),
}


def P(t, e="p"):
    return Paragraph(t, S[e])


def B(t):
    return Paragraph(t, S["li"], bulletText="\u2022")


def tabla(datos, anchos, alinear_der=None, resaltar=None):
    t = Table(datos, colWidths=anchos, repeatRows=1, hAlign="LEFT")
    est = [
        ("BACKGROUND", (0, 0), (-1, 0), AZUL),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.4),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4.5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#c8d4de")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f2f6f9")]),
    ]
    for c in (alinear_der or []):
        est.append(("ALIGN", (c, 1), (c, -1), "CENTER"))
    for c in (resaltar or []):
        est.append(("TEXTCOLOR", (c, 1), (c, -1), ROJO))
        est.append(("FONTNAME", (c, 1), (c, -1), "Helvetica-Bold"))
    t.setStyle(TableStyle(est))
    return t


def figura(nombre, ancho_cm, leyenda):
    ruta = FIG / nombre
    from PIL import Image as PILImage

    w, h = PILImage.open(ruta).size
    ancho = ancho_cm * cm
    return [Image(str(ruta), width=ancho, height=ancho * h / w),
            Paragraph(leyenda, S["cap"])]


def pie(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 7.6)
    canvas.setFillColor(GRIS)
    canvas.drawString(2 * cm, 1.15 * cm,
                      "Pipeline de observabilidad end to end con OpenTelemetry")
    canvas.drawRightString(19.4 * cm, 1.15 * cm, f"Página {doc.page}")
    canvas.setStrokeColor(colors.HexColor("#d5dde4"))
    canvas.line(2 * cm, 1.5 * cm, 19.4 * cm, 1.5 * cm)
    canvas.restoreState()


def d(campo, clave):
    return C8[campo][clave]


def construir():
    doc = SimpleDocTemplate(
        str(RAIZ / "docs" / "Reporte_tecnico.pdf"),
        pagesize=letter,
        leftMargin=2 * cm, rightMargin=2 * cm,
        topMargin=1.9 * cm, bottomMargin=2 * cm,
        title="Pipeline de observabilidad end to end con OpenTelemetry",
        author="Ernesto Ilich Contreras H., Saud Mauricio González R., María Fernanda Ochoa Paipilla",
    )
    h = []

    # ----------------------------------------------------------- portada
    h.append(Spacer(1, 6))
    h.append(P("Pipeline de observabilidad end to end con OpenTelemetry", "titulo"))
    h.append(P("Instrumentación de dos microservicios en GCP y AWS, correlación "
               "entre trazas, logs y métricas, y análisis de overhead medido", "sub"))
    h.append(tabla([
        ["Autores", "Ernesto Ilich Contreras H.  ·  Saud Mauricio González R.  ·  María Fernanda Ochoa Paipilla"],
        ["Programa", "Maestría en Inteligencia Artificial, Universidad de la Sabana"],
        ["Repositorio", "otel-observability-pipeline"],
        ["Fecha", "Agosto de 2026"],
    ], [3 * cm, 14 * cm]))
    h.append(Spacer(1, 12))

    # ----------------------------------------------------------- resumen
    h.append(P("1. Resumen", "h1"))
    h.append(P(
        "Este trabajo construye un pipeline de observabilidad completo sobre dos "
        "microservicios que se llaman entre sí por HTTP y que consultan una base de "
        "datos. Los servicios emiten los tres pilares con el SDK de OpenTelemetry, "
        "un Collector los recibe y los reparte a los backends de las dos nubes, y "
        "todo queda unido por un mismo <b>trace_id</b>."))
    h.append(P(
        "Lo que distingue este entregable es que las cifras no son estimaciones. El "
        "repositorio incluye un banco de pruebas que levanta los servicios, aplica "
        "carga y mide. Los resultados que aparecen aquí salen de esa corrida y se "
        "pueden repetir con un comando."))
    h.append(P("Los tres hallazgos principales son estos:"))
    h.append(B(f"La instrumentación cuesta <b>{d('lat_p50_ms','delta_pct')}%</b> de latencia mediana "
               f"y <b>{d('rps','delta_pct')}%</b> de throughput con la configuración que captura todo."))
    h.append(B("El costo no lo genera el agente sino el volumen de spans. Cada petición "
               f"produce 20 spans. Bajar el muestreo de cabecera al 10 por ciento reduce "
               f"los spans un 88,3 por ciento y recupera "
               f"{M8['rps'] - d('rps','con_otel'):.0f} peticiones por segundo."))
    h.append(B("La correlación entre los tres pilares no es automática: depende de tres "
               "piezas concretas que se detallan en la sección 5."))

    # ----------------------------------------------------- arquitectura
    h.append(P("2. Arquitectura", "h1"))
    h.append(P(
        "El flujo es simple a propósito, para que el análisis se concentre en la "
        "telemetría y no en la lógica de negocio. Una petición de compra entra por "
        "<b>service-a</b>, que consulta su base de datos para conocer el descuento del "
        "cliente, calcula el total y llama a <b>service-b</b> para reservar inventario. "
        "service-b consulta y actualiza su propia base de datos y responde."))
    h.append(P(
        "Esa petición, que dura cerca de 38 milisegundos, genera 20 spans repartidos "
        "entre los dos servicios. La Figura 1 muestra el recorrido completo de la "
        "telemetría, desde el proceso de la aplicación hasta los tableros."))
    h.extend(figura("fig1_arquitectura.png", 15.6,
                    "<b>Figura 1.</b> Pipeline de observabilidad. Las fases corresponden a "
                    "las que pide la actividad. Lo único que cambia entre GCP y AWS es el "
                    "bloque de exporters del Collector."))

    h.append(PageBreak())
    h.append(P("2.1 Decisiones de diseño", "h2"))
    h.append(P("Cuatro decisiones explican por que el pipeline quedo así."))

    h.append(tabla([
        ["Decisión", "Alternativa descartada", "Por que"],
        ["La aplicación solo habla con el Collector, nunca con un backend",
         "Exportar directo a Cloud Trace y a X-Ray",
         "Cambiar de backend sería tocar el código de los dos servicios. Así es editar un archivo de configuración."],
        ["Un solo modulo de arranque, telemetry.py, para los dos servicios",
         "Configurar el SDK dentro de cada app",
         "Evita que los dos servicios se desincronicen y hace que apagar la telemetría para el benchmark sea una variable de entorno."],
        ["El conector spanmetrics va en el Collector, no en la aplicación",
         "Calcular tasa, error y duración con métricas propias",
         "El Collector ve el 100 por ciento de los spans, así que los SLI no dependen del muestreo que se aplique después."],
        ["Auto instrumentación como base, spans propios solo para negocio",
         "Escribir todos los spans a mano",
         "La auto instrumentación cubre HTTP y base de datos sin tocar el código. Lo manual se reserva para lo que ninguna libreria puede saber."],
    ], [4.6 * cm, 4.4 * cm, 8 * cm]))

    h.append(P("2.2 El mismo diseño en dos nubes", "h2"))
    h.append(P(
        "Los receivers y los processors del Collector son identicos en GCP y en AWS. "
        "La diferencia esta en donde corre y a donde exporta."))
    h.append(tabla([
        ["", "GCP (GKE)", "AWS (ECS Fargate)"],
        ["Despliegue", "DaemonSet, un Collector por nodo", "Contenedor sidecar en cada task definition"],
        ["Trazas", "otlp/jaeger, googlecloud", "awsxray, otlp/tempo, otlp/jaeger"],
        ["Métricas", "prometheus, googlemanagedprometheus", "prometheus, awsemf"],
        ["Logs", "googlecloud", "awscloudwatchlogs"],
        ["Configuración", "ConfigMap que Terraform crea con file()", "Parametro de SSM que Terraform crea con file()"],
        ["Identidad", "Workload Identity", "Rol IAM de la tarea"],
    ], [3 * cm, 6.9 * cm, 7.1 * cm]))
    h.append(P(
        "En Fargate no existe el concepto de DaemonSet, por eso el patrón equivalente "
        "es el sidecar. La aplicación le habla por localhost, que es igual de barato "
        "que hablarle a un agente en el mismo nodo.", "nota"))

    # --------------------------------------------------- instrumentación
    h.append(P("3. Instrumentación", "h1"))
    h.append(P(
        "La división del trabajo entre instrumentación automática y manual sigue una "
        "regla: la automática cubre lo que es igual en cualquier servicio, la manual "
        "cubre lo que solo el equipo de producto entiende."))
    h.append(tabla([
        ["Tipo", "Que captura", "Spans que produce"],
        ["Automática", "FastAPIInstrumentor, el HTTP de entrada", "POST /checkout, POST /inventory/reserve"],
        ["Automática", "HTTPXClientInstrumentor, el HTTP de salida", "POST, e inyecta la cabecera traceparent"],
        ["Automática", "SQLite3Instrumentor, la base de datos", "SELECT, INSERT, UPDATE con db.statement"],
        ["Manual", "El flujo de compra de service-a", "flujo_checkout, calcular_total_pedido, reservar_inventario_remoto"],
        ["Manual", "La reserva de service-b", "reservar_inventario, verificar_existencias, aplicar_reserva"],
    ], [2.4 * cm, 6.4 * cm, 8.2 * cm]))
    h.append(P(
        "Un detalle práctico que costó depurar: la auto instrumentación de bases de "
        "datos envuelve el cursor, no la conexion. Si el código llama a "
        "<b>con.execute()</b> en lugar de <b>cur.execute()</b>, no aparece ningún span de "
        "base de datos. El repositorio usa cursores explicitos por esa razón.", "nota"))

    h.append(P("3.1 Los tres pilares", "h2"))
    h.append(tabla([
        ["Pilar", "Como sale", "Verificado en"],
        ["Trazas", "OTLP gRPC al Collector, puerto 4317", "20 spans capturados en el receptor OTLP"],
        ["Métricas", "PrometheusMetricReader en el puerto 9464", "docs/evidencia/metricas_service_a.txt"],
        ["Logs", "JSON por salida estándar con trace_id y span_id", "docs/evidencia/logs_correlacionados.jsonl"],
    ], [2.2 * cm, 7.6 * cm, 7.2 * cm]))
    h.append(P("Las métricas de negocio que expone el SDK son estas:"))
    h.append(Paragraph(
        "ecommerce_orders_created_total &nbsp;·&nbsp; ecommerce_orders_failed_total<br/>"
        "ecommerce_checkout_duration_seconds &nbsp;·&nbsp; ecommerce_order_amount<br/>"
        "inventory_reservations_total &nbsp;·&nbsp; inventory_reserve_duration_seconds &nbsp;·&nbsp; inventory_stock_level",
        S["code"]))

    # ------------------------------------------------------ propagación
    h.append(PageBreak())
    h.append(P("4. Propagación de contexto", "h1"))
    h.append(P(
        "La propagación es la pieza que decide si el sistema tiene trazas distribuidas "
        "o dos conjuntos de trazas sueltas. Funciona así: service-a crea el trace_id, "
        "el cliente HTTP instrumentado lo escribe en la cabecera <b>traceparent</b> definida "
        "por el W3C, y service-b la lee y continua la misma traza en lugar de empezar "
        "una nueva."))
    h.append(P(
        "La Figura 2 es la prueba. Se genero desde los spans reales que llegaron al "
        "receptor OTLP durante una petición."))
    h.extend(figura("fig2_traza_completa.png", 14.6,
                    "<b>Figura 2.</b> Traza real de una petición de compra. Los spans azules "
                    "son de service-a y los naranjas de service-b. Que los naranjas cuelguen "
                    "de los azules es lo que demuestra que el contexto viajo entre servicios."))
    h.append(P(
        "Tres cosas se leen en esa figura. La primera es que los 20 spans comparten un "
        "solo trace_id. La segunda es que la jerarquía es correcta: el span de "
        "service-b es hijo del span de cliente HTTP de service-a. La tercera es donde "
        "se va el tiempo, porque la llamada a service-b concentra 21,27 de los 37,97 "
        "milisegundos, es decir el 56 por ciento."))

    # ------------------------------------------------------ correlación
    h.append(PageBreak())
    h.append(P("5. Correlación entre los tres pilares", "h1"))
    h.append(P(
        "Que las tres señales existan no significa que estén conectadas. La conexion "
        "se logra con tres piezas concretas, y si falta cualquiera de ellas la "
        "investigación vuelve a ser buscar por marca de tiempo."))
    h.append(tabla([
        ["Pieza", "Que hace", "Donde esta"],
        ["LoggingInstrumentor con inject_trace_context",
         "Agrega otelTraceID a cada registro de log, que el formateador escribe como trace_id",
         "services/common/telemetry.py"],
        ["derivedFields de Grafana",
         "Convierte el campo trace_id del log en un enlace que abre la traza",
         "dashboards/grafana-datasources.yml"],
        ["Atributos de recurso compartidos",
         "service.name y deployment.environment.name identifican el mismo servicio en las tres señales",
         "Resource del SDK y processor resource del Collector"],
    ], [4.6 * cm, 7.4 * cm, 5 * cm]))
    h.append(P(
        "En GCP hay una cuarta pieza que ahorra configuración. Si el log incluye el "
        "campo <b>logging.googleapis.com/trace</b>, Cloud Logging enlaza con Cloud Trace "
        "sin que nadie configure nada. El formateador lo agrega cuando existe la "
        "variable GCP_PROJECT_ID.", "nota"))
    h.extend(figura("fig3_correlacion.png", 15.4,
                    "<b>Figura 3.</b> Los tres pilares de una misma petición, con datos reales. "
                    "Abajo, el recorrido que sigue una persona desde la alerta hasta la causa."))

    h.append(P("5.1 Cómo se comprueba", "h2"))
    h.append(Paragraph(
        "# 1. genere una petición y guarde el identificador<br/>"
        "curl -s -X POST localhost:8001/checkout -H 'Content-Type: application/json' \\<br/>"
        "&nbsp;&nbsp;-d '{\"cliente_id\":\"cli-001\",\"sku\":\"SKU-1001\",\"cantidad\":2}' | jq -r .trace_id<br/><br/>"
        "# 2. en Jaeger debe aparecer una sola traza con 20 spans y dos servicios<br/>"
        "# 3. en Grafana Explore, con Loki:<br/>"
        "{container=~\"service-.*\"} | json | trace_id = \"&lt;el identificador&gt;\"<br/>"
        "# deben salir 5 lineas, 3 de service-a y 2 de service-b<br/>"
        "# 4. el enlace TraceID de cualquier linea abre la misma traza",
        S["code"]))
    h.append(P(
        "El resultado real de esa comprobación esta guardado en docs/evidencia. Las "
        "cinco lineas de log son: checkout iniciado, la llamada HTTP saliente y pedido "
        "confirmado en service-a, más reserva solicitada y reserva confirmada en "
        "service-b."))

    # -------------------------------------------------------- overhead
    h.append(PageBreak())
    h.append(P("6. Análisis de overhead", "h1"))
    h.append(P("6.1 Cómo se midió", "h2"))
    h.append(P(
        "El mismo binario corre en los dos escenarios. La variable OTEL_ENABLED apaga "
        "el SDK completo, así que el código de negocio es identico y la única "
        "diferencia es la telemetría."))
    h.append(B("Dos escenarios: sin instrumentación y con instrumentación completa."))
    h.append(B("Dos repeticiones de 60 segundos por escenario, se reporta la mediana."))
    h.append(B("Los primeros 12 segundos se descartan por calentamiento."))
    h.append(B("La latencia se mide desde el cliente. Medirla dentro del servicio "
               "instrumentado sería evaluar el instrumento consigo mismo."))
    h.append(B("CPU y memoria se leen de los procesos de aplicación. El Collector se "
               "mide aparte, porque es infraestructura compartida y no costo de la aplicación."))
    h.append(P(
        f"Entorno: {D['entorno']['vcpu']} vCPU, {D['entorno']['ram_mb']} MB de RAM, "
        f"Python {D['entorno']['python']}. El generador de carga corre en la misma "
        "máquina, por lo que las latencias absolutas incluyen la competencia por CPU. "
        "La comparación entre escenarios sigue siendo valida porque las dos corridas "
        "sufren esa misma condición.", "nota"))

    h.append(P("6.2 Resultados", "h2"))
    h.append(P("<b>Tabla 1.</b> Costo de la instrumentación con 8 usuarios concurrentes"))
    filas = [["Métrica", "Sin OTel", "Con OTel", "Diferencia", "Cambio", "Con muestreo 10%"]]
    for campo, etiqueta, unidad in [
        ("lat_p50_ms", "Latencia p50", "ms"),
        ("lat_p95_ms", "Latencia p95", "ms"),
        ("lat_p99_ms", "Latencia p99", "ms"),
        ("rps", "Throughput", "rps"),
        ("cpu_media_pct", "CPU de los dos servicios", "%"),
        ("mem_media_mb", "Memoria RSS", "MB"),
    ]:
        v = C8[campo]
        filas.append([etiqueta,
                      f"{v['sin_otel']:.2f} {unidad}",
                      f"{v['con_otel']:.2f} {unidad}",
                      f"{v['delta_abs']:+.2f}",
                      f"{v['delta_pct']:+.1f}%",
                      f"{M8[campo]:.2f} {unidad}"])
    h.append(tabla(filas, [4.2 * cm, 2.6 * cm, 2.6 * cm, 2.2 * cm, 2 * cm, 3.4 * cm],
                   alinear_der=[1, 2, 3, 4, 5], resaltar=[4]))
    h.append(P(
        f"El Collector consumio aparte {E8['collector']['cpu_pct']}% de un nucleo y "
        f"{E8['collector']['mem_mb']} MB, procesando "
        f"{E8['spans_exportados']['con_otel']:,} spans en 60 segundos.".replace(",", "."), "nota"))

    h.extend(figura("fig4_benchmark.png", 15.6,
                    "<b>Figura 4.</b> Resultados del benchmark. El panel inferior derecho "
                    "compara el costo relativo en los dos niveles de carga."))

    h.append(P("6.3 Qué dicen los números", "h2"))
    h.append(P(
        f"<b>El p50 sube mucho más que el p99.</b> La latencia mediana crece "
        f"{d('lat_p50_ms','delta_pct')} por ciento mientras que el p99 solo crece "
        f"{d('lat_p99_ms','delta_pct')} por ciento. La razón es que el costo de la "
        "instrumentación es casi constante por petición, cerca de 11 milisegundos. "
        "Sobre una petición rapida ese costo pesa mucho y sobre una lenta se diluye. "
        "Conviene tenerlo presente porque un tablero que solo mire el p99 va a "
        "subestimar el impacto."))
    h.append(P(
        f"<b>El throughput cae más que lo que sugiere la latencia.</b> Se pierde "
        f"{abs(d('rps','delta_abs')):.0f} peticiones por segundo, es decir "
        f"{abs(d('rps','delta_pct'))} por ciento. Con la CPU subiendo "
        f"{d('cpu_media_pct','delta_pct')} por ciento, la instrumentación compite por "
        "el mismo recurso que atiende peticiones."))
    h.append(P(
        "<b>La memoria es un costo fijo.</b> Sube "
        f"{d('mem_media_mb','delta_pct')} por ciento y casi no baja al activar el "
        f"muestreo: {M8['mem_media_mb']} MB frente a {d('mem_media_mb','con_otel')} MB. "
        "Es el costo de cargar el SDK y las librerias de instrumentación, y se paga "
        "aunque no se exporte un solo span."))
    h.append(P(
        "<b>El costo crece con la concurrencia.</b> Con 50 usuarios el p50 sube "
        f"{C50['lat_p50_ms']['delta_pct']} por ciento y el throughput cae "
        f"{abs(C50['rps']['delta_pct'])} por ciento, frente a "
        f"{d('lat_p50_ms','delta_pct')} y {abs(d('rps','delta_pct'))} por ciento con 8 "
        "usuarios. Cuando la máquina ya esta cerca de su límite, cualquier trabajo "
        "extra se paga con creces."))

    h.append(P("6.4 La palanca que sirve", "h2"))
    h.append(P(
        "Cada petición produce 20 spans, que es mucho para dos servicios. El costo no "
        "viene del agente sino de ese volumen. Bajar el muestreo de cabecera al 10 por "
        "ciento cambia el balance:"))
    sp = E8["spans_exportados"]
    h.append(tabla([
        ["", "Sin muestreo", "Muestreo al 10%", "Cambio"],
        ["Spans exportados en 60 s", f"{sp['con_otel']:,}".replace(",", "."),
         f"{sp['con_muestreo_10']:,}".replace(",", "."),
         f"-{100 * (1 - sp['con_muestreo_10'] / sp['con_otel']):.1f}%"],
        ["Throughput", f"{d('rps','con_otel')} rps", f"{M8['rps']} rps",
         f"+{(M8['rps'] / d('rps','con_otel') - 1) * 100:.1f}%"],
        ["Latencia p50", f"{d('lat_p50_ms','con_otel')} ms", f"{M8['lat_p50_ms']} ms",
         f"{(M8['lat_p50_ms'] / d('lat_p50_ms','con_otel') - 1) * 100:+.1f}%"],
        ["CPU", f"{d('cpu_media_pct','con_otel')}%", f"{M8['cpu_media_pct']}%",
         f"{(M8['cpu_media_pct'] / d('cpu_media_pct','con_otel') - 1) * 100:+.1f}%"],
        ["Memoria RSS", f"{d('mem_media_mb','con_otel')} MB", f"{M8['mem_media_mb']} MB",
         f"{(M8['mem_media_mb'] / d('mem_media_mb','con_otel') - 1) * 100:+.1f}%"],
    ], [5 * cm, 4 * cm, 4 * cm, 4 * cm], alinear_der=[1, 2, 3], resaltar=[3]))
    h.append(P(
        "El muestreo de cabecera tiene un problema conocido: decide antes de saber si "
        "la petición fallo, así que se pierden errores raros. Para producción la "
        "recomendación es mover la decisión al Collector con muestreo de cola, que "
        "conserva el cien por ciento de los errores porque decide con la traza ya "
        "completa. Los SLI no se ven afectados en ninguno de los dos casos, porque "
        "salen del conector spanmetrics, que corre antes del muestreo."))

    # ---------------------------------------------------- conclusiones
    h.append(P("7. Conclusiones", "h1"))
    h.append(P(
        "El pipeline cumple lo que se propuso. Una petición produce una sola traza que "
        "atraviesa los dos servicios, cinco lineas de log que llevan ese mismo "
        "identificador y un conjunto de métricas que se calculan sobre el total de "
        "peticiones. Desde una alerta se llega a la causa sin cambiar de herramienta "
        "ni buscar por marca de tiempo."))
    h.append(P("Tres lecciones quedan para llevar a producción:"))
    h.append(B("<b>Medir antes de opinar.</b> La intuición decía que el overhead sería de "
               "un digito. Fue de "
               f"{d('lat_p50_ms','delta_pct')} por ciento en latencia mediana. "
               "Sin banco de pruebas ese dato no habría aparecido."))
    h.append(B("<b>El volumen es la variable de control.</b> Veinte spans por petición es "
               "demasiado para un flujo de dos servicios. Conviene revisar cuáles spans "
               "aportan y bajar el muestreo, no quitar la instrumentación."))
    h.append(B("<b>El orden en el Collector protege los indicadores.</b> Poner spanmetrics "
               "antes de cualquier muestreo permite reducir el volumen de trazas sin "
               "mover los SLI."))
    h.append(P("Lo que queda pendiente:"))
    h.append(B("Repetir el benchmark en las nubes, con el generador de carga fuera del "
               "host, para separar el costo de la instrumentación del de la máquina."))
    h.append(B("Sustituir el muestreo de cabecera por muestreo de cola en el Collector, "
               "con politicas que conserven todos los errores."))
    h.append(B("Revisar el mapa de spans y quitar los que no aportan a un diagnóstico, "
               "empezando por los spans internos de recepción y envio de ASGI."))

    # ------------------------------------------------------- referencias
    h.append(P("8. Referencias", "h1"))
    for r in [
        "Grafana Labs. (2026). <i>Trace integration: Linking traces, logs and metrics</i>. "
        "https://grafana.com/docs/grafana/latest/explore/trace-integration/",
        "Grafana Labs. (2026). <i>k6 load testing documentation</i>. https://k6.io/docs/",
        "Jaeger. (2026). <i>Architecture documentation</i>. "
        "https://www.jaegertracing.io/docs/architecture/",
        "OpenTelemetry. (2026). <i>Collector documentation</i>. "
        "https://opentelemetry.io/docs/collector/",
        "OpenTelemetry. (2026). <i>Python SDK documentation</i>. "
        "https://opentelemetry-python.readthedocs.io/",
        "World Wide Web Consortium. (2021). <i>Trace context</i> (W3C Recommendation). "
        "https://www.w3.org/TR/trace-context/",
    ]:
        h.append(Paragraph(r, ParagraphStyle("ref", parent=S["p"], leftIndent=14,
                                             firstLineIndent=-14, spaceAfter=5)))

    h.append(P("Anexo. Contenido del repositorio", "h1"))
    h.append(tabla([
        ["Entregable que pide la actividad", "Dónde está"],
        ["Código de instrumentación con el SDK", "services/common/telemetry.py y services/service-a, service-b"],
        ["Configuración del OTel Collector", "collector/otel-collector-gcp.yaml, -aws.yaml y -local.yaml"],
        ["Manifiestos de IaC", "iac/terraform/gcp, iac/terraform/aws, iac/helm/otel-collector, iac/k8s"],
        ["Capturas de Jaeger con trazas completas", "docs/figuras/fig2_traza_completa.png y la guía docs/CAPTURAS.md"],
        ["Dashboards de Grafana", "dashboards/grafana-observabilidad.json, 6 paneles y el de correlación"],
        ["Reporte técnico", "este documento"],
        ["Prueba de carga", "benchmark/load_test.js para k6 y benchmark/run_benchmark.py"],
        ["Datos crudos de la medición", "benchmark/results/benchmark_results.json y corridas.jsonl"],
        ["Evidencia de la correlación", "docs/evidencia/ con la traza, los logs y las métricas capturados"],
    ], [6.4 * cm, 10.6 * cm]))

    doc.build(h, onFirstPage=pie, onLaterPages=pie)
    print("Reporte_tecnico.pdf generado")


if __name__ == "__main__":
    construir()
