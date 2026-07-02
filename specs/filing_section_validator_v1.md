# FutureAnalysis — Filing Section Validator Spec v1.0
*Autor: FutureTrends Intelligence System*
*Fecha: 2026-07-02*
*Estado: DRAFT — pre-registro de gates, previo a Etapa 2 de P1.5*

---

## 1. Objetivo

Recortar de cada 10-K del universo ampliado (136 empresas, `data/universe_selection_20260702.json`) los Item 1 (Business) e Item 1A (Risk Factors) — únicas secciones que llegan al extractor LLM de la Etapa 3. Este documento fija los criterios de validez del recorte **antes** de elegir o probar el método de extracción, para que la definición de "recorte válido" no se ajuste mirando qué produce cada herramienta.

**Principio de diseño:** el validador es la pieza pre-registrada; el extractor es intercambiable. Si el método de extracción elegido falla en una fracción de los filings, se cae a un método alternativo o a cola de revisión manual sin tocar los gates — los gates definen qué es correcto, no cómo se logra.

---

## 2. Método de extracción — decisión, no pre-registro

A diferencia de los gates (Sección 3), el método de extracción es una decisión empírica sobre una muestra, revisable sin afectar la validez de los criterios.

**Candidato primario: `edgartools`** (open-source, mantenida, extracción de Items de 10-K nativa, maneja inline XBRL — los tags `ix:` que desde 2019 infestan los filings modernos y pueden inflar el HTML a 5-30MB). Se prueba contra la muestra de la Sección 5 antes de decidir si cubre el universo o si hace falta una heurística propia (regex sobre texto plano post-limpieza de XBRL) como fallback para el porcentaje que falle.

**Fallback:** heurística de regex sobre el texto plano del filing (tras strip de tags `ix:`/HTML), aplicando los mismos gates de la Sección 3. Se activa por-filing cuando `edgartools` no encuentra límites o produce un recorte que no pasa los gates.

---

## 3. Los cinco gates

### Gate 1 — Orden estructural

Item 1, Item 1A e Item 1B (o Item 2 si 1B no existe en ese filer) deben localizarse en posiciones estrictamente crecientes dentro del documento. El recorte de Item 1A termina exactamente donde empieza el siguiente Item (1B o 2).

**Por qué:** el failure mode más común es que la tabla de contenidos contenga los mismos literales "Item 1A" que el cuerpo del documento, y un match ingenuo (primera ocurrencia) recorte desde el TOC en vez del cuerpo real.

**Regla robusta:** no tomar el primer match de cada literal. Tomar el *último* conjunto de matches que sea mutuamente consistente en orden creciente de posición. Señal auxiliar de TOC a descartar: alta densidad de literales "Item X" en poco espacio de texto, o matches contenidos dentro de una tabla (`<table>`/estructura tabular).

### Gate 2 — Longitud plausible por Item

| Item | Rango de caracteres (texto limpio, sin markup) |
|------|------------------------------------------------|
| Item 1 (Business) | 10,000 – 150,000 |
| Item 1A (Risk Factors) | 20,000 – 250,000 |

**Por qué:** fuera de banda por abajo casi siempre indica que se recortó el TOC, un header de página, o una sección de "incorporated by reference" (ver Gate 5). Fuera de banda por arriba indica que no se encontró el límite final y el recorte se comió secciones posteriores.

**Nota:** estas bandas son un punto de partida, no un pre-registro rígido — se calibran empíricamente sobre la muestra de 10 filings (Sección 5) antes de la pasada completa sobre los 136, y una vez calibradas para la pasada completa, no se ajustan mirando la tasa de paso de esa pasada (eso sería ajustar el gate al resultado).

### Gate 3 — Marcadores de contenido

El texto recortado como Item 1A debe superar una densidad mínima de lenguaje de riesgo: términos como "risk", "adversely affect", "could harm", "may not", "material adverse effect" por cada N caracteres. El texto recortado como Item 1 debe superar una densidad mínima de lenguaje de negocio (descripción de producto/mercado/competencia, ausencia de la densidad de riesgo del 1A).

