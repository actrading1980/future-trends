"""
parse_etf_holdings.py — P1.5, Etapa 1: convierte los CSV/XLS completos
descargados manualmente de cada emisor (data/etf_sources source files en
Docs/) al formato raw_holdings_YYYYMMDD.json que select_universe.py consume.

Cada emisor tiene un formato distinto -- un parser dedicado por fuente,
documentado inline. Filtra en origen: posiciones de cash, contra/earnout
instruments, y tickers claramente no-US (formato "XXXX TT" con espacio,
codigo de bolsa Bloomberg) se marcan foreign=true igual que en la version
anterior -- el filtro definitivo de "presenta 10-K" en select_universe.py
es la fuente de verdad, esto es solo para no ensuciar el candidato con
basura obvia (posiciones de cash, instrumentos sin ticker real).
"""
import csv
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

DOCS = Path(r"C:\projects\FutureTrends\data\etf_sources\raw_downloads_20260702")
OUT  = Path(r"C:\projects\FutureTrends\data\etf_sources\raw_holdings_20260702.json")

NS = {"ss": "urn:schemas-microsoft-com:office:spreadsheet"}
FULL_NS = "{urn:schemas-microsoft-com:office:spreadsheet}"

def clean_ticker(t):
    if not t:
        return None
    t = t.strip()
    if t in ("-", "--", ""):
        return None
    if re.search(r"\s", t):  # "2357 TT" estilo Bloomberg -- foreign exchange code
        return None
    if not re.match(r"^[A-Z]{1,6}(\.[A-Z])?$", t):  # descarta earnout codes, CUSIPs colados, etc
        return None
    return t

def parse_smh():
    """VanEck SMH -- CSV separado por ';', header en fila 3, numeros con coma de miles."""
    path = DOCS / "SMH_asof_20260701.csv"
    holdings = []
    with open(path, encoding="utf-8-sig") as f:
        reader = csv.reader(f, delimiter=";")
        rows = list(reader)
    header_idx = next(i for i, r in enumerate(rows) if r and r[0] == "Number")
    for row in rows[header_idx + 1:]:
        if len(row) < 9 or not row[1]:
            continue
        ticker = clean_ticker(row[1])
        if not ticker:
            continue  # excluye -USD CASH-, Other/Cash
        weight_str = row[8].replace("%", "").strip()
        try:
            weight = float(weight_str)
        except ValueError:
            continue
        holdings.append({"ticker": ticker, "weight": weight})
    return holdings

def parse_xbi():
    """State Street XBI -- CSV separado por ';', header en fila 5, decimal con coma (formato europeo)."""
    path = DOCS / "holdings-daily-us-en-xbi.csv"
    holdings = []
    with open(path, encoding="utf-8-sig") as f:
        reader = csv.reader(f, delimiter=";")
        rows = list(reader)
    header_idx = next(i for i, r in enumerate(rows) if r and r[0] == "Name")
    for row in rows[header_idx + 1:]:
        if not any(row):
            continue
        if len(row) < 5 or not row[1]:
            continue
        ticker = clean_ticker(row[1])
        if not ticker:
            continue  # excluye contra/earnout instruments, US DOLLAR, etc
        weight_str = row[4].replace(",", ".").strip()
        try:
            weight = float(weight_str)
        except ValueError:
            continue
        if weight <= 0:
            continue
        holdings.append({"ticker": ticker, "weight": weight})
    return holdings

def parse_qtum():
    """Defiance QTUM -- CSV separado por ';', columnas: %;Name;Ticker;CUSIP;Shares;MarketValue."""
    path = DOCS / "qtum-07-02-2026.csv"
    holdings = []
    non_equity = {"Cash&Other", "CASHTWD", "CASHEUR", "FGXXX"}  # cash, divisas, money market fund
    with open(path, encoding="utf-8-sig") as f:
        reader = csv.reader(f, delimiter=";")
        rows = list(reader)
    header_idx = next(i for i, r in enumerate(rows) if r and "% of Net Assets" in r[0])
    for row in rows[header_idx + 1:]:
        if len(row) < 3 or not row[0]:
            continue
        raw_ticker = row[2].strip()
        if raw_ticker in non_equity:
            continue
        ticker = clean_ticker(raw_ticker)
        if not ticker:
            continue  # foreign exchange codes tipo "2357 TT", basura
        weight_str = row[0].replace("%", "").strip()
        try:
            weight = float(weight_str)
        except ValueError:
            continue
        holdings.append({"ticker": ticker, "weight": weight})
    return holdings

