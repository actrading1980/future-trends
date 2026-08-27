# Incidente crónico — guard N≥40 de `tech_scores`, cobertura degradada
*Abierto: 2026-08-27 · Onset real: 2026-07-07 · Estado: ABIERTO, sin causa raíz*

---

## 1. Cronología

- **2026-07-07**: primer disparo real del guard (`solo 15 registros insertados... minimo esperado 40`). Coincide con el cierre del incidente de trust-dialog (`0c7a0c9`), pero es un síntoma **distinto** — no vuelve a aparecer el patrón "reporte demasiado corto" de junio, ahora el reporte se genera bien pero la extracción de scores devuelve menos empresas de las esperadas.
- **2026-07-07 → 2026-08-26** (última fecha con log disponible al momento de abrir este expediente): el guard dispara en **~30 de las fechas de ejecución del período**, con N típico 0-34 sobre un mínimo de 40 (universo de 51). No es esporádico — es el estado normal de las últimas 7 semanas.
- **2026-07-28**: `run_daily.ps1` se modifica para que el guard deje de bloquear los pasos 9-12 (precios, notas, comparativo, deploy) y pase a alarmar al final sin detener el run (commit de este expediente, ver más abajo). **Esto cambia el síntoma (el run ya no aborta pasos independientes de N), no la causa** — el guard sigue disparando después del cambio exactamente igual (ver 08-25, 08-26 en la cronología del log). Confirmado con `logs/scheduler.log`: el ablandamiento fue correcto para el side-effect que resolvía, pero no debe leerse como "problema resuelto" — no lo estaba y no lo está.

## 2. Pregunta 1 — ¿subconjunto muerto o degradación estocástica?

`GROUP BY ticker` sobre `tech_scores` desde 2026-07-07 (30 fechas con al menos una fila):

```
tickers con alguna fila: 51/51 (ninguno ausente al 100%)
distribución de días presentes por ticker: rango 2-28 de 30, sin bimodalidad
  2 días: 8 tickers    8 días: 4 tickers   20 días: 2 tickers
  3 días: 7 tickers   10 días: 2 tickers   21 días: 1 ticker
  4 días: 5 tickers   12 días: 1 ticker    22 días: 1 ticker
  5 días: 3 tickers   14 días: 1 ticker    23 días: 1 ticker
  7 días: 2 tickers   15 días: 1 ticker    24 días: 3 tickers
                       17 días: 1 ticker    25 días: 2 tickers
                       18 días: 2 tickers   27 días: 3 tickers
                                            28 días: 1 ticker
```

**Veredicto: degradación estocástica, no subconjunto muerto.** No hay un grupo fijo de ~25 tickers ausente cada día — todos los 51 aparecen alguna vez, con una distribución continua desde "casi nunca" hasta "casi siempre". Esto descarta la hipótesis de un cambio de fuente/formato que rompiera la extracción de un subconjunto fijo el ~07-07. Apunta a un mecanismo que trunca la respuesta de forma variable — candidatos: rate-limit/timeout de la llamada a Claude CLI que genera el CSV de scores (la segunda llamada, paso 7 de `run_daily.ps1`), o contención de recursos en la máquina que ejecuta la tarea programada a las 07:00. **No investigado aún — es el siguiente paso, no parte de este expediente de apertura.**

## 3. Pregunta 2 — contaminación aguas abajo, era declarada

Todo cálculo o comparación que use `tech_scores`/`reports/comparative_*.md`/`comparative_*.json` en el rango **2026-07-07 → presente** operó sobre una población con cobertura ~20-65% del universo de 51, variable día a día y sin declaración de universo en el propio artefacto. Los comparativos diarios de este tramo comparan conjuntos de empresas distintos entre sí sin decirlo.

**Era declarada, cuarta casa donde aplica el patrón era-split:**
- Antes de 2026-07-07: cobertura ~100%, universo estable (pipeline normal + los días `pipeline_writetool_recovered` ya reconciliados).
- 2026-07-07 → presente: **cobertura degradada, universo variable no declarado por fecha — cualquier lectura de tendencia, IC exploratorio (F1) o comparativo que cruce este límite debe declarar el universo real por fecha, no asumir N=51.**

Esto no invalida el trabajo de validación futuro (F1/F2/F3 aún no empiezan a correr datos reales), pero sí cualquier lectura retrospectiva informal de los comparativos de este tramo — y es una precondición que `compute_validation.py` deberá resolver cuando exista (ponderar o excluir por cobertura real de la fecha, no por conteo pooled).

## 4. Pregunta 3 — el canal

El guard funcionó correctamente cada uno de los ~30 días: detectó la cobertura baja y lo dejó escrito en `logs/scheduler.log`. No sirvió de nada operativamente porque ese log no tiene lector humano diario — es el mismo patrón que el mother-house ya nombró (alertado separado de causa) y que reversal-system repitió (Task Scheduler se traga stdout, nadie ve el fallo hasta que se busca expresamente).

