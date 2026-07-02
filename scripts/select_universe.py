"""
select_universe.py — P1.5, Etapa 1, pieza 1: seleccion mecanica de candidatos
para ampliar el universo de 51 a ~150 empresas.

Regla pre-registrada (spec maestro FutureTrendsAnalysis_v3_reviewed.md, Seccion 5.4 / 9):
  1. Candidatos = holdings de un conjunto fijo de ETFs sectoriales, a fecha fija,
     con fuente citada (data/etf_sources/raw_holdings_YYYYMMDD.json).
  2. Filtro: capitalizacion >= CAP_FLOOR_USD, volumen medio >= VOLUME_FLOOR,
     y la empresa debe presentar 10-K ante la SEC (excluye foreign private
     issuers que presentan 20-F, sin necesidad de un filtro geografico aparte).
  3. Dedup contra las 51 empresas existentes.
  4. Categoria asignada = categoria del ETF de origen (contrastable en Etapa 3
     contra la categoria que asigne el extractor LLM desde el 10-K -- discrepancia
     entre ambas fuentes va a cola de revision manual, no se resuelve aqui).

No escribe companies.json. Output: data/universe_selection_YYYYMMDD.json,
auditable y con timestamp -- es el artefacto de pre-registro.
"""
import json
import sys
import time
import urllib.request
from datetime import date
from pathlib import Path

PROJECT_DIR   = Path(r"C:\projects\FutureTrends")
RAW_HOLDINGS  = PROJECT_DIR / "data" / "etf_sources" / "raw_holdings_20260702.json"
COMPANIES     = PROJECT_DIR / "data" / "companies.json"
OUT_DIR       = PROJECT_DIR / "data"

CAP_FLOOR_USD    = 2_000_000_000
VOLUME_FLOOR_SHR = 200_000  # volumen medio diario minimo, evita micro-caps ilíquidas en yfinance
SEC_USER_AGENT   = "FutureTrends Research contact@futuretrends.local"

def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)

def sec_get(url):
    req = urllib.request.Request(url, headers={"User-Agent": SEC_USER_AGENT})
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))

def load_sec_ticker_map():
    data = sec_get("https://www.sec.gov/files/company_tickers.json")
    return {row["ticker"]: row["cik_str"] for row in data.values()}

def files_10k(cik, ticker_map_cache={}):
    """True si el ultimo filing tipo 10-K existe en submissions.json (no 20-F/40-F)."""
    cik10 = str(cik).zfill(10)
    url = f"https://data.sec.gov/submissions/CIK{cik10}.json"
    try:
        data = sec_get(url)
    except Exception:
        return False, None
    forms = data.get("filings", {}).get("recent", {}).get("form", [])
    dates = data.get("filings", {}).get("recent", {}).get("filingDate", [])
    for form, fdate in zip(forms, dates):
        if form == "10-K":
            return True, fdate
    return False, None

def market_cap_and_volume(ticker):
    try:
        import yfinance as yf
        t = yf.Ticker(ticker)
        info = t.fast_info  # claves camelCase: marketCap, threeMonthAverageVolume (verificado 2026-07-02)
        cap = info.get("marketCap") or 0
        vol = info.get("threeMonthAverageVolume") or 0
        return cap, vol
    except Exception:
        return 0, 0

def main():
    today = sys.argv[1] if len(sys.argv) > 1 else date.today().isoformat()

    raw = load_json(RAW_HOLDINGS)
    existing = {c["ticker"] for c in load_json(COMPANIES)["companies"]}

    print("INFO: cargando mapeo ticker->CIK de SEC EDGAR...")
    ticker_cik = load_sec_ticker_map()

    candidates = {}  # ticker -> {categorias: set, peso_max: float, fuentes: [etf,...]}
    for etf_symbol, etf in raw["etfs"].items():
        categoria = etf["categoria"]
        for h in etf["holdings"]:
            ticker = h["ticker"]
            if h.get("foreign"):
                continue  # excluidos ya en origen -- ticker no US-listable de forma fiable
            if ticker in existing:
                continue
            if ticker not in candidates:
                candidates[ticker] = {"categorias": set(), "peso_max": 0.0, "fuentes": []}
            candidates[ticker]["categorias"].add(categoria)
            candidates[ticker]["peso_max"] = max(candidates[ticker]["peso_max"], h["weight"])
            candidates[ticker]["fuentes"].append(etf_symbol)

    print(f"INFO: {len(candidates)} candidatos unicos tras dedup contra 51 existentes y contra si mismos")

    accepted, rejected = [], []
    for i, (ticker, meta) in enumerate(sorted(candidates.items())):
        cik = ticker_cik.get(ticker)
        if not cik:
            rejected.append({"ticker": ticker, "razon": "sin CIK en SEC EDGAR (no reporta a SEC bajo ese ticker)"})
            continue

        time.sleep(0.15)  # EDGAR: max 10 req/s, margen conservador
        has_10k, last_10k_date = files_10k(cik)
        if not has_10k:
            rejected.append({"ticker": ticker, "razon": "no presenta 10-K (foreign private issuer u otro tipo de filer)"})
            continue

        cap, vol = market_cap_and_volume(ticker)
        if cap < CAP_FLOOR_USD:
            rejected.append({"ticker": ticker, "razon": f"cap {cap/1e9:.2f}B < floor {CAP_FLOOR_USD/1e9:.0f}B"})
            continue
        if vol < VOLUME_FLOOR_SHR:
            rejected.append({"ticker": ticker, "razon": f"volumen medio {vol:.0f} < floor {VOLUME_FLOOR_SHR}"})
            continue

        accepted.append({
            "ticker": ticker,
            "cik": cik,
            "categorias_etf": sorted(meta["categorias"]),
            "peso_max_etf": meta["peso_max"],
            "fuentes_etf": sorted(set(meta["fuentes"])),
            "market_cap_usd": cap,
            "volumen_medio": vol,
            "ultimo_10k": last_10k_date,
        })
        print(f"  [{i+1}/{len(candidates)}] {ticker}: ACEPTADO (cap={cap/1e9:.1f}B, 10-K={last_10k_date})")

    output = {
        "fecha_seleccion": today,
        "regla": "ETFs sectoriales fijos a fecha 2026-07-02 (data/etf_sources/raw_holdings_20260702.json) + filtro cap>=2B + volumen>=200k + presenta 10-K ante SEC",
        "universo_existente_n": len(existing),
        "candidatos_evaluados": len(candidates),
        "aceptados_n": len(accepted),
        "rechazados_n": len(rejected),
        "aceptados": accepted,
        "rechazados": rejected,
    }

    out_path = OUT_DIR / f"universe_selection_{today.replace('-','')}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"\nSELECTION_SAVED: {out_path.name} — {len(accepted)} aceptados, {len(rejected)} rechazados de {len(candidates)} candidatos")
    print(f"Universo resultante: {len(existing)} existentes + {len(accepted)} nuevos = {len(existing) + len(accepted)}")

if __name__ == "__main__":
    main()
