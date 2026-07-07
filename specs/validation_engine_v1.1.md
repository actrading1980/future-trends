# FutureAnalysis — Validation Engine Spec v1.1
*Autor: FutureTrends Intelligence System*
*Fecha: 2026-06-10 (revisión 2 el mismo día, tras segunda pasada adversarial sobre el primer borrador de v1.1)*
*Estado: DRAFT — lista para pre-registro, pendiente de confirmación de push*
*Reemplaza: `validation_engine_v1.md` — v1.0 queda archivada como referencia histórica, no usar para el gate*

---

## 0. Qué cambió respecto a v1.0 y por qué

v1.0 tenía tres defectos que, sin corregir antes de acumular datos, invalidarían la decisión del gate F3 independientemente del resultado obtenido:

1. **No-independencia de observaciones intra-día.** v1.0 lo admitía en su Sección 6.2 ("los IC diarios no son independientes entre sí") pero no actuaba en consecuencia — seguía definiendo N como observaciones pooled (ticker×fecha), permitiendo alcanzar N=65 con solo 2 días de calendario. Es el mismo patrón de correlación intra-batch identificado en Calibration01/FlowBias, donde el criterio vinculante pasó a ser `N_batches ≥ 30` en vez de `N_señales ≥ 38`. Aquí el criterio vinculante pasa a ser **número de fechas independientes**, vía Fama-MacBeth (Sección 4).

2. **Umbral de gate mal calibrado.** IC ≥ 0.25 exige superar a la práctica totalidad de factores publicados en literatura quant (la propia tabla de interpretación de v1.0 lo decía: "0.15–0.30 = señal moderada", ">0.30 = raro en mercados eficientes"). Ese umbral condena el proyecto a fallar el gate con probabilidad >95% incluso si el sistema aporta señal real explotable. Recalibrado en Sección 4.1.

3. **Sin control de momentum.** `S_tecnico` (15% del score) es RSI/momentum de precio — un factor con IC positivo bien documentado. Sin aislarlo, un gate superado no distingue "Claude aporta información" de "hemos redescubierto momentum con ruido encima". Añadido en Sección 4.4.

Correcciones adicionales incorporadas: excess return vs SPY como variable objetivo primaria (no retorno bruto), exclusión de `no_catalyst` del cálculo de IC (no solo de los extremos), terciles en vez de deciles dado el tamaño del universo, y una hipótesis paralela de **event study sobre Δscore** que no estaba en v1.0 pese a que el dato ya existe como subproducto de `generate_comparative.py`.

**Segunda pasada (mismo día, sobre el primer borrador de v1.1):** una revisión adicional encontró que el propio primer borrador subestimaba la autocorrelación de la serie de IC (asumía ρ≈0.3-0.5; la estructura real de ventanas solapadas produce ρ≈1 en el rango relevante), lo cual invalidaba el horizonte 90d como test primario y el cálculo de T mínimo. Corregido en la Sección 6.2 con la estructura correcta (T_efectivo≈T/h) y una tabla de potencia estadística explícita, que revela una consecuencia de fondo: **el gate F3 es indetectable con el universo actual de 51 empresas en un plazo razonable** — la ampliación a ~150 empresas pasa de "palanca recomendada" a **prerequisito del gate** (Fase P1.5, Sección 10). Además: el horizonte primario del gate cambia de 90d a 30d; el event study se corrige para separar eventos por signo (Sección 4.7); el control de momentum se rediseña sobre un factor externo (RSI-14 desde `prices`) en vez de un componente interno del score que puede no existir en el histórico persistido (Sección 4.4); y los umbrales se fijan a números únicos en vez de rangos, con el test primario excluido de la corrección por múltiples comparaciones (Sección 6.3).

---

## 1. Objetivo

Medir si el score diario generado por FutureAnalysis tiene poder predictivo real sobre los retornos futuros de las empresas del universo, con una metodología que sea válida incluso cuando el número de fechas de calendario disponibles es pequeño respecto al número de observaciones pooled.

Dos hipótesis se evalúan en paralelo, no una sola:

> **H1 — Niveles:** El *nivel* del score en la fecha `t` predice el retorno relativo desde `t`.
> **H2 — Eventos:** Un *cambio* material en el score (Δscore, entrada en zona BULLISH, resolución de conflicto) predice un retorno anormal (CAR) en la ventana post-evento.

H2 se añade porque un sistema temático de horizonte 3-18 meses tiene una razón estructural para que H1 sea débil: el mercado descuenta rápido lo ampliamente conocido (ver Sección 7.2 del spec maestro `FutureTrendsAnalysis_v3_reviewed.md`). El punto de entrada de información nueva —el evento, no el nivel— es donde es más plausible que exista edge, y además da mayor potencia estadística por observación que el IC de niveles.

Bajo H1:
> **H₀:** El score no contiene información predictiva sobre retornos futuros (media del IC diario = 0).
> **H₁:** El score está positivamente correlacionado con retornos futuros (media del IC diario > 0).

---

## 2. Datos de entrada

### 2.1 Tabla `tech_scores`
```
ticker         TEXT   — identificador del activo (ej. NVDA)
date           TEXT   — fecha del score en formato ISO (ej. 2026-05-27)
score          INT    — score compuesto 0-100
scenario       TEXT   — BULLISH / STRONG_BULLISH / NEUTRAL / BEARISH
intensity      INT    — exposición -3 a +3
prompt_version TEXT   — 'v1' (hasta 2026-06-09) | 'v2' (desde 2026-06-10)
score_status   TEXT   — 'scored' / 'no_catalyst' / 'not_in_universe' (pendiente de implementar, ver Sección 9)
```

### 2.2 Tabla `prices`
```
ticker  TEXT  — mismo namespace que tech_scores, más SPY como benchmark
date    TEXT  — fecha de cierre en formato ISO
close   REAL  — precio de cierre ajustado (split + dividendo), fuente yfinance
source  TEXT  — 'yfinance' (única fuente actualmente)
```

