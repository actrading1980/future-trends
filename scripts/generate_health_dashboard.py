"""
Panel de salud del pipeline, local-first: nunca se empuja al repo publico
(ver local_dashboard/ en .gitignore). Lee fa.db + scheduler.log + el marcador
de escritorio y genera un HTML estatico que se abre con doble clic, sin server.
"""
import codecs
import os
import re
import sqlite3
from datetime import date, timedelta

PROJECT_DIR = r"C:\projects\FutureTrends"
DB_PATH = os.path.join(PROJECT_DIR, "data", "fa.db")
LOG_PATH = os.path.join(PROJECT_DIR, "logs", "scheduler.log")
OUT_DIR = os.path.join(PROJECT_DIR, "local_dashboard")
OUT_PATH = os.path.join(OUT_DIR, "health.html")
MARKER_PATH = os.path.join(os.environ.get("USERPROFILE", ""), "Desktop", "PIPELINE_ERROR.txt")
MIN_EXPECTED = 40
LOOKBACK_DAYS = 35

os.makedirs(OUT_DIR, exist_ok=True)

db = sqlite3.connect(DB_PATH)

since = (date.today() - timedelta(days=LOOKBACK_DAYS)).isoformat()
rows = db.execute(
    "SELECT date, day_quality, COUNT(*) FROM tech_scores WHERE date >= ? GROUP BY date, day_quality ORDER BY date DESC",
    (since,),
).fetchall()

by_date = {}
for d, quality, n in rows:
    by_date.setdefault(d, []).append((quality or "scored_normal", n))

max_notes_date = db.execute("SELECT MAX(date_created) FROM review_notes").fetchone()[0]
max_trends_date = None
try:
    max_trends_date = db.execute("SELECT MAX(date) FROM trends").fetchone()[0]
except sqlite3.OperationalError:
    pass

comparative_files = sorted(
    f for f in os.listdir(os.path.join(PROJECT_DIR, "reports"))
    if re.match(r"comparative_\d{8}\.md$", f)
)
last_comparative = comparative_files[-1] if comparative_files else None

log_text = codecs.open(LOG_PATH, encoding="utf-16").read()
log_lines = log_text.splitlines()
last_ok = next((l for l in reversed(log_lines) if "OK: informe guardado" in l), None)

last_header_idx = next(
    (i for i in range(len(log_lines) - 1, -1, -1) if "=== FutureAnalysis daily run" in log_lines[i]),
    None,
)
if last_header_idx is not None:
    last_run_header = log_lines[last_header_idx]
    tail = log_lines[last_header_idx + 1:]
    if any("=== Run completado (degradado)" in l for l in tail):
        last_run_status = "completado, degradado (N bajo el umbral)"
    elif any("=== Run completado" in l for l in tail):
        last_run_status = "completado, sano"
    elif any("ERROR" in l for l in tail):
        last_error_line = next(l for l in tail if "ERROR" in l)
        last_run_status = f"abortado — {last_error_line.split('ERROR:',1)[-1].strip()}"
    else:
        last_run_status = "sin cierre en el log (¿corriendo aun, o el proceso murio sin loguear?)"
else:
    last_run_header = None
    last_run_status = "sin runs registrados"

marker_present = os.path.exists(MARKER_PATH)
marker_content = ""
if marker_present:
    marker_content = codecs.open(MARKER_PATH, encoding="utf-8").read()

def fmt_row(d):
    entries = by_date.get(d, [])
    total = sum(n for _, n in entries)
    qualities = ", ".join(f"{q} ({n})" for q, n in entries) if entries else "—"
    status = "ok" if total >= MIN_EXPECTED else ("hueco" if total == 0 else "bajo")
    return d, total, qualities, status

all_dates = sorted({since[:10]} | set(by_date.keys()), reverse=True)
day_range = [(date.today() - timedelta(days=i)).isoformat() for i in range(LOOKBACK_DAYS)]
table_rows = [fmt_row(d) for d in day_range]

