# Handoff — FutureTrends Intelligence System
*Actualizado: 2026-07-06*

---

## Estado del proyecto

Dos líneas de trabajo activas y desacopladas:

1. **Producción (Phase 1, universo de 51)**: pipeline diario autónomo vía Task Scheduler. Prompt v2 corriendo desde 2026-06-01. **Causa raíz del corte 2026-06-25→07-03 diagnosticada y fixeada esta sesión** (ver hallazgo crítico abajo); el hueco real quedó reducido a solo 2 días (06-25, 06-26) tras verificar e ingerir reportes generados manualmente durante la ventana. Pendiente: confirmar con el run de mañana (07-07) que el fix sostiene.
2. **P1.5 (expansión a 136 empresas)**: en curso, no integrada a producción. `data/companies.json` sigue en 51 — el universo de 136 vive solo en `data/filings/universe_selection_20260702.json` + manifiestos, y aún no ha pasado el gate de extracción limpia (Etapa 2) ni existe el extractor de keywords (Etapa 3).

Próximo hito de producción: gate P1→P2 requería 30 días sin fallos desde 2026-05-22 (~2026-06-22) — **ese gate está probablemente invalidado** por la ruptura del 06-25, hay que auditar si se cumplió antes de la ruptura o si el conteo se reinicia.

---

## Lo que se hizo en esta sesión (2026-07-06)