### 2.3 Restricciones de datos

- Solo `prompt_version = 'v2'` entra en el cálculo del gate F3. Los registros v1 se reportan en un anexo exploratorio separado, nunca mezclados con v2 en el mismo test.
- Una observación válida requiere: score en fecha `t` **y** precio en fecha `t` **y** precio en fecha `t+N` (ajustado al siguiente día hábil disponible).
- **`no_catalyst` (score=50 imputado) se excluye del cálculo de IC**, no solo del análisis de extremos. Empates mecánicos en 50 sin contenido informativo encogen el Spearman hacia cero y contaminan la estimación aunque no exista error real. Se reportan aparte como diagnóstico de cobertura (% de universo sin catalizador por fecha).
- `not_in_universe` se descarta siempre — es un hueco de proceso, no una observación neutral.
- Mientras `score_status` no exista (histórico anterior a su implementación), todo registro `v2` se trata como `scored` por defecto — es una aproximación conservadora que **infla** el N real; documentar la fecha de corte cuando se implemente.

---

## 3. Cálculo de retornos

### 3.1 Retorno simple a N días

```
return_Nd(ticker, t) = (close(ticker, t+N) - close(ticker, t)) / close(ticker, t)
```

`t+N` es el N-ésimo día calendario posterior, ajustado al siguiente día hábil disponible en `prices`.

| Alias | N días calendario | Propósito |
|-------|------------------|-----------|
| return_7d   | 7   | Diagnóstico, NUNCA gate — ver Sección 4.1 |
| return_30d  | 30  | Primer validador con peso real |
| return_90d  | 90  | Horizonte principal del gate F3 |
| return_180d | 180 | Validación de tesis 6 meses |

### 3.2 Retorno logarítmico

```
log_return_Nd(ticker, t) = ln(close(ticker, t+N) / close(ticker, t))
```

Check de robustez en paralelo; el retorno simple sigue siendo la base del IC principal por interpretabilidad.

### 3.3 Excess return vs SPY — variable objetivo primaria (cambio respecto a v1.0)

```
excess_return_Nd(ticker, t) = return_Nd(ticker, t) - return_Nd(SPY, t)
```

**v1.0 usaba retorno bruto como variable principal y relegaba esto a "alternativa". Se invierte en v1.1:** con un universo 100% tech, el IC sobre retorno bruto está dominado por beta de mercado — "la IA subió este trimestre" contamina cualquier lectura de si el score aporta información idiosincrática. El excess return vs SPY es la variable objetivo primaria de aquí en adelante; el retorno bruto se reporta solo como referencia.

Segmentación por sector (AI/Semis, Biotech, Energy, Cloud, Quantum) queda diferida hasta que exista la columna `sector` en `companies.json` — no bloquea el gate F3, que puede evaluarse con SPY como único benchmark.

**Acción técnica:** `SPY` debe añadirse a `fetch_prices.py` como ticker adicional siempre descargado, excluido explícitamente de `companies.json` (es benchmark, no empresa del universo).

---

## 4. Métricas de evaluación

### 4.1 Information Coefficient — Fama-MacBeth con errores Newey-West (reemplaza el Spearman pooled de v1.0)

**Paso 1 — IC diario (cross-sectional):**
```
IC_t = Spearman(score_i,t, excess_return_Nd_i,t)   para todos los tickers i con observación válida en fecha t
```
Esto es idéntico al "IC diario" que v1.0 ya definía en su Sección 4.2 (ICIR) — la corrección no es un concepto nuevo, es promoverlo de métrica secundaria a **la** métrica.

**Paso 2 — Serie temporal de IC:**
Se obtiene una serie {IC_t1, IC_t2, ..., IC_tT} con T = número de fechas de calendario distintas con datos suficientes (no T = número de observaciones ticker×fecha).

**Paso 3 — Inferencia sobre la media de la serie, con Newey-West:**
```
IC_mean = mean(IC_t)
```
El t-stat NO puede calcularse con la fórmula estándar de v1.0 (Sección 6.1) porque las ventanas de retorno se solapan masivamente para horizontes ≥30 días con scoring diario: el retorno_30d calculado en `t` y en `t+1` comparten 29 días de la ventana, generando autocorrelación fuerte en la serie de IC_t con lag aproximado igual al horizonte en días hábiles.

```
t-stat_NW = IC_mean / SE_NW(IC_t)
```
Donde `SE_NW` es el error estándar de Newey-West con lag máximo = horizonte en días hábiles (ej. lag=21 para el horizonte 30d, lag≈63 para 90d). Implementación vía `statsmodels.stats.sandwich_covariance` o cálculo directo de la fórmula HAC.

**Gate F3 recalibrado (reemplaza IC≥0.25 de v1.0) — test primario: IC_30d, excess return vs SPY, global, prompt_version='v2', universo ampliado (Sección 10, Fase P1.5). Todo lo demás en esta spec es exploratorio bajo BH (Sección 6.3), no compite con el gate.**

