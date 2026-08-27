"""
Ingesta puntual de reportes escritos por el propio CLI via herramienta Write mientras
el workspace no estaba confiado (2026-06-25->07-03, ver causa raiz en HANDOFF.md): el
wrapper media el stdout corto y aborta, pero el reporte completo ya habia sido guardado
en disco por el modelo. mtime coincide con la hora de la tarea programada (no con una
sesion manual), y el contenido no referencia fechas posteriores a su propia fecha --
misma fuente y momento que un run normal, solo que via una ruta de escritura distinta.
Se marcan day_quality='pipeline_writetool_recovered' para distinguirlos de filas
insertadas por el flujo normal de run_daily.ps1 (paso 8, INSERT via stdout+parser).
NO se genera nada para 2026-06-25/26 (no hay reporte -- ese hueco genuino se queda
como hueco, ver HANDOFF.md Regla 1).
"""
import re, sqlite3
from pathlib import Path

REPORTS_DIR = Path(r"C:\projects\FutureTrends\reports")
DB_PATH = r"C:\projects\FutureTrends\data\fa.db"

TARGETS = ["20260714", "20260717", "20260720", "20260721", "20260723"]

db = sqlite3.connect(DB_PATH)
valid = {r[0] for r in db.execute("SELECT ticker FROM companies").fetchall()}

total_inserted = 0
for d in TARGETS:
    date_iso = f"{d[0:4]}-{d[4:6]}-{d[6:8]}"
    path = REPORTS_DIR / f"{d}.md"
    if not path.exists():
        print(f"SKIP {date_iso}: no existe {path.name}")
        continue
    text = path.read_text(encoding="utf-8")
    m = re.search(r"SCORES_CSV_START\s*\n(.*?)SCORES_CSV_END", text, re.DOTALL)
    if not m:
        print(f"SKIP {date_iso}: sin bloque SCORES_CSV")
        continue

    existing = db.execute("SELECT COUNT(*) FROM tech_scores WHERE date=?", (date_iso,)).fetchone()[0]
    if existing:
        print(f"SKIP {date_iso}: ya hay {existing} filas para esta fecha")
        continue

    inserted = 0
    for line in m.group(1).strip().splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 3:
            continue
        ticker, score, scenario = parts[0], parts[1], parts[2]
        intensity = int(parts[3]) if len(parts) > 3 else 0
        if ticker not in valid:
            continue
        try:
            score = int(score)
        except ValueError:
            continue
        if score < 0 or score > 100:
            continue
        if scenario not in ("BULLISH", "STRONG_BULLISH", "NEUTRAL", "BEARISH"):
            scenario = "BULLISH" if score >= 70 else ("BEARISH" if score < 30 else "NEUTRAL")
        db.execute(
            """INSERT OR REPLACE INTO tech_scores
               (ticker, score, trend_name, intensity, scenario, conflicto, date,
                prompt_version, universe_version, day_quality)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (ticker, score, "daily_run", intensity, scenario, 0, date_iso,
             "v2", 1, "pipeline_writetool_recovered"),
        )
        inserted += 1

    print(f"OK {date_iso}: {inserted} registros insertados (day_quality=pipeline_writetool_recovered)")
    total_inserted += inserted

db.commit()
db.close()
print(f"TOTAL: {total_inserted} registros")
