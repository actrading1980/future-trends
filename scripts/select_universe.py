"""
select_universe.py — P1.5, Etapa 1, pieza 1: seleccion mecanica de candidatos
para ampliar el universo de 51 a ~150 empresas.

Regla pre-registrada (spec maestro FutureTrendsAnalysis_v3_reviewed.md, Seccion 5.4 / 9):
  1. Candidatos = holdings de un conjunto fijo de ETFs sectoriales, a fecha fija,
     con fuente citada (data/etf_sources/raw_holdings_YYYYMMDD.json). Fuente
     primaria: CSV completo del emisor descargado manualmente (los sitios de
     los emisores bloquean fetch automatizado -- ver nota en el JSON de origen).
  2. Filtro: dollar ADV (precio x volumen medio) >= DOLLAR_ADV_FLOOR, y la
     empresa debe presentar 10-K ante la SEC (excluye foreign private issuers
     que presentan 20-F, sin necesidad de un filtro geografico aparte).
     NOTA: el floor es en dolares, no en acciones -- un floor en acciones
     penaliza precios altos y deja pasar chicharros de precio bajo.
  3. Dedup contra las 51 empresas existentes.
  4. Recorte a TARGET_TOTAL: cuota fija por categoria = (TARGET_TOTAL - N_existente)
     / N_categorias, redondeada, con el resto repartido a las categorias con
     mas candidatos elegibles (regla determinista, no por volumen de sobrante).
     Dentro de cada categoria, ranking por dollar ADV descendente -- NO por
     cap ni por peso en el ETF, para no reintroducir el sesgo large-cap que
     el dollar-ADV-en-vez-de-cap ya buscaba evitar. Categoria de un candidato
     = la del ETF donde tiene mayor peso (un candidato puede aparecer en
     varios ETFs). Slots no usados por categorias con pocos candidatos se
     redistribuyen a las demas por ranking global de dollar ADV.

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
COMPANIES     = PROJECT_DIR / "data" / "companies.json"
OUT_DIR       = PROJECT_DIR / "data"

DOLLAR_ADV_FLOOR = 15_000_000  # dolares/dia, precio x volumen medio 3M -- suelo unico, no rango
TARGET_TOTAL      = 150
SEC_USER_AGENT    = "FutureTrends Research contact@futuretrends.local"

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

def files_10k(cik):
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

def price_and_volume(ticker):
    try:
        import yfinance as yf
        info = yf.Ticker(ticker).fast_info  # claves camelCase (verificado 2026-07-02)
        price = info.get("lastPrice") or 0
        vol   = info.get("threeMonthAverageVolume") or 0
        return price, vol
    except Exception:
        return 0, 0

def build_candidates(raw, existing):
    """ticker -> {categorias: {cat: peso_max}, fuentes: [etf,...]}"""
    candidates = {}
    for etf_symbol, etf in raw["etfs"].items():
        categoria = etf["categoria"]
        for h in etf["holdings"]:
            ticker = h["ticker"]
            if h.get("foreign") or ticker in existing:
                continue
            c = candidates.setdefault(ticker, {"categorias": {}, "fuentes": []})
            c["categorias"][categoria] = max(c["categorias"].get(categoria, 0.0), h["weight"])
            c["fuentes"].append(etf_symbol)
    return candidates

def primary_category(meta):
    return max(meta["categorias"].items(), key=lambda kv: kv[1])[0]

def apply_filters(candidates, ticker_cik):
    accepted, rejected = [], []
    for i, (ticker, meta) in enumerate(sorted(candidates.items())):
        cik = ticker_cik.get(ticker)
        if not cik:
            rejected.append({"ticker": ticker, "razon": "sin CIK en SEC EDGAR"})
            continue

        time.sleep(0.15)  # EDGAR: max 10 req/s, margen conservador
        has_10k, last_10k_date = files_10k(cik)
        if not has_10k:
            rejected.append({"ticker": ticker, "razon": "no presenta 10-K (foreign private issuer u otro tipo de filer)"})
            continue

        price, vol = price_and_volume(ticker)
        dollar_adv = price * vol
        if dollar_adv < DOLLAR_ADV_FLOOR:
            rejected.append({"ticker": ticker, "razon": f"dollar ADV ${dollar_adv/1e6:.1f}M < floor ${DOLLAR_ADV_FLOOR/1e6:.0f}M"})
            continue

        cat = primary_category(meta)
        accepted.append({
            "ticker": ticker,
            "cik": cik,
            "categoria_primaria": cat,
            "categorias_etf": sorted(meta["categorias"].keys()),
            "fuentes_etf": sorted(set(meta["fuentes"])),
            "dollar_adv": dollar_adv,
            "ultimo_10k": last_10k_date,
        })
        print(f"  [{i+1}/{len(candidates)}] {ticker} ({cat}): PASA FILTROS (ADV=${dollar_adv/1e6:.1f}M, 10-K={last_10k_date})")
    return accepted, rejected

def apply_quota(accepted_all, existing_n, target_total):
    """Cuota fija por categoria + redistribucion determinista del sobrante."""
    by_cat = {}
    for c in accepted_all:
        by_cat.setdefault(c["categoria_primaria"], []).append(c)
    for cat in by_cat:
        by_cat[cat].sort(key=lambda c: c["dollar_adv"], reverse=True)

    categorias = sorted(by_cat.keys())
    n_slots = target_total - existing_n
    base_quota = n_slots // len(categorias)
    remainder = n_slots - base_quota * len(categorias)

    # Remainder va a las categorias con mas candidatos elegibles (orden determinista, desempate alfabetico)
    cats_by_surplus = sorted(categorias, key=lambda c: (-len(by_cat[c]), c))
    quota = {cat: base_quota for cat in categorias}
    for cat in cats_by_surplus[:remainder]:
        quota[cat] += 1

    selected, waitlist = [], []
    for cat in categorias:
        pool = by_cat[cat]
        selected.extend(pool[:quota[cat]])
        waitlist.extend(pool[quota[cat]:])

    unused_slots = sum(max(0, quota[cat] - len(by_cat[cat])) for cat in categorias)
    if unused_slots > 0 and waitlist:
        waitlist.sort(key=lambda c: c["dollar_adv"], reverse=True)
        fill = waitlist[:unused_slots]
        selected.extend(fill)
        for c in fill:
            waitlist.remove(c)

    return selected, waitlist, quota

def main():
    today = sys.argv[1] if len(sys.argv) > 1 else date.today().isoformat()
    raw_path = PROJECT_DIR / "data" / "etf_sources" / f"raw_holdings_{today.replace('-','')}.json"
    if not raw_path.exists():
        print(f"ERROR: {raw_path} no existe. Descargar los CSV completos de los emisores primero.")
        sys.exit(1)

    raw = load_json(raw_path)
    existing = {c["ticker"] for c in load_json(COMPANIES)["companies"]}

    print("INFO: cargando mapeo ticker->CIK de SEC EDGAR...")
    ticker_cik = load_sec_ticker_map()

    candidates = build_candidates(raw, existing)
    print(f"INFO: {len(candidates)} candidatos unicos tras dedup contra {len(existing)} existentes")

    accepted_all, rejected = apply_filters(candidates, ticker_cik)
    selected, waitlist, quota = apply_quota(accepted_all, len(existing), TARGET_TOTAL)

    output = {
        "fecha_seleccion": today,
        "regla": f"ETFs sectoriales a fecha {today} + filtro dollar_ADV>=${DOLLAR_ADV_FLOOR/1e6:.0f}M + presenta 10-K, recorte a {TARGET_TOTAL} total con cuota fija por categoria ranking por dollar ADV",
        "universo_existente_n": len(existing),
        "candidatos_evaluados": len(candidates),
        "pasan_filtros_n": len(accepted_all),
        "rechazados_filtros_n": len(rejected),
        "cuota_por_categoria": quota,
        "seleccionados_n": len(selected),
        "en_waitlist_n": len(waitlist),
        "seleccionados": selected,
        "waitlist": waitlist,
        "rechazados_filtros": rejected,
    }

    out_path = OUT_DIR / f"universe_selection_{today.replace('-','')}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"\nSELECTION_SAVED: {out_path.name}")
    print(f"Candidatos: {len(candidates)} | pasan filtros: {len(accepted_all)} | seleccionados: {len(selected)} | waitlist: {len(waitlist)} | rechazados: {len(rejected)}")
    print(f"Universo resultante: {len(existing)} existentes + {len(selected)} nuevos = {len(existing) + len(selected)}")
    print("Cuota por categoria:", quota)

if __name__ == "__main__":
    main()
