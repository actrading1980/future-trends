"""
download_filings.py — P1.5 Etapa 2, paso 1: descarga el 10-K mas reciente
de las 136 empresas del universo (51 originales + 85 seleccionadas en
data/universe_selection_20260702.json).

Restricciones operativas (heredadas de Etapa 1, ver select_universe.py):
  - User-Agent con contacto real (sin el, 403)
  - Maximo 10 req/s contra EDGAR (sleep conservador)

Persiste:
  - data/filings/{ticker}_{accession}.htm  (documento primario)
  - data/filings/manifest_20260702.json    (accession, tamaño, errores)
"""
import json
import re
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

PROJECT_DIR   = Path(r"C:\projects\FutureTrends")
COMPANIES     = PROJECT_DIR / "data" / "companies.json"
SELECTION     = PROJECT_DIR / "data" / "universe_selection_20260702.json"
FILINGS_DIR   = PROJECT_DIR / "data" / "filings"
MANIFEST      = FILINGS_DIR / "manifest_20260702.json"
SEC_USER_AGENT = "FutureTrends Research contact@futuretrends.local"

def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)

def sec_get(url):
    req = urllib.request.Request(url, headers={"User-Agent": SEC_USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()

def sec_get_json(url):
    return json.loads(sec_get(url).decode("utf-8"))

def full_universe():
    companies = load_json(COMPANIES)["companies"]
    existing = [{"ticker": c["ticker"], "cik": c["cik"].lstrip("0") or "0"} for c in companies]
    selection = load_json(SELECTION)["seleccionados"]
    nuevos = [{"ticker": c["ticker"], "cik": str(c["cik"])} for c in selection]
    return existing + nuevos

def latest_10k(cik):
    """Devuelve (accession, primary_doc, filing_date) del 10-K mas reciente, o None."""
    cik10 = str(cik).zfill(10)
    try:
        data = sec_get_json(f"https://data.sec.gov/submissions/CIK{cik10}.json")
    except urllib.error.HTTPError as e:
        return None, f"HTTP {e.code} en submissions.json"
    except Exception as e:
        return None, f"error submissions.json: {e}"

    recent = data.get("filings", {}).get("recent", {})
    forms = recent.get("form", [])
    accns = recent.get("accessionNumber", [])
    docs  = recent.get("primaryDocument", [])
    dates = recent.get("filingDate", [])

    for form, accn, doc, fdate in zip(forms, accns, docs, dates):
        if form == "10-K":
            return {"accession": accn, "primary_doc": doc, "filing_date": fdate}, None
    return None, "no se encontro 10-K en filings.recent"

def download_filing(cik, accession, primary_doc):
    accn_nodash = accession.replace("-", "")
    url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accn_nodash}/{primary_doc}"
    try:
        content = sec_get(url)
        return content, None
    except urllib.error.HTTPError as e:
        return None, f"HTTP {e.code} descargando {url}"
    except Exception as e:
        return None, f"error descargando: {e}"

def main():
    FILINGS_DIR.mkdir(parents=True, exist_ok=True)
    universe = full_universe()
    print(f"INFO: {len(universe)} empresas en el universo (esperado 136)")

    manifest = {"fecha": "2026-07-02", "filings": [], "errores": []}
    ok, fail = 0, 0

    for i, c in enumerate(universe):
        ticker, cik = c["ticker"], c["cik"]
        time.sleep(0.12)  # ~8.3 req/s, margen bajo el limite de 10 req/s (2 llamadas por empresa)

        info, err = latest_10k(cik)
        if err:
            manifest["errores"].append({"ticker": ticker, "cik": cik, "etapa": "submissions", "error": err})
            fail += 1
            print(f"  [{i+1}/{len(universe)}] {ticker}: FALLO ({err})")
            continue

        time.sleep(0.12)
        content, err = download_filing(cik, info["accession"], info["primary_doc"])
        if err:
            manifest["errores"].append({"ticker": ticker, "cik": cik, "etapa": "descarga",
                                          "accession": info["accession"], "error": err})
            fail += 1
            print(f"  [{i+1}/{len(universe)}] {ticker}: FALLO descarga ({err})")
            continue

        fname = f"{ticker}_{info['accession']}.htm"
        fpath = FILINGS_DIR / fname
        fpath.write_bytes(content)

        manifest["filings"].append({
            "ticker": ticker,
            "cik": cik,
            "accession": info["accession"],
            "filing_date": info["filing_date"],
            "primary_doc": info["primary_doc"],
            "archivo": fname,
            "bytes": len(content),
        })
        ok += 1
        print(f"  [{i+1}/{len(universe)}] {ticker}: OK ({len(content)/1024:.0f} KB, {info['filing_date']})")

    manifest["ok_n"] = ok
    manifest["fail_n"] = fail
    with open(MANIFEST, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    print(f"\nDESCARGA_COMPLETA: {ok}/{len(universe)} OK, {fail} fallos")
    print(f"Manifest: {MANIFEST}")

if __name__ == "__main__":
    main()
