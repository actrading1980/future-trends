# FutureAnalysis — Validation Engine Spec v1.0
*Autor: FutureTrends Intelligence System*
*Fecha: 2026-06-10*
*Estado: ARCHIVADA — reemplazada por `validation_engine_v1.1.md` tras revisión adversarial (2026-06-10). NO usar para el gate F3: el umbral IC≥0.25, el conteo de N como observaciones pooled, y la ausencia de control de momentum invalidan la decisión del gate. Conservada solo como referencia histórica del diseño inicial.*

---

## 1. Objetivo

Medir si el score diario generado por FutureAnalysis tiene poder predictivo real sobre los retornos futuros de las empresas del universo. La hipótesis central es:

> **H₀ (nula):** El score no contiene información predictiva sobre retornos futuros (Spearman = 0).
> **H₁ (alternativa):** El score está positivamente correlacionado con retornos futuros (Spearman > 0).

El sistema rechaza H₀ si Spearman ≥ 0.25 con N ≥ 65 observaciones y p-value < 0.05.

---

## 2. Datos de entrada

### 2.1 Tabla `tech_scores`
```
ticker        TEXT    — identificador del activo (ej. NVDA)
date          TEXT    — fecha del score en formato ISO (ej. 2026-05-27)
score         INT     — score compuesto 0-100
scenario      TEXT    — BULLISH / STRONG_BULLISH / NEUTRAL / BEARISH
intensity     INT     — exposición -3 a +3
prompt_version TEXT   — 'v1' (hasta 2026-06-09) | 'v2' (desde 2026-06-10)
```

### 2.2 Tabla `prices`
```
ticker  TEXT  — mismo namespace que tech_scores
date    TEXT  — fecha de cierre en formato ISO
close   REAL  — precio de cierre ajustado (split + dividendo), fuente yfinance
source  TEXT  — 'yfinance' (única fuente actualmente)
```

### 2.3 Restricciones de datos
- Solo se usan registros donde `prompt_version = 'v2'` para el cálculo de Spearman principal. Los registros v1 se excluyen por inconsistencia de cobertura (cuota fija 3-5 tendencias vs umbral de relevancia).
- Una observación válida requiere: score en fecha `t` **y** precio en fecha `t` **y** precio en fecha `t+N` (ajustado al siguiente día hábil si cae en fin de semana o festivo).
- Si `score_status` = `not_in_universe` (cuando se implemente), la observación se descarta. Si = `no_catalyst`, se incluye con score=50 (neutral por convención).

---

## 3. Cálculo de retornos

### 3.1 Retorno simple a N días

```
return_Nd(ticker, t) = (close(ticker, t+N) - close(ticker, t)) / close(ticker, t)
```

Donde `t+N` es el N-ésimo día **calendario** posterior, ajustado al siguiente día hábil disponible en `prices` si no hay precio exacto en esa fecha.

**Horizontes calculados:**
| Alias | N días calendario | Propósito |
|-------|------------------|-----------|
| return_7d  | 7   | Señal de corto plazo (early proxy) |
| return_30d | 30  | Horizonte medio — primer validador relevante |
| return_90d | 90  | Horizonte principal del sistema |
| return_180d| 180 | Validación de tesis 6 meses |

### 3.2 Retorno logarítmico (alternativa)

```
log_return_Nd(ticker, t) = ln(close(ticker, t+N) / close(ticker, t))
```

Se calcula en paralelo al simple para detectar asimetría en la distribución. El Spearman principal usa retorno simple para interpretabilidad; el logarítmico se reporta como check de robustez.

### 3.3 Retorno relativo al mercado (excess return)

```
excess_return_Nd(ticker, t) = return_Nd(ticker, t) - return_Nd(SPY, t)
```

Donde SPY es el ETF del S&P 500 (ticker `SPY` añadido como benchmark, no como empresa del universo). Mide si el sistema identifica alpha genuino vs beta de mercado.

**Nota:** SPY debe añadirse a `fetch_prices.py` como ticker adicional siempre descargado, no como empresa del universo.

---

## 4. Métricas de evaluación

### 4.1 Information Coefficient (IC) — métrica principal

El IC es el coeficiente de correlación de Spearman entre el score y el retorno realizado:

```
IC_Nd = Spearman(score_t, return_Nd_t)   para todas las observaciones válidas
```

