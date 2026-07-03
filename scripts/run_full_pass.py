"""
run_full_pass.py — P1.5 Etapa 2, paso 5: pasada completa sobre los 130 10-K
con los gates ya congelados (2026-07-03). Sin ajustes de umbral -- lo que
falla, falla y va a cola con su etiqueta (spec Seccion 6/8).

Reporta: tasa de paso limpio, desglose de cola por etiqueta, cuantos filings
necesitaron fallback/cross-check, y distribucion de longitudes/densidades
observadas contra las bandas congeladas (registro, no recalibracion).
"""
import json
from collections import Counter
from pathlib import Path

from filing_gates import process_filing, full_universe_lookup

FILINGS_DIR = Path(r"C:\projects\FutureTrends\data\filings")
MANIFEST = FILINGS_DIR / "manifest_20260702.json"


def main():
    manifest = json.load(open(MANIFEST, encoding="utf-8"))
    names = full_universe_lookup()

    results = []
    for i, f in enumerate(manifest["filings"]):
        ticker = f["ticker"]
        path = FILINGS_DIR / f["archivo"]
        try:
            r = process_filing(ticker, f["cik"], path, names.get(ticker), accession=f["accession"])
        except Exception as e:
            r = {"ticker": ticker, "metodo": "ERROR", "error": str(e)}
        results.append(r)
        gates_ok = all(
            r.get(g, {}).get("pass") if isinstance(r.get(g), dict) else None
            for g in ("gate0_identidad", "gate1_orden", "gate2_longitud", "gate3_marcadores", "gate4_ratio")
        ) and r.get("gate5_caso_especial") is None
        status = "OK" if gates_ok else ("ERROR" if "error" in r else "COLA")
        print(f"  [{i+1}/{len(manifest['filings'])}] {ticker}: {status} (metodo={r.get('metodo')})")

    # --- Analisis agregado ---
    n = len(results)
    limpio = 0
    cola_por_etiqueta = Counter()
    metodos = Counter()
    item1_lens, item1a_lens, risk_dens, biz_dens, ratios, ratios_asimetria = [], [], [], [], [], []

    for r in results:
        metodos[r.get("metodo", "ERROR")] += 1

        if r.get("metodo") == "ERROR" or "error" in r:
            cola_por_etiqueta["ERROR_PROCESAMIENTO"] += 1
            continue

        gates = ("gate0_identidad", "gate1_orden", "gate2_longitud", "gate3_marcadores", "gate4_ratio")
        gate_results = {g: r.get(g, {}) for g in gates}
        all_pass = all(gr.get("pass") for gr in gate_results.values())
        especial = r.get("gate5_caso_especial")

        if all_pass and especial is None:
            limpio += 1
        elif especial:
            cola_por_etiqueta[especial] += 1
        else:
            fallos = [g for g, gr in gate_results.items() if gr.get("pass") is False]
            cola_por_etiqueta[f"FALLO_{'+'.join(fallos)}" if fallos else "FALLO_INDETERMINADO"] += 1

        g2 = r.get("gate2_longitud", {})
        if "item1_len" in g2:
            item1_lens.append(g2["item1_len"])
            item1a_lens.append(g2["item1a_len"])
        g3 = r.get("gate3_marcadores", {})
        if "ratio_1a_sobre_1" in g3:
            risk_dens.append(g3["risk_density_item1"])
            biz_dens.append(g3["risk_density_item1a"])
            ratios_asimetria.append(g3["ratio_1a_sobre_1"])
        g4 = r.get("gate4_ratio", {})
        if "ratio" in g4:
            ratios.append(g4["ratio"])

    def dist(vals):
        if not vals:
            return None
        s = sorted(vals)
        return {"min": s[0], "p25": s[len(s)//4], "mediana": s[len(s)//2], "p75": s[3*len(s)//4], "max": s[-1]}

    summary = {
        "total": n,
        "limpio_n": limpio,
        "tasa_paso_limpio": round(limpio / n, 4) if n else 0,
        "cola_por_etiqueta": dict(cola_por_etiqueta),
        "metodos": dict(metodos),
        "necesitaron_fallback_o_cross_check": sum(v for k, v in metodos.items() if k != "edgartools"),
        "distribucion_item1_len": dist(item1_lens),
        "distribucion_item1a_len": dist(item1a_lens),
        "distribucion_risk_density_item1": dist(risk_dens),
        "distribucion_risk_density_item1a": dist(biz_dens),
        "distribucion_ratio_asimetria_1a_sobre_1": dist(ratios_asimetria),
        "distribucion_ratio_documento": dist(ratios),
        "bandas_congeladas_v1_2": {"item1": [10_000, 280_000], "item1a": [20_000, 400_000],
                                    "asimetria_riesgo_min": 1.0, "ratio_documento": [0.30, 0.80],
                                    "nota": "techos de item1/item1a y de ratio_documento son informativos (no bloquean) cuando end_verified_structurally=True"},
    }

    out_slim = [{k: v for k, v in r.items() if k not in ("item1_text", "item1a_text")} for r in results]
    with open(FILINGS_DIR / "full_pass_results_20260703.json", "w", encoding="utf-8") as f:
        json.dump(out_slim, f, indent=2, ensure_ascii=False)
    with open(FILINGS_DIR / "full_pass_summary_20260703.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    print("\n=== RESUMEN ===")
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
