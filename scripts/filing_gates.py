"""
filing_gates.py — P1.5 Etapa 2, paso 3: implementacion de los 6 gates
(filing_section_validator_v1.md) + fallback de regex para cuando edgartools
falla o tiene confidence baja.

Uso: python filing_gates.py <ticker>  -- procesa un filing y muestra el
resultado de cada gate. Sin argumento, procesa toda la muestra de calibracion
(10 mecanicos + BBIO).
"""
import json
import re
import sys
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path

from edgar import Company, set_identity
from bs4 import BeautifulSoup

set_identity("FutureTrends Research contact@futuretrends.local")

FILINGS_DIR = Path(r"C:\projects\FutureTrends\data\filings")
MANIFEST = FILINGS_DIR / "manifest_20260702.json"
COMPANIES = Path(r"C:\projects\FutureTrends\data\companies.json")
SELECTION = Path(r"C:\projects\FutureTrends\data\universe_selection_20260702.json")

# --- Bandas de Gate 2 -- CONGELADAS 2026-07-03 tras inspeccion humana 11/11 confirmada ---
# (ver commit de congelacion para la referencia completa; especificado inline por gate)
BANDS = {
    # Techo ampliado a 280k tras inspeccion confirmar BBIO (Item 1 = 233,577 chars,
    # ~50 paginas describiendo su portfolio multi-programa) como frontera correcta,
    # no como fallo de extraccion. Evidencia + margen 20%: 233,577 * 1.2 ≈ 280,000.
    "item1":  (10_000, 280_000),
    # Techo ampliado a 400k por la misma razon: BBIO Item 1A = 333,127 chars,
    # confirmado correcto en inspeccion (termina justo antes de "ITEM 1B.
    # UNRESOLVED STAFF COMMENTS"). 333,127 * 1.2 ≈ 400,000.
    "item1a": (20_000, 400_000),
}
RATIO_MAX = 0.80  # techo, ver RATIO_MIN_V12 abajo para el piso vigente
RISK_MARKERS = ["risk", "adversely affect", "could harm", "may not", "material adverse effect"]

# --- HISTORICO, ya no en uso -- Gate 3 v1.1 (vocabulario), reemplazado por el test
# relacional v1.2 (gate3_relational, abajo). Conservado como registro de la
# trayectoria: v1.1 amplio vocabulario para tapar el hueco biotech (CYTK/BBIO,
# 0.06-0.14 -> 2.21-2.84), pero la pasada sobre 130 mostro que el hueco siguiente
# era de REGISTRO GRAMATICAL (tercera persona: IBM, CNH, CWEN, GPRE, QUBT, RGTI),
# no sectorial -- una lista de vocabulario muere por mil ampliaciones. v1.2
# abandona el diccionario para el check de negocio y usa una propiedad relacional
# universal (ver RISK_ASYMMETRY_MIN_RATIO).
_BUSINESS_MARKERS_HISTORICO_V11 = [
    "our business", "our products", "we compete", "our customers", "our operations",
    "our product candidates", "clinical trials", "clinical trial", "our pipeline",
    "fda", "patients", "our technology", "our platform", "regulatory approval",
    "our revenue", "our industry", "our employees", "intellectual property",
]
_MIN_RISK_DENSITY_PER_1000_HISTORICO_V11 = 0.75
_MIN_BIZ_DENSITY_PER_1000_HISTORICO_V11 = 0.4
MIN_HEADER_GAP = 5000  # separacion minima entre Item1/Item1A para no ser TOC (BBIO: TOC~1250 de gap, real~388k)
NAME_MATCH_THRESHOLD = 0.6