| Condición | Umbral (número único) | Justificación |
|-----------|------------------------|----------------|
| IC_mean_30d (excess return) | > 0 | Dirección correcta, condición necesaria |
| t-stat_NW (lag=21 días hábiles) | ≥ 2.0 | Significancia bajo la estructura de solape de 6.2 |
| \|IC_mean_30d\| | ≥ 0.05 | Umbral único de relevancia económica — factor usable como tiebreaker/filtro (ver nota de uso abajo). Se elige el extremo superior del rango de v1.1-borrador porque es el único detectable con potencia adecuada en el calendario de Fase P1.5 (Sección 6.2, tabla de potencia) |
| T_efectivo (serie diaria de IC_30d, N=136 real; NW con lag=21 es válido aquí porque T_raw≈252 días hábiles ≫ lag=21 — a diferencia del caso 90d de 6.2 donde T_raw≈lag) | = 12 | Ver Sección 6.2, tabla de potencia — número fijo, no rango. Con N=136 el margen sobre el umbral es cero (Sección 6.2), puede requerir K=13-14. **No confundir con el confirmatorio 90d**, que sí usa bloques literalmente no solapados por ser el único método válido a ese horizonte |
| ICIR (Sección 4.2, sobre la serie diaria de IC_30d) | ≥ 0.4 | Estabilidad de la señal en el tiempo — punto medio único, no rango |
| Spread top-tercil vs bottom-tercil (excess return, 30d) | > 0, consistente en signo con IC | Confirmación no paramétrica del IC |
| IC_mean_90d no solapado (Sección 6.2) | > 0, mismo signo que IC_30d | Confirmatorio — no decide el gate por sí solo, pero un signo contrario invalida la lectura de 30d |

**Nota sobre el umbral 0.05 vs el 0.25 de v1.0:** el proyecto tiene dos usos posibles definidos en la Sección 8 del spec maestro — (a) señal standalone en la IB platform, (b) tiebreaker/filtro dentro de FAS. Un IC de 0.05 sostenido y significativo NO habilita (a) pero SÍ habilita (b), que es el uso que la Sección 8 asigna explícitamente. El gate F3 de esta spec valida (b). Si en el futuro se quisiera evaluar (a), el umbral correcto sería más alto y es una decisión separada, no automática por superar F3.

**Interpretación de referencia (sin cambios respecto a v1.0, solo reencuadrada):**
| IC medio | Interpretación |
|----------|----------------|
| < 0.03 | Sin señal económicamente relevante, aunque sea estadísticamente distinguible de 0 |
| 0.03 – 0.08 | Señal débil pero usable como filtro/tiebreaker — rango típico de factores individuales en literatura quant |
| 0.08 – 0.15 | Señal moderada |
| > 0.15 | Señal fuerte — verificar que no sea momentum disfrazado (Sección 4.4) antes de celebrar |

### 4.2 ICIR (sin cambios conceptuales respecto a v1.0)

```
ICIR = mean(IC_t) / std(IC_t)
```
Calculado sobre la misma serie temporal de IC_t de 4.1. Umbral de gate: ICIR ≥ 0.4 (número único, ver tabla de gate en 4.1).

### 4.3 Hit Rate — con exclusión de `no_catalyst`

```
HR_Nd = P(excess_return_Nd > 0 | score ≥ 70, score_status='scored') − P(excess_return_Nd > 0 | score < 30, score_status='scored')
```
Idéntico a v1.0 salvo la exclusión explícita de `no_catalyst`. Requiere ≥20 observaciones por grupo; con universo de 51-150 empresas esto puede requerir agregar varias fechas — reportar T (fechas) usadas, no solo N.

### 4.4 Control de momentum (nuevo en v1.1 — no existía en v1.0; corregido tras revisión)

Objetivo: distinguir si el IC del score proviene de información genuina de FutureAnalysis o es momentum de precio disfrazado.

**Corrección respecto al primer borrador de esta sección:** el diseño original asumía que `S_tecnico` existe como componente persistido o recalculable (`score − 0.15 × S_tecnico`). No hay garantía de eso — el pipeline actual (`run_daily.ps1`) extrae el score compuesto final del informe narrativo de Claude vía una segunda llamada dedicada a CSV; el desglose interno S_analistas/S_escenario/S_hype no se persiste en `tech_scores`. Construir el control de momentum sobre un componente que puede no existir en el histórico es frágil. Además, aunque existiera, restar linealmente no ortogonaliza si `S_hype` correlaciona con el precio reciente (plausible: el hype mediático sigue al precio, no al revés) — la resta dejaría momentum filtrándose por la puerta de atrás.

**Diseño corregido — factor de momentum independiente, calculado determinísticamente desde `prices`, sin depender de qué hizo Claude internamente:**
```
momentum_i,t = RSI_14(precio_i, hasta fecha t)
```
RSI de 14 periodos, **variante de Wilder** (suavizado exponencial con α=1/14 sobre ganancias/pérdidas medias, no media simple — convención estándar; la media simple da valores distintos y no es lo que la mayoría de literatura/plataformas llaman "RSI-14" sin calificar), calculado directamente sobre la serie de `close` **ajustado** (split+dividendo) de la tabla `prices` para cada ticker, sin fuente ni parámetro alternativo. Es un factor de control externo al sistema, no una pieza del score. Fijar esta definición es necesario para que "recalculable determinista desde prices" sea literalmente cierto — sin especificar la variante, dos implementaciones del mismo pseudocódigo producirían controles de momentum distintos.

**Cálculo:**
1. `IC_momentum_t = Spearman(RSI_14_i,t, excess_return_30d_i,t)` — misma metodología Fama-MacBeth/NW de 4.1, mismo horizonte primario (30d).
2. `IC_residual_t = Spearman(score_i,t, excess_return_30d_i,t | controlando por RSI_14)`, vía **residualización cross-sectional por fecha**: para cada fecha `t`, regresión OLS `excess_return_30d ~ RSI_14` sobre las N empresas de esa fecha, tomar los residuos, y calcular `Spearman(score_i,t, residuo_i,t)`. Esto sí ortogonaliza correctamente frente al momentum observado ese día, a diferencia de la resta lineal del diseño original.

**Condición añadida al gate F3:** `IC_mean_30d(score) > IC_mean_30d(RSI_14)`, y adicionalmente `IC_mean_30d(residual) > 0` con t-stat NW ≥ 2.0 sobre la serie residualizada. Si el score no aporta información más allá de lo que ya captura el momentum de precio, el gate F3 no se considera superado independientemente de que el IC del score bruto cumpla el umbral de 4.1.