**Propiedades:**
- Rango: [-1, +1]
- 0 = sin poder predictivo
- +1 = ranking de scores predice perfectamente el ranking de retornos
- Se usa Spearman (rank correlation) en lugar de Pearson porque el score es ordinal y los retornos tienen colas pesadas

**Gate P1→P2:** IC_90d ≥ 0.25 con N ≥ 65 y p-value < 0.05.

**Interpretación de referencia:**
| IC | Interpretación |
|----|---------------|
| < 0.05 | Sin señal detectable |
| 0.05 – 0.15 | Señal débil (típico de factores individuales en quant) |
| 0.15 – 0.30 | Señal moderada — económicamente explotable |
| > 0.30 | Señal fuerte — raro en mercados eficientes |

### 4.2 IC medio acumulado (ICIR)

```
ICIR = mean(IC diario) / std(IC diario)
```

Donde el IC diario se calcula para cada fecha `t` con todas las observaciones de ese día. El ICIR mide la estabilidad de la señal en el tiempo (análogo al Sharpe de la señal de predicción).

**Umbral de referencia:** ICIR > 0.5 indica señal estable y explotable.

### 4.3 Hit Rate

```
HR_Nd = P(return_Nd > 0 | score >= 70) — P(return_Nd > 0 | score < 30)
```

Mide la diferencia en la tasa de acierto direccional entre las empresas clasificadas BULLISH (score ≥ 70) y BEARISH (score < 30).

**Umbral:** HR > 0.10 (10 puntos porcentuales de diferencia) para considerarlo señal.

**Nota:** requiere al menos 20 observaciones en cada grupo para ser interpretable.

### 4.4 Retorno de cartera simulada (long/short)

```
portfolio_return_Nd(t) = mean(return_Nd | score >= 70) - mean(return_Nd | score < 30)
```

Cartera long en empresas BULLISH, short en empresas BEARISH, igual-ponderada, rebalanceo diario. No incluye costes de transacción ni slippage (es una señal de paper trading, no una estrategia ejecutable).

```
Sharpe_señal = (mean(portfolio_return_Nd) / std(portfolio_return_Nd)) × sqrt(252/N)
```

Anualizado asumiendo N días de horizonte.

### 4.5 Decile analysis

Agrupa observaciones en 10 deciles por score y calcula el retorno medio de cada decil. Una señal válida debe mostrar monotonicidad aproximada (decil 10 = mayor retorno, decil 1 = menor retorno).

---

## 5. Segmentación del análisis

Todas las métricas se calculan en los siguientes cortes:

| Segmento | Descripción |
|----------|-------------|
| Global | Todas las observaciones válidas |
| Por horizonte | 7d / 30d / 90d / 180d |
| Por prompt_version | v2 exclusivamente para Spearman principal |
| Por sector | AI/Semis / Biotech / Energy / Cloud / Quantum |
| Por rango de score | Extremos (score<30 o score>70) vs Centro (30-70) |
| Por intensidad | CORE (±3) / HIGH (±2) / MEDIUM (±1) |

La segmentación por sector requiere añadir columna `sector` a `companies.json` (actualmente ausente — deuda técnica).

---

## 6. Significancia estadística

### 6.1 Test para IC (Spearman)

Para N observaciones, el estadístico:

```
t = IC × sqrt((N - 2) / (1 - IC²))
```

sigue una distribución t de Student con N-2 grados de libertad bajo H₀.

**Reportar:** IC, N, p-value bilateral, intervalo de confianza al 95%.

### 6.2 Tamaño mínimo de muestra

Con α=0.05 y potencia=0.80 para detectar IC=0.25:

```
N_min ≈ 65 observaciones
```

(derivado de la fórmula de potencia para correlación de Spearman)

Con universo de 51 empresas, se alcanza N=65 en ~2 días de datos (51×2=102). Sin embargo, los IC diarios no son independientes entre sí (mismo contexto de mercado), por lo que el N efectivo es menor. Se recomienda tratar las observaciones de un mismo día como un cluster y aplicar standard errors clusterizados.

### 6.3 Corrección por múltiples comparaciones

Al calcular IC para 4 horizontes × 5 segmentos = 20 tests, aplicar corrección Benjamini-Hochberg (FDR) para controlar la tasa de falsos positivos. Solo reportar como "señal detectada" si supera el umbral corregido.

---

## 7. Pipeline de cálculo

### 7.1 Script: `scripts/compute_validation.py`

Se ejecuta:
- Manualmente por el usuario cuando lo solicite
- **No** se añade al pipeline diario automático hasta tener N ≥ 65 observaciones v2

