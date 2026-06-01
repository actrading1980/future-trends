"""
generate_comparative.py — genera un informe comparativo entre hoy y ayer:
  - Delta de scores por empresa
  - Fuentes nuevas vs repetidas entre reportes
  - Empresas que entraron/salieron de BULLISH/BEARISH
Salida: reports/comparative_YYYYMMDD.md
"""
import sqlite3, re, sys
from datetime import date, timedelta
from pathlib import Path

DB_PATH      = r"C:\projects\FutureTrends\data\fa.db"
REPORTS_DIR  = Path(r"C:\projects\FutureTrends\reports")

def extract_urls(md_text):
    return set(re.findall(r'https?://[^\s\)\]>,\"]+', md_text))

def load_report(report_date: str):
    p = REPORTS_DIR / f"{report_date.replace('-','')}.md"
    if p.exists():
        return p.read_text(encoding="utf-8")
    return ""

def score_delta_table(db, date_today, date_yesterday):
    rows = db.execute("""
        SELECT a.ticker, a.score, b.score, a.score - b.score, a.scenario, a.intensity
        FROM tech_scores a
        JOIN tech_scores b ON a.ticker = b.ticker
        WHERE a.date = ? AND b.date = ?
        ORDER BY (a.score - b.score) DESC
    """, (date_today, date_yesterday)).fetchall()
    return rows

def only_today(db, date_today, date_yesterday):
    return db.execute("""
        SELECT ticker, score, scenario FROM tech_scores
        WHERE date = ? AND ticker NOT IN (
            SELECT ticker FROM tech_scores WHERE date = ?
        )
    """, (date_today, date_yesterday)).fetchall()

def only_yesterday(db, date_today, date_yesterday):
    return db.execute("""
        SELECT ticker, score, scenario FROM tech_scores
        WHERE date = ? AND ticker NOT IN (
            SELECT ticker FROM tech_scores WHERE date = ?
        )
    """, (date_yesterday, date_today)).fetchall()

def scenario_emoji(scenario):
    return {"STRONG_BULLISH": "🟢🟢", "BULLISH": "🟢", "NEUTRAL": "⚪", "BEARISH": "🔴"}.get(scenario, "⚪")

def intensity_str(i):
    if i is None: return "0"
    return f"+{i}" if i > 0 else str(i)

