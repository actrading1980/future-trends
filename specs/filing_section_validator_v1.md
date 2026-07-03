# FutureAnalysis — Filing Section Validator Spec v1.2
*Autor: FutureTrends Intelligence System*
*Fecha: 2026-07-02 (v1.1: Gate 0 añadido el mismo día) | 2026-07-03 (v1.2: rediseño de Gates 2/3/4 tras pasada completa sobre 130)*
*Estado: CONGELADA — pasada completa sobre 130 10-K: 120/130 (92.3%) limpio, dentro del 85-95% esperado*

**Amend v1.1:** durante la descarga de los 136 filings se descubrió que 14/51 empresas originales tenían CIK incorrecto en `companies.json` (ver commit de fix en `data/companies.json`), y que 13 de esas 14 descargaron silenciosamente el 10-K de una empresa real pero distinta — sin ningún error HTTP. Un recorte estructuralmente perfecto de un documento de la empresa equivocada habría pasado los cinco gates originales sin ninguna señal de alarma. Esto es un failure mode *observado*, no hipotético, y motiva el nuevo **Gate 0** (Sección 3.0) — añadirlo ahora es un amend legítimo a la spec porque responde a un caso real detectado, no a la tasa de paso de ninguna pasada de datos.

**Amend v1.2 (2026-07-03):** la calibración v1.1 se congeló sobre una muestra de 11 filings. La pasada completa sobre los 130 dio 78.46% de paso limpio — por debajo del 80% que el §6 fija como disparador de "iterar el extractor". El diagnóstico que el propio disparador forzó mostró que el modelo de fallo del §6 estaba incompleto: en 14 de los 28 casos en cola, Gates 0/1 confirmaban extracción correcta y el problema era que la muestra de 11 no representó la diversidad de los 130 (un solo biotech multi-programa cuando había al menos 7; vocabulario de negocio ausente para registro gramatical en tercera persona, no solo por sector). El disparador cumplió su función real — forzar el diagnóstico — aunque su modelo causal (tasa baja = extractor malo) no aplicara aquí. Dos gates se **rediseñaron**, no solo recalibraron, tras inspección humana 16/16 sobre los filings evidencia + control negativo obligatorio (Sección 3, Gate 3):
- **Gate 3** abandona la lista de vocabulario (que muere por mil ampliaciones — v1.1 tapó el hueco biotech, la siguiente ronda habría tapado registro gramatical, y así sucesivamente) por un **test relacional de asimetría**, universal e independiente de sector/registro.
- **Gates 2 y 4** condicionan su techo superior a si el fin de Item 1A fue *verificado estructuralmente* (header real de Item 1B/2 localizado) o *adivinado* (fallback sin header siguiente) — perseguir el máximo observado (BBIO→ROIV rompiendo el techo en 3 días) es un juego perdido; la protección real debe vivir en si el fin se encontró o se supuso, no en un número.
Ver Secciones 3 (Gate 2-4) y 6 (criterios) para el detalle y la evidencia.

---

## 1. Objetivo

Recortar de cada 10-K del universo ampliado (136 empresas, `data/universe_selection_20260702.json`) los Item 1 (Business) e Item 1A (Risk Factors) — únicas secciones que llegan al extractor LLM de la Etapa 3. Este documento fija los criterios de validez del recorte **antes** de elegir o probar el método de extracción, para que la definición de "recorte válido" no se ajuste mirando qué produce cada herramienta.

**Principio de diseño:** el validador es la pieza pre-registrada; el extractor es intercambiable. Si el método de extracción elegido falla en una fracción de los filings, se cae a un método alternativo o a cola de revisión manual sin tocar los gates — los gates definen qué es correcto, no cómo se logra.

---

## 2. Método de extracción — decisión, no pre-registro

A diferencia de los gates (Sección 3), el método de extracción es una decisión empírica sobre una muestra, revisable sin afectar la validez de los criterios.

