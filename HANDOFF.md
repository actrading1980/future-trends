# Handoff — FutureTrends Intelligence System
*Actualizado: 2026-09-30*

---

## Estado del proyecto

- **Producción (Phase 1, universo de 51):** el pipeline diario funciona y **vuelve al prompt v2 desde el run del 2026-09-30**, tras revertir `ff380b6`. v2 es el mal menor conocido, no un régimen sano.
- **P1.5 (universo de 136):** sin avances desde julio. Está bloqueada en la sesión humana de inspección.
- **Camino crítico:** dos sesiones humanas (inspección P1.5 + triaje de 98 notas MANUAL) → migración v3 como un único corte de régimen. El reloj del gate F3 no arranca hasta entonces.

---

## Lo que se hizo en esta sesión (2026-09-29 → 2026-09-30)

| Item | Estado |
|------|--------|
| Diagnóstico de `trends.json` vacío: **no es regresión del 22-sep; roto desde 2026-05-27**. `''ticker''` dentro de un string PS con comillas dobles → error de sintaxis SQLite, oculto por `except` desnudo | ✅ |
| Hallazgo asociado: **las notas carry-forward nunca llegaron al prompt (desde 2026-06-02)**. PS 5.1 elimina las `"` embebidas → `NameError` → siempre `(ninguna)`. 254 notas escritas, 0 leídas | ✅ |
| Fail-loud en ambos pasos: `ERROR` con el traceback real y `WARN` con conteo 0 (`b4f371e`). El contenido del prompt no cambia | ✅ |
| Serie **homogénea** en falta de contexto (v1/v2/v2.1): no se marca ningún tramo como `trends_context_lost` | ✅ |
| Sub-régimen **v2.1** (`ff380b6`, 09-23→09-29) registrado: 204 filas re-etiquetadas; cobertura efectiva 6.3/día frente a 24.2 en v2 (relleno 50/0) | ✅ |
| Adenda en `specs/validation_engine_v1.1.md` (puntos 1-7): regla 50/0 = `no_catalyst` en v2.1, frontera v1/v2 = **2026-06-01** (por la longitud del prompt en el log), hueco 09-25, reversión | ✅ |
| **Revert de `ff380b6`** (`ae7a90d`): prompt v2 exacto, 10352 chars verificados en seco. `.gitattributes` `eol=lf` para `prompts/*.md` (el revert con autocrlf había dejado CRLF: 10551 chars) | ✅ |
| Incidente N40 **cerrado sin causa raíz establecida** para el onset del 07-07 (el prompt no cambió ese día). La narrativa de julio (`$Date7d` / notas congeladas) era falsa | ✅ |
| Filings P1.5: diff por filing de la pasada 07-03 → **solo cambia BE** (fix em-dash `65c16d7`), 121/130. IBM/CSCO no se mueven. Commit `9797ead` + tabla §6 actualizada | ✅ |
| `scripts/build_context.py`: continuidad (opción b: parseo determinista de tendencias de secciones 4/5 + notas AUTO con tope de 14 días). **En seco, sin conectar** | ✅ |
| `docs/v3_migration_notes.md`: requisitos de v3 con motivación citada (`no_catalyst`, continuidad, bump de versión, salud >24h) | ✅ |
| Verificar el primer run v2 (2026-09-30) con los 3 criterios pre-fijados | ⏳ |

---

## Arquitectura actual

### Pipeline diario (`scripts/run_daily.ps1`)
Task Scheduler `\FutureAnalysis\FutureAnalysis_DailyRun`, lunes a viernes 7:00, LogonType=S4U. Pasos: tendencias (rotas, WARN) → notas (rotas, ERROR) → prompt → Claude CLI → segunda llamada con CSV → `tech_scores` (etiqueta `prompt_version` **hardcodeada en el INSERT, hoy `'v2'`**) → guard N≥40 (alarma sin abortar) → precios → notas → comparativo → `deploy_report.ps1` (git push → Cloudflare Pages).