def parse_tan():
    """Invesco TAN -- CSV separado por ',', comillas, header: Ticker,Company,Share/Par,% TNA,Class of shares,CUSIP,Coupon/Div yield,Market value."""
    path = DOCS / "invesco_solar_etf-Complete_Holdings.csv"
    holdings = []
    with open(path, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            raw_ticker = (row.get("Ticker") or "").strip()
            ticker = clean_ticker(raw_ticker)
            if not ticker:
                continue  # excluye tickers extranjeros tipo "3800" (HK), instrumentos sin ticker
            klass = (row.get("Class of shares") or "").strip()
            if klass and klass != "Common Stock":
                continue  # excluye cash/otros instrumentos no-equity
            weight_str = (row.get("% TNA") or "").replace("%", "").strip()
            try:
                weight = float(weight_str)
            except ValueError:
                continue
            holdings.append({"ticker": ticker, "weight": weight})
    return holdings

def sanitize_xml_ampersands(text):
    """Escapa '&' sueltos que no forman parte de una entidad valida.

    Los exports de BlackRock incluyen hrefs de disclaimer con '&' sin escapar
    (ej. '?style=All&view=quarterlyPerfNav'), lo que rompe el XML (visto en
    SOXX, 2026-07-02). IGV/ICLN no tenian el problema por suerte de contenido,
    no porque el export sea consistente -- se sanea siempre, no solo cuando falla.
    """
    return re.sub(r"&(?!(?:amp|lt|gt|quot|apos|#\d+|#x[0-9a-fA-F]+);)", "&amp;", text)

def parse_blackrock_xml(filename):
    """iShares (IGV, ICLN, SOXX) -- SpreadsheetML XML, hoja 'Holdings', columnas Ticker/Weight (%)/Exchange/Currency."""
    path = DOCS / filename
    raw = path.read_text(encoding="utf-8")
    tree = ET.ElementTree(ET.fromstring(sanitize_xml_ampersands(raw)))
    root = tree.getroot()
    ws_list = root.findall(".//ss:Worksheet", NS)
    holdings_ws = next(w for w in ws_list if w.get(f"{FULL_NS}Name") == "Holdings")
    table = holdings_ws.find(".//ss:Table", NS)
    rows = table.findall("ss:Row", NS)

    def row_values(r):
        return [
            (c.find("ss:Data", NS).text if c.find("ss:Data", NS) is not None else None)
            for c in r.findall("ss:Cell", NS)
        ]

    header_idx = next(i for i, r in enumerate(rows) if row_values(r) and row_values(r)[0] == "Ticker")
    header = row_values(rows[header_idx])
    idx_ticker  = header.index("Ticker")
    idx_weight  = header.index("Weight (%)")
    idx_currency = header.index("Currency") if "Currency" in header else None

    holdings = []
    for r in rows[header_idx + 1:]:
        vals = row_values(r)
        if not vals or not vals[idx_ticker]:
            continue
        raw_ticker = vals[idx_ticker].strip()
        currency = vals[idx_currency] if idx_currency is not None and idx_currency < len(vals) else None
        ticker = clean_ticker(raw_ticker)
        foreign = ticker is None or (currency is not None and currency != "USD")
        if foreign:
            continue  # mismo criterio que la version anterior: excluir foreign en origen
        try:
            weight = float(vals[idx_weight])
        except (ValueError, TypeError, IndexError):
            continue
        holdings.append({"ticker": ticker, "weight": weight})
    return holdings

def main():
    etfs = {
        "SMH": {"name": "VanEck Semiconductor ETF", "categoria": "Advanced Semiconductors",
                "fuente": "https://www.vaneck.com/us/en/investments/semiconductor-etf-smh/downloads/holdings/",
                "holdings": parse_smh()},
        "IGV": {"name": "iShares Expanded Tech-Software Sector ETF", "categoria": "AI/ML y Software/Cloud",
                "fuente": "https://www.ishares.com/us/products/239771/ishares-north-american-techsoftware-etf",
                "holdings": parse_blackrock_xml("iShares-Expanded-Tech-Software-Sector-ETF_fund.xls")},
        "XBI": {"name": "SPDR S&P Biotech ETF", "categoria": "Gene Editing / Biotech",
                "fuente": "https://www.ssga.com/us/en/intermediary/etfs/state-street-spdr-sp-biotech-etf-xbi",
                "holdings": parse_xbi()},
        "ICLN": {"name": "iShares Global Clean Energy ETF", "categoria": "Clean Energy",
                 "fuente": "https://www.ishares.com/us/products/239738/ishares-global-clean-energy-etf",
                 "holdings": parse_blackrock_xml("iShares-Global-Clean-Energy-ETF_fund.xls")},
        "QTUM": {"name": "Defiance Quantum ETF", "categoria": "Quantum Computing",
                 "fuente": "https://www.defianceetfs.com/qtum-full-holdings/",
                 "holdings": parse_qtum()},
        "SOXX": {"name": "iShares Semiconductor ETF", "categoria": "Advanced Semiconductors",
                 "fuente": "https://www.ishares.com/us/products/239705/ishares-phlx-semiconductor-etf",
                 "nota": "Añadido 2026-07-02 (mismo dia, antes de cualquier dato de scoring) para completar el pool de Semiconductores -- SMH solo (26 holdings) dejaba pool=7 tras filtros, insuficiente para su cuota. Ver select_universe.py docstring, NOTA SOBRE PRECEDENTE.",
                 "holdings": parse_blackrock_xml("iShares-Semiconductor-ETF_fund.xls")},
        "TAN": {"name": "Invesco Solar ETF", "categoria": "Clean Energy",
                "fuente": "https://www.invesco.com/us/financial-products/etfs/holdings?audienceType=Institutional&ticker=TAN",
                "nota": "Añadido 2026-07-02 (mismo dia, antes de cualquier dato de scoring) para completar el pool de Clean Energy -- ICLN solo dejaba pool=10 tras filtros.",
                "holdings": parse_tan()},
    }

    for symbol, etf in etfs.items():
        etf["total_holdings_obtenidos"] = len(etf["holdings"])
        print(f"{symbol}: {len(etf['holdings'])} holdings parseados")

    output = {
        "fetch_date": "2026-07-02",
        "source_pattern": "CSV/XLS completo descargado manualmente del sitio del emisor (ver 'fuente' por ETF) -- reemplaza la version truncada de stockanalysis.com (ver data/etf_sources/SUPERSEDED_20260702.md)",
        "etfs": etfs,
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"\nGUARDADO: {OUT}")

if __name__ == "__main__":
    main()