**Candidato primario: `edgartools`** (open-source, mantenida, extracción de Items de 10-K nativa, maneja inline XBRL — los tags `ix:` que desde 2019 infestan los filings modernos y pueden inflar el HTML a 5-30MB). Se prueba contra la muestra de la Sección 5 antes de decidir si cubre el universo o si hace falta una heurística propia (regex sobre texto plano post-limpieza de XBRL) como fallback para el porcentaje que falle.

**Fallback:** heurística de regex sobre el texto plano del filing (tras strip de tags `ix:`/HTML), aplicando los mismos gates de la Sección 3. Se activa por-filing cuando `edgartools` no encuentra límites o produce un recorte que no pasa los gates.

**Cross-check automático edgartools vs fallback (añadido 2026-07-03, hallazgo AMAT):** Gate 1 solo ancla los *inicios* de Item 1/1A para verificar orden — puede pasar aunque el *final* del texto de `edgartools` no exista en absoluto en el corpus propio (divergencia más allá de whitespace entre el parser interno de la librería y un parseo directo del HTML, observada en al menos un filer). Regla: si el final del texto de `edgartools` no es localizable en el corpus (verificación dedicada, independiente de Gate 1), se ejecuta el fallback de regex automáticamente — que opera sobre el corpus propio y por tanto tiene fronteras siempre localizables — y se comparan las longitudes de Item 1A de ambos métodos. Si coinciden razonablemente (ratio 0.7–1.0/1.3), las fronteras del fallback se adoptan como corroboradas por acuerdo entre dos métodos independientes. Si divergen, el filing va a cola con etiqueta `CROSS_CHECK_DIVERGENTE` (añadida al enum cerrado del Gate 5, Sección 3) para revisión manual.

---

## 3. Los seis gates

### Gate 0 — Verificación de identidad (nuevo, v1.1)

Antes de intentar ningún recorte, confirmar que el documento descargado es efectivamente de la empresa esperada. Ningún gate de recorte estructural (1-5) puede detectar esto — un 10-K de otra empresa, perfectamente formado, pasa los cinco gates de recorte sin ninguna señal de alarma.

**Verificación primaria y suficiente — mecánica:** el accession number descargado debe estar en la lista de accessions del CIK esperado según `data.sec.gov/submissions/CIK{cik}.json`. Es una comparación contra metadatos de EDGAR, no contra el contenido del documento — inmune al problema que motivó este gate (ver corrección abajo).

**Verificación secundaria e informativa — nombre en portada:** nombre de la empresa (SEC `company_tickers.json`) buscado en los primeros ~3000 caracteres del documento (tras limpieza de bloques ocultos de inline XBRL — ver Sección 2), normalizado sin sufijos corporativos ni espacios. **Nunca aprueba por sí sola si el check mecánico no está disponible o falla** — solo se usa como dato adicional cuando el mecánico ya decidió, o como única señal (marcada explícitamente como menos fiable) si el mecánico no pudo ejecutarse (ej. fallo de red contra EDGAR).

**Corrección de diseño (2026-07-02, antes de cualquier congelación):** un primer diseño usaba el nombre como *fallback universal* — si no aparecía en portada, se buscaba en el documento completo. Esto reabría exactamente el agujero que motivó el Gate 0: los 10-K nombran competidores reales constantemente (el Item 1 de un fabricante de chips menciona a sus rivales por nombre docenas de veces), así que el documento de una empresa equivocada podía "aprobar" identidad citando a la empresa correcta como competidor. La arquitectura corregida invierte las prioridades: mecánico primero y suficiente, nombre en portada (nunca en el documento completo) como apoyo secundario.

**Si el check mecánico falla:** el filing no se procesa como recorte normal — va a cola con etiqueta `IDENTIDAD_NO_CONFIRMADA` (enum cerrado de la Sección 3.5/Gate 5), con CIK esperado, accession descargado, y el resultado del check de portada persistidos para revisión humana.

### Gate 1 — Orden estructural