**Estado esperado del log desde 2026-09-30 (no son incidentes):**
- `ERROR: exportacion de tendencias fallo` + `WARN: trends.json actualizado: 0 entradas`
- `ERROR: carga de notas carry-forward fallo` + `WARN: notas carry-forward: 0 inyectadas`
- Guard N≥40 disparando casi a diario (propio de v2)

### Regímenes de `prompt_version` en `tech_scores`
| Versión | Fechas | Prompt | Nota |
|---|---|---|---|
| v1 | 2026-05-26 → 05-29 | 9806 chars | anexo exploratorio |
| v2 | 2026-06-01 → 09-21, y desde 2026-09-30 | 10156 (06-01..02) / 10352 | cobertura efectiva ~24/día; onset de caída 07-07 sin causa |
| v2.1 | 2026-09-23 → 09-29 | 12183 | paréntesis cerrado; 50/0 = `no_catalyst` |

### Deuda técnica activa
| Item | Severidad | Nota |
|------|-----------|------|
| Sin contexto de continuidad en el prompt (tendencias + notas) | Alta | Arreglo listo en `build_context.py`; se activa **solo** con la migración v3 (corte único pre-registrado) |
| Cobertura v2 degradada desde 2026-07-07 sin causa raíz | Alta | Aceptado como mal conocido hasta v3 (`no_catalyst` explícito). Expediente cerrado: `docs/incident_guard_n40_coverage_20260827.md` |
| Schema de 3 estados sin implementar (`score_status='scored'` en todo) | Alta | Va en la migración v3, junto con `universe_version` |
| 98 notas MANUAL sin triar (~12.4K chars; duplicarían el prompt) | Media | Sesión humana, prerrequisito de la activación |
| `PIPELINE_ERROR.txt` se borra al arrancar cada run (`run_daily.ps1:33-34`) | Media | Un fallo solo es visible hasta el siguiente run (el 09-25 se perdió así). Solución: panel de salud con la serie completa |
| `prompt_version` hardcodeada en el INSERT | Media | Cualquier cambio de prompt exige bump manual (`ff380b6` no lo hizo) |
| Python inline en `.ps1` con comillas | Media | Patrón roto en PS 5.1: usar `.py` separado (como `build_context.py`) |
| `WorkingDirectory` de la tarea sigue en `C:\` mayúscula | Baja | Mitigado por `$ProjectDir` en minúscula; los runs funcionan. Comando abajo (requiere PowerShell elevada) |
| Gate P1→P2: decisión pendiente sobre si los días inválidos reinician el contador | Baja | Criterio de integridad pre-registrado el 2026-07-07; la decisión es del usuario |
| Sparklines + tab Histórico en el viewer | Baja | Cuando se pida |

---

## P1.5 — estado (sin cambios desde 2026-07-06, salvo el diff de filings)

- Pasada de filings: **121/130 limpios (93.08%)** tras v1.2 + fix em-dash. El diff por filing está verificado (solo BE).
- **Sesión de inspección única (9 piezas):** INTC (8 fragmentos), NVEC (8, ¿excepción de piso?), INCY (veredicto), TSM/ARM/BABA/BIDU/SE (fragmentos limpios), ASML (lectura manual del 20-F).
- **Pendientes mecánicos:** metadata `metodo` de INTC en `data/filings/intc_manual_extract.json`; firma de `HEADER_SIN_LABEL_ITEM` para Gate 5; tabla de estado terminal de las 136; empaquetar las 9 piezas en texto plano para el chat; re-run de `run_full_pass.py` tras INTC/INCY/ASML.
- Después: spec del extractor de keywords (Etapa 3).

---

## Próximos pasos (en orden de prioridad)

### 1. Verificar el run del 2026-09-30 (primer run v2 revertido)
Criterios pre-fijados (adenda 7):
- (a) `prompt generado (10352 chars)` en `logs/scheduler.log`
- (b) filas nuevas con `prompt_version='v2'`
- (c) sin relleno: unas 13-40 filas

Lectura de (c): 51 filas con unas 25 de 50/0 cabe dentro de v2 (pasó el 09-03). 51 filas con 45 o más de 50/0 sería información nueva. Mirar 3-4 días, no uno. De paso, confirmar que el fail-loud da los ERROR/WARN esperados y que el deploy subió los commits de esta sesión.

### 2. Sesión humana A: inspección P1.5 (9 piezas)
Único bloqueante del universo de 136 y, por tanto, del reloj del gate F3.

### 3. Sesión humana B: triaje de las 98 notas MANUAL
Decidir qué sigue vigente, qué caduca y qué se archiva. Prerrequisito para activar `build_context.py`.

### 4. Migración v3 (corte único)
Continuidad + 3 estados + universo 136 + prompt v3 con cláusula `no_catalyst` + bump de versión, con pre-registro fechado antes del primer run. Requisitos en `docs/v3_migration_notes.md`.

### 5. Panel de salud con la serie completa de días
Para que huecos como el del 09-25 sigan visibles después de las 24 h.

---

## Comandos operativos

```powershell
# Log del scheduler (el archivo es UTF-16)
Get-Content C:\projects\FutureTrends\logs\scheduler.log -Tail 30