| Item | Estado |
|------|--------|
| Auditoría de estado real (git log, DB, scheduler.log) para regenerar este handoff | ✅ |
| **Hallazgo crítico**: pipeline diario de scoring roto desde 2026-06-25 | ✅ detectado y diagnosticado |
| Causa raíz: trust dialog case-sensitive (`C:\` vs `c:\`) en `.claude.json` | ✅ fix aplicado |
| Fix: `.claude.json` — ambas variantes de ruta marcadas `hasTrustDialogAccepted: true` | ✅ (backup en `.claude.json.bak_20260706`) |
| Fix: `run_daily.ps1` — `$ProjectDir` normalizado a minúscula | ✅ |
| Fix: `WorkingDirectory` de la tarea programada a minúscula | ⏳ requiere PowerShell elevada — comando dado al usuario, no ejecutado aún |
| Regla 2 (`gap_spanning`) implementada en `generate_comparative.py` | ✅ |
| Regla 3 (aserción fail-loud `inserted >= 40`) implementada en `run_daily.ps1` paso 8b | ✅ |
| Verificación de procedencia de los 6 reportes untracked (06-29→07-06) e ingesta con `day_quality='manual_session_verified'` | ✅ 202 registros ingeridos |
| Continuación de P1.5 Etapa 2 (validador de gates, ver sección propia) | ⏳ en curso, ver "P1.5 — estado detallado" |

---

## 🔴 Hallazgo crítico: pipeline de scoring roto 2026-06-25→07-03 — RESUELTO (pendiente confirmar con run de 07-07)

### Causa raíz (confirmada, no hipótesis)
`.claude.json` tenía dos entradas para el mismo directorio, distintas solo por mayúscula/minúscula de la unidad:
- `C:/projects/FutureTrends` → `hasTrustDialogAccepted: false`
- `c:/projects/FutureTrends` → `hasTrustDialogAccepted: true`

La sesión interactiva usa `c:\...` (confiada). La tarea programada (S4U) tenía `WorkingDirectory: C:\projects\FutureTrends` (mayúscula, no confiada) — confirmado con `Get-ScheduledTask`. Con el workspace no confiado, el CLI ignora `permissions.allow` de `.claude/settings.json` y el modelo, bajo permisos por defecto, usa la herramienta Write para guardar el reporte él mismo en vez de devolverlo por stdout — dejando solo un resumen corto en el stdout que el wrapper mide (`$ReportSize -lt 3000` en `run_daily.ps1`), que lo rechaza como "reporte demasiado corto" y aborta antes de llegar al INSERT en `tech_scores`.

Confirmado con `logs/scheduler.log`: último éxito **2026-06-24** (26,585 bytes, 51 insertados), primer fallo **2026-06-25** (1,035 bytes). Fecha exacta y estable, consistente con un cambio de entorno discreto, no degradación gradual.

**Sin verificar (hipótesis, no hallazgo)**: que el gate de confianza case-sensitive haya aparecido por una actualización del CLI justo el 2026-06-25. Versión actual instalada: `2.1.201`. No se verificó fecha de instalación/changelog — si se quiere cerrar esta pregunta, comparar con el historial de npm (`npm list -g --depth=0` + fecha de mtime del paquete) o el changelog de Claude Code alrededor de esa fecha.

### Fixes aplicados (2026-07-06)
1. `.claude.json`: ambas variantes de ruta marcadas `hasTrustDialogAccepted: true` (backup en `C:\Users\tatym\.claude.json.bak_20260706`). Frágil si el archivo se regenera — de ahí el fix #2.
2. `scripts/run_daily.ps1`: `$ProjectDir` normalizado a `c:\projects\FutureTrends` (minúscula) — el `Set-Location $ProjectDir` del paso 4 fija el cwd real al invocar el CLI, así que esto por sí solo ya cierra el bug aunque la tarea programada no se toque.
3. **Pendiente de que el usuario lo corra** (requiere PowerShell elevada, acceso denegado a este agente): apuntar `WorkingDirectory` de la tarea `\FutureAnalysis\FutureAnalysis_DailyRun` también a minúscula:
   ```powershell
   $task = Get-ScheduledTask -TaskPath '\FutureAnalysis\' -TaskName 'FutureAnalysis_DailyRun'
   $action = $task.Actions[0]
   $action.WorkingDirectory = 'c:\projects\FutureTrends'
   Set-ScheduledTask -TaskPath '\FutureAnalysis\' -TaskName 'FutureAnalysis_DailyRun' -Action $action
   ```
4. Regla 2 (`gap_spanning`) implementada en `scripts/generate_comparative.py`: calcula `gap_days` contra la fecha real anterior en DB; si `gap_days > 4`, marca banner de advertencia en el `.md` y escribe `reports/comparative_YYYYMMDD.json` con `{gap_days, gap_spanning}` para que el análisis de H2 filtre sin parsear markdown.
5. Regla 3 (fail-loud) implementada en `scripts/run_daily.ps1` paso 8b: si `inserted < 40`, `ERROR` explícito en el log + `exit 1`. Antes, un fallo silencioso en el INSERT no abortaba nada aguas abajo.

### Criterios de éxito del run de 2026-07-07 (escritos hoy, antes del run)
Los cuatro deben cumplirse para dar el fix por confirmado:
- [ ] Reporte >20,000 bytes (no el resumen corto de ~1,000-2,700 bytes de los fallos)
- [ ] ~51 filas insertadas en `tech_scores` con `date='2026-07-07'` (aserción del paso 8b en verde, sin `ERROR` en el log)
- [ ] `logs/scheduler.log` sin la línea `ERROR: reporte demasiado corto`
- [ ] `reports/comparative_20260707.json` con `gap_spanning=false` (comparando contra 2026-07-06, 1 día — si comparara contra una fecha más vieja, algo más sigue roto)

### Estado final del hueco tras verificación de procedencia
Los 6 reportes untracked del rango (06-29, 06-30, 07-01, 07-02, 07-03, 07-06) se verificaron con dos criterios: (a) `mtime` del archivo dentro de ~10 minutos del timestamp de ejecución en `scheduler.log` (contemporáneo, no generado después en lote) y (b) sin referencias a fechas posteriores a la propia dentro del texto (sin look-ahead). Ambos pasaron para los 6. Se ingirieron con `python3 scripts/ingest_manual_reports.py` → 202 registros con `day_quality='manual_session_verified'` (columna nueva en `tech_scores`), **reemplazando el supuesto hueco de 12 días por uno real de solo 2 días: 2026-06-25 y 2026-06-26** (para esas dos fechas no existe ningún reporte, ni siquiera parcial — ahí el hueco se queda como hueco, sin generar nada retroactivo, tal como manda la Regla 1).

**Nota sobre cobertura parcial**: 3 de los 6 días ingeridos tienen N menor a 51 (reportes más cortos → menos filas de CSV extraíbles): 07-02 (12), 07-03 (19), 07-06 (18). Esto no es un hueco pero sí reduce el N efectivo de esos días para cualquier cálculo — tenerlo presente en el futuro cálculo de IC/F3 al filtrar por `day_quality`.

### 🔒 Reglas pre-registradas sobre el hueco (fijadas 2026-07-06, antes de reanudar el pipeline)

**Regla 1 — el hueco NO se rellena retroactivamente.** Vigente solo para **2026-06-25 y 2026-06-26** (los únicos dos días sin ningún reporte, ni siquiera parcial, tras la verificación de procedencia de arriba). No generar scores para esas dos fechas con fecha retroactiva bajo ninguna circunstancia — un score para el 25-jun generado después de esa fecha lo produce un modelo que ya conoce eventos posteriores, look-ahead invisible en la DB. Si algún día se quiere marcar explícitamente el hueco en `tech_scores` (en vez de dejarlo como ausencia), usar `day_quality='pipeline_gap'` — pero sin insertar scores inventados para llegar ahí.

**Regla 2 — deltas que cruzan un hueco no son eventos.** Implementada en `scripts/generate_comparative.py` (ver Fixes aplicados arriba): cualquier comparativo cuyo `gap_days > 4` se marca `gap_spanning=true` en `reports/comparative_YYYYMMDD.json` y debe excluirse del conteo de eventos Tipo A+/A− de H2. El primer comparativo afectado será el que compare contra 2026-06-24 saltando el hueco de 06-25/06-26 — identificarlo por el JSON, no asumir cuál fecha es.

**Regla 3 — todo escritor diario debe fallar ruidoso, no silencioso.** Implementada para `tech_scores` en `run_daily.ps1` paso 8b (aserción `inserted >= 40`). Patrón generalizable a cualquier otro escritor diario de este proyecto (y ya visto antes en SPYCAST: `hybrid_5min_updater`, `exhaustion_updater`, `shadow_outcome`) — el fallo de 06-25→07-03 fue invisible porque los reportes de texto seguían publicándose mientras el INSERT simplemente no ocurría.

**Nota sobre el gate F3**: el hueco no mueve su reloj — esos días son del tramo `universe_version=1` que F3 ya excluye (cuenta desde P1.5 operativa con universo completo). El daño real fue en diagnósticos exploratorios F1/F2 y en el arranque limpio de H2 (Regla 2).

---

## Arquitectura actual (producción, 51 empresas)

### Pipeline diario (`run_daily.ps1`)
1. Carga `.env` y exporta tendencias activas desde `tech_scores`
2. Construye prompt con fechas y tendencias → `$env:TEMP\fa_prompt_YYYYMMDD.md`
3. Claude CLI vía stdin → reporte `reports/YYYYMMDD.md` (umbral mínimo 3000 bytes) — **falló aquí 06-25→07-03, fix aplicado, confirmar con run de 07-07**
4. Segunda llamada Claude → extrae bloque `SCORES_CSV_START/END` → parser Python → `tech_scores` (con `prompt_version`) — paso 8b añade aserción fail-loud (`inserted >= 40`)
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
| `tech_scores` | 1018 (158 v1 + 860 v2) | v1: 2026-05-26→05-29 · v2: 2026-06-01→06-24 (pipeline normal) + 2026-06-29→07-06 (`day_quality='manual_session_verified'`, N parcial en 3 de 6 días — ver hallazgo crítico) |
| `prices` | 715 | 2026-05-27 → 2026-07-01 |
| `companies` | 51 | universo fijo de producción |

Distribución v2 por día revisada: estable en 48-51 empresas scoreadas/día, sin señales de umbral demasiado estricto (<3) ni demasiado laxo (>10) en las tendencias — el chequeo pendiente de la ventana 06-10→06-16 se dio por bueno retroactivamente, no hay anomalía que resolver ahí. El problema real resultó ser la ruptura del 06-25, ya diagnosticada y fixeada (ver hallazgo crítico arriba).

### Infra
- GitHub: `https://github.com/actrading1980/future-trends`
- Cloudflare Pages: `future-trends.pages.dev`

### Deuda técnica activa
| Item | Severidad | Nota |
|------|-----------|------|
| Pipeline de scoring roto 2026-06-25→07-03 | **Alta → fixeado, confirmar 07-07** | Causa raíz + fix en sección de hallazgo crítico arriba. No dar por cerrado hasta que el run de mañana cumpla los 4 criterios de éxito. |
| Gate P1→P2 (30 días sin fallos) posiblemente invalidado por la ruptura | Alta | Auditar si se cumplió antes del 06-25 o si el contador debe reiniciarse tras el fix |
| `.claude.json` puede regenerarse y perder el `hasTrustDialogAccepted=true` de la variante mayúscula | Media | Mitigado en paralelo normalizando `$ProjectDir` en `run_daily.ps1` a minúscula — pero si se toca `.claude.json` de nuevo, revisar ambas variantes de ruta |
| 3 de los 6 días ingeridos manualmente (07-02, 07-03, 07-06) tienen N parcial (12, 19, 18 de 51) | Media | No es un hueco pero reduce el N efectivo — filtrar/ponderar por `day_quality` en cualquier cálculo futuro de IC |
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

### 1. Confirmar el fix del pipeline con el run de 2026-07-07
Ejecutar (o dejar correr la tarea programada) y verificar los 4 criterios de éxito de la sección de hallazgo crítico. Si falla de nuevo, el siguiente sospechoso es que `.claude.json` se haya regenerado sin la variante mayúscula confiada, o que el `WorkingDirectory` de la tarea programada (aún no corregido, requiere PowerShell elevada) esté interactuando con algo más. Correr también el comando de `Set-ScheduledTask` pendiente (ver arriba) cuando se tenga una sesión elevada.

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

# Re-ingesta de reportes manuales verificados (NO usar para nada mas alla del rango 06-29->07-06
# ya procesado -- ver Regla 1, prohibido generar retroactivo)
python3 C:\projects\FutureTrends\scripts\ingest_manual_reports.py

# Fix pendiente de WorkingDirectory de la tarea (requiere PowerShell elevada)
$task = Get-ScheduledTask -TaskPath '\FutureAnalysis\' -TaskName 'FutureAnalysis_DailyRun'
$action = $task.Actions[0]; $action.WorkingDirectory = 'c:\projects\FutureTrends'
Set-ScheduledTask -TaskPath '\FutureAnalysis\' -TaskName 'FutureAnalysis_DailyRun' -Action $action
```

---

*Spec autorizada (producción): `C:\projects\FutureTrends\FutureTrendsAnalysis_v3_reviewed.md` (v3.1)*
*Spec autorizada (P1.5 validación): `C:\projects\FutureTrends\specs\validation_engine_v1.1.md`*
*Spec autorizada (P1.5 extracción): `C:\projects\FutureTrends\specs\filing_section_validator_v1.md` (v1.2, congelada)*
