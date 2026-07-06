# Handoff — FutureTrends Intelligence System
*Actualizado: 2026-07-06*

---

## Estado del proyecto

Dos líneas de trabajo activas y desacopladas:

1. **Producción (Phase 1, universo de 51)**: pipeline diario autónomo vía Task Scheduler. Prompt v2 corriendo desde 2026-06-01. **El paso de scoring automático está roto desde 2026-06-25** — ver Deuda técnica Alta abajo. Los reportes siguen publicándose (probablemente generados o completados manualmente), pero `tech_scores` no recibe filas nuevas desde entonces.
2. **P1.5 (expansión a 136 empresas)**: en curso, no integrada a producción. `data/companies.json` sigue en 51 — el universo de 136 vive solo en `data/filings/universe_selection_20260702.json` + manifiestos, y aún no ha pasado el gate de extracción limpia (Etapa 2) ni existe el extractor de keywords (Etapa 3).

Próximo hito de producción: gate P1→P2 requería 30 días sin fallos desde 2026-05-22 (~2026-06-22) — **ese gate está probablemente invalidado** por la ruptura del 06-25, hay que auditar si se cumplió antes de la ruptura o si el conteo se reinicia.

---

## Lo que se hizo en esta sesión (2026-07-06)

| Item | Estado |
|------|--------|
| Auditoría de estado real (git log, DB, scheduler.log) para regenerar este handoff | ✅ |
| **Hallazgo crítico**: pipeline diario de scoring roto desde 2026-06-25 | ✅ detectado, ⏳ sin diagnosticar causa raíz |
| Continuación de P1.5 Etapa 2 (validador de gates, ver sección propia) | ⏳ en curso, ver "P1.5 — estado detallado" |

---

## 🔴 Hallazgo crítico: pipeline de scoring roto desde 2026-06-25

`tech_scores` tiene 658 filas `prompt_version='v2'`, última fecha **2026-06-24**. Sin filas desde entonces (12 días hábiles sin scorear al 2026-07-06).

`logs/scheduler.log` muestra que cada run desde **2026-06-29** (el log no cubre 06-25→06-28) termina con:
```
ERROR: reporte demasiado corto (672-1137 bytes) - ver $env:TEMP\fa_report_YYYYMMDD.md
```
Esto aborta el pipeline en el paso 3 (llamada Claude CLI → `reports/YYYYMMDD.md`), por lo que nunca llega al paso 4 (extracción de `SCORES_CSV_START/END` → `tech_scores`).

Sin embargo, existen `reports/20260629.md` … `reports/20260706.md` con contenido real (167-191 líneas, no vacíos) como **archivos untracked** — es decir, alguien (el usuario o una sesión de Claude Code manual) generó esos reportes por fuera del pipeline automático después de que el run fallara. **No hay CSV de scores asociado a ellos** — probablemente `tech_scores` quedó congelado en 06-24 aunque los reportes de texto sí se sigan produciendo y publicando.

**No diagnosticado aún**: por qué el output de Claude CLI vía stdin colapsa a <2000 bytes desde el 06-25. Candidatos sin verificar: cambio en el prompt (`prompts/daily.md` v2), cambio de versión del CLI, timeout/truncamiento del stdin, o un cambio de entorno en la tarea programada (S4U). **Este es el ítem de mayor prioridad de esta lista** — cada día que pasa sin arreglarlo es un día de N perdido para el futuro gate de validación estadística.

---

## Arquitectura actual (producción, 51 empresas)

### Pipeline diario (`run_daily.ps1`)
1. Carga `.env` y exporta tendencias activas desde `tech_scores`
2. Construye prompt con fechas y tendencias → `$env:TEMP\fa_prompt_YYYYMMDD.md`
3. Claude CLI vía stdin → reporte `reports/YYYYMMDD.md` (umbral mínimo 3000 bytes) — **falla aquí desde 06-25**
4. Segunda llamada Claude → extrae bloque `SCORES_CSV_START/END` → parser Python → `tech_scores` (con `prompt_version`) — **no se alcanza desde 06-25**
5. Elimina bloque CSV del `.md`
6. `fetch_prices.py` → precios de cierre ajustados → tabla `prices`
7. `generate_comparative.py` → `reports/comparative_YYYYMMDD.md`
8. `deploy_report.ps1` → genera `reports/index.html` + git push → Cloudflare Pages (~20s)