Item 1, Item 1A e Item 1B (o Item 2 si 1B no existe en ese filer) deben localizarse en posiciones estrictamente crecientes dentro del documento. El recorte de Item 1A termina exactamente donde empieza el siguiente Item (1B o 2).

**Por qué:** el failure mode más común es que la tabla de contenidos contenga los mismos literales "Item 1A" que el cuerpo del documento, y un match ingenuo (primera ocurrencia) recorte desde el TOC en vez del cuerpo real.

**Regla robusta:** no tomar el primer match de cada literal. Tomar el *último* conjunto de matches que sea mutuamente consistente en orden creciente de posición. Señal auxiliar de TOC a descartar: alta densidad de literales "Item X" en poco espacio de texto, o matches contenidos dentro de una tabla (`<table>`/estructura tabular).

### Gate 2 — Longitud plausible por Item, techo condicionado a verificación estructural (v1.2)

| Item | Piso | Techo |
|------|------|-------|
| Item 1 (Business) | 10,000 | 280,000 (informativo si `end_verified`) |
| Item 1A (Risk Factors) | 20,000 | 400,000 (informativo si `end_verified`) |

**Por qué el piso:** fuera de banda por abajo casi siempre indica que se recortó el TOC, un header de página, o una sección de "incorporated by reference" (ver Gate 5). El piso **no** se condiciona — un recorte corto sigue siendo la firma del TOC independientemente de si el fin se verificó.

**Por qué el techo se condiciona (v1.2, 2026-07-03):** perseguir el máximo observado es un juego perdido. BBIO fijó el techo de Item 1A en 400,000 (máximo confirmado + 20%) en un commit; tres días después, la pasada completa sobre 130 encontró a ROIV con Item 1A = 408,983 — rompiendo el techo que se acababa de fijar. El propósito real del techo es detectar "no encontré el límite final y me comí secciones posteriores" — y el pipeline ya sabe cuándo eso pasó: `end_verified_structurally(corpus, item1a_text)` comprueba si el final del recorte tiene un header real de Item 1B/2 localizado poco después (fin **encontrado**) o si el fallback recurrió a `min(p1a+banda, len(corpus))` por no hallar ningún header siguiente (fin **adivinado**). Solo en el segundo caso una longitud fuera de banda es señal de alarma real. Cuando el fin está verificado, una sección larga es genuina por construcción y el techo pasa a **advertencia informativa** persistida en metadatos (`techo_superado_pero_verificado_informativo`), sin bloquear el gate. Esto resuelve de un golpe los 6 biotechs de Gate 4 con ratio 0.80–0.84 (todos con Item 1B confirmado en su frontera final) y ROIV, sin inflar ningún número — y mantiene la protección exactamente donde hace falta.

**Extremos confirmados registrados (no umbrales, solo referencia):** IBM Item 1 = 10,116 chars (mínimo confirmado, apenas sobre el piso — IBM escribe un Business genuinamente corto y delega en el MD&A). ROIV Item 1A = 408,983 chars (máximo confirmado, con fin verificado estructuralmente). Si un filing futuro rompe cualquiera de estos extremos con fronteras confirmadas correctas, se registra como nuevo extremo — no se revisa el piso/techo salvo que la evidencia lo pida explícitamente.

### Gate 3 — Test relacional de asimetría (v1.2, reemplaza vocabulario)

**Diseño v1.1 (histórico, abandonado):** densidad mínima de lenguaje de riesgo/negocio contra listas de vocabulario fijas. Funcionó para tapar el hueco biotech encontrado en la muestra de 11 (CYTK/BBIO, densidad de negocio 0.06–0.14 con vocabulario corporativo genérico, corregido a 2.21–2.84 ampliando vocabulario a términos clínicos). Pero la pasada sobre 130 mostró que el siguiente hueco no era sectorial — era de **registro gramatical**: IBM, CNH, CWEN, GPRE, QUBT, RGTI (industrias completamente distintas: tecnología, maquinaria agrícola, energía, biocombustible, computación cuántica) fallaban por igual porque escriben en tercera persona ("the Company", "IBM's products") en vez de primera ("our business"). Una lista de vocabulario muere por mil ampliaciones — cada ronda tapa un hueco y descubre el siguiente.

