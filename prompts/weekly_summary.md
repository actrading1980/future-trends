# FutureAnalysis — Weekly Summary
# Semana: {FECHA_INICIO} a {FECHA_FIN}

Genera un informe consolidado de la semana basado en los reportes diarios.

Lee con filesystem MCP los informes de la semana en reports/ y los scores en data/fa.db.

## 1. Top 5 tendencias de la semana
Las 5 tendencias con mayor momentum (apariciones × score promedio)

## 2. Movimientos de score significativos
Empresas con Δscore > 10 puntos en la semana (subidas y bajadas)

## 3. Tendencias nuevas detectadas esta semana
Que no aparecían en la semana anterior

## 4. Tendencias que han perdido momentum
Score cayó > 15 puntos o desaparecieron de discovery

## 5. Tabla resumen de scores actuales
Top 20 empresas por score, con tendencia asociada

## 6. Estadísticas de sistema
- Días ejecutados exitosamente: X/5
- Total tendencias monitoreadas: N
- Empresas con score activo: N

VALIDATION_STATUS: UNVALIDATED
