"""
Genera las figuras del reporte a partir de los datos reales del repositorio.

  Figura 2: cascada de la traza, con el mismo formato que la vista de Jaeger,
            construida desde docs/evidencia/traza_completa.json
  Figura 4: graficas del benchmark, desde benchmark/results/benchmark_results.json

Las figuras 1 y 3 son diagramas de arquitectura y se escriben a mano en SVG.
"""

import json
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
FIG = RAIZ / "docs" / "figuras"
FIG.mkdir(parents=True, exist_ok=True)

COLOR = {"service-a": "#4285f4", "service-b": "#ff9900"}


# ----------------------------------------------------- Figura 2: la cascada

def figura_traza():
    spans = json.loads((RAIZ / "docs" / "evidencia" / "traza_completa.json").read_text())
    if not spans:
        return
    t0 = min(s["start"] for s in spans)
    total_ms = (max(s["end"] for s in spans) - t0) / 1e6

    hijos = {}
    for s in spans:
        hijos.setdefault(s["parent_span_id"], []).append(s)

    ordenados = []

    def recorrer(pid, nivel):
        for s in sorted(hijos.get(pid, []), key=lambda x: x["start"]):
            ordenados.append((s, nivel))
            recorrer(s["span_id"], nivel + 1)

    recorrer("", 0)

    fila_h, top, izq, ancho_barra = 30, 112, 22, 560
    alto = top + fila_h * len(ordenados) + 74
    ancho = 1020
    etiquetas_x = izq + 300

    p = []
    p.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{ancho}" height="{alto}" '
             f'viewBox="0 0 {ancho} {alto}" font-family="Helvetica, Arial, sans-serif">')
    p.append(f'<rect width="{ancho}" height="{alto}" fill="#ffffff"/>')
    p.append(f'<text x="{izq}" y="30" font-size="16" font-weight="bold" fill="#111">'
             f'Traza completa del flujo de compra</text>')
    p.append(f'<text x="{izq}" y="52" font-size="12.5" fill="#444">'
             f'trace_id {spans[0]["trace_id"]}  ·  {len(spans)} spans  ·  '
             f'{total_ms:.2f} ms  ·  2 servicios</text>')

    # leyenda
    for i, (svc, col) in enumerate(COLOR.items()):
        x = izq + i * 130
        p.append(f'<rect x="{x}" y="66" width="13" height="13" rx="2" fill="{col}"/>')
        p.append(f'<text x="{x + 19}" y="77" font-size="12" fill="#333">{svc}</text>')

    # eje de tiempo
    for i in range(6):
        x = etiquetas_x + ancho_barra * i / 5
        ms = total_ms * i / 5
        p.append(f'<line x1="{x:.1f}" y1="{top - 16}" x2="{x:.1f}" y2="{alto - 60}" '
                 f'stroke="#e8e8e8" stroke-width="1"/>')
        p.append(f'<text x="{x:.1f}" y="{top - 22}" font-size="10.5" fill="#888" '
                 f'text-anchor="middle">{ms:.1f} ms</text>')

    for i, (s, nivel) in enumerate(ordenados):
        y = top + i * fila_h
        col = COLOR.get(s["service.name"], "#888")
        x0 = etiquetas_x + ancho_barra * ((s["start"] - t0) / 1e6) / total_ms
        w = max(ancho_barra * (s["duration_ms"] / total_ms), 2.0)

        if i % 2 == 0:
            p.append(f'<rect x="{izq - 6}" y="{y - 13}" width="{ancho - 30}" '
                     f'height="{fila_h}" fill="#fafafa"/>')

        nombre = s["name"]
        if len(nombre) > 30:
            nombre = nombre[:29] + "…"
        p.append(f'<text x="{izq + nivel * 13}" y="{y + 3}" font-size="11.5" fill="#222">'
                 f'{"└ " if nivel else ""}{nombre}</text>')

        p.append(f'<rect x="{x0:.1f}" y="{y - 8}" width="{w:.1f}" height="13" rx="2.5" '
                 f'fill="{col}" opacity="0.88"/>')
        p.append(f'<text x="{x0 + w + 7:.1f}" y="{y + 3}" font-size="10.5" fill="#555">'
                 f'{s["duration_ms"]:.2f} ms</text>')

        db = s["attributes"].get("db.statement")
        if db:
            corto = db[:44] + ("…" if len(db) > 44 else "")
            p.append(f'<text x="{izq + nivel * 13 + 12}" y="{y + 15}" font-size="8.5" '
                     f'fill="#999">{corto}</text>')

    p.append(f'<line x1="{izq}" y1="{alto - 52}" x2="{ancho - 30}" y2="{alto - 52}" '
             f'stroke="#ddd"/>')
    p.append(f'<text x="{izq}" y="{alto - 32}" font-size="11" fill="#444">'
             f'El contexto viaja en la cabecera traceparent del W3C, por eso los spans de '
             f'service-b cuelgan de los de service-a</text>')
    p.append(f'<text x="{izq}" y="{alto - 16}" font-size="11" fill="#444">'
             f'y los 20 spans quedan en una sola traza. Datos exportados por OTLP y '
             f'capturados en el receptor del Collector.</text>')
    p.append("</svg>")

    (FIG / "fig2_traza_completa.svg").write_text("\n".join(p), encoding="utf-8")
    print("fig2_traza_completa.svg")


# ------------------------------------------------- Figura 4: el benchmark