### 4.5 Retorno de cartera simulada (long/short) — sobre excess return

```
portfolio_excess_return_Nd(t) = mean(excess_return_Nd | score≥70, scored) − mean(excess_return_Nd | score<30, scored)
```
Long BULLISH / short BEARISH, igual-ponderada. Sin costes de transacción (señal de paper trading).

```
Sharpe_señal = mean(portfolio_excess_return_Nd) / std(portfolio_excess_return_Nd) × sqrt(252/N_rebalanceos)
```
Con el mismo cuidado de autocorrelación de 4.1: si el rebalanceo es diario pero el horizonte es 90d, las carteras consecutivas comparten 89/90 de composición — el Sharpe anualizado ingenuo sobreestima. Reportar también el Sharpe calculado sobre observaciones no solapadas (una cada N días) como cota inferior conservadora.

### 4.6 Análisis por terciles (reemplaza deciles de v1.0)

v1.0 proponía deciles (10 grupos); con 51-150 empresas por fecha eso da grupos de 5-15 nombres, demasiado ruidoso. **Se usan terciles** (3 grupos) hasta que el universo supere **~250 empresas** (quintiles de 150 dan grupos de 30, todavía ruidosos para retornos a 30d; ~250 da grupos de 50, donde la media por grupo empieza a estabilizarse), punto en el que quintiles pasan a ser viables. Se reporta el retorno medio (excess) de cada tercil y se verifica monotonicidad direccional (tercil superior > tercil medio > tercil inferior).

### 4.7 Event study sobre Δscore — hipótesis H2, nueva en v1.1

No existía en v1.0 pese a que el dato ya se genera como subproducto de `scripts/generate_comparative.py` (deltas de score día-a-día, entradas/salidas de zona BULLISH/BEARISH).

**Definición de evento — separada por signo (corrección tras revisión: el diseño original pooleaba Tipo A independientemente del signo del delta, lo cual cancela un upgrade de +15 contra un downgrade de −12 y produce CAAR≈0 aunque ambos eventos tengan efecto real):**
- Tipo A+: `Δscore ≥ +10` respecto a la fecha anterior con datos.
- Tipo A−: `Δscore ≤ −10` respecto a la fecha anterior con datos.
- Tipo B: entrada en zona BULLISH (score cruza de <70 a ≥70).
- Tipo C: resolución de `CONFLICTO DETECTADO` (el conflicto desaparece entre `t` y `t+1`).

Cada tipo se analiza por separado. A+ y A− nunca se agregan en el mismo CAAR.

**Validez de eventos ante huecos de datos (añadido tras el incidente de pipeline 2026-06-25→07-03, ver `HANDOFF.md`):** un Δscore solo es evento si la fecha anterior con datos está a ≤1 día hábil de mercado; la comprobación se hace sobre las fechas reales de `tech_scores` en tiempo de análisis — los sidecars `comparative_*.json` con `gap_spanning` son ayuda, no fuente de verdad, porque no existen para rangos donde el pipeline abortó antes del paso de comparativo (ej. 06-25→07-06, donde el comparativo nunca se generó). Días con `day_quality` distinto de pipeline normal se tratan según su N efectivo, no se asumen completos solo por tener filas.

**Cálculo — Cumulative Abnormal Return (CAR), ventana fija D=20 días hábiles (número único, no "ej."):**
```
AR_i,d = excess_return_1d(ticker_i, evento_date + d)     para d = 1 .. 20
CAR_i(0,20) = sum(AR_i,d for d in 1..20)
```

Promediado cross-sectionalmente dentro de cada tipo (A+, A−, B, C por separado):
```
CAAR_tipo(0,20) = mean(CAR_i(0,20) for i in eventos de ese tipo)
```

**Clustering de eventos — no ignorar:** eventos del mismo tipo en la misma fecha de calendario (ej. un catalizador sectorial dispara Δscore≥10 en varios tickers AI el mismo día) no son independientes entre sí. Se reporta siempre `n_eventos` junto a `n_fechas_distintas` por tipo, y el t-test usa `n_fechas_distintas` como base de grados de libertad, no `n_eventos` — misma disciplina que T (fechas) vs N (observaciones) en H1.

**Criterios de decisión pre-registrados para H2 (ausentes en el primer borrador — corregido):**

| Condición | Umbral (número único) |
|-----------|------------------------|
| \|CAAR_tipo(0,20)\| | ≥ 3% (excess return acumulado en 20 días hábiles) |
| Signo de CAAR | Consistente con la dirección del evento (A+ y B positivo; A− negativo) |
| t-stat (sobre distribución de CAR entre fechas distintas, no eventos) | ≥ 2.0 si `n_fechas_distintas` ≥ 15; si es menor, reportar percentil bootstrap (10,000 resamples por bloques de fecha) en vez de t-stat paramétrico, y marcar `NO CONCLUYENTE` si el percentil no aísla claramente de 0 |
| n_eventos mínimo por tipo | ≥ 20 |
| n_fechas_distintas mínimo por tipo | ≥ 10 |

Si Tipo A+ o Tipo B alcanza estos umbrales antes de que H1 alcance T=12 (Sección 6.2), **H2 se reporta como el hallazgo primario** en `reports/validation_YYYYMMDD.md`, con H1 como contexto. La spec anticipa explícitamente esta posibilidad — no es un cambio de criterio post-hoc si ocurre.

**Por qué se prioriza como hipótesis paralela, no secundaria:** cada evento tiene timestamp preciso y ventanas post-evento de 20 días que no se solapan entre eventos suficientemente espaciados — evita en gran medida el problema de solapamiento masivo que domina la Sección 6.2 para H1. Da más potencia estadística por unidad de dato acumulado y es plausible que alcance significancia antes que H1 en el mismo calendario.

