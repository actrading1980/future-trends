# Incidente: 0/40 en tech_scores, 2026-09-10 a 2026-09-16

## Síntoma
6 corridas seguidas (09-10, 11, 14, 15, 16) terminaron en "Run completado (degradado)"
con 0 registros insertados en `tech_scores`, pese a que los informes se generaban
y publicaban con normalidad.

## Diagnóstico
No fue un problema del parser, del formato CSV, ni del fix por-ticker agendado
para 09-12 (ese fix nunca se llegó a commitear — `git log` no muestra cambios a
`scripts/run_daily.ps1` entre el 27-ago y el 18-sep).

Causa raíz: `run_daily.ps1` invocaba `python3` a secas. En esta máquina, `python3`
resuelve al stub de Windows Store (`AppData\Local\Microsoft\WindowsApps\python3.exe`),
un "app execution alias" que requiere contexto de activación de paquete disponible
solo en sesiones interactivas. La tarea `FutureAnalysis_DailyRun` corre con
`LogonType: S4U` (no interactivo). Bajo ese logon, el alias falla completamente en
silencio: no hay excepción, no hay stderr, no hay stdout — la variable que captura
el resultado queda vacía.

Esto no afectaba solo al parser de scores: las cuatro llamadas a `python3` de cada
corrida (parse de scores, precios de cierre, notas de revisión, comparativo) quedaban
mudas el mismo día. Confirmado corriendo el parser a mano contra `reports/20260916.md`:
el bloque `SCORES_CSV_START/END` está bien formado y produce 20 inserts sin error
alguno cuando se invoca el intérprete real directamente.

El 09-18 la corrida programada sí insertó registros (37/40) porque la máquina tenía
sesión interactiva activa esa mañana — lo que confirma que el fallo depende del
estado de sesión, no del código del pipeline.

## Superficies de alarma (verificadas, no rediseñadas)
Las tres funcionaron como estaban diseñadas tras el incidente de julio:
1. Log ERROR en `scheduler.log` — disparó los 6 días.
2. `PIPELINE_ERROR.txt` en el escritorio — se sobrescribió cada corrida con el detalle correcto.
3. Exit code de la tarea — `LastTaskResult: 1` confirmado en Task Scheduler.

Ninguna alarma falló. El panel de salud (`generate_health_dashboard.py`) sigue
siendo la pieza pendiente que habría hecho visible esto sin depender de que alguien
mirara el escritorio o el log a diario — segunda vez que esta ausencia cuesta una
semana de datos.

## Fix aplicado
`scripts/run_daily.ps1`: se reemplazaron las 7 invocaciones de `python3` por
`& $PythonExe` apuntando a la ruta absoluta del intérprete real
(`C:\Users\tatym\AppData\Local\Programs\Python\Python313\python.exe`), eliminando
la dependencia del alias de Windows Store y por tanto del estado de sesión.

## Recuperación de datos
Los 5 reportes (09-10, 11, 14, 15, 16) tenían su bloque `SCORES_CSV_START/END`
intacto y bien formado — el fallo fue puramente de inserción, no de generación.
Se corrió el mismo parser manualmente contra cada uno, respetando la fecha propia
del reporte (no es scoring retroactivo: son datos ya generados el día correspondiente
que nunca llegaron a persistir):

| Fecha | Registros recuperados |
|---|---|
| 2026-09-10 | 17 |
| 2026-09-11 | 14 |
| 2026-09-14 | 10 |
| 2026-09-15 | 18 |
| 2026-09-16 | 20 |

Cobertura individual por debajo de 40 en cada día — consistente con el patrón
preexistente de Phase 0 (no forma parte de este incidente).

## 2026-09-17: incidente distinto, sin recuperación posible
Falla de red transitoria (DNS/ENOTFOUND) en la llamada al CLI a las 07:00 ET.
El pipeline abortó antes de generar el reporte (`stdout=83 bytes`), por lo que no
hay CSV que recuperar. Regla 1 (no scoring retroactivo) impide regenerar el reporte
hoy con conocimiento posterior al 09-17. Ese día queda como hueco genuino con su
`day_quality`, igual que 06-25/26.
