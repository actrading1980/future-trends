"""
generate_boundary_fragments.py — genera los fragmentos de frontera para la
inspeccion manual (filing_section_validator_v1.md Seccion 5/6): por cada
Item (1 y 1A) de cada filing, contexto anterior + marca de inicio + primeros
200 chars del recorte, y el espejo en el fin -- 4 fragmentos por Item,
8 por filing.
"""
import json
from pathlib import Path
from filing_gates import html_to_clean_text, build_stripped_index, _find_all_stripped

FILINGS_DIR = Path(r"C:\projects\FutureTrends\data\filings")
CONTEXT_LEN = 200

def get_fragments(corpus, item_text, label):
    stripped, index_map = build_stripped_index(corpus)
    def _find_with_retry(text_slice_fn):
        """Reintenta con anclas mas cortas (80->40->20) -- una divergencia de
        caracteres especiales entre el parser de edgartools y el nuestro
        (comillas curvas, guiones no separables) puede invalidar un ancla larga
        sin que la posicion en si sea incorrecta; un ancla mas corta tiene mas
        probabilidad de sobrevivir a esa divergencia puntual."""
        for length in (80, 40, 20):
            anchor = text_slice_fn(length)
            positions = _find_all_stripped(stripped, index_map, anchor)
            if positions:
                return positions, anchor
        return [], None

    start_positions, anchor_start_used = _find_with_retry(lambda n: item_text[:n])
    end_positions_start_of_anchor, anchor_end_used = _find_with_retry(lambda n: item_text[-n:])
    anchor_end = anchor_end_used or item_text[-20:]

    if not start_positions:
        return {"error": f"no se pudo localizar el inicio de {label} en el documento (ni con ancla de 20 chars)"}

    pos_start = start_positions[-1]
    ctx_before_start = corpus[max(0, pos_start - CONTEXT_LEN):pos_start]
    ctx_after_start = corpus[pos_start:pos_start + CONTEXT_LEN]

    if not end_positions_start_of_anchor:
        return {
            "inicio": f"{ctx_before_start} ▮INICIO▮ {ctx_after_start}",
            "fin": "(no localizado)",
        }

    pos_end_anchor_start = end_positions_start_of_anchor[-1]
    pos_end = pos_end_anchor_start + len(anchor_end.replace(" ", ""))  # aproximado, sin-espacios
    # recalcular pos_end real buscando el final del anchor_end en el corpus normal
    end_region = corpus[pos_end_anchor_start:pos_end_anchor_start + CONTEXT_LEN + len(anchor_end)]
    ctx_before_end = corpus[max(0, pos_end_anchor_start - 20):pos_end_anchor_start] + end_region[:len(anchor_end)]
    ctx_after_end = corpus[pos_end_anchor_start + len(anchor_end):pos_end_anchor_start + len(anchor_end) + CONTEXT_LEN]

    return {
        "inicio": f"[...] {ctx_before_start} ▮INICIO▮ {ctx_after_start} [...]",
        "fin": f"[...] {ctx_before_end} ▮FIN▮ {ctx_after_end} [...]",
    }


def main():
    manifest = json.load(open(FILINGS_DIR / "manifest_20260702.json", encoding="utf-8"))
    by_ticker = {f["ticker"]: f for f in manifest["filings"]}

    results = json.load(open(FILINGS_DIR / "gates_test_full_20260703.json", encoding="utf-8"))

    output = {}
    for row in results:
        ticker = row["ticker"]
        f = by_ticker[ticker]
        raw = open(FILINGS_DIR / f["archivo"], "rb").read()
        corpus = html_to_clean_text(raw)

        item1_frag = get_fragments(corpus, row["item1_text"], "item1")
        item1a_frag = get_fragments(corpus, row["item1a_text"], "item1a")

        output[ticker] = {
            "metodo": row["metodo"],
            "item1_len": len(row["item1_text"]),
            "item1a_len": len(row["item1a_text"]),
            "item1": item1_frag,
            "item1a": item1a_frag,
        }
        print(f"=== {ticker} ({row['metodo']}) ===")
        print(f"Item 1 ({len(row['item1_text'])} chars):")
        print(f"  INICIO: {item1_frag['inicio']}")
        print(f"  FIN:    {item1_frag['fin']}")
        print(f"Item 1A ({len(row['item1a_text'])} chars):")
        print(f"  INICIO: {item1a_frag['inicio']}")
        print(f"  FIN:    {item1a_frag['fin']}")
        print()

    out_path = FILINGS_DIR / "boundary_fragments_20260703.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"GUARDADO: {out_path}")


if __name__ == "__main__":
    main()