**Por qué:** caza el error que los Gates 1-2 dejan pasar — límites bien formados y longitud plausible, pero desplazados una sección completa (ej. lo que se etiquetó como "Item 1A" es en realidad Item 1B, con longitud y forma similares pero contenido distinto).

**Umbral:** a calibrar sobre la muestra — punto de partida propuesto: ≥3 ocurrencias de marcadores de riesgo por cada 1,000 caracteres para Item 1A.

### Gate 4 — Ratio sobre el documento total

Item 1 + Item 1A combinados deben representar entre 15% y 60% del texto limpio total del filing.

**Por qué:** complementa el Gate 2 en filings anómalamente cortos (smaller reporting companies con Business/Risk Factors mínimos) o anómalamente largos (filers con Item 1A extenso que aun así podría estar mal delimitado).

### Gate 5 — Casos especiales, explícitos y etiquetados

No se procesan como recorte normal — se detectan y van a cola con etiqueta de una **lista cerrada** (no texto libre — si las etiquetas fueran libres, la cola no sería agregable y se perdería la señal de qué caso especial domina):

| Caso | Detección | Etiqueta de cola (enum cerrado) |
|------|-----------|-------------------|
| Incorporación por referencia | Texto "is incorporated by reference to" cerca de donde debería estar Item 1A | `INCORPORADO_POR_REFERENCIA` |
| Items combinados (ej. "Item 1 and 1A") | Header combinado detectado, un solo bloque para ambos | `ITEMS_COMBINADOS` |
| 10-K/A en vez de 10-K original | Form type = 10-K/A en submissions.json | `ENMIENDA` |
| Smaller reporting company sin Item 1A | Ausencia legal de la sección (permitida para SRC) | `SIN_ITEM_1A_SRC` |
| Cualquier caso especial no cubierto arriba | Detectado manualmente o por heurística nueva no prevista | `OTHER` — **obligatorio** acompañar de un campo `descripcion` de texto libre; si `OTHER` acumula >10% de la cola, se promueve a etiqueta propia del enum (revisión de la spec, no ampliación silenciosa) |

Fallos de gates 1-4 (recorte intentado pero no válido) usan una etiqueta separada, no parte de este enum: `FALLO_GATE_N` (N = número de gate que no se superó). Distinción: el enum de arriba son casos especiales *detectados antes* de intentar el recorte estándar; `FALLO_GATE_N` es un recorte que se intentó y no pasó validación.

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

Ordenar los 136 filings descargados por tamaño en bytes del documento primario. Tomar los filings en los percentiles fijos **p5, p15, p25, p40, p55, p70, p80, p90, p95** (9 filings) más **1 adicional**: el filing de mayor tamaño absoluto del universo (caso extremo de inline XBRL pesado, casi con certeza >p95 pero se incluye explícitamente para no depender de que el percentil lo capture). Total: 10.

Esta regla por percentil de tamaño de archivo — no por categoría, no por nombre reconocible — es una proxy mecánica razonable de complejidad de parseo (más bytes ≈ más inline XBRL / HTML más denso) y evita la tentación de elegir a mano filers "que seguro van a funcionar bien".

### 5.2 Qué se permite ajustar sobre la muestra, y qué queda congelado

**Se permite ajustar** (mirando los 10 filings de calibración): las bandas de longitud del Gate 2, el umbral de densidad del Gate 3, el umbral de ratio del Gate 4. Esto es legítimo porque lo que se observa para ajustar es **estructura documental** (dónde caen los límites reales de Item 1/1A en documentos conocidos), no retornos ni scores — misma distinción outcome/no-outcome que en `select_universe.py` (ver ese docstring, "NOTA SOBRE PRECEDENTE"): revisar un umbral mirando la forma de un documento es pre-registro legítimo; revisarlo mirando cuántos filings "pasan" en la pasada completa no lo sería.