**Estado: RESUELTO.** Verificado en `scripts/run_daily.ps1` (commit `4e9e4fa`): `Write-PipelineErrorMarker` ya se invoca en el bloque del guard N≥40 (paso 13), no solo en el de reporte-corto — el flag de escritorio cubre ambos síntomas desde el fix de julio. No requiere trabajo adicional.

## 5. Mecanismo — primera pasada de diagnóstico (2026-08-27, media sesión, solo lectura)

**Discriminador de posición:** correlación de Spearman entre posición del ticker en `data/companies.json` y días presentes en `tech_scores` desde 2026-07-07: **ρ ≈ −0.53** — moderada, no perfecta. Los tickers listados antes tienden a aparecer más días, pero hay ruido claro por categoría (ej. el bloque SaaS/software en posiciones 17-24 cae en bloque, semiconductores y quantum/biotech se mantienen altos pese a posiciones dispersas). No es un cuello de botella secuencial limpio tipo rate-limit por-ticker.

**El hallazgo real no estaba donde se esperaba — la extracción (paso 7) no es el mecanismo.** Tiempos de `logs/scheduler.log`: la segunda llamada Claude (extracción CSV) tarda **7-10 segundos de forma consistente**, sin importar si el resultado es N=0, 10, 21 o 34 — no hay timeout ni degradación proporcional al conteo. El mecanismo está aguas arriba, en la **generación del informe narrativo** (paso 3-4, escrito directamente por el modelo vía Write): el tamaño del `.md` generado correlaciona directamente con la cobertura — 08-19 (9,143 bytes) mencionaba 13/51 tickers y extrajo 0; 08-26 (18,841 bytes) extrajo 34. El extractor del paso 7 es fiel al texto que recibe; el universo simplemente **no llega completo al informe** en la mayoría de los días.

**Mecanismo nombrado, con evidencia — no es rate-limit de API, es presupuesto de salida/atención de la llamada de generación del informe** (la primera llamada Claude, no la segunda): el modelo no cubre las 51 empresas del prompt en una sola pasada narrativa, con una tendencia leve (no absoluta) a priorizar las primeras del prompt y ciertas categorías completas sobre otras. **Sin aislar aún:** si es tope de tokens de salida, un patrón de "me canso de listar" del modelo, o el propio prompt (10,352 chars, tamaño estable) no pidiendo estructura suficiente para forzar cobertura completa.

**Siguiente paso (no hoy):** el discriminador de orden-de-la-pasada que Andrés anotó ya está parcialmente respondido — no hay corte posicional limpio, hay un efecto de cobertura narrativa. El paso pendiente es leer `scripts/generate_daily_prompt.py` (o el que arme el prompt de la llamada 1) para ver si pide explícitamente una tabla/checklist por-ticker (fuerza cobertura) o narrativa libre (no la fuerza) — y si el fix es de prompt (estructura obligatoria), no de reintentos/backoff. Cambia la categoría de fix esperada en la Sección 6 (era "presupuesto/límite secuencial", pasa a candidato más probable: "prompt no fuerza cobertura completa, modelo la resuelve con criterio propio y variable").

**Tercera casa de la flota con la familia de bug stdout/streams-bajo-Windows-sin-consola** (orquestador de trading-platform → Task Scheduler de reversal-system → contrato flapeante stdout/Write-directo de FutureTrends). Deja de ser anécdota de casa — es un patrón estructural transversal a cualquier proceso de la flota que corra desatendido bajo Windows Task Scheduler sin redirección de stream explícita. Merece entrada en el catálogo general de la flota (pendiente, fuera del alcance de este expediente de un solo proyecto).

**Fix mínimo aplicado (parte del commit de este expediente):** el flag `PIPELINE_ERROR.txt` en escritorio, introducido el 07-28 para el síntoma de reporte-corto/escritura-directa, se extiende para disparar también en el guard de N≥40 (ya estaba parcialmente hecho en el mismo commit del 07-28 — `Write-PipelineErrorMarker` se invoca en ambos puntos de fallo de `run_daily.ps1`). Es el canal mínimo, no resuelve la causa — solo la hace visible sin tener que ir a leer el log.

## 6. Estado y siguiente paso

**ABIERTO — causa acotada a una familia (cobertura narrativa del paso 3-4), mecanismo exacto sin aislar, sin fix aplicado todavía.** No cerrar sin: (a) leer el generador de prompt de la llamada 1 para confirmar si pide estructura por-ticker o narrativa libre — determina si el fix es de prompt o de reintentos; (b) aplicar el fix que la lectura indique y verificar N≥40 sostenido una semana antes de declarar cerrado con fecha de fin; (c) decidir si `compute_validation.py` (cuando se construya) pondera o excluye las fechas de este tramo por cobertura declarada. El canal (d) ya está resuelto — ver Sección 4.
