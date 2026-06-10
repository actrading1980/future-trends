# Handoff — FutureTrends Intelligence System
*Actualizado: 2026-06-10*

---

## Estado del proyecto

Phase 1 activa desde 2026-05-22. Pipeline autónomo operativo (Task Scheduler, lunes-viernes 7:00 AM, LogonType=S4U). 11 días de histórico en `tech_scores` (511 registros), 7 días de precios en `prices` (357 registros). Próximo hito: 2026-06-22 (30 días sin fallos = gate P1→P2).

---

## Lo que se hizo en esta sesión (2026-06-10)

| Item | Estado |
|------|--------|
| Tabla `prices` en fa.db + `fetch_prices.py` (yfinance batch) | ✅ |
| Integración de `fetch_prices.py` en `run_daily.ps1` (paso 9) | ✅ |
| Script `generate_comparative.py` — delta de scores + solapamiento de fuentes | ✅ |
| Comparativos diarios integrados en pipeline y en git deploy | ✅ |
| Cambio prompt v1→v2: cuota "3-5 tendencias" → umbral de relevancia (≥2 catalizadores) | ✅ |
| Columna `prompt_version` en `tech_scores` (histórico = v1, desde hoy = v2) | ✅ |
| Schema de 3 estados `scored/no_catalyst/not_in_universe` | ⏳ Esperar 5 días con v2 |

---

## Arquitectura actual

### Pipeline diario (`run_daily.ps1`)
1. Carga `.env` y exporta tendencias activas desde `tech_scores`
2. Construye prompt con fechas y tendencias → `$env:TEMP\fa_prompt_YYYYMMDD.md`
3. Claude CLI vía stdin → reporte `reports/YYYYMMDD.md` (umbral mínimo 3000 bytes)
4. Segunda llamada Claude → extrae bloque `SCORES_CSV_START/END` → parser Python → `tech_scores` (con `prompt_version`)
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
| `data/companies.json` | Universo de 51 empresas |
| `reports/YYYYMMDD.md` | Reportes diarios |
| `reports/comparative_YYYYMMDD.md` | Comparativos diarios |
| `reports/index.html` | Viewer HTML (Cloudflare Pages) |

### Task Scheduler
- Nombre: `\FutureAnalysis\FutureAnalysis_DailyRun`
- Horario: lunes-viernes 7:00 AM, LogonType=S4U
- Log: `logs/scheduler.log`

### DB (`data/fa.db`)
| Tabla | Registros | Fechas disponibles |
|-------|-----------|-------------------|
| `tech_scores` | 511 | 2026-05-26 → 2026-06-09 (11 días) |
| `prices` | 357 | 2026-05-27 → 2026-06-08 (7 días) |
| `companies` | 51 | universo fijo |

### Infra
- GitHub: `https://github.com/actrading1980/future-trends`
- Cloudflare Pages: `future-trends.pages.dev`

### Deuda técnica activa
| Item | Severidad | Nota |
|------|-----------|------|
| Schema 3 estados (`scored/no_catalyst/not_in_universe`) no implementado | Media | Esperar 5 días de runs v2 para ver distribución; implementar ~2026-06-16 |
| Sparklines + tab Histórico en el viewer HTML | Media | Requiere ≥7 días de `prices`; ya disponible, implementar cuando el usuario lo active |
| `prices` tiene gap 2026-06-09 y 2026-06-10 | Baja | fetch_prices corre al final del pipeline; si el run falla, no hay precio ese día |
| 15 empresas sin score algunos días (v1) | Baja | Resuelto estructuralmente en v2 con umbral de relevancia; monitorear |

---

## Próximos pasos (en orden de prioridad)

### 1. Monitorear distribución de tendencias con prompt v2 (2026-06-10 → 2026-06-16)
Después de 5 runs: revisar cuántas tendencias salen en promedio. Si media 5-7 → calibrado. Si <3 → umbral demasiado estricto. Si >10 → relajar a 3 catalizadores.

### 2. Schema de 3 estados (~2026-06-16)
Una vez estabilizado v2, añadir al prompt la instrucción de marcar explícitamente `no_catalyst` vs `not_in_universe`. Añadir columna `score_status` a `tech_scores`. Los registros anteriores quedan con `score_status = NULL` (interpretable como v1/no_catalyst indistinguible).

### 3. Sparklines + tab Histórico en el viewer HTML
`prices` tiene 7 días. Implementar: sparkline de score por ticker en sección BULLISH/BEARISH + segundo tab "Histórico" con tabla empresas × últimos 30 días. Listo para activar cuando el usuario lo pida.

### 4. Validación estadística (horizonte: ~2026-11-26)
Con 6 meses de histórico: calcular Spearman(score_t, return_90d_t) por ticker. Gate P1→P2: Spearman ≥ 0.25, N ≥ 65. Filtrar por `prompt_version = 'v2'` para excluir v1 del cálculo.

---

## Comandos operativos

```powershell
# Lanzar run manual
powershell.exe -ExecutionPolicy Bypass -File C:\projects\FutureTrends\scripts\run_daily.ps1

# Ver log del scheduler
Get-Content C:\projects\FutureTrends\logs\scheduler.log -Tail 30

# Generar comparativo manualmente para una fecha
python3 C:\projects\FutureTrends\scripts\generate_comparative.py 2026-06-10

# Ver scores de hoy en DB
# (abrir SQLite browser o query directa)

# Deploy manual si no se lanzó solo
powershell.exe -ExecutionPolicy Bypass -File C:\projects\FutureTrends\scripts\deploy_report.ps1 `
  -ReportFile C:\projects\FutureTrends\reports\20260610.md `
  -ProjectDir C:\projects\FutureTrends
```

---

*Spec autorizada: `C:\projects\FutureTrends\FutureTrendsAnalysis_v3_reviewed.md` (v3.1)*