# Composición del día: N total y filas de relleno 50/0
C:\Users\tatym\AppData\Local\Programs\Python\Python313\python.exe -c "import sqlite3;db=sqlite3.connect(r'C:\projects\FutureTrends\data\fa.db');print(db.execute('SELECT date,prompt_version,COUNT(*),SUM(score=50 AND intensity=0) FROM tech_scores WHERE date>=''2026-09-29'' GROUP BY 1,2').fetchall())"

# Vista previa del contexto de continuidad (en seco)
C:\Users\tatym\AppData\Local\Programs\Python\Python313\python.exe C:\projects\FutureTrends\scripts\build_context.py --as-of 2026-09-30

# Run manual
powershell.exe -ExecutionPolicy Bypass -File C:\projects\FutureTrends\scripts\run_daily.ps1

# P1.5: pasada completa de gates de extracción
C:\Users\tatym\AppData\Local\Programs\Python\Python313\python.exe C:\projects\FutureTrends\scripts\run_full_pass.py

# WorkingDirectory de la tarea a minúscula (requiere PowerShell elevada)
$task = Get-ScheduledTask -TaskPath '\FutureAnalysis\' -TaskName 'FutureAnalysis_DailyRun'
$action = $task.Actions[0]; $action.WorkingDirectory = 'c:\projects\FutureTrends'
Set-ScheduledTask -TaskPath '\FutureAnalysis\' -TaskName 'FutureAnalysis_DailyRun' -Action $action
```

Usar siempre la ruta absoluta de Python en scripts programados; `python3` a secas falla en silencio bajo S4U.

---

## DB / State (`data/fa.db`, no versionada; backup `data/fa.db.bak_20260930_prompt_v21`)

| Tabla | Estado |
|---|---|
| `tech_scores` | 2042 filas: v1 158 (4 días), v2 1680 (61 días), v2.1 204 (4 días). 11 días con `day_quality='pipeline_writetool_recovered'`. `trend_name='daily_run'` en todas; `score_status='scored'` en todas |
| `prices` | 2067 filas, 2026-05-27 → 2026-09-28 |
| `review_notes` | 254 (156 auto, 98 manual), 0 resueltas, nunca inyectadas |
| `trends` | 0 filas (la tabla nunca se ha usado) |

Huecos genuinos (Regla 1, no se rellenan): 2026-06-25, 06-26, 09-17, 09-25.

---
*Spec autorizada (producción): `FutureTrendsAnalysis_v3_reviewed.md` (v3.1) · Validación: `specs/validation_engine_v1.1.md` (+ adenda 2026-09-30) · Extracción P1.5: `specs/filing_section_validator_v1.md` (v1.2, congelada) · v3: `docs/v3_migration_notes.md`*