STATUS_COLOR = {"ok": "#3fb950", "bajo": "#d29922", "hueco": "#f85149"}
STATUS_LABEL = {"ok": "OK", "bajo": "cobertura baja", "hueco": "hueco total"}

rows_html = ""
for d, total, qualities, status in table_rows:
    color = STATUS_COLOR[status]
    label = STATUS_LABEL[status]
    rows_html += f"""
    <tr>
      <td>{d}</td>
      <td style="color:{color}; font-weight:600;">{total}</td>
      <td>{qualities}</td>
      <td style="color:{color};">{label}</td>
    </tr>"""

marker_html = (
    f'<div class="alert bad">PIPELINE_ERROR.txt presente en el escritorio:<pre>{marker_content}</pre></div>'
    if marker_present
    else '<div class="alert good">Sin marcador de error en el escritorio.</div>'
)

html = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>FutureTrends — Panel de Salud (local)</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #0f1117; color: #e6edf3; padding: 40px 20px; }}
  #wrap {{ max-width: 900px; margin: 0 auto; }}
  h1 {{ font-size: 1.6em; color: #58a6ff; margin-bottom: 4px; }}
  .sub {{ color: #6e7681; font-size: 0.85em; margin-bottom: 28px; }}
  h2 {{ font-size: 1.1em; color: #79c0ff; margin: 28px 0 10px; }}
  .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; margin-bottom: 8px; }}
  .card {{ background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 14px 16px; }}
  .card .label {{ color: #8b949e; font-size: 0.78em; text-transform: uppercase; letter-spacing: 0.03em; }}
  .card .value {{ color: #f0f6fc; font-size: 0.95em; margin-top: 4px; word-break: break-word; }}
  .alert {{ border-radius: 8px; padding: 12px 16px; margin: 8px 0 20px; font-size: 0.9em; }}
  .alert.good {{ background: #0d2818; border: 1px solid #238636; color: #7ee787; }}
  .alert.bad {{ background: #2d1214; border: 1px solid #da3633; color: #ffa198; }}
  .alert pre {{ white-space: pre-wrap; margin-top: 8px; font-size: 0.85em; color: #ffa198; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 0.88em; }}
  th {{ background: #161b22; color: #79c0ff; padding: 8px 12px; text-align: left; border: 1px solid #30363d; }}
  td {{ padding: 7px 12px; border: 1px solid #30363d; color: #c9d1d9; }}
  tr:nth-child(even) td {{ background: #161b22; }}
  code {{ background: #161b22; border: 1px solid #30363d; padding: 1px 5px; border-radius: 4px; font-size: 0.85em; color: #79c0ff; }}
</style>
</head>
<body>
<div id="wrap">
  <h1>FutureTrends — Panel de Salud</h1>
  <div class="sub">Local, no publicado. Generado {date.today().isoformat()} leyendo <code>fa.db</code> + <code>scheduler.log</code>.</div>

  {marker_html}

  <h2>Último run</h2>
  <div class="grid">
    <div class="card"><div class="label">Última cabecera de log</div><div class="value">{last_run_header or '—'}</div></div>
    <div class="card"><div class="label">Estado del último run</div><div class="value">{last_run_status}</div></div>
    <div class="card"><div class="label">Último "OK: informe guardado"</div><div class="value">{last_ok or '—'}</div></div>
    <div class="card"><div class="label">Notas carry-forward (max date_created)</div><div class="value">{max_notes_date or '—'}</div></div>
    <div class="card"><div class="label">Último comparative_*.md</div><div class="value">{last_comparative or '—'}</div></div>
  </div>

  <h2>Cobertura diaria (últimos {LOOKBACK_DAYS} días, umbral {MIN_EXPECTED})</h2>
  <table>
    <tr><th>Fecha</th><th>N insertado</th><th>day_quality</th><th>Estado</th></tr>
    {rows_html}
  </table>
</div>
</body>
</html>
"""

with open(OUT_PATH, "w", encoding="utf-8") as f:
    f.write(html)

print(f"Panel generado: {OUT_PATH}")