---

## 5. Segmentación del análisis

| Segmento | Descripción | Cambios v1.1 |
|----------|-------------|--------------|
| Global | Todas las observaciones válidas (`scored`, v2) | Excluye `no_catalyst` (antes se incluía) |
| Por horizonte | 7d (diagnóstico) / 30d / 90d (gate) / 180d | 7d marcado explícitamente como no-gate |
| Por prompt_version | v2 exclusivamente para el gate; v1 en anexo exploratorio | Sin cambios |
| Por sector | Diferido — requiere columna `sector` | Sin cambios, no bloquea F3 |
| Por rango de score | Terciles (Sección 4.6) | Deciles → terciles |
| Por intensidad | CORE / HIGH / MEDIUM | Sin cambios |
| Por tipo de evento (Δscore) | Tipo A / B / C (Sección 4.7) | Nuevo |

---

## 6. Significancia estadística

### 6.1 Test para IC — Newey-West (reemplaza el t-test estándar de v1.0)

Ver fórmula completa en Sección 4.1. La fórmula `t = IC × sqrt((N-2)/(1-IC²))` de v1.0 asume observaciones independientes y **no debe usarse** para el gate — sobreestima la significancia al tratar 51 observaciones del mismo día como si fueran independientes.

### 6.2 Tamaño mínimo de muestra — estructura de ventanas solapadas, no AR(1) genérico

v1.0 calculaba N_min≈65 observaciones y notaba (sin resolverlo) que con 51 empresas eso se alcanza en ~2 días. La primera corrección de v1.1 (Fama-MacBeth/NW con ρ≈0.3-0.5 supuesto) seguía siendo optimista: no modelaba correctamente la estructura del problema. Se reformula aquí con la estructura real.

**Por qué ρ no es 0.3-0.5.** Con scoring diario y horizonte `h` días hábiles, las ventanas de retorno usadas en `IC_t` e `IC_{t+1}` comparten `h−1` de `h` días — para h=63 (horizonte 90d), eso es 62/63 = 98% de solape. Los rankings cross-sectionales de retorno en fechas consecutivas son casi idénticos, luego `IC_t ≈ IC_{t+1}` y la autocorrelación empírica de la serie será cercana a 1, no a 0.3-0.5. La estructura correcta es la de un proceso de medias móviles solapadas, donde la autocorrelación en el lag `k < h` decae aproximadamente de forma lineal:
```
ρ_k ≈ (h − k) / h    para k = 1 .. h−1;  ρ_k ≈ 0 para k ≥ h
```
Sumando esta estructura, el número efectivo de observaciones independientes en una serie diaria de longitud T es:
```
T_efectivo ≈ T / h
```
Es decir: una serie diaria de `IC_h` contiene aproximadamente **una observación independiente por cada `h` días hábiles**, no una por día. Esta es la razón por la que Newey-West con `lag=h` sobre una serie corta es inestable — NW requiere T ≫ lag, y aquí T ≈ lag en los horizontes de interés durante el primer año del sistema.

**Consecuencia directa — el horizonte primario del gate cambia de 90d a 30d.** A horizonte 90d (h≈63 días hábiles), T_efectivo≈1 con menos de ~4 meses de calendario en producción; el t-stat NW no es fiable con lag≈T. A horizonte 30d (h≈21 días hábiles), T_efectivo crece 3× más rápido. **El test primario del gate F3 es IC_30d**; el IC_90d se calcula de forma no solapada (un IC por bloque de 63 días hábiles consecutivos, sin solape, t-test simple de Student sobre los K bloques resultantes — no NW, porque con K de un dígito NW no aporta nada y produce una falsa sensación de rigor) y se reporta como **confirmatorio**, no como el test que decide el gate.

**Cálculo de potencia — IC mínimo detectable con t≥2, universo N empresas, K ventanas independientes:**
```
SE_por_ventana ≈ 1 / sqrt(N − 3)
IC_detectable  ≈ 2 × SE_por_ventana / sqrt(K)  =  2 / (sqrt(N−3) × sqrt(K))
```

| Universo | Horizonte | K disponible | Calendario aprox. | IC detectable (t≥2) |
|----------|-----------|--------------|--------------------|--------------------|
| N=51  | 30d | K≈3  | ~4 meses tras inicio v2  | ≈0.17 |
| N=51  | 30d | K≈12 | ~12 meses tras inicio v2 | ≈0.08 |
| N=51  | 30d | K≈33 | **≈2.8 años**            | ≈0.05 |
| N=136 (real, seleccionado 2026-07-02) | 30d | K≈12 | ~12 meses **tras que Fase P1.5 esté operativa** (no tras inicio v2 — el gate excluye fechas con universo mixto, ver `universe_version` en el spec maestro Sección 9) | **≈0.050** |

**Implicación que cambia el roadmap:** con el universo original de 51 empresas, el umbral de gate de la Sección 4.1 (IC≥0.05) es indetectable en un plazo razonable incluso con K≈33 (≈2.8 años) — se reproduciría el defecto original de v1.0 (gate diseñado para fallar), esta vez por potencia estadística insuficiente en vez de por umbral imposible. **La ampliación del universo deja de ser una palanca opcional y pasa a ser prerequisito del gate F3**, con fase propia — ver Sección 10, Fase P1.5.

**N real vs N objetivo:** la ejecución de P1.5 (`data/universe_selection_20260702.json`) produjo un universo de **136**, no 150 — Advanced Semiconductors y Clean Energy quedaron bajo cuota por pool insuficiente tras los filtros mecánicos (dollar ADV, 10-K), sin redistribución entre categorías (decisión pre-registrada: redistribuir por ranking global reintroduce sesgo tamaño/liquidez cross-categoría). Con N=136, IC_detectable = 2/(√133·√12) ≈ **0.0501** — prácticamente idéntico al umbral del gate (0.05). La frase "combinación mínima viable, no margen cómodo" del borrador anterior era optimista: con el N real, **el margen es cero**. Un IC verdadero ligeramente por debajo de 0.05 será indistinguible de ruido en el primer checkpoint (K=12); puede requerir K=13-14 (~13-14 meses) para confirmar, no 12.

