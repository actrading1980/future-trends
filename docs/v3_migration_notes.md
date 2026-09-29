# Migración v3: requisitos acumulados

*Abierto: 2026-09-30. Documento de trabajo: recoge los requisitos que salen de los diagnósticos para que no se pierdan antes de redactar la spec v3. No es la spec ni el pre-registro.*

## Principio: un solo corte de régimen

La continuidad (tendencias + notas), el esquema de 3 estados, el universo 136 y el prompt v3 se activan **el mismo día**, con pre-registro fechado antes del primer run: los Δscore no se comparan a través de la frontera, H2 se analiza dentro de cada régimen y la varianza de Δ cambia por diseño (anclaje). Es la Regla 2 aplicada a un corte deliberado. Ver adenda 2026-09-30 en `specs/validation_engine_v1.1.md`.

## Requisitos

1. **Cláusula `no_catalyst` en el prompt.** Una empresa sin novedad hoy emite `no_catalyst`, que en la DB queda como ausencia explícita, no como un score neutro fabricado.
   *Motivación:* en las notas de sección 7, el modelo da por hecho que el score anterior sigue vigente. Por ejemplo: «CRSP,BEAM,…,FSLR sin catalizador hoy; últimos scores en DB vigentes» (2026-09-21) y «scores vigentes = ayer» (2026-09-22). Esa semántica nunca existió: v2 omitía la fila y v2.1 (`ff380b6`) la sobreescribe con 50/0. El esquema de 3 estados implementa justo lo que el modelo ya supone. El relleno 50/0 de v2.1 dejó la cobertura efectiva en 6.3 empresas/día (frente a 24.2 en v2), maquillada como 51/51.

2. **Contexto de continuidad.** Conectar `scripts/build_context.py` en lugar de los dos bloques inline de `run_daily.ps1`, que están rotos desde su creación por las comillas de PS 5.1. El conteo 0 debe seguir dando WARN/ERROR.
   *Prerrequisito humano:* triar las 98 notas MANUAL (~12.4K chars, lo que duplicaría el prompt). Las AUTO llevan un tope mecánico de 14 días.

3. **Subir `prompt_version` en el INSERT** de `run_daily.ps1`, que está hardcodeada. `ff380b6` demostró que un cambio de prompt sin bump pasa desapercibido.

4. **Salud visible más allá de 24 h.** `PIPELINE_ERROR.txt` se borra al arrancar cada run (`run_daily.ps1:33-34`), así que solo refleja el último. El fallo del 2026-09-25 (ENOTFOUND) estuvo visible del viernes 07:03 al lunes 07:00 y luego desapareció sin rastro. Limitación conocida, que no se arregla complicando el marcador: el panel de salud local (`generate_health_dashboard.py`) debe mostrar la serie completa de días, huecos incluidos.

## Prerrequisitos humanos (camino crítico)

- Inspección P1.5 (universo 136, Etapa 2).
- Triaje de las 98 notas MANUAL.
