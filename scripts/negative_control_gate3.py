"""
negative_control_gate3.py — control negativo obligatorio antes de congelar v1.2
(condicion del freeze, spec Seccion 5.2 extendida): el test relacional de Gate 3
debe APROBAR los pares reales y RECHAZAR los pares cruzados (item1/item1a
intercambiados) sobre la poblacion de filings ya confirmados limpios. Si los
cruces empiezan a pasar, el gate no discrimina y hay que redisenarlo, no
seguir engordandolo.
"""
import json
from pathlib import Path
from filing_gates import process_filing, full_universe_lookup, gate3_relational

FILINGS_DIR = Path(r"C:\projects\FutureTrends\data\filings")

def main():
    manifest = json.load(open(FILINGS_DIR / "manifest_20260702.json", encoding="utf-8"))
    names = full_universe_lookup()

    prev = json.load(open(FILINGS_DIR / "full_pass_results_20260703.json", encoding="utf-8"))
    limpios = [r["ticker"] for r in prev
               if r.get("gate1_orden", {}).get("pass") and r.get("gate2_longitud", {}).get("pass")
               and r.get("gate5_caso_especial") is None and "error" not in r]

    print(f"Poblacion limpia disponible para control negativo: {len(limpios)}")

    real_pass, real_fail, cruce_pass, cruce_fail = 0, 0, 0, 0
    fails_reales, pasa_cruces = [], []
    ratios_reales, ratios_cruzados = [], []

    for ticker in limpios:
        f = next(x for x in manifest["filings"] if x["ticker"] == ticker)
        r = process_filing(ticker, f["cik"], FILINGS_DIR / f["archivo"], names.get(ticker), accession=f["accession"])
        item1, item1a = r["item1_text"], r["item1a_text"]

        real = gate3_relational(item1, item1a)
        cruzado = gate3_relational(item1a, item1)  # intercambiados
        ratios_reales.append((ticker, real["ratio_1a_sobre_1"]))
        ratios_cruzados.append((ticker, cruzado["ratio_1a_sobre_1"]))

        if real["pass"]:
            real_pass += 1
        else:
            real_fail += 1
            fails_reales.append((ticker, real))

        if cruzado["pass"]:
            cruce_pass += 1
            pasa_cruces.append((ticker, cruzado))
        else:
            cruce_fail += 1

    print(f"\nPares REALES -- deben pasar: {real_pass}/{len(limpios)} pasan ({real_fail} fallan)")
    if fails_reales:
        print("  Reales que fallaron (falsos negativos del gate):")
        for t, g in fails_reales:
            print(f"    {t}: {g}")

    print(f"\nPares CRUZADOS -- deben fallar: {cruce_fail}/{len(limpios)} fallan ({cruce_pass} pasan)")
    if pasa_cruces:
        print("  Cruces que pasaron (el gate NO los detecto -- problema si hay muchos):")
        for t, g in pasa_cruces:
            print(f"    {t}: {g}")

    print(f"\nSEPARACION: reales={real_pass}/{len(limpios)} ({100*real_pass/len(limpios):.1f}%), "
          f"cruces_rechazados={cruce_fail}/{len(limpios)} ({100*cruce_fail/len(limpios):.1f}%)")

    ratios_reales_sorted = sorted(ratios_reales, key=lambda x: x[1])
    ratios_cruzados_sorted = sorted(ratios_cruzados, key=lambda x: -x[1])
    print(f"\nMinimo ratio en pares REALES: {ratios_reales_sorted[0]}")
    print(f"5 reales mas bajos: {ratios_reales_sorted[:5]}")
    print(f"\nMaximo ratio en pares CRUZADOS: {ratios_cruzados_sorted[0]}")
    print(f"5 cruzados mas altos: {ratios_cruzados_sorted[:5]}")
    print(f"\nGAP de separacion: real_min={ratios_reales_sorted[0][1]:.3f} vs cruzado_max={ratios_cruzados_sorted[0][1]:.3f}")

if __name__ == "__main__":
    main()