### 7.2 Lógica del script

```python
# Pseudocódigo — implementación pendiente
def compute_ic(horizon_days, prompt_version='v2'):
    scores = load_scores(prompt_version=prompt_version)
    prices = load_prices()
    
    observations = []
    for (ticker, date, score) in scores:
        price_t  = lookup_price(ticker, date, prices)
        price_tN = lookup_price(ticker, date + horizon_days, prices)  # next available
        if price_t and price_tN:
            ret = (price_tN - price_t) / price_t
            observations.append((score, ret))
    
    scores_arr  = [o[0] for o in observations]
    returns_arr = [o[1] for o in observations]
    
    ic, pvalue = spearmanr(scores_arr, returns_arr)
    return ic, pvalue, len(observations)
```

### 7.3 Output: `reports/validation_YYYYMMDD.md`

Informe markdown con:
- Fecha de cálculo y ventana de datos usada
- IC por horizonte (tabla)
- Hit rate BULLISH vs BEARISH
- Retorno de cartera simulada
- N observaciones por segmento
- Flag si supera gate P1→P2
- Advertencia si N < 65 (resultados no concluyentes)

---

## 8. Casos edge y decisiones de diseño

| Caso | Decisión |
|------|----------|
| Precio faltante en t+N (festivo/fin de semana) | Usar el siguiente día hábil disponible en `prices` |
| Precio faltante en t+N por más de 5 días hábiles | Descartar la observación |
| Empresa con score en t pero sin precio en t | Descartar (no hay baseline de retorno) |
| Score = 50 con `no_catalyst` | Incluir en análisis global; excluir del análisis de extremos (HR, cartera L/S) |
| Score v1 | Excluir del Spearman principal; incluir en análisis exploratorio separado con flag |
| Empresa eliminada del universo antes de t+N | Descartar la observación (survivorship bias explícito — documentar) |
| Split de acciones entre t y t+N | Cubierto por el precio ajustado de yfinance |
| Dividendos entre t y t+N | Cubiertos por el precio ajustado de yfinance |

### 8.1 Sesgo de supervivencia

El universo de 51 empresas es fijo desde 2026-05-22. Si una empresa fuera eliminada por quiebra o adquisición, sus observaciones pasadas se descartarían del análisis retrospectivo. Este sesgo se documenta pero no se corrige en v1 del validation engine (el universo es curado y estable).

---

## 9. Dependencias técnicas

| Dependencia | Versión mínima | Estado |
|-------------|---------------|--------|
| Python 3.10+ | 3.10 | ✅ disponible |
| `scipy.stats.spearmanr` | scipy 1.9 | por verificar |
| `numpy` | 1.24 | por verificar |
| `sqlite3` | stdlib | ✅ |
| `yfinance` | 1.4.0 | ✅ instalado |
| Ticker `SPY` en tabla `prices` | — | ⏳ pendiente añadir |
| Columna `sector` en `companies.json` | — | ⏳ pendiente |
| Columna `score_status` en `tech_scores` | — | ⏳ pendiente (schema v2) |

---

## 10. Fases de implementación

| Fase | Condición de entrada | Entregable |
|------|---------------------|------------|
| **F0 — Infraestructura** | Hoy | `prices` + `tech_scores` acumulando (✅ hecho) |
| **F1 — Script básico** | N ≥ 30 obs v2 (~2026-06-16) | `compute_validation.py` con IC_7d e IC_30d |
| **F2 — Reporte completo** | N ≥ 65 obs v2 (~2026-06-18) | Todos los horizontes + segmentación |
| **F3 — Gate P1→P2** | IC_90d disponible (~2026-08-26) | Decisión estadística sobre H₀ |
| **F4 — Automatización** | Superado gate P1→P2 | Añadir al pipeline diario |

---

## 11. Lo que esta spec NO cubre (fuera de scope v1)

- Optimización del score (no se retroalimenta el prompt con resultados de validación hasta P2)
- Análisis de factor attribution (qué componente del score — S_analistas, S_escenario, S_hype — aporta más IC)
- Portfolio construction real (sizing, riesgo, correlaciones entre posiciones)
- Costes de transacción y market impact
- Benchmark alternativo al SPY (equal-weighted, sector ETFs)

---

*Spec lista para auditoría. Ver sección 6 para las fórmulas estadísticas críticas y sección 8 para las decisiones de diseño que requieren validación.*