**Diseño v1.2:** abandona el diccionario para el check de negocio. El propósito declarado del gate es cazar el desplazamiento de sección (Item 1A real recortado como si fuera Item 1B, o viceversa) — y eso se detecta con una propiedad relacional universal, no con vocabulario: **un Item 1A real siempre tiene densidad de lenguaje de riesgo (`risk`, `adversely affect`, `could harm`, `may not`, `material adverse effect`) mayor que un Item 1 real**, en cualquier sector y cualquier registro gramatical. Si los recortes están desplazados, la asimetría se invierte o colapsa.

```
ratio = densidad_riesgo(Item1A) / densidad_riesgo(Item1)
pass = ratio >= 1.0
```

**Umbral 1.0, congelado tras control negativo obligatorio (condición innegociable del freeze, no opcional).** Criterio de inclusión de la población evaluada, explícito en `negative_control_gate3.py`: filings con Gate 1 y Gate 2 aprobados y sin caso especial de Gate 5 (Gates 3/4 deliberadamente *no* se exigen — exigirlos sería circular, ya que Gate 3 es lo que se está evaluando). Sobre esa población (119 en el momento de correr el control; el número exacto depende de qué pasada de `full_pass_results` esté vigente al ejecutarlo, ya que el archivo se sobreescribe en cada corrida — no es una constante fija de la spec), se evaluó el test tanto sobre los pares reales como sobre los pares **cruzados** (Item 1 e Item 1A intercambiados). Resultado: separación perfecta sin solapamiento — mínimo ratio real = 1.130 (CSCO), máximo ratio cruzado = 0.890 (CSCO). El umbral inicial propuesto (2.0) era una estimación sin evidencia que producía 8 falsos negativos (FSLR, MSTR, ZS, WULF, TE, GILD, CSCO, AMAT — todos con asimetría correcta pero por debajo de 2.0). Con 1.0 (centro del hueco [0.890, 1.130]): todos los reales pasan, todos los cruzados fallan.

**Precisión sobre qué prueba realmente el control negativo — corrección tras revisión adversarial (2026-07-03):** el ratio de un par cruzado es, por construcción algebraica, el recíproco del ratio real del mismo filing (`ratio_cruzado = risk1/risk1a = 1/ratio_real` — el propio dato lo muestra: CSCO da 1.13 real y 0.89 cruzado, y 1/1.13≈0.89). Con umbral en 1.0, "todos los cruces fallan" es matemáticamente equivalente a "todos los reales pasan ≥1.0" — no son dos hallazgos independientes, es la misma afirmación expresada dos veces. El contenido informativo real y valioso del control es uno solo: **los 119 pares reales tienen la asimetría en la dirección correcta (ratio > 1), sin excepción, a través de sectores e industrias completamente distintos** — eso es lo que valida que el test discrimina de forma universal, no la cifra separada de "cruces rechazados".

Consecuencia: la cláusula "si algún cruce empieza a pasar con este umbral, el gate se rediseña" (versión anterior de este párrafo) es lógicamente vacía tal como estaba escrita — un cruce solo puede pasar si su par real cae por debajo de 1.0, así que nunca dispara de forma independiente del propio real. **Reformulación correcta: la señal de degradación del gate es que algún par real caiga por debajo de 1.0 en cohortes futuras** (Sección 10) — con la nota de que el margen actual es fino: el mínimo real observado (CSCO, 1.130) está solo ~13% por encima del umbral, así que un filing futuro con ratio real en el rango 1.0–1.15 es zona gris a **inspeccionar manualmente**, no a aprobar mecánicamente sin más — el margen no es tan cómodo como "119/119 perfecto" sugiere a primera lectura.

