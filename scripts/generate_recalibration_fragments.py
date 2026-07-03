"""
generate_recalibration_fragments.py — P1.5 Etapa 2, ronda de recalibracion v1.2:
genera los 8 fragmentos de frontera para los candidatos identificados en la
pasada completa sobre 130 (6 biotech de ratio + 8 de vocabulario + ROIV + SMCI).
"""
import json
from pathlib import Path
from filing_gates import process_filing, full_universe_lookup, html_to_clean_text
from generate_boundary_fragments import get_fragments

FILINGS_DIR = Path(r"C:\projects\FutureTrends\data\filings")

CANDIDATOS = [
    "RXRX", "RVMD", "APGE", "NUVL", "CRSP", "BEAM",  # gate4 ratio (biotech largo)
    "TSLA", "IBM", "CNH", "CWEN", "GPRE", "CSCO", "QUBT", "RGTI",  # gate3 vocabulario
    "ROIV", "SMCI",  # gate2 longitud
]

def main():
    manifest = json.load(open(FILINGS_DIR / "manifest_20260702.json", encoding="utf-8"))
    by_ticker = {f["ticker"]: f for f in manifest["filings"]}
    names = full_universe_lookup()

    output = {}
    for ticker in CANDIDATOS:
        f = by_ticker[ticker]
        path = FILINGS_DIR / f["archivo"]
        r = process_filing(ticker, f["cik"], path, names.get(ticker), accession=f["accession"])

        raw = open(path, "rb").read()
        corpus = html_to_clean_text(raw)
        item1_frag = get_fragments(corpus, r["item1_text"], "item1")
        item1a_frag = get_fragments(corpus, r["item1a_text"], "item1a")

        output[ticker] = {
            "metodo": r["metodo"],
            "item1_len": len(r["item1_text"]),
            "item1a_len": len(r["item1a_text"]),
            "gate3": r.get("gate3_marcadores"),
            "gate4": r.get("gate4_ratio"),
            "item1": item1_frag,
            "item1a": item1a_frag,
        }
        print(f"=== {ticker} ({r['metodo']}) ===")
        print(f"Item 1 ({len(r['item1_text'])} chars) | gate3={r.get('gate3_marcadores')}")
        print(f"  INICIO: {item1_frag['inicio']}")
        print(f"  FIN:    {item1_frag['fin']}")
        print(f"Item 1A ({len(r['item1a_text'])} chars) | gate4={r.get('gate4_ratio')}")
        print(f"  INICIO: {item1a_frag['inicio']}")
        print(f"  FIN:    {item1a_frag['fin']}")
        print()

    out_path = FILINGS_DIR / "recalibration_fragments_20260703.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"GUARDADO: {out_path}")

if __name__ == "__main__":
    main()
