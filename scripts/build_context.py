"""Contexto de continuidad para el prompt diario: tendencias activas + notas carry-forward.

Sustituye a los dos bloques Python inline de run_daily.ps1, que nunca funcionaron por
problemas de comillas de PowerShell 5.1 (ver specs/validation_engine_v1.1.md, adenda
2026-09-30). NO esta conectado al pipeline: activarlo es un corte de regimen deliberado
que va empaquetado con la migracion v3, con su pre-registro fechado.

Tendencias: se parsean de forma determinista las lineas de las secciones 4/5 de los
informes ("TICKER | Empresa | Sc.:NN | Tendencia: X | Int.: ..." o "T1(NN): X + T2(NN): Y").
Solo se usan informes con fecha ESTRICTAMENTE anterior a --as-of (sin look-ahead).

Notas: AUTO con tope mecanico de --auto-days dias por date_created; MANUAL sin filtrar,
pendientes de triaje humano antes de activar.

Uso en seco:  python scripts/build_context.py --as-of 2026-09-30
"""
import argparse
import json
import re
import sqlite3
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPORTS = ROOT / "reports"
DB = ROOT / "data" / "fa.db"

LINE = re.compile(
    r"(?P<ticker>\b[A-Z][A-Z.]{0,5})(?:\s*/\s*[A-Z.]+)?\s*\|\s*[^|\n]+\|\s*\**Sc\.:\s*(?P<score>\d+)\**"
    r"\s*\|\s*(?P<trends>[^|\n]+?)\s*\|\s*\**Int\.:"
)
MULTI = re.compile(r"T\d+\((?P<score>\d+)\):\s*(?P<name>.+)")


def parse_trend_lines(text):
    """Devuelve [(ticker, score, [(tendencia, score_tendencia), ...])]."""
    out = []
    for m in LINE.finditer(text):
        score = int(m.group("score"))
        part = m.group("trends").strip()
        trends = []
        if part.lower().startswith("tendencia:"):
            trends.append((part.split(":", 1)[1].strip(), score))
        else:
            for chunk in part.split(" + "):
                mm = MULTI.match(chunk.strip())
                if mm:
                    trends.append((mm.group("name").strip(), int(mm.group("score"))))
        if trends:
            out.append((m.group("ticker"), score, trends))
    return out


def report_dates_before(as_of):
    dates = []
    for f in REPORTS.glob("20[0-9][0-9][0-1][0-9][0-3][0-9].md"):
        d = date(int(f.stem[:4]), int(f.stem[4:6]), int(f.stem[6:8]))
        if d < as_of:
            dates.append(d)
    return sorted(dates)


def active_trends(as_of, lookback_reports=3, max_trends=10):
    """Tendencias vistas en los ultimos N informes previos a as_of; la aparicion mas reciente manda."""
    trends = {}
    for d in reversed(report_dates_before(as_of)[-lookback_reports:]):
        text = (REPORTS / f"{d:%Y%m%d}.md").read_text(encoding="utf-8", errors="ignore")
        for ticker, _, tlist in parse_trend_lines(text):
            for name, tscore in tlist:
                t = trends.setdefault(name, {"trend": name, "last_seen": d.isoformat(), "tickers": {}})
                if t["last_seen"] == d.isoformat():
                    t["tickers"].setdefault(ticker, tscore)
    ranked = sorted(
        trends.values(),
        key=lambda t: (t["last_seen"], max(t["tickers"].values())),
        reverse=True,
    )[:max_trends]
    return [
        {"trend": t["trend"], "last_seen": t["last_seen"],
         "tickers": [{"ticker": k, "score": v} for k, v in sorted(t["tickers"].items(), key=lambda kv: -kv[1])]}
        for t in ranked
    ]


def load_notes(as_of, auto_days=14):
    db = sqlite3.connect(DB)
    try:
        auto = db.execute(
            "SELECT ticker, note, date_created FROM review_notes WHERE resolve_trigger='auto' AND resolved=0"
            " AND date_created >= ? AND date_created < ? AND (expires IS NULL OR expires >= ?)"
            " ORDER BY date_created DESC",
            ((as_of - timedelta(days=auto_days)).isoformat(), as_of.isoformat(), as_of.isoformat()),
        ).fetchall()
        manual = db.execute(
            "SELECT ticker, note, date_created FROM review_notes WHERE resolve_trigger='manual' AND resolved=0"
            " AND date_created < ? ORDER BY date_created DESC",
            (as_of.isoformat(),),
        ).fetchall()
    finally:
        db.close()
    return auto, manual


def fmt_notes(rows):
    if not rows:
        return "(ninguna)"
    return "\n".join(f"- [{t or 'general'}] ({d}) {n}" for t, n, d in rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--as-of", type=date.fromisoformat, default=date.today())
    ap.add_argument("--lookback-reports", type=int, default=3)
    ap.add_argument("--max-trends", type=int, default=10)
    ap.add_argument("--auto-days", type=int, default=14)
    ap.add_argument("--trends-out", type=Path, help="escribe el JSON de tendencias (solo tras activar)")
    ap.add_argument("--notes-out", type=Path, help="escribe AUTO/MANUAL como JSON (solo tras activar)")
    args = ap.parse_args()

    trends = active_trends(args.as_of, args.lookback_reports, args.max_trends)
    auto, manual = load_notes(args.as_of, args.auto_days)
    trends_json = json.dumps(trends, ensure_ascii=False)
    notes = {"auto": fmt_notes(auto), "manual": fmt_notes(manual)}

    if args.trends_out:
        args.trends_out.write_text(trends_json, encoding="utf-8")
    if args.notes_out:
        args.notes_out.write_text(json.dumps(notes, ensure_ascii=False), encoding="utf-8")

    # Resumen para el log (el llamador debe tratar 0 tendencias como WARN, no como exito).
    print(f"CONTEXT: as_of={args.as_of} tendencias={len(trends)} ({len(trends_json)} chars) "
          f"notas_auto={len(auto)} ({len(notes['auto'])} chars) notas_manual={len(manual)} ({len(notes['manual'])} chars)")
    if not (args.trends_out or args.notes_out):
        print("\n--- TENDENCIAS_ACTIVAS ---")
        print(json.dumps(trends, ensure_ascii=False, indent=1))
        print("\n--- NOTAS_AUTO ---\n" + notes["auto"])
        print(f"\n--- NOTAS_MANUAL: {len(manual)} pendientes de triaje (no se muestran) ---")
    return 0


if __name__ == "__main__":
    sys.exit(main())