**Queda congelado tras la calibración, sin excepción:** el Gate 1 (orden estructural — es lógico, no numérico, no se calibra) y los umbrales numéricos de Gates 2-4 una vez fijados. El momento exacto de congelación es un **commit dedicado "umbrales calibrados: filing_section_validator"** entre el commit de la muestra (con hallazgos de la inspección manual) y el commit de la pasada completa — ese commit lleva timestamp y es el punto de no retorno.

**Los 10 filings de la muestra se re-validan con los umbrales ya congelados en la pasada completa**, exactamente igual que los otros 126 — no quedan exentos ni pre-aprobados por haber sido inspeccionados a mano. La inspección manual valida el *validador*; la pasada completa valida cada *filing*, incluidos esos 10.

Para cada uno de los 10: inspección manual de los límites extraídos contra el documento real (abrir el 10-K, verificar que el recorte empieza y termina donde debe). Si los gates dejan pasar un recorte manifiestamente mal delimitado en la inspección manual, se ajustan aquí — antes del commit de congelación, nunca después.

---

## 6. Criterios de aceptación de la Etapa 2 (pre-fijados)

| Métrica | Umbral | Acción si no se cumple |
|---------|--------|--------------------------|
| Tasa de paso limpio (gates 1-4 superados sin caer en Gate 5) sobre los 136 | 85-95% esperado | Si <80%: iterar heurística/extractor antes de revisión manual masiva — una cola grande es señal de extractor malo, no de documentos raros |
| Filings en cola de revisión (Gate 5 + fallos) | El resto | Revisión manual filing por filing, sin pasar texto no validado al extractor de Etapa 3 |
| Inspección manual de la muestra de calibración (Sección 5) | 10/10 límites correctos antes de la pasada completa | Si falla: ajustar gates o extractor, repetir con nueva muestra (mecanismo de re-muestreo abajo) |

**Mecanismo de re-muestreo (determinista, no discreción encubierta):** la regla de percentiles de la Sección 5.1 es determinista — repetirla sin más devolvería exactamente los mismos 10 archivos. Si la inspección manual falla y hace falta una nueva muestra, se usan percentiles desplazados **p10, p20, p30, p45, p60, p75, p85** + el **segundo mayor** archivo por tamaño absoluto, excluyendo cualquier filing ya inspeccionado en la ronda anterior. Sigue siendo mecánico (otro conjunto fijo de percentiles, no elegido por resultado) y mantiene el espíritu de la Sección 5.1.

---

## 7. Restricciones operativas (heredadas de Etapa 1)

- User-Agent con contacto real en toda descarga de SEC EDGAR (sin él, 403)
- Máximo 10 req/s contra EDGAR — con 136 filings y sleep conservador, ~5 minutos de descarga total
- Descarga a disco local (`data/filings/{ticker}_{accession}.htm`), idempotente, con `accession_number` persistida para trazabilidad (mismo patrón que Etapa 1)

---

## 8. Orden de implementación

1. Descarga de los 136 filings completos (restricciones de Sección 7, ~5 min con sleep conservador) + cómputo de percentiles de tamaño en bytes sobre esos 136 + selección de la muestra de 10 según la regla de la Sección 5.1. (La muestra no puede seleccionarse antes de tener los 136 en disco — no hay percentiles sin la población completa.)
2. Probar `edgartools` contra la muestra, decidir si cubre el universo o si el fallback de regex es necesario para una fracción
3. Implementar los cinco gates (Sección 3) sobre el output del extractor elegido, calibrar bandas/umbrales sobre la muestra (Sección 5.2)
4. **Commit de congelación de umbrales** ("umbrales calibrados: filing_section_validator") — punto de no retorno, timestamp
5. Pasada completa sobre los 136 (incluidos los 10 de la muestra, re-validados sin excepción), con reporte de cola (Sección 6)

---

*Spec lista para pre-registro. Los gates de la Sección 3 y los umbrales de la Sección 6 son las piezas que no deben ajustarse después de ver la tasa de paso de la pasada completa — solo la Sección 5 (calibración sobre la muestra) es el punto legítimo de ajuste antes de correr sobre los 136.*
