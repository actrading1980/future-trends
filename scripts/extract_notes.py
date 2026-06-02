"""
extract_notes.py — extrae las notas de seccion 7 del reporte diario,
las clasifica como auto/manual, y las persiste en review_notes.
Se ejecuta via run_daily.ps1 despues de generar el reporte.

Uso: python3 extract_notes.py <report_path> <date_iso>
"""
import sys, re, json, sqlite3, subprocess, os
from pathlib import Path

DB_PATH = r"C:\projects\FutureTrends\data\fa.db"


def extract_section7(text):
    m = re.search(r'##\s*7\..*?\n(.*?)(?=\n##\s|\Z)', text, re.DOTALL | re.IGNORECASE)
    return m.group(1).strip() if m else ""


def classify_notes_via_claude(section7_text, report_date):
    prompt = f"""Eres un asistente de analisis de inversiones. Lee estas notas de revision humana de un informe de hoy ({report_date}) y clasifica cada una.

Para cada nota devuelve un objeto JSON con:
- ticker: el ticker principal al que aplica (o null si es general)
- note: la nota resumida en max 120 caracteres
- resolve_trigger: "auto" si Claude puede resolverla sola buscando noticias en futuros runs (evento temporal, anuncio esperado, catalizador de mercado); "manual" si requiere accion humana o datos externos no disponibles via web (Polygon, Phase 1, decision de sizing)
- expires: fecha ISO "YYYY-MM-DD" si hay un deadline claro (ej. evento en fecha concreta + 2 dias), o null si es open-ended

Devuelve SOLO un array JSON valido, sin texto adicional. Ejemplo:
[
  {{"ticker": "MSFT", "note": "Build 2026 keynote - monitorear Azure AI pricing", "resolve_trigger": "auto", "expires": "2026-06-04"}},
  {{"ticker": "NVDA", "note": "Score 93 - verificar Polygon tecnico antes de sizing", "resolve_trigger": "manual", "expires": null}}
]

NOTAS A CLASIFICAR:
{section7_text}
"""
    tmp = Path(os.environ.get("TEMP", r"C:\Windows\Temp")) / f"fa_notes_prompt_{report_date}.txt"
    tmp.write_text(prompt, encoding="utf-8")
    # Invocar via PowerShell pipe (igual que run_daily.ps1)
    ps_cmd = f'$c = [System.IO.File]::ReadAllText("{tmp}", [System.Text.Encoding]::UTF8); [Console]::OutputEncoding = [System.Text.Encoding]::UTF8; $o = $c | claude --output-format text --dangerously-skip-permissions 2>&1; ($o | ForEach-Object {{ "$_" }}) -join [Environment]::NewLine'
    result = subprocess.run(
        ["powershell.exe", "-NonInteractive", "-Command", ps_cmd],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    tmp.unlink(missing_ok=True)
    return result.stdout.strip()


def parse_json_array(text):
    m = re.search(r'\[.*\]', text, re.DOTALL)
    if not m:
        return []
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return []


def insert_notes(db, notes, date_created):
    inserted = 0
    for n in notes:
        ticker  = n.get("ticker")
        note    = n.get("note", "").strip()
        trigger = n.get("resolve_trigger", "manual")
        expires = n.get("expires")
        if not note:
            continue
        if trigger not in ("auto", "manual"):
            trigger = "manual"
        db.execute(
            "INSERT INTO review_notes (date_created, ticker, note, resolve_trigger, expires) VALUES (?,?,?,?,?)",
            (date_created, ticker, note, trigger, expires),
        )
        inserted += 1
    db.commit()
    return inserted


def main():
    if len(sys.argv) < 3:
        print("Uso: extract_notes.py <report_path> <date_iso>")
        sys.exit(1)

    report_path = sys.argv[1]
    date_iso    = sys.argv[2]

    text = Path(report_path).read_text(encoding="utf-8")
    section7 = extract_section7(text)

    if not section7:
        print("NOTES_SKIP: seccion 7 no encontrada")
        return

    raw = classify_notes_via_claude(section7, date_iso)
    notes = parse_json_array(raw)

    if not notes:
        print(f"NOTES_WARN: Claude no devolvio JSON valido. Raw: {raw[:200]}")
        return

    db = sqlite3.connect(DB_PATH)
    n = insert_notes(db, notes, date_iso)
    db.close()
    print(f"NOTES_SAVED: {n} notas persistidas ({sum(1 for x in notes if x.get('resolve_trigger')=='auto')} auto, {sum(1 for x in notes if x.get('resolve_trigger')=='manual')} manual)")


if __name__ == "__main__":
    main()