def main():
    date_today     = sys.argv[1] if len(sys.argv) > 1 else date.today().isoformat()
    date_yesterday = (date.fromisoformat(date_today) - timedelta(days=1)).isoformat()

    db = sqlite3.connect(DB_PATH)

    # Buscar la fecha anterior real en la DB (puede no ser ayer calendario)
    prev = db.execute(
        "SELECT MAX(date) FROM tech_scores WHERE date < ?", (date_today,)
    ).fetchone()[0]
    if not prev:
        print(f"COMPARATIVE_SKIP: no hay datos anteriores a {date_today}")
        db.close()
        return

    date_yesterday = prev

    md_today     = load_report(date_today)
    md_yesterday = load_report(date_yesterday)

    urls_today     = extract_urls(md_today)
    urls_yesterday = extract_urls(md_yesterday)
    urls_repeated  = urls_today & urls_yesterday
    urls_new       = urls_today - urls_yesterday

    deltas    = score_delta_table(db, date_today, date_yesterday)
    new_ticks = only_today(db, date_today, date_yesterday)
    gone_ticks= only_yesterday(db, date_today, date_yesterday)
    db.close()

    gainers = [(t, a, b, d, s, i) for t, a, b, d, s, i in deltas if d > 0]
    losers  = [(t, a, b, d, s, i) for t, a, b, d, s, i in deltas if d < 0]
    flat    = [(t, a, b, d, s, i) for t, a, b, d, s, i in deltas if d == 0]

    lines = []
    a = lines.append

    a(f"# Comparativo {date_yesterday} → {date_today}")
    a("")
    a(f"> Empresas comparadas: **{len(deltas)}** | Nuevas en universe: {len(new_ticks)} | Salieron: {len(gone_ticks)}")
    a("")

    # --- Fuentes ---
    a("## Fuentes")
    a("")
    if not urls_today:
        a("_El reporte de hoy no contiene URLs explícitas._")
    else:
        if urls_repeated:
            a(f"### ⚠️ Fuentes repetidas vs ayer ({len(urls_repeated)})")
            a("")
            a("Estas URLs aparecen en ambos reportes — posible contenido reutilizado:")
            a("")
            for u in sorted(urls_repeated):
                a(f"- {u}")
            a("")
        else:
            a("### ✅ Sin solapamiento de fuentes con ayer")
            a("")

        a(f"### Fuentes nuevas hoy ({len(urls_new)})")
        a("")
        for u in sorted(urls_new):
            a(f"- {u}")
        a("")

    # --- Score deltas ---
    a("## Cambios de score")
    a("")
    a("| Ticker | Ayer | Hoy | Δ | Escenario | Int. |")
    a("|--------|------|-----|---|-----------|------|")

    for t, today_s, yest_s, d, s, i in gainers:
        arrow = f"+{d}" if d > 0 else str(d)
        a(f"| **{t}** | {yest_s} | {today_s} | **{arrow}** ↑ | {scenario_emoji(s)} {s} | {intensity_str(i)} |")

    for t, today_s, yest_s, d, s, i in flat:
        a(f"| {t} | {yest_s} | {today_s} | — | {scenario_emoji(s)} {s} | {intensity_str(i)} |")

    for t, today_s, yest_s, d, s, i in losers:
        a(f"| **{t}** | {yest_s} | {today_s} | **{d}** ↓ | {scenario_emoji(s)} {s} | {intensity_str(i)} |")

    a("")

    # --- Movimientos BULLISH/BEARISH ---
    bullish_today = {t for t, a_, b_, d_, s, i in deltas if a_ >= 70}
    bearish_today = {t for t, a_, b_, d_, s, i in deltas if a_ < 30}
    bullish_yest  = {t for t, a_, b_, d_, s, i in deltas if b_ >= 70}
    bearish_yest  = {t for t, a_, b_, d_, s, i in deltas if b_ < 30}

    entered_bull = bullish_today - bullish_yest
    exited_bull  = bullish_yest  - bullish_today
    entered_bear = bearish_today - bearish_yest
    exited_bear  = bearish_yest  - bearish_today

    if any([entered_bull, exited_bull, entered_bear, exited_bear]):
        a("## Cambios de zona BULLISH / BEARISH")
        a("")
        if entered_bull: a(f"- **Entran BULLISH (≥70):** {', '.join(sorted(entered_bull))}")
        if exited_bull:  a(f"- **Salen de BULLISH:** {', '.join(sorted(exited_bull))}")
        if entered_bear: a(f"- **Entran BEARISH (<30):** {', '.join(sorted(entered_bear))}")
        if exited_bear:  a(f"- **Salen de BEARISH:** {', '.join(sorted(exited_bear))}")
        a("")

    # --- Empresas nuevas/desaparecidas ---
    if new_ticks:
        a("## Empresas nuevas en el scoring de hoy")
        a("")
        for t, s, sc in new_ticks:
            a(f"- **{t}** — Score: {s} | {sc}")
        a("")

    if gone_ticks:
        a("## Empresas que desaparecieron del scoring")
        a("")
        for t, s, sc in gone_ticks:
            a(f"- **{t}** — Score ayer: {s} | {sc}")
        a("")

    output = "\n".join(lines)
    out_path = REPORTS_DIR / f"comparative_{date_today.replace('-','')}.md"
    out_path.write_text(output, encoding="utf-8")
    print(f"COMPARATIVE_SAVED: {out_path.name} ({len(deltas)} empresas, {len(urls_repeated)} fuentes repetidas)")

if __name__ == "__main__":
    main()