**T mínimo del gate (número único, no rango):** T=12 bloques de 30 días hábiles no solapados con N=136 empresas (real). Equivalente aproximado: T_efectivo≈12 en la serie diaria de IC_30d bajo la estructura de solape de arriba.

### 6.2.1 Regla de atrición del universo (nueva, 2026-07-02)

El universo de 136 empresas seleccionado en P1.5 no se reemplaza empresa por empresa si alguna sale (delisting, adquisición, fallo persistente de captura de precio/score). **Regla: sin reemplazos a mitad de camino, ni desde la waitlist del propio `universe_selection_20260702.json`.** Un reemplazo introduciría una empresa con historial de scores más corto que el resto del tramo `universe_version=2`, y el gate F3 ya excluye fechas con universo mixto (Sección 9 del spec maestro) — meter una empresa nueva a mitad del período de acumulación crearía un tercer tramo temporal sin necesidad.

La atrición se acepta como dato, no se corrige. Se documenta con fecha en el campo `atricion_log` de `universe_selection_20260702.json` cada vez que ocurra. Si el N cae de forma material (ej. >10 empresas, ~7% del universo), la tabla de potencia de esta sección se recalcula con el N real vigente en ese momento — la tabla debe describir el universo que existe en la fecha de evaluación del gate, no el que se seleccionó al inicio. Degradación de referencia: N=136→130 (pérdida de 6) mueve el IC detectable de 0.0501 a ≈0.0512 con K=12, o requiere K=13 (≈0.0492) para volver a cruzar el umbral — degradación suave, no un punto de quiebre.

### 6.3 Corrección por múltiples comparaciones — con test primario excluido de la corrección

**Corrección tras revisión:** v1.1-borrador metía el propio gate dentro del conjunto de 20 tests sujetos a FDR, lo cual reduce aún más la poca potencia disponible (Sección 6.2) penalizando la pregunta que sí importa por las que son exploratorias.

**Test primario del gate (Sección 4.1): IC_30d, excess return vs SPY, global, prompt_version='v2'.** Este test se evalúa a su umbral nominal (t≥2.0), **sin corrección FDR** — es la hipótesis pre-registrada única que decide el gate F3, no un hallazgo entre veinte.

**Todo lo demás es exploratorio:** IC por segmento (sector, intensidad, tercil), IC_90d no solapado, IC_7d, y los cuatro tipos de evento de H2 (Tipo A+/A−/B/C). Sobre ese conjunto (aprox. 15-20 tests según qué segmentaciones estén disponibles en cada corte) sí se aplica Benjamini-Hochberg. Se reporta explícitamente cuántos tests exploratorios se corrieron antes de aplicar la corrección.

**Excepción:** si H2 Tipo A+ o Tipo B alcanza sus propios umbrales de decisión (Sección 4.7) antes de que el test primario tenga potencia suficiente, se promueve a hallazgo primario para ese reporte — declarado así explícitamente en la Sección 4.7, no una regla nueva introducida aquí.

---

## 7. Pipeline de cálculo

### 7.1 Script: `scripts/compute_validation.py`

Ejecución manual únicamente hasta superar los umbrales de T de la Sección 6.2. No se automatiza en el pipeline diario antes de eso — no tiene sentido recalcular un gate que no puede superarse aún.

### 7.2 Lógica del script (actualizada)

```python
# Pseudocódigo — implementación pendiente
import numpy as np
from scipy.stats import spearmanr
from statsmodels.stats.sandwich_covariance import cov_hac  # o cálculo HAC directo

def compute_ic_series(horizon_days, prompt_version='v2', exclude_no_catalyst=True):
    scores = load_scores(prompt_version=prompt_version, exclude_status=['no_catalyst', 'not_in_universe'] if exclude_no_catalyst else ['not_in_universe'])
    prices = load_prices()  # incluye SPY
    
    ic_by_date = {}
    for date_t in distinct_dates(scores):
        obs = []
        for (ticker, score) in scores_at(scores, date_t):
            price_t   = lookup_price(ticker, date_t, prices)
            price_tN  = lookup_price(ticker, date_t + horizon_days, prices)
            spy_t     = lookup_price('SPY', date_t, prices)
            spy_tN    = lookup_price('SPY', date_t + horizon_days, prices)
            if all([price_t, price_tN, spy_t, spy_tN]):
                raw_ret   = (price_tN - price_t) / price_t
                spy_ret   = (spy_tN - spy_t) / spy_t
                excess    = raw_ret - spy_ret
                obs.append((score, excess))
        if len(obs) >= 5:  # mínimo cross-sectional para Spearman no degenerado
            s_arr = [o[0] for o in obs]
            r_arr = [o[1] for o in obs]
            ic, _ = spearmanr(s_arr, r_arr)
            ic_by_date[date_t] = ic
    
    return ic_by_date  # serie temporal de IC_t

def fama_macbeth_test(ic_by_date, horizon_days):
    ic_series = np.array(list(ic_by_date.values()))
    ic_mean = ic_series.mean()
    # HAC/Newey-West con lag = horizon en dias habiles aproximado
    lag = business_days_approx(horizon_days)
    se_nw = newey_west_se(ic_series, lag=lag)
    t_stat = ic_mean / se_nw
    T = len(ic_series)
    return ic_mean, t_stat, T

def rsi_14(ticker, as_of_date, prices):
    # RSI de 14 periodos calculado desde el historico de 'close' en prices, sin dependencia del score
    closes = price_history(ticker, as_of_date, lookback=15, prices)
    return compute_rsi(closes, period=14)

def momentum_control(horizon_days, prompt_version='v2'):
    ic_score_by_date = compute_ic_series(horizon_days, prompt_version, x='score')
    ic_rsi_by_date   = compute_ic_series(horizon_days, prompt_version, x='rsi_14')  # factor externo, no componente del score
    ic_residual_by_date = {}
    for date_t in distinct_dates(scores):
        obs = [(score, excess_return, rsi_14(ticker, date_t, prices)) for ...]
        # residualizacion cross-sectional por fecha: OLS excess_return ~ rsi_14, tomar residuos
        residuals = ols_residuals(y=[o[1] for o in obs], x=[o[2] for o in obs])
        ic_residual_by_date[date_t], _ = spearmanr([o[0] for o in obs], residuals)
    return ic_score_by_date, ic_rsi_by_date, ic_residual_by_date

def non_overlapping_blocks(horizon_days, prompt_version='v2'):
    # Para el confirmatorio IC_90d: un IC por bloque de horizon_days habiles, sin solape
    all_dates = sorted(distinct_dates(scores))
    step = business_days_to_calendar(horizon_days)
    block_dates = all_dates[::step]  # una fecha cada `step`, no una serie diaria
    return {d: compute_ic_series(horizon_days, prompt_version)[d] for d in block_dates if d in ic_by_date}
```

