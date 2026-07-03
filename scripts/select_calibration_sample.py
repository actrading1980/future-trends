"""
select_calibration_sample.py — P1.5 Etapa 2, paso 1 (continuacion): calcula
percentiles de tamaño sobre los filings descargados y selecciona la muestra
de 10 segun la regla de filing_section_validator_v1.md Seccion 5.1.
"""
import json
from pathlib import Path

MANIFEST = Path(r"C:\projects\FutureTrends\data\filings\manifest_20260702.json")

PERCENTILES = [5, 15, 25, 40, 55, 70, 80, 90, 95]

def percentile(sorted_vals, p):
    k = (len(sorted_vals) - 1) * (p / 100)
    f = int(k)
    c = min(f + 1, len(sorted_vals) - 1)
    if f == c:
        return sorted_vals[f]
    return sorted_vals[f] + (sorted_vals[c] - sorted_vals[f]) * (k - f)

def main():
    manifest = json.load(open(MANIFEST, encoding="utf-8"))
    filings = manifest["filings"]
    filings_sorted = sorted(filings, key=lambda f: f["bytes"])
    sizes = [f["bytes"] for f in filings_sorted]

    print(f"N filings: {len(filings_sorted)}")
    print(f"min: {sizes[0]/1024:.0f} KB | mediana: {percentile(sizes,50)/1024:.0f} KB | max: {sizes[-1]/1024:.0f} KB")
    print()

    seleccionados = []
    seen_tickers = set()

    for p in PERCENTILES:
        target = percentile(sizes, p)
        closest = min(filings_sorted, key=lambda f: abs(f["bytes"] - target))
        if closest["ticker"] not in seen_tickers:
            seleccionados.append({**closest, "percentil": p})
            seen_tickers.add(closest["ticker"])

    mayor = filings_sorted[-1]
    if mayor["ticker"] not in seen_tickers:
        seleccionados.append({**mayor, "percentil": "max_absoluto"})
        seen_tickers.add(mayor["ticker"])

    print("=== Muestra de calibracion ===")
    for s in seleccionados:
        print(f"  p{s['percentil']}: {s['ticker']} — {s['bytes']/1024:.0f} KB ({s['archivo']})")

    out = {
        "fecha": "2026-07-02",
        "regla": "percentiles p5,p15,p25,p40,p55,p70,p80,p90,p95 de tamaño en bytes + mayor absoluto (filing_section_validator_v1.md Seccion 5.1)",
        "distribucion": {"min_kb": sizes[0]/1024, "mediana_kb": percentile(sizes,50)/1024, "max_kb": sizes[-1]/1024, "n": len(sizes)},
        "muestra": seleccionados,
    }
    out_path = Path(r"C:\projects\FutureTrends\data\filings\calibration_sample_20260702.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    print(f"\nGUARDADO: {out_path}")

if __name__ == "__main__":
    main()
