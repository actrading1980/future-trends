"""
test_edgartools_sample.py — P1.5 Etapa 2, paso 2: prueba edgartools contra
la muestra de calibracion de 10 filings, reportando lo necesario para decidir
el paso 3 (implementacion de gates): si encuentra Item 1/1A, longitudes, y
si expone offsets absolutos reutilizables o solo texto plano local.
"""
import json
from pathlib import Path
from edgar import Company, set_identity

set_identity("FutureTrends Research contact@futuretrends.local")

SAMPLE = Path(r"C:\projects\FutureTrends\data\filings\calibration_sample_20260702.json")

def main():
    sample = json.load(open(SAMPLE, encoding="utf-8"))["muestra"]

    # BBIO: 11o caso, etiquetado caso_regresion_conocido, fuera del conteo mecanico
    manifest = json.load(open(r"C:\projects\FutureTrends\data\filings\manifest_20260702.json", encoding="utf-8"))
    bbio = next(f for f in manifest["filings"] if f["ticker"] == "BBIO")
    sample = sample + [{"ticker": "BBIO", "percentil": "caso_regresion_conocido",
                         "bytes": bbio["bytes"], "accession": bbio["accession"]}]

    results = []

    for s in sample:
        ticker = s["ticker"]
        cik = s["cik"] if "cik" in s else None
        accession = s["accession"]
        print(f"=== {ticker} (percentil {s['percentil']}, {s['bytes']/1024:.0f} KB) ===")
        try:
            # Buscar CIK desde manifest si no viene en la muestra
            manifest = json.load(open(r"C:\projects\FutureTrends\data\filings\manifest_20260702.json", encoding="utf-8"))
            cik = next(f["cik"] for f in manifest["filings"] if f["ticker"] == ticker)

            company = Company(cik)
            filing = company.get_filings(form="10-K", accession_number=accession).latest()
            if filing is None:
                # fallback: buscar por accession en todas las 10-K recientes
                filing = next((f for f in company.get_filings(form="10-K") if f.accession_no == accession), None)
            tenk = filing.obj()
            sections = tenk.sections

            row = {"ticker": ticker, "percentil": s["percentil"], "bytes": s["bytes"]}

            for key, label in [("part_i_item_1", "item1"), ("part_i_item_1a", "item1a"), ("part_i_item_1b", "item1b")]:
                if key in [k for k in dir(sections)] or True:
                    try:
                        sec = sections[key]
                        txt = sec.text() if callable(sec.text) else sec.text
                        row[f"{label}_encontrado"] = True
                        row[f"{label}_len"] = len(txt)
                        row[f"{label}_confidence"] = sec.confidence
                        row[f"{label}_detection_method"] = sec.detection_method
                        row[f"{label}_validated"] = sec.validated
                        row[f"{label}_warnings"] = sec.warnings
                        row[f"{label}_start_offset"] = sec.start_offset
                        row[f"{label}_end_offset"] = sec.end_offset
                    except KeyError:
                        row[f"{label}_encontrado"] = False

            print(json.dumps(row, indent=2, ensure_ascii=False))
            results.append(row)
        except Exception as e:
            print(f"  ERROR: {e}")
            results.append({"ticker": ticker, "error": str(e)})
        print()

    out_path = Path(r"C:\projects\FutureTrends\data\filings\edgartools_test_20260702.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"GUARDADO: {out_path}")

if __name__ == "__main__":
    main()