### 7.3 Output: `reports/validation_YYYYMMDD.md`

- Fecha de cálculo y ventana de datos usada (T fechas, rango de calendario)
- IC_mean, t-stat NW, ICIR por horizonte — tabla, con excess return vs SPY como columna principal y retorno bruto como referencia
- Control de momentum: IC_full vs IC_momentum vs IC_residual (Sección 4.4)
- Hit rate BULLISH vs BEARISH (excluyendo `no_catalyst`)
- Retorno de cartera simulada + Sharpe (ingenuo y no-solapado)
- Análisis por terciles con verificación de monotonicidad
- Event study CAAR sobre Δscore (Tipo A/B/C) — cuando haya suficientes eventos
- % de universo en `no_catalyst` por fecha (diagnóstico de cobertura)
- **Diagnóstico de dispersión del score** (ya implementado en `generate_comparative.py` desde 2026-06-10 — ver Sección 9.1): si el % en banda [40,60] es sistemáticamente >60%, el IC no tiene rango con el que trabajar y el resultado del gate no es interpretable independientemente de las demás correcciones.
- Flag explícito: T actual vs T mínimo requerido (Sección 6.2) — si T < mínimo, el reporte se marca `NO CONCLUYENTE`, no se reporta un IC puntual como si fuera la respuesta final.

---

## 8. Casos edge y decisiones de diseño

| Caso | Decisión | Cambio v1.1 |
|------|----------|-------------|
| Precio faltante en t+N (festivo/fin de semana) | Siguiente día hábil disponible | Sin cambios |
| Precio faltante por >5 días hábiles | Descartar observación | Sin cambios |
| Empresa con score en t sin precio en t | Descartar | Sin cambios |
| `no_catalyst` (score=50 imputado) | **Excluir del cálculo de IC** (antes solo se excluía de extremos) | Cambiado |
| `not_in_universe` | Descartar siempre | Nuevo (v1.0 no distinguía este estado) |
| Score v1 | Excluir del gate F3; anexo exploratorio separado, nunca mezclado en el mismo test | Sin cambios de fondo, aclarado |
| Empresa eliminada del universo antes de t+N | Descartar (survivorship bias documentado, no corregido) | Sin cambios |
| Split / dividendos | Cubierto por precio ajustado yfinance | Sin cambios |
| Ventanas de retorno solapadas (horizonte largo, scoring diario) | Corregido vía Newey-West (Sección 4.1) — **no ignorar** | Nuevo — v1.0 no lo trataba |
| Autocorrelación en Sharpe de cartera simulada | Reportar versión no-solapada como cota inferior (Sección 4.5) | Nuevo |
| Dispersión de score degenerada (>60% en banda [40,60]) | Gate no interpretable hasta corregir prompt; diagnóstico corre desde 2026-06-10 | Nuevo |

### 8.1 Sesgo de supervivencia

Sin cambios respecto a v1.0: universo fijo desde 2026-05-22, no se corrige en esta versión del validation engine.

---

## 9. Dependencias técnicas

| Dependencia | Versión mínima | Estado |
|-------------|---------------|--------|
| Python 3.10+ | 3.10 | ✅ disponible |
| `scipy.stats.spearmanr` | scipy 1.9 | por verificar |
| `numpy` | 1.24 | por verificar |
| `statsmodels` (Newey-West / HAC) | 0.14 | ⏳ pendiente instalar y verificar |
| `sqlite3` | stdlib | ✅ |
| `yfinance` | 1.4.0 | ✅ instalado |
| Ticker `SPY` en tabla `prices` | — | ⏳ pendiente añadir a `fetch_prices.py` |
| Columna `sector` en `companies.json` | — | ⏳ pendiente, no bloquea F3 |
| Columna `score_status` en `tech_scores` | — | ⏳ pendiente (schema 3 estados, ver conversación FutureAnalysis 2026-06-09) |
| **Diagnóstico de dispersión en `generate_comparative.py`** | — | ✅ **implementado 2026-06-10** — reporta std, rango y % en banda [40,60] en cada comparativo diario |
| Universo ampliado a ~150 empresas (Opción B, spec maestro Sección 5.4) | — | ⏳ **prerequisito del gate F3** (Sección 10, Fase P1.5) — no bloquea F1/F2 exploratorios |
| Cálculo de RSI-14 desde `prices` para control de momentum (Sección 4.4) | Solo `close` histórico, sin dependencia externa nueva | ⏳ pendiente implementar en `compute_validation.py` |