### Archivos clave
| Path | Descripción |
|------|-------------|
| `scripts/run_daily.ps1` | Script principal de automatización |
| `scripts/deploy_report.ps1` | Genera HTML + git push |
| `scripts/fetch_prices.py` | Descarga cierres vía yfinance |
| `scripts/generate_comparative.py` | Comparativo de scores y fuentes entre días |
| `prompts/daily.md` | Prompt master (actualmente v2) |
| `data/fa.db` | SQLite: `tech_scores`, `prices`, `companies`, `trends` |
| `data/companies.json` | Universo de 51 empresas (producción — NO es el de P1.5) |
| `reports/YYYYMMDD.md` | Reportes diarios |
| `reports/comparative_YYYYMMDD.md` | Comparativos diarios |
| `reports/index.html` | Viewer HTML (Cloudflare Pages) |
| `logs/scheduler.log` | Log del Task Scheduler — revisar aquí primero ante cualquier falla |

### Task Scheduler
- Nombre: `\FutureAnalysis\FutureAnalysis_DailyRun`
- Horario: lunes-viernes 7:00 AM, LogonType=S4U

### DB (`data/fa.db`)
| Tabla | Registros | Fechas disponibles |
|-------|-----------|-------------------|
| `tech_scores` | 816 (158 v1 + 658 v2) | v1: 2026-05-26→05-29 · v2: 2026-06-01→**06-24 (congelado)** |
| `prices` | 715 | 2026-05-27 → 2026-07-01 |
| `companies` | 51 | universo fijo de producción |

Distribución v2 por día revisada: estable en 48-51 empresas scoreadas/día, sin señales de umbral demasiado estricto (<3) ni demasiado laxo (>10) en las tendencias — el chequeo pendiente de la ventana 06-10→06-16 se dio por bueno retroactivamente, no hay anomalía que resolver ahí. El problema real resultó ser la ruptura del 06-25, no la calibración del umbral.

### Infra
- GitHub: `https://github.com/actrading1980/future-trends`
- Cloudflare Pages: `future-trends.pages.dev`

### Deuda técnica activa
| Item | Severidad | Nota |
|------|-----------|------|
| Pipeline de scoring roto desde 2026-06-25 (`tech_scores` sin filas nuevas) | **Alta** | Ver sección de hallazgo crítico arriba. Bloquea todo cálculo de N para el gate estadístico. |
| Gate P1→P2 (30 días sin fallos) posiblemente invalidado por la ruptura | Alta | Auditar si se cumplió antes del 06-25 o si el contador debe reiniciarse tras el fix |
| Schema de 3 estados (`scored/no_catalyst/not_in_universe`) no implementado | Media | Sigue vigente y ahora es más urgente: cada día v2 sin `score_status` real infla el N futuro del IC. Implementar junto con el próximo cambio de schema por `universe_version` (ver P1.5), no por separado — evitar dos migraciones de schema seguidas. |
| Sparklines + tab Histórico en el viewer HTML | Media | `prices` ya tiene >30 días de histórico; implementar cuando el usuario lo active |
| `prices` con gaps ocasionales (ej. cuando el run falla antes del paso 6) | Baja | Dependiente del fix del hallazgo crítico |
| Horizonte "Spearman ~2026-11-26" del handoff anterior | **Obsoleto — eliminado** | Ese horizonte venía de la spec v1.0 pre-revisión. El vigente es el gate F3 de `specs/validation_engine_v1.1.md` (~12 meses tras P1.5 operativa, Fama-MacBeth/Newey-West sobre IC diario, no Spearman pooled). No reintroducir la fecha de noviembre. |

---

## P1.5 — estado detallado (expansión a 136 empresas, no integrada a producción)

### Decisiones ya tomadas (no re-litigar)
- **ASML**: diferido a lectura manual de documento abierto, dentro de la sesión de inspección única — no es una decisión pendiente. Pista dejada: el 20-F de ASML es el "Annual Report 2025" completo estilo europeo (IFRS integrado); "Item 4"/"Item 3" literales no aparecen en el cuerpo real, solo un mapeo formal cerca de la posición ~1.11M de un corpus de ~1.15M caracteres. Los headings reales de negocio/riesgo ("Our business", "Risk and security") son indistinguibles por regex de ~126 repeticiones del mismo texto en el menú de navegación — requiere lectura directa, no más arqueología de patrones.
- **Sesión de inspección única**: agrupa 9 piezas — INTC (8 fragmentos), NVEC (8 fragmentos, confirmar como excepción de piso tipo "IBM del piso"), INCY (veredicto pendiente sobre cuál texto es correcto), TSM/ARM/BABA/BIDU/SE (fragmentos ya generados y limpios), y ASML (pendiente, ver arriba).
- **Filings `INCORPORADO_POR_REFERENCIA`**: se tratarán en Etapa 3 con extracción solo de Item 1 + flag de metadata `keywords_coverage='item1_only'`.
- **Fix de separadores em/en-dash** (commit `65c16d7`) subió el pase automático de 78.46% a 93.08% (121/130) y de paso resolvió IBM y CSCO — pendiente diff entre pasadas (antes/después del fix) para confirmar que ningún filing previamente limpio cambió de resultado por el fix, más allá de BE/IBM/CSCO ya explicados.