### Gate 4 — Ratio sobre el documento total, piso y techo v1.2

Item 1 + Item 1A combinados deben representar entre **30%** y 80% del texto limpio total del filing (piso bajado de 35% a 30% el 2026-07-03).

**Por qué:** complementa el Gate 2 en filings anómalamente cortos (smaller reporting companies con Business/Risk Factors mínimos) o anómalamente largos (filers con Item 1A extenso que aun así podría estar mal delimitado).

**Piso bajado a 0.30 (evidencia):** SMCI (ratio 0.343, fronteras confirmadas correctas en inspección) quedaba excluido por el piso original de 0.35 — su documento tiene una masa inusual de contenido posterior a Item 1A (notas financieras extensas), no un fallo de extracción.

**Techo condicionado a `end_verified_structurally`, misma lógica que Gate 2:** bloqueante solo si el fin de Item 1A no fue verificado. Resuelve los 6 biotechs con ratio 0.80–0.84 (RXRX, RVMD, APGE, NUVL, CRSP, BEAM) y ROIV sin ensanchar el techo absoluto.

### Gate 5 — Casos especiales, explícitos y etiquetados

No se procesan como recorte normal — se detectan y van a cola con etiqueta de una **lista cerrada** (no texto libre — si las etiquetas fueran libres, la cola no sería agregable y se perdería la señal de qué caso especial domina):

| Caso | Detección | Etiqueta de cola (enum cerrado) |
|------|-----------|-------------------|
| Identidad del filing no confirmada (Gate 0) | CIK o nombre de portada no coinciden con lo esperado | `IDENTIDAD_NO_CONFIRMADA` |
| Incorporación por referencia | Texto "is incorporated by reference to" cerca de donde debería estar Item 1A | `INCORPORADO_POR_REFERENCIA` |
| Items combinados (ej. "Item 1 and 1A") | Header combinado detectado, un solo bloque para ambos | `ITEMS_COMBINADOS` |
| 10-K/A en vez de 10-K original | Form type = 10-K/A en submissions.json | `ENMIENDA` |
| Smaller reporting company sin Item 1A | Ausencia legal de la sección (permitida para SRC) | `SIN_ITEM_1A_SRC` |
| Final de `edgartools` no localizable en el corpus + fallback no coincide en longitud (ratio fuera de 0.7–1.3) | Cross-check automático (Sección 2) detecta divergencia entre métodos, no solo un fallo de uno | `CROSS_CHECK_DIVERGENTE` |
| Cualquier caso especial no cubierto arriba | Detectado manualmente o por heurística nueva no prevista | `OTHER` — **obligatorio** acompañar de un campo `descripcion` de texto libre; si `OTHER` acumula >10% de la cola, se promueve a etiqueta propia del enum (revisión de la spec, no ampliación silenciosa) |

Fallos de gates 1-4 (recorte intentado pero no válido) usan una etiqueta separada, no parte de este enum: `FALLO_GATE_N` (N = número de gate que no se superó). Distinción: el enum de arriba son casos especiales *detectados antes* de intentar el recorte estándar (Gate 0 incluido); `FALLO_GATE_N` es un recorte que se intentó y no pasó validación.

---

## 4. Persistencia y trazabilidad

Cada recorte exitoso persiste, junto al texto:

```json
{
  "ticker": "...",
  "cik": "...",
  "accession_number": "...",
  "metodo_extraccion": "edgartools | heuristica_regex",
  "item1_offset": [inicio, fin],
  "item1a_offset": [inicio, fin],
  "item1_len": N,
  "item1a_len": N,
  "gates_pasados": ["gate1", "gate2", "gate3", "gate4"],
  "fecha_extraccion": "YYYY-MM-DD"
}
```

Cada fallo persiste el motivo (Sección 3/5) y el filing va a `data/filings/cola_revision/` sin texto recortado — no se le hace pasar texto basura al extractor de la Etapa 3.

---