def normalize_text(s):
    s = unicodedata.normalize("NFKD", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def html_to_clean_text(html_bytes_or_str):
    """Limpia HTML a texto plano, eliminando ademas los bloques ocultos de
    inline XBRL (ix:header/ix:hidden dentro de divs display:none) -- sin esto,
    los primeros miles de caracteres del corpus son metadata XBRL invisible
    en el filing real, no la portada, contaminando cualquier lectura de
    "primeros N caracteres" (Gate 0 en particular)."""
    if isinstance(html_bytes_or_str, bytes):
        html_bytes_or_str = html_bytes_or_str.decode("utf-8", errors="ignore")
    soup = BeautifulSoup(html_bytes_or_str, "lxml")
    for tag in soup(["script", "style"]):
        tag.decompose()
    # Eliminar bloques ocultos display:none (contienen ix:header/ix:hidden con
    # los hechos XBRL invisibles) y cualquier tag del namespace ix: restante
    for tag in soup.find_all(style=lambda v: v and "display:none" in v.replace(" ", "")):
        tag.decompose()
    for tag in soup.find_all(lambda t: t.name and t.name.startswith("ix:")):
        tag.decompose()
    text = soup.get_text(separator=" ")
    return normalize_text(text)


def full_universe_lookup():
    """Nombre legal esperado por ticker, desde la fuente autoritativa de la SEC
    -- universe_selection_20260702.json no persiste nombre para las 85 nuevas
    (solo ticker/CIK), asi que companies.json/seleccion no son fuente fiable
    para Gate 0."""
    import urllib.request
    req = urllib.request.Request("https://www.sec.gov/files/company_tickers.json",
                                  headers={"User-Agent": "FutureTrends Research contact@futuretrends.local"})
    sec_map = json.loads(urllib.request.urlopen(req).read())
    return {row["ticker"]: row["title"] for row in sec_map.values()}


# --- Gate 0: identidad ---
CORPORATE_SUFFIXES = {
    "inc", "incorporated", "corp", "corporation", "company", "co", "ltd",
    "limited", "holdings", "holding", "plc", "llc", "group", "de", "sa",
    "nv", "ag", "class", "a", "the",
}

def _normalize_name_for_match(name):
    """Minuscula, sin puntuacion, sin sufijos corporativos, sin espacios --
    para comparar contra un corpus que puede tener espacios espurios de
    BeautifulSoup en limites de tags (ver build_stripped_index)."""
    name = name.lower()
    name = re.sub(r"[^\w\s]", " ", name)
    words = [w for w in name.split() if w not in CORPORATE_SUFFIXES]
    return "".join(words)

def gate0_mechanical(cik_expected, accession_downloaded):
    """Check primario y suficiente: el accession number descargado debe estar
    en la lista de filings del CIK esperado segun submissions.json de la SEC.
    No toca contenido del documento -- es la razon por la que es inmune al
    problema que el check de nombre (secundario, abajo) reabre si se usa como
    fallback de documento completo: un 10-K de la empresa equivocada puede
    mencionar el nombre de la empresa correcta docenas de veces como
    competidor (ej. AMD nombra a NVIDIA constantemente en su Item 1)."""
    import urllib.request
    cik10 = str(cik_expected).zfill(10)
    req = urllib.request.Request(f"https://data.sec.gov/submissions/CIK{cik10}.json",
                                  headers={"User-Agent": "FutureTrends Research contact@futuretrends.local"})
    try:
        data = json.loads(urllib.request.urlopen(req, timeout=30).read())
    except Exception as e:
        return {"pass": None, "detalle": f"no se pudo verificar contra submissions.json: {e}"}
    accessions = data.get("filings", {}).get("recent", {}).get("accessionNumber", [])
    match = accession_downloaded in accessions
    return {"pass": match, "cik_esperado": cik_expected, "accession": accession_downloaded}


def gate0_identity(ticker, expected_name, cover_text, cik_expected=None, accession=None):
    """Gate 0 = mecanico (CIK/accession vs submissions.json) como check primario
    y suficiente. El match de nombre en portada es secundario e informativo --
    NUNCA aprueba por si solo si el check mecanico no esta disponible o falla,
    y esta restringido a la portada (no al documento completo: un documento de
    otra empresa puede mencionar el nombre correcto como competidor)."""
    mech = None
    if cik_expected is not None and accession is not None:
        mech = gate0_mechanical(cik_expected, accession)

    name_key = _normalize_name_for_match(expected_name) if expected_name else None
    cover_match = None
    if name_key:
        cover_stripped, _ = build_stripped_index(cover_text[:3000])
        cover_match = name_key in cover_stripped

    if mech is not None and mech["pass"] is not None:
        # el check mecanico decide; el de portada queda como nota informativa
        return {"pass": mech["pass"], "metodo": "mecanico_cik_accession",
                "detalle_mecanico": mech, "match_portada_informativo": cover_match}

    # sin verificacion mecanica disponible: el match de portada es el unico dato,
    # pero se marca como no concluyente, no como aprobado
    if cover_match is None:
        return {"pass": None, "detalle": "sin nombre esperado ni verificacion mecanica -- omitido"}
    return {"pass": cover_match, "metodo": "portada_sin_verificacion_mecanica",
            "nombre_normalizado": name_key, "esperado": expected_name,
            "advertencia": "check mecanico no disponible -- este resultado es menos fiable"}


# --- Fallback de regex: localizar headers reales de Item 1/1A, descartando pares tipo TOC ---
# Patrones sobre el corpus SIN espacios (ver build_stripped_index) -- evita que un
# espacio espurio de BeautifulSoup en el limite de un tag (ej. "R ISK" en vez de
# "RISK") rompa el match, sin necesidad de \s* tolerante a dedazos en el patron.
# separador entre numero de item y titulo: punto, dos puntos, guion ASCII, guion
# largo (em-dash U+2014) o corto (en-dash U+2013), o nada.
# (AMAT usa "Item 1: Business" con dos puntos -- hallazgo 2026-07-03. BE usa
# "ITEM 1—BUSINESS" con em-dash -- hallazgo 2026-07-03, el patron original
# solo aceptaba guion ASCII y fallaba silenciosamente. build_stripped_index
# solo elimina whitespace, no dashes Unicode, asi que sobreviven literales en
# el texto stripped y deben cubrirse explicitamente en el patron.)
HEADER_RE_STRIPPED = {
    "item1":  re.compile(r"item1[.:\-—–]?business"),
    "item1a": re.compile(r"item1a[.:\-—–]?riskfactors"),
}

def regex_fallback_extract(corpus):
    stripped, index_map = build_stripped_index(corpus)
    pos1_all = [index_map[m.start()] for m in HEADER_RE_STRIPPED["item1"].finditer(stripped)]
    pos1a_all = [index_map[m.start()] for m in HEADER_RE_STRIPPED["item1a"].finditer(stripped)]

    if not pos1_all or not pos1a_all:
        return None, "no se encontraron headers de Item 1 o Item 1A"

    # buscar el par (p1, p1a) con p1 < p1a, gap >= MIN_HEADER_GAP, prefiriendo el ultimo par valido
    best_pair = None
    for p1 in pos1_all:
        for p1a in pos1a_all:
            if p1a > p1 and (p1a - p1) >= MIN_HEADER_GAP:
                if best_pair is None or p1 > best_pair[0]:
                    best_pair = (p1, p1a)

    if best_pair is None:
        return None, f"ningun par Item1/Item1A con gap >= {MIN_HEADER_GAP} (posible TOC-only, ver posiciones: item1={pos1_all}, item1a={pos1a_all})"

    p1, p1a = best_pair
    # fin de Item1A: buscar el siguiente header plausible (Item 1B o Item 2) tras p1a,
    # tambien sobre el corpus sin espacios por la misma razon que arriba
    end_re_stripped = re.compile(r"item1b[.:\-—–]?unresolved|item2[.:\-—–]?propert")
    end_matches = [index_map[m.start()] for m in end_re_stripped.finditer(stripped) if index_map[m.start()] > p1a]
    end = min(end_matches) if end_matches else min(p1a + BANDS["item1a"][1], len(corpus))

    item1_text = corpus[p1:p1a]
    item1a_text = corpus[p1a:end]
    return {
        "item1_text": item1_text, "item1a_text": item1a_text,
        "item1_start": p1, "item1_end": p1a,
        "item1a_start": p1a, "item1a_end": end,
    }, None


# --- Gate 1: orden estructural via localizacion de anclas en el documento normalizado ---
def _find_all(corpus, needle):
    if not needle:
        return []
    positions, start = [], 0
    while True:
        i = corpus.find(needle, start)
        if i == -1:
            break
        positions.append(i)
        start = i + 1
    return positions


def build_stripped_index(corpus):
    """Version del corpus sin espacios + mapa de vuelta a posiciones reales.

    BeautifulSoup inserta espacios espurios en limites de tags inline (ej.
    un header con la primera letra en <span> separado divide 'RISK' en
    'R ISK') -- comparar ignorando todo whitespace evita que ese ruido de
    parseo rompa la localizacion de anclas."""
    chars, index_map = [], []
    for i, ch in enumerate(corpus):
        if not ch.isspace():
            chars.append(ch.lower())
            index_map.append(i)
    return "".join(chars), index_map


def _find_all_stripped(stripped_corpus, index_map, needle_raw):
    needle_stripped = "".join(c.lower() for c in needle_raw if not c.isspace())
    if not needle_stripped:
        return []
    positions_stripped = _find_all(stripped_corpus, needle_stripped)
    return [index_map[p] for p in positions_stripped]


def end_boundary_locatable(corpus, item_text, retry_lengths=(80, 40, 20)):
    """Verifica que el FINAL del texto extraido sea localizable en el corpus
    propio -- Gate 1 (gate1_order) solo ancla los INICIOS de item1/item1a para
    verificar orden, asi que puede pasar (True) aunque el final del texto de
    edgartools no exista en absoluto en el corpus (hallazgo AMAT, 2026-07-03).
    Sin este check dedicado, un final divergente queda invisible."""
    stripped, index_map = build_stripped_index(corpus)
    for length in retry_lengths:
        anchor = item_text[-length:]
        if _find_all_stripped(stripped, index_map, anchor):
            return True
    return False


def end_verified_structurally(corpus, item1a_text):
    """Distingue un fin de Item1A ENCONTRADO (header real de Item1B/Item2
    localizado poco despues) de un fin ADIVINADO (el fallback recurrio a
    min(p1a+BANDA, len) porque no encontro ningun header siguiente). Solo en
    el segundo caso una longitud fuera de banda es señal de "me comi
    secciones posteriores" -- en el primero, una seccion larga es genuina
    por construccion (v1.2, tras ROIV superar el techo que BBIO acababa de
    fijar: perseguir el maximo es un juego perdido si el fin ya esta
    verificado estructuralmente)."""
    stripped, index_map = build_stripped_index(corpus)
    for length in (80, 40, 20):
        anchor = item1a_text[-length:]
        positions = _find_all_stripped(stripped, index_map, anchor)
        if positions:
            pos_end = positions[-1] + len("".join(c for c in anchor if not c.isspace()))
            window = corpus[pos_end:pos_end + 300]
            window_stripped = "".join(c.lower() for c in window if not c.isspace())
            return bool(re.search(r"item1b|item2", window_stripped))
    return False


def gate1_order(corpus, item1_text, item1a_text):
    stripped, index_map = build_stripped_index(corpus)
    anchor1 = item1_text[:200][:80]
    anchor1a = item1a_text[:200][:80]

    pos1_all = _find_all_stripped(stripped, index_map, anchor1)
    pos1a_all = _find_all_stripped(stripped, index_map, anchor1a)

    if not pos1_all or not pos1a_all:
        return {"pass": False, "detalle": "ancla no localizada en el documento normalizado (posible discrepancia de normalizacion)"}

    pos1 = pos1_all[-1]  # ultimo match, no el primero (regla de la spec)
    candidatos_1a = [p for p in pos1a_all if p > pos1]
    if not candidatos_1a:
        return {"pass": False, "detalle": f"item1a no aparece despues de item1 (pos1={pos1}, pos1a_all={pos1a_all})"}
    pos1a = candidatos_1a[-1]

    return {"pass": True, "pos_item1": pos1, "pos_item1a": pos1a, "gap": pos1a - pos1}


# --- Gate 2: longitud plausible ---
# v1.2 (2026-07-03): el techo superior de item1a es bloqueante SOLO cuando el fin
# no esta verificado estructuralmente (ver end_verified_structurally). ROIV
# (408,983 chars, fin en header real de Item 1B) rompio el techo que BBIO acababa
# de fijar dias antes -- perseguir el maximo observado es un juego perdido; el
# proposito real del techo es cazar "no encontre el limite y me comi secciones
# posteriores", que end_verified_structurally ya detecta directamente.
# El piso se mantiene sin condicionar: un recorte corto sigue siendo la firma
# del TOC independientemente de si el fin se verifico.
def gate2_length(item1_text, item1a_text, end_verified=True):
    l1, l1a = len(item1_text), len(item1a_text)
    ok1_floor = l1 >= BANDS["item1"][0]
    ok1a_floor = l1a >= BANDS["item1a"][0]
    ok1_ceil = (l1 <= BANDS["item1"][1]) or end_verified
    ok1a_ceil = (l1a <= BANDS["item1a"][1]) or end_verified
    ok1 = ok1_floor and ok1_ceil
    ok1a = ok1a_floor and ok1a_ceil
    techo_informativo = end_verified and (l1 > BANDS["item1"][1] or l1a > BANDS["item1a"][1])
    return {"pass": ok1 and ok1a, "item1_len": l1, "item1a_len": l1a,
            "item1_en_banda": ok1, "item1a_en_banda": ok1a,
            "techo_superado_pero_verificado_informativo": techo_informativo}


# --- Gate 3: test relacional de asimetria (v1.2, reemplaza lista de vocabulario) ---
# La pasada sobre 130 mostro que el fallo de la version por vocabulario (v1.1) no
# era sectorial -- era de registro gramatical: filers que escriben en tercera
# persona ("the Company", "IBM's products") en vez de primera ("our business")
# fallaban el check de negocio sin importar el sector (IBM, CNH, CWEN, GPRE, QUBT,
# RGTI no comparten industria, comparten registro). Una lista de vocabulario
# muere por mil ampliaciones -- cada ronda tapa un hueco y abre el siguiente
# (v1.1 tapo biotech, v1.2 tendria que tapar tercera persona, la siguiente ronda
# taparia otra cosa). El proposito declarado del gate (Seccion 3, Gate 3 de la
# spec) es cazar el desplazamiento de seccion -- y eso se detecta con una
# propiedad relacional universal, no con diccionario: un Item 1A real siempre
# tiene densidad de lenguaje de riesgo mucho mayor que un Item 1 real, en
# cualquier sector y cualquier registro gramatical. Si los recortes estan
# desplazados (ej. lo etiquetado "Item 1A" es en realidad Item 1B), la asimetria
# se invierte o colapsa.
# CONGELADO 2026-07-03 tras control negativo sobre 119 filings confirmados limpios:
# separacion perfecta sin solapamiento -- minimo ratio real=1.130 (CSCO), maximo ratio
# cruzado=0.890 (CSCO, exactamente el reciproco: 1/1.13≈0.89). Umbral 1.0 cae en el
# centro del hueco [0.890, 1.130] con ~13% de margen simetrico a cada lado. El primer
# valor (2.0) era una estimacion sin evidencia y producia 8 falsos negativos
# (FSLR, MSTR, ZS, WULF, TE, GILD, CSCO, AMAT) con ratios reales de 1.13-1.88 --
# correctos pero por debajo de un umbral arbitrario.
RISK_ASYMMETRY_MIN_RATIO = 1.0

def _density(text, markers):
    if not text:
        return 0.0
    text_l = text.lower()
    count = sum(text_l.count(m) for m in markers)
    return count / (len(text) / 1000)

def gate3_relational(item1_text, item1a_text):
    risk1 = _density(item1_text, RISK_MARKERS)
    risk1a = _density(item1a_text, RISK_MARKERS)
    ratio = risk1a / max(risk1, 0.01)
    ok = ratio >= RISK_ASYMMETRY_MIN_RATIO
    return {"pass": ok, "risk_density_item1": round(risk1, 3), "risk_density_item1a": round(risk1a, 3),
            "ratio_1a_sobre_1": round(ratio, 2)}

# Alias retrocompatible -- el nombre del gate en el resto del pipeline sigue
# siendo "gate3_marcadores" en el output, pero la logica interna es la relacional
gate3_markers = gate3_relational


# --- Gate 4: ratio sobre el documento ---
# Piso bajado de 0.35 a 0.30 (v1.2): SMCI (ratio 0.343, fronteras confirmadas
# correctas en inspeccion) evidencio que el piso original excluia documentos
# legitimos con masa inusual de contenido post-Item-1A. Techo condicionado a
# verificacion estructural, misma logica que Gate 2 (ver end_verified_structurally).
RATIO_MIN_V12 = 0.30

def gate4_ratio(item1_text, item1a_text, corpus, end_verified=True):
    total = len(item1_text) + len(item1a_text)
    ratio = total / len(corpus) if corpus else 0
    ok_floor = ratio >= RATIO_MIN_V12
    ok_ceil = (ratio <= RATIO_MAX) or end_verified
    return {"pass": ok_floor and ok_ceil, "ratio": round(ratio, 3),
            "techo_superado_pero_verificado_informativo": end_verified and ratio > RATIO_MAX}


# --- Gate 5: casos especiales (enum cerrado) ---
def gate5_special_cases(corpus, item1a_text):
    if "incorporated by reference" in item1a_text.lower()[:500]:
        return "INCORPORADO_POR_REFERENCIA"
    if re.search(r"item\s*1\s*and\s*1a", corpus, re.IGNORECASE):
        return "ITEMS_COMBINADOS"
    return None


def process_filing(ticker, cik, archivo_path, expected_name, accession=None):
    raw = open(archivo_path, "rb").read()
    corpus = html_to_clean_text(raw)

    gate0 = gate0_identity(ticker, expected_name, corpus, cik_expected=cik, accession=accession)

    # Intentar edgartools primero
    edgartools_result = None
    try:
        c = Company(str(int(cik)))
        filing = c.get_filings(form="10-K").latest()
        tenk = filing.obj()
        sec = tenk.sections
        s1, s1a = sec["part_i_item_1"], sec["part_i_item_1a"]
        item1_text = s1.text() if callable(s1.text) else s1.text
        item1a_text = s1a.text() if callable(s1a.text) else s1a.text
        edgartools_result = {"confidence_item1": s1.confidence, "confidence_item1a": s1a.confidence,
                              "warnings": (s1.warnings or []) + (s1a.warnings or [])}
    except Exception as e:
        item1_text, item1a_text = "", ""
        edgartools_result = {"error": str(e)}

    metodo = "edgartools"
    low_confidence = edgartools_result.get("confidence_item1", 1.0) < 0.9 or edgartools_result.get("confidence_item1a", 1.0) < 0.9
    if low_confidence or not item1_text or not item1a_text:
        fallback, err = regex_fallback_extract(corpus)
        if fallback:
            item1_text, item1a_text = fallback["item1_text"], fallback["item1a_text"]
            metodo = "regex_fallback"
        elif not item1_text:
            return {"ticker": ticker, "metodo": "NINGUNO", "error": err, "gate0": gate0}

    g1 = gate1_order(corpus, item1_text, item1a_text)
    cross_check = None

    # Regla operativa (generalizada tras el hallazgo de AMAT, 2026-07-03; ampliada
    # tras el hallazgo de ABNB/INCY/MKSI, pasada completa 2026-07-03): dos clases
    # de divergencia distintas disparan el cross-check, no solo una.
    #   (a) g1["pass"] False -- el propio orden falla. Hallazgo ABNB: edgartools
    #       le asigna a Item 1 (Business) el mismo "Risk Factors Summary" con que
    #       abre Item 1A (bug/ambigüedad de la libreria en filings con resumen de
    #       riesgos antes de Part I, no un problema de mis anclas) -- los inicios
    #       de item1 e item1a resuelven a la MISMA posicion.
    #   (b) end_boundary_locatable(item1a) False -- el final no es localizable
    #       (hallazgo AMAT original), aunque el orden de inicios si pase.
    # Gate 1 solo ancla los inicios para verificar orden; ninguna de las dos
    # clases era detectable mirando unicamente gate1["pass"] o unicamente el
    # final -- hacen falta ambos triggers.
    end_ok = end_boundary_locatable(corpus, item1a_text)
    if metodo == "edgartools" and (not g1.get("pass") or not end_ok):
        fallback, ferr = regex_fallback_extract(corpus)
        if fallback:
            fb_item1a_len = len(fallback["item1a_text"])
            len_ratio = fb_item1a_len / len(item1a_text) if item1a_text else None
            coincide = len_ratio is not None and 0.7 <= len_ratio <= 1.3
            cross_check = {
                "razon": "gate1 fallo sobre texto de edgartools -- cross-check automatico con fallback",
                "resultado": "corroborado" if coincide else "diverge",
                "len_ratio_item1a": round(len_ratio, 3) if len_ratio else None,
                "fallback_item1_len": len(fallback["item1_text"]),
                "fallback_item1a_len": fb_item1a_len,
            }
            if coincide:
                # las fronteras del fallback quedan corroboradas por acuerdo aproximado
                # con edgartools -- se usan porque son localizables por construccion
                item1_text, item1a_text = fallback["item1_text"], fallback["item1a_text"]
                metodo = "edgartools_divergente+fallback_corroborado"
                g1 = gate1_order(corpus, item1_text, item1a_text)
            else:
                metodo = "edgartools_divergente+fallback_no_coincide"
        else:
            cross_check = {"razon": "gate1 fallo, fallback tampoco disponible", "resultado": "sin_fallback", "error": ferr}

    end_verified = end_verified_structurally(corpus, item1a_text)
    g2 = gate2_length(item1_text, item1a_text, end_verified=end_verified)
    g3 = gate3_markers(item1_text, item1a_text)
    g4 = gate4_ratio(item1_text, item1a_text, corpus, end_verified=end_verified)
    g5 = gate5_special_cases(corpus, item1a_text)
    if cross_check and cross_check["resultado"] == "diverge":
        g5 = "CROSS_CHECK_DIVERGENTE"

    return {
        "ticker": ticker, "metodo": metodo, "edgartools_meta": edgartools_result,
        "cross_check": cross_check,
        "gate0_identidad": gate0, "gate1_orden": g1, "gate2_longitud": g2,
        "gate3_marcadores": g3, "gate4_ratio": g4, "gate5_caso_especial": g5,
        "item1_text": item1_text, "item1a_text": item1a_text,
    }


def main():
    manifest = json.load(open(MANIFEST, encoding="utf-8"))
    by_ticker = {f["ticker"]: f for f in manifest["filings"]}
    names = full_universe_lookup()

    sample = json.load(open(FILINGS_DIR / "calibration_sample_20260702.json", encoding="utf-8"))["muestra"]
    tickers = [s["ticker"] for s in sample] + ["BBIO"]

    if len(sys.argv) > 1:
        tickers = [sys.argv[1]]

    results = []
    for ticker in tickers:
        f = by_ticker[ticker]
        path = FILINGS_DIR / f["archivo"]
        result = process_filing(ticker, f["cik"], path, names.get(ticker), accession=f["accession"])
        results.append(result)
        g1ok = result.get("gate1_orden", {}).get("pass")
        g2ok = result.get("gate2_longitud", {}).get("pass")
        g0 = result.get("gate0_identidad", {})
        g0_metodo = g0.get("metodo", "?")
        print(f"{ticker:6s} metodo={result.get('metodo'):15s} gate0={g0.get('pass')}({g0_metodo}) gate1={g1ok} gate2={g2ok} gate3={result.get('gate3_marcadores',{}).get('pass')} gate4={result.get('gate4_ratio',{}).get('pass')} gate5={result.get('gate5_caso_especial')}")

    out_path = FILINGS_DIR / "gates_test_20260703.json"
    # no persistir el texto completo en el json de reporte (solo para el output de fragmentos)
    slim = [{k: v for k, v in r.items() if k not in ("item1_text", "item1a_text")} for r in results]
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(slim, f, indent=2, ensure_ascii=False)
    print(f"\nGUARDADO: {out_path}")

    # guardar version completa (con texto) para el script de fragmentos
    full_path = FILINGS_DIR / "gates_test_full_20260703.json"
    with open(full_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    main()