### Pendientes mecánicos (antes de la spec del extractor)
1. **INTC**: falta escribir `metodo='manual_heading_no_item'` (o equivalente) en el registro persistido — hoy `data/filings/intc_manual_extract.json` solo tiene el texto extraído, sin metadata de método.
2. **`HEADER_SIN_LABEL_ITEM`**: falta definir la firma de detección mecánica antes de promoverlo al enum cerrado de Gate 5 (`filing_section_validator_v1.md`) — criterio ya acordado en palabras: "los literales 'Item 1'/'Item 1A' existen solo concentrados en una región (índice cruzado del final), sin ningún par válido con gap suficiente en el cuerpo", falta traducirlo a chequeo de código.
3. **Diff entre pasadas pre/post fix em-dash**: correr y confirmar que solo BE/IBM/CSCO cambiaron de estado.
4. **Tabla de estado terminal de las 136 empresas** (limpio/cola/incorporado/manual/pendiente) como insumo directo de la spec de Etapa 3.
5. Empaquetar los 9 ítems de inspección en texto plano para pegar en el chat (no vía archivo — confirmado que las herramientas de archivo no llegan al cliente del usuario).
6. Re-correr `run_full_pass.py` una vez cerrados INTC/INCY/ASML para el conteo final autoritativo.

### Siguiente after eso
Borrador de la spec del extractor de keywords (Etapa 3): trata contenido del filing como dato-nunca-instrucción, patrón diff-nunca-escribe (como `company_update.md`), taxonomía cerrada con blacklist de términos genéricos, asignación de categoría dual-fuente (LLM extractor vs. categoría de origen del ETF, con discrepancia a cola de revisión), validación contra las 51 empresas curadas manualmente antes de confiar en las 85 nuevas, y campo de metadata que registre cuál de las 4 vías de extracción (edgartools / regex fallback / cross-check corroborado / manual) produjo el texto de cada filing.

---

## Próximos pasos (en orden de prioridad real)

### 1. Diagnosticar y arreglar el pipeline de scoring roto (06-25→hoy)
Revisar `$env:TEMP\fa_report_YYYYMMDD.md` de un run reciente fallido, comparar con `prompts/daily.md`, y determinar si el CLI está devolviendo error/truncamiento silencioso. Esto bloquea el N de cualquier validación futura — es la prioridad real de producción.

### 2. Cerrar los pendientes mecánicos de P1.5 (lista de 6 arriba)
Antes de la sesión de inspección y antes de la spec del extractor.

### 3. Sesión de inspección única (9 piezas)
Requiere tu firma explícita — no se auto-aprueba nada.

### 4. Schema de 3 estados + `universe_version` (juntos, una sola migración)
Ahora más urgente por el gap del pipeline; conviene resolver junto con la integración eventual del universo de 136.

### 5. Borrador de spec del extractor de keywords (Etapa 3)
Puede avanzar en paralelo a la sesión de inspección.

### 6. Sparklines + tab Histórico en el viewer
Baja prioridad, activar cuando el usuario lo pida.

### 7. Validación estadística (gate F3)
Horizonte: ~12 meses desde P1.5 operativa, según `specs/validation_engine_v1.1.md` — no antes. Fama-MacBeth/Newey-West sobre IC diario, gate ≥0.05, filtrando `prompt_version='v2'` y (cuando exista) `universe_version`.

---

## Comandos operativos

```powershell
# Lanzar run manual
powershell.exe -ExecutionPolicy Bypass -File C:\projects\FutureTrends\scripts\run_daily.ps1

# Ver log del scheduler (revisar aquí primero ante cualquier falla)
Get-Content C:\projects\FutureTrends\logs\scheduler.log -Tail 30

# Generar comparativo manualmente para una fecha
python3 C:\projects\FutureTrends\scripts\generate_comparative.py 2026-07-06

# Deploy manual si no se lanzó solo
powershell.exe -ExecutionPolicy Bypass -File C:\projects\FutureTrends\scripts\deploy_report.ps1 `
  -ReportFile C:\projects\FutureTrends\reports\20260706.md `
  -ProjectDir C:\projects\FutureTrends

# P1.5: correr el pase completo de gates de extraccion
python3 C:\projects\FutureTrends\scripts\run_full_pass.py

# P1.5: control negativo de Gate 3 (antes de tocar el umbral de asimetria)
python3 C:\projects\FutureTrends\scripts\negative_control_gate3.py
```

---

*Spec autorizada (producción): `C:\projects\FutureTrends\FutureTrendsAnalysis_v3_reviewed.md` (v3.1)*
*Spec autorizada (P1.5 validación): `C:\projects\FutureTrends\specs\validation_engine_v1.1.md`*
*Spec autorizada (P1.5 extracción): `C:\projects\FutureTrends\specs\filing_section_validator_v1.md` (v1.2, congelada)*