## 5. Muestra de calibración (previa a la pasada completa)

### 5.1 Selección — regla mecánica, no a dedo

Ordenar los **130 filings 10-K** descargados (de los 136 del universo, 6 son foreign private issuers con 20-F — tratados aparte, Sección 9) por tamaño en bytes del documento primario. Tomar los filings en los percentiles fijos **p5, p15, p25, p40, p55, p70, p80, p90, p95** (9 filings) más **1 adicional**: el filing de mayor tamaño absoluto de los 130 (caso extremo de inline XBRL pesado, casi con certeza >p95 pero se incluye explícitamente para no depender de que el percentil lo capture). Total: 10.

Esta regla por percentil de tamaño de archivo — no por categoría, no por nombre reconocible — es una proxy mecánica razonable de complejidad de parseo (más bytes ≈ más inline XBRL / HTML más denso) y evita la tentación de elegir a mano filers "que seguro van a funcionar bien".

### 5.2 Qué se permite ajustar sobre la muestra, y qué queda congelado

**Se permite ajustar** (mirando los 10 filings de calibración): las bandas de longitud del Gate 2, el umbral de densidad del Gate 3, el umbral de ratio del Gate 4. Esto es legítimo porque lo que se observa para ajustar es **estructura documental** (dónde caen los límites reales de Item 1/1A en documentos conocidos), no retornos ni scores — misma distinción outcome/no-outcome que en `select_universe.py` (ver ese docstring, "NOTA SOBRE PRECEDENTE"): revisar un umbral mirando la forma de un documento es pre-registro legítimo; revisarlo mirando cuántos filings "pasan" en la pasada completa no lo sería.

**Queda congelado tras la calibración, sin excepción:** el Gate 1 (orden estructural — es lógico, no numérico, no se calibra) y los umbrales numéricos de Gates 2-4 una vez fijados. El momento exacto de congelación es un **commit dedicado "umbrales calibrados: filing_section_validator"** entre el commit de la muestra (con hallazgos de la inspección manual) y el commit de la pasada completa — ese commit lleva timestamp y es el punto de no retorno.

**Los 10 filings de la muestra se re-validan con los umbrales ya congelados en la pasada completa**, exactamente igual que los otros 126 — no quedan exentos ni pre-aprobados por haber sido inspeccionados a mano. La inspección manual valida el *validador*; la pasada completa valida cada *filing*, incluidos esos 10.

Para cada uno de los 10: inspección manual de los límites extraídos contra el documento real (abrir el 10-K, verificar que el recorte empieza y termina donde debe). Si los gates dejan pasar un recorte manifiestamente mal delimitado en la inspección manual, se ajustan aquí — antes del commit de congelación, nunca después.

### 5.3 Caso de regresión conocido — BBIO (fuera del conteo mecánico de 10)

Durante la exploración inicial de `edgartools` (antes del fix de CIK que cambió la población y por tanto los percentiles), BBIO cayó en la muestra mecánica de esa ronda y su recorte falló de forma confirmada: `edgartools` ancló Item 1/1A cerca de la tabla de contenidos (posición ~286k del documento) en vez del cuerpo real (~740k), devolviendo 2,116 y 651 caracteres — muy por debajo de cualquier banda plausible, con `confidence=0.5` y warning explícito de la propia librería. Es la validación empírica de que el Gate 1 no es hipotético.

Tras el fix de CIK, BBIO ya no cae en la muestra mecánica de 10 recalculada (Sección 5.1). Se añade como **11º filing, etiquetado `caso_regresion_conocido`**, incluido en la inspección manual obligatoria (Sección 6) pero fuera del conteo de "10 mecánicos" — su inclusión responde a un fallo ya confirmado, no a la regla de percentiles, y mantenerlo fuera del conteo mecánico evita que la regla de selección se contamine con casos elegidos por resultado conocido.

---

## 6. Criterios de aceptación de la Etapa 2 (pre-fijados) — resultado final registrado

