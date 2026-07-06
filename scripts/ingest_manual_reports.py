"""
Ingesta puntual de reportes generados fuera del pipeline automatico (2026-06-29..07-06),
verificados como contemporaneos (mtime ~= hora de ejecucion programada, sin referencias
a fechas posteriores a la propia). Se marcan day_quality='manual_session_verified' para
distinguirlos de filas insertadas por run_daily.ps1. NO se genera nada para 2026-06-25/26
(no hay reporte -- ese hueco genuino se queda como hueco, ver HANDOFF.md Regla 1).
"""
import re, sqlite3
from pathlib import Path

REPORTS_DIR = Path(r"C:\projects\FutureTrends\reports")
DB_PATH = r"C:\projects\FutureTrends\data\fa.db"

TARGETS = ["20260629", "20260630", "20260701", "20260702", "20260703", "20260706"]

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
             "v2", 1, "manual_session_verified"),
        )
        inserted += 1

    print(f"OK {date_iso}: {inserted} registros insertados (day_quality=manual_session_verified)")
    total_inserted += inserted

db.commit()
db.close()
print(f"TOTAL: {total_inserted} registros")