### 9.1 Diagnóstico de dispersión — ya en producción

Verificación recomendada por el revisor: si Claude puntúa la mayoría del universo en una banda estrecha (comportamiento típico de LLM sin calibración forzada), el IC no tiene rango con el que trabajar aunque la información subyacente exista. Implementado en `scripts/generate_comparative.py` (función `dispersion_stats`): calcula media, std, rango y % de empresas en banda [40,60] por fecha, con warning explícito si ese porcentaje supera 60%.

**Primera lectura (2026-06-09):** N=51, media=75.1, std=11.3, 14% en banda [40,60]. No degenerado. Continuar monitoreando en cada run — un solo día no establece el patrón.

---

## 10. Fases de implementación — timeline recalculado (2ª corrección)

v1.0 estimaba T≈65 "observaciones" en 2 días. El primer borrador de v1.1 corregía a fechas de calendario pero seguía asumiendo ρ≈0.3-0.5, subestimando cuánto tiempo hace falta. Esta versión usa la estructura de solape de la Sección 6.2 (T_efectivo ≈ T/h) y hace explícito que ampliar el universo es prerequisito, no opcional.

| Fase | Condición de entrada | Entregable |
|------|---------------------|------------|
| **F0 — Infraestructura** | Hecho (2026-06-10) | `prices` + `tech_scores` v2 acumulando; diagnóstico de dispersión activo |
| **F1 — Script básico, diagnóstico only** | Primeras fechas con horizonte 7d resuelto (~2026-06-17) | `compute_validation.py` con IC_7d — **diagnóstico, nunca gate**. Detecta bugs de pipeline, no decide nada sobre el sistema |
| **P1.5 — Ampliación de universo a ~150 empresas (prerequisito del gate, no palanca opcional)** | Tan pronto como sea viable tras F1 | Ejecutar la Opción B del spec maestro (Sección 5.4): extracción de keywords tecnológicas vía 10-Ks/SEC EDGAR + validación humana de muestra. Sin esto, el gate F3 con N=51 es indetectable en menos de ~2.8 años (Sección 6.2, tabla de potencia) |
| **F2 — Horizonte 30d, primeras lecturas exploratorias** | Primeras fechas con horizonte 30d resueltas sobre universo ampliado | IC_30d con Fama-MacBeth/NW; T_efectivo aún <12, se reporta `NO CONCLUYENTE` con T actual explícito frente al T=12 requerido |
| **F3 — Gate P1→P2, test primario IC_30d** | T_efectivo=12 bloques de 30 días hábiles no solapados con N=136 (real): **≈12-14 meses de calendario desde que P1.5 esté operativo**, no desde el inicio de v2 (Sección 6.2, tabla de potencia: N=136, 30d, K≈12 → IC detectable ≈0.0501, margen cero sobre el umbral 0.05 — puede requerir K=13-14 para confirmar) | Decisión estadística sobre H1 con todas las correcciones de esta spec. IC_90d no solapado como confirmatorio |
| **F4 — Automatización** | Superado F3 | Añadir al pipeline diario, solo si F3 confirma señal usable como filtro/tiebreaker (Sección 4.1) |

**Consecuencia explícita para el usuario:** con el universo actual de 51 empresas sin ampliar, el gate F3 tal como está pre-registrado no es alcanzable en un plazo operativamente útil. La fecha ~diciembre 2026/enero 2027 mencionada en el primer borrador de esta spec asumía potencia estadística que no existe a N=51. El timeline real depende de cuándo se ejecute P1.5 — si se inicia en las próximas semanas, F3 es plausible hacia mediados-finales de 2027, no antes.

**Nota sobre H2 (event study, Sección 4.7):** no depende de la ampliación de universo de la misma manera — un solo ticker puede generar un evento válido. Puede alcanzar sus criterios de decisión (Sección 4.7) con el universo actual de 51 empresas y sin esperar a P1.5, monitoreable desde ya leyendo los comparativos diarios existentes. Es la vía más rápida a una lectura con peso estadístico real.

**Uso honesto del sistema entre hoy y F3:** ningún IC calculado antes de alcanzar el T mínimo de la Sección 6.2 debe interpretarse como señal, sino como diagnóstico de pipeline. El uso legítimo del sistema en este período es (a) watchlist temática con revisión humana (Sección 8 del spec maestro) y (b) candidatos de cruce con `FINRA_SHORT_DIVERGENCE` vía eventos de Δscore, siempre en shadow mode. El header `VALIDATION_STATUS: UNVALIDATED` permanece en todos los informes hasta que F3 se resuelva formalmente.

---

## 11. Lo que esta spec NO cubre (fuera de scope v1.1)

- Optimización del score / retroalimentación del prompt con resultados de validación (solo tras F3)
- Factor attribution completo más allá del control de momentum de 4.4 (ej. separar S_analistas vs S_hype)
- Portfolio construction real (sizing, riesgo, correlaciones entre posiciones)
- Costes de transacción y market impact
- Benchmarks alternativos a SPY (equal-weighted, sector ETFs) — depende de columna `sector`
- Uso del sistema como señal standalone (Sección 8, uso (a)) — decisión separada y posterior a F3, con umbral propio a definir si se llega a ese punto

---

*Spec v1.1 (revisión 2) lista para pre-registro. La Sección 6.2 (tamaño de muestra y potencia estadística) es la sección que más cambió respecto al primer borrador y la que más condiciona el resto: fuerza el horizonte primario a 30d, fuerza la ampliación de universo a prerequisito (Fase P1.5, Sección 10), y fija el T mínimo en un número único. Junto con la Sección 4.1 (gate) y la 4.7 (criterios de H2), son las tres secciones que deciden si el gate F3 es válido cuando llegue el momento de evaluarlo — pre-registradas ahora, antes de que exista tentación de ajustar criterios mirando resultados.*