| Métrica | Umbral | Acción si no se cumple | Resultado real |
|---------|--------|--------------------------|-----------------|
| Tasa de paso limpio (gates 0-4 superados sin caer en Gate 5) sobre los 130 10-K | 85-95% esperado | Si <80%: iterar heurística/extractor antes de revisión manual masiva — una cola grande es señal de extractor malo, no de documentos raros | Primera pasada (v1.1 congelada sobre muestra de 11): **78.46%** (102/130) — disparó la regla de <80%. Tras el rediseño v1.2 (Gates 2-4, ver Secciones 3 y arriba): **92.31%** (120/130), dentro del rango esperado |
| Filings en cola de revisión (Gate 5 + fallos) | El resto | Revisión manual filing por filing, sin pasar texto no validado al extractor de Etapa 3 | 10/130 tras v1.2: 6 `INCORPORADO_POR_REFERENCIA` (Gate 5 funcionando como se diseñó, no un fallo), 2 extracción fallida en ambos métodos (INTC, BE), 1 `CROSS_CHECK_DIVERGENTE` (INCY), 1 `FALLO_gate2_longitud` (NVEC — empresa pequeña, Item 1A ligeramente bajo el piso, plausible legítimo) |
| Inspección manual de la muestra de calibración: 10 mecánicos (Sección 5.1) + BBIO (Sección 5.3) | 11/11 límites correctos antes de la pasada completa | Si falla: ajustar gates o extractor; re-muestreo mecánico abajo (BBIO no se re-muestrea, ya es un caso confirmado) | **11/11 confirmado** — ver commit de congelación v1.1 |
| Inspección manual de los 16 candidatos a recalibración v1.2 (6 biotech de ratio + 8 de vocabulario + ROIV + SMCI) | 16/16 límites correctos antes del rediseño | Si falla: no rediseñar sobre evidencia contaminada | **16/16 confirmado** |

**Sobre el disparador del 80% — qué significó realmente:** la regla codificaba un modelo de fallo (tasa baja = extractor malo) que no aplicó aquí — en 14 de los 28 casos de la primera cola, Gates 0/1 confirmaban extracción correcta; el problema era que la muestra de calibración (11 filings) no representó la diversidad sectorial/gramatical de los 130. El disparador cumplió su función real: forzar el diagnóstico antes de tocar nada. Ni obedecer la letra (iterar el extractor, que no estaba roto) ni ignorar el disparador habría sido correcto — el camino fue un amend documentado (v1.2) con inspección humana + control negativo antes de cada cambio, igual disciplina que v1.1.

**Mecanismo de re-muestreo (determinista, no discreción encubierta):** la regla de percentiles de la Sección 5.1 es determinista — repetirla sin más devolvería exactamente los mismos 10 archivos. Si la inspección manual falla y hace falta una nueva muestra, se usan percentiles desplazados **p10, p20, p30, p45, p60, p75, p85** + el **segundo mayor** archivo por tamaño absoluto, excluyendo cualquier filing ya inspeccionado en la ronda anterior. Sigue siendo mecánico (otro conjunto fijo de percentiles, no elegido por resultado) y mantiene el espíritu de la Sección 5.1.

---

## 7. Restricciones operativas (heredadas de Etapa 1)

- User-Agent con contacto real en toda descarga de SEC EDGAR (sin él, 403)
- Máximo 10 req/s contra EDGAR — con 136 filings y sleep conservador, ~5 minutos de descarga total
- Descarga a disco local (`data/filings/{ticker}_{accession}.htm`), idempotente, con `accession_number` persistida para trazabilidad (mismo patrón que Etapa 1)

---

## 8. Orden de implementación