def figura_benchmark():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    d = json.loads((RAIZ / "benchmark" / "results" / "benchmark_results.json").read_text())
    e8 = d["escenario_8_usuarios"]
    c8 = e8["comparacion"]
    m8 = e8["con_muestreo_10_pct"]
    e50 = d["escenario_50_usuarios"]["comparacion"]

    fig, ax = plt.subplots(2, 2, figsize=(12.4, 8.2))
    fig.suptitle("Costo de la instrumentacion OpenTelemetry (mediciones propias)",
                 fontsize=14, fontweight="bold", y=0.98)

    gris, azul, verde = "#8a8a8a", "#c0392b", "#2e9e63"

    # a) latencia por percentil, 8 usuarios
    a = ax[0][0]
    ps = ["lat_p50_ms", "lat_p95_ms", "lat_p99_ms"]
    x = range(len(ps))
    a.bar([i - 0.26 for i in x], [c8[p]["sin_otel"] for p in ps], 0.26,
          label="sin OTel", color=gris)
    a.bar([i for i in x], [c8[p]["con_otel"] for p in ps], 0.26,
          label="con OTel", color=azul)
    a.bar([i + 0.26 for i in x], [m8[p] for p in ps], 0.26,
          label="OTel + muestreo 10%", color=verde)
    a.set_xticks(list(x)); a.set_xticklabels(["p50", "p95", "p99"])
    a.set_ylabel("milisegundos"); a.set_title("Latencia con 8 usuarios", fontsize=11)
    a.legend(fontsize=8.5); a.grid(axis="y", alpha=0.3)
    for i, p in enumerate(ps):
        a.text(i, c8[p]["con_otel"], f"{c8[p]['delta_pct']:+.0f}%", ha="center",
               va="bottom", fontsize=8.5, color=azul)

    # b) throughput
    b = ax[0][1]
    barras = ["sin OTel", "con OTel", "OTel +\nmuestreo 10%"]
    vals = [c8["rps"]["sin_otel"], c8["rps"]["con_otel"], m8["rps"]]
    cols = [gris, azul, verde]
    bb = b.bar(barras, vals, color=cols, width=0.55)
    b.set_ylabel("peticiones por segundo")
    b.set_title("Throughput con 8 usuarios", fontsize=11)
    b.grid(axis="y", alpha=0.3)
    base = vals[0]
    for r, v in zip(bb, vals):
        pct = (v - base) / base * 100
        b.text(r.get_x() + r.get_width() / 2, v + 4,
               f"{v:.0f}" + (f"\n({pct:+.1f}%)" if pct else ""),
               ha="center", fontsize=9)

    # c) CPU y memoria
    c = ax[1][0]
    x2 = [0, 1]
    c.bar([i - 0.26 for i in x2],
          [c8["cpu_media_pct"]["sin_otel"], c8["mem_media_mb"]["sin_otel"]], 0.26,
          label="sin OTel", color=gris)
    c.bar(x2, [c8["cpu_media_pct"]["con_otel"], c8["mem_media_mb"]["con_otel"]], 0.26,
          label="con OTel", color=azul)
    c.bar([i + 0.26 for i in x2],
          [m8["cpu_media_pct"], m8["mem_media_mb"]], 0.26,
          label="OTel + muestreo 10%", color=verde)
    c.set_xticks(x2)
    c.set_xticklabels(["CPU (% de un nucleo,\nsuma de los 2 servicios)", "Memoria RSS (MB)"])
    c.set_title("Recursos consumidos", fontsize=11)
    c.set_ylim(0, max(c8["cpu_media_pct"]["con_otel"], c8["mem_media_mb"]["con_otel"]) * 1.34)
    c.legend(fontsize=8.5, loc="upper center", ncol=3, framealpha=0.95)
    c.grid(axis="y", alpha=0.3)
    c.text(0, c8["cpu_media_pct"]["con_otel"] + 4,
           f"{c8['cpu_media_pct']['delta_pct']:+.0f}%", ha="center", fontsize=8.5, color=azul)
    c.text(1, c8["mem_media_mb"]["con_otel"] + 4,
           f"{c8['mem_media_mb']['delta_pct']:+.0f}%", ha="center", fontsize=8.5, color=azul)

    # d) comparacion de los dos niveles de carga
    dd = ax[1][1]
    campos = ["lat_p50_ms", "lat_p99_ms", "rps", "cpu_media_pct", "mem_media_mb"]
    nombres = ["p50", "p99", "rps", "CPU", "memoria"]
    v8 = [c8[k]["delta_pct"] for k in campos]
    v50 = [e50[k]["delta_pct"] for k in campos]
    x3 = range(len(campos))
    dd.bar([i - 0.2 for i in x3], v8, 0.4, label="8 usuarios", color="#4285f4")
    dd.bar([i + 0.2 for i in x3], v50, 0.4, label="50 usuarios", color="#a3358f")
    dd.axhline(0, color="#333", linewidth=0.9)
    dd.set_xticks(list(x3)); dd.set_xticklabels(nombres)
    dd.set_ylabel("cambio frente a la linea base (%)")
    dd.set_title("El costo crece con la concurrencia", fontsize=11)
    dd.set_ylim(min(min(v8), min(v50)) - 12, max(max(v8), max(v50)) + 12)
    dd.legend(fontsize=8.5, loc="lower left"); dd.grid(axis="y", alpha=0.3)
    for i, (a1, a2) in enumerate(zip(v8, v50)):
        dd.text(i - 0.2, a1 + (1.6 if a1 >= 0 else -4.6), f"{a1:+.0f}", ha="center", fontsize=8)
        dd.text(i + 0.2, a2 + (1.6 if a2 >= 0 else -4.6), f"{a2:+.0f}", ha="center", fontsize=8)

    fig.tight_layout(rect=[0, 0.02, 1, 0.96])
    fig.savefig(FIG / "fig4_benchmark.png", dpi=165)
    print("fig4_benchmark.png")


if __name__ == "__main__":
    figura_traza()
    figura_benchmark()