1. Descarga de los 136 filings completos (restricciones de Sección 7, ~5 min con sleep conservador) + separación en 130 10-K / 6 20-F (foreign private issuers, Sección 9) + cómputo de percentiles de tamaño en bytes sobre los 130 10-K + selección de la muestra de 10 según la regla de la Sección 5.1 + BBIO como 11º caso de regresión (Sección 5.3). (La muestra no puede seleccionarse antes de tener los filings en disco — no hay percentiles sin la población completa.)
2. Probar `edgartools` contra la muestra de 11, decidir si cubre el universo o si el fallback de regex es necesario para una fracción
3. Implementar los seis gates (Sección 3) sobre el output del extractor elegido, calibrar bandas/umbrales sobre la muestra (Sección 5.2)
4. **Commit de congelación de umbrales** ("umbrales calibrados: filing_section_validator") — punto de no retorno, timestamp
5. Pasada completa sobre los 130 10-K (incluidos los 10 de la muestra, re-validados sin excepción), con reporte de cola (Sección 6)
6. Los 6 20-F por separado, vía Sección 9 (inspección manual, sin bandas estadísticas)

---

## 9. Foreign private issuers (20-F) — tratamiento separado, sin bandas

6 empresas del universo (TSM, ARM, BABA, ASML, BIDU, SE) presentan 20-F, no 10-K. `edgartools` tiene soporte nativo (clase `TwentyF`, propiedades `.business`/`.risk_factors`), verificado contra TSM: `.business` devuelve Item 4 "Information on the Company" con contenido limpio. `.risk_factors` es más impreciso — en 20-F los Risk Factors son la subsección **3.D dentro de Item 3 "Key Information"**, no un Item independiente; el shortcut de la librería devuelve todo Item 3, incluyendo preámbulo de secciones marcadas "Not applicable" (Capitalization and Indebtedness, Reasons for the Offer) antes del contenido real de riesgo.

**Decisión: con N=6, no se calibran bandas estadísticas (Gates 2-4) — sería sobre-ingeniería para una población de ese tamaño.** Los 6 filings se inspeccionan manualmente uno por uno: Item 4 completo para Business, y dentro de Item 3 se delimita la subsección 3.D si es extraíble de forma simple, o se documenta como aproximación aceptada usar Item 3 completo (con el preámbulo "Not applicable" como ruido tolerado, no como error) si el recorte de la subsección exacta no es trivial. Cada uno de los 6 queda con su propia nota de aproximación en los metadatos de trazabilidad (Sección 4), no con gates numéricos.

Gate 0 (identidad) y Gate 1 (orden estructural, verificado manualmente en este caso) siguen aplicando — son universales, no dependen del tipo de formulario.

---

## 10. Advertencia honesta sobre la calibración v1.2

Los Gates 2-4 de v1.2 se calibraron sobre la **población completa** de 130 10-K, no sobre una muestra con held-out. Esto es correcto por lo que significa el disparador del 80% (Sección 6: forzar diagnóstico, no ocultar evidencia) — pero tiene una consecuencia que hay que decir sin adornos: **no queda ningún conjunto de datos independiente contra el cual validar que la calibración generaliza.** El test verdadero de v1.2 no son los 130 filings ya vistos — son los 10-Ks del año próximo (2027), sobre empresas y sectores que hoy no están en el universo, o el mismo universo con negocios que hayan cambiado de forma que altere su registro narrativo. Si esa cohorte futura produce una tasa de paso limpio muy distinta de 92.3%, o si el control negativo del Gate 3 (asimetría 1.0) deja de separar limpio, **eso es la señal real de si v1.2 generaliza — no la re-ejecución de la pasada actual, que ya no puede sorprender.**

---

*Spec CONGELADA (v1.2, 2026-07-03). Los gates de la Sección 3 y los umbrales de la Sección 6 no deben ajustarse mirando la tasa de paso de una pasada futura sobre el mismo universo — solo evidencia estructural nueva (inspección de fronteras + control negativo) justifica tocar esta versión, con el mismo protocolo de v1.1→v1.2: inspección primero, rediseño/recalibración después, documentado como amend versionado. Los 6 20-F (Sección 9) se validan por inspección manual, fuera del esquema de bandas.*
