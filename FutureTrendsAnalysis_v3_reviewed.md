# FutureAnalysis – Inteligencia de Tendencias Tecnológicas para Inversores
## Versión 3.1 – CRÍTICOs Pendientes Resueltos

> **Nota de revisión v3:** Este documento integra el análisis crítico de v2 (MiniMax Agent) y añade una capa de revisión contextual basada en el perfil real del proyecto: **inversor retail, developer solo, licencia Claude MAX, infraestructura cuantitativa existente en Valencia, España**. El v2 era técnicamente correcto pero genérico; el v3 es específico. Los comentarios editoriales aparecen como bloques `>` diferenciados por prioridad.

---

## 0. NUEVO — Diagnóstico de Contexto (Ausente en v1 y v2)

> **❌ OMISIÓN CRÍTICA en v1 y v2:** Ambas versiones ignoran completamente quién construye esto y con qué ya cuenta. Esto no es un error menor — cambia el 60% de las decisiones de diseño.

**Perfil del constructor:**
- Developer solo, trader sistemático, no un equipo de ingeniería
- Licencia Claude MAX (Claude.ai / Claude CLI) — coste fijo mensual
- Calls a Claude API son **coste adicional** sobre el MAX — cada llamada cuenta
- Infraestructura existente: plataforma IB equities, plataforma crypto Binance/Bitget, MacroSentinel, FCI/HMM, FAS (85 símbolos), SmartMoney Tracker
- Principio operativo: **demostrar valor antes de construir**; gate de validación antes de cada fase
- Stack conocido: Python, TypeScript, SQLite/PostgreSQL, Streamlit, Claude CLI con MCP servers

**Implicaciones que el v2 ignora:**

| Implicación | Decisión que cambia |
|------------|---------------------|
| Solo developer → no CI/CD compleja, no microservicios | Arquitectura monolítica o scripts orquestados es correcta |
| MAX license → Claude CLI calls gratis (fair use) | El "coste por ejecución" del v2 asume API billing — incorrecto aquí |
| analyst-sim via API = coste extra | Los analistas deben implementarse como **personas dentro de un solo contexto Claude CLI**, no como calls API separadas |
| Infraestructura existente | FutureAnalysis NO es un sistema standalone — debe integrarse o hay redundancia masiva |
| Polygon.io ya disponible | No hace falta `financial-data-mcp` nuevo — adaptar lo existente |

> **✅ BIEN en v2:** Identificó los problemas técnicos reales (sintaxis CLI, fórmula indefinida, base de datos de empresas). Esos siguen siendo válidos.

---

## 1. Visión y Objetivos (Revisada)

**Objetivo primario:** Sistema de escaneo de horizonte tecnológico que identifica, puntúa y rastrea tendencias emergentes para informar decisiones de inversión en renta variable (US equities).

**Diferenciación respecto a sistemas existentes:**

| Sistema existente | Qué hace | FutureAnalysis añade |
|-------------------|----------|----------------------|
| MacroSentinel | Macro sentiment (política, fed, tariffs) | Tendencias tecnológicas de largo plazo (2-5 años) |
| FCI/HMM | Condiciones financieras, régimen de mercado | N/A (no overlap) |
| FAS (85 símbolos) | Valuation + Earnings + CANSLIM | Exposición temática no capturada en fundamentales |
| SmartMoney Tracker | Flujos institucionales (13F, Form 4) | Smart money sigue temas; FutureAnalysis los identifica antes |

> **✅ BIEN original:** Visión clara.
>
> **✅ AÑADIDO v3:** La tabla de diferenciación es obligatoria — sin ella el proyecto es redundante con lo existente.
>
> **⚠️ INCOMPLETO aún:** El horizonte temporal de las predicciones importa enormemente para la integración con la plataforma IB. Tendencias de 2-5 años generan señales útiles para un trader sistemático **solo si** el scoring captura la fase de aceleración de adopción (típicamente 6-18 meses antes del impacto en earnings). Definir explícitamente: este sistema opera en horizonte **táctico-temático de 3-18 meses**, no daily trading.
>
> **❌ FALTA aún:** Alcance geográfico. Para equities US en IB: S&P 500 + NASDAQ Composite como universo inicial. Añadir ADRs de empresas tech europeas/asianas en v2.

---

## 2. Fuentes de Información (Revisada)

| Tipo | Fuentes | Acceso | Frecuencia sugerida | Prioridad |
|------|---------|--------|---------------------|-----------|
| Papers científicos | arXiv (cs.AI, cs.LG, q-bio, eess) | **API gratuita** | Diaria | Alta |
| Patentes | USPTO Patent Full-Text API | **Gratuita** | Semanal | Alta |
| Patentes | Espacenet OPS API (EPO) | **Gratuita con registro** | Semanal | Alta |
| Tech business | TechCrunch, Wired | RSS gratuito | Diaria | Alta |
| Tendencias VC | Crunchbase (API free tier) | Free tier limitado (~200 req/mes, sin funding rounds RT) | Semanal | Baja |
| GitHub | GitHub Search API (`/search/repositories?sort=stars`) | **Gratuita (5000 req/h autenticado)** | Diaria | Alta |
| Papers con código | Papers with Code API | **Gratuita** | Diaria | Alta |
| Financiero | Polygon.io | ✅ **Ya disponible** | On-demand | Alta |
| FRED | FRED API | **Gratuita** | Semanal | Media |
| Noticias | Tavily MCP (ya configurado) | ✅ **Ya disponible** | Diaria | Alta |
| Earnings releases | SEC EDGAR 8-K (Item 2.02) | **Gratuita** | Semanal (earnings season) | Alta |

**❌ ELIMINAR del spec (fuentes inviables para retail):**
- The Information, Stratechery: suscripciones caras ($300-500/año), sin API
- PitchBook, CB Insights: enterprise pricing ($10k+/año)
- Forrester, Gartner: idem
- Reddit r/MachineLearning: Reddit API cambió en 2023, ahora de pago ($12k/mes para >100 req/min)
- Google Patents: sin API oficial, scraping frágil (CAPTCHAs, DOM cambia sin aviso). **Reemplazado por Espacenet OPS API** (EPO, oficial, 500 req/h, cubre USPTO+EU).
- GitHub Trending (`github.com/trending`): solo es HTML, no hay API oficial. **Reemplazado por GitHub Search API**.

> **✅ BIEN en v2:** Señaló el problema de acceso a fuentes de pago.
>
> **✅ AÑADIDO v3:** Tabla con columna de acceso real y eliminación de inviables. La priorización por frecuencia es crucial para gestionar el rate limiting.
>
> **✅ RESUELTO (audit-council 2026-05-22):** Deduplicación. El mismo paper de arXiv aparecerá en arXiv + Papers with Code + TechCrunch. Estrategia:
> - **arXiv:** usar `arxiv_id` nativo (ej. `2405.12345`) como primary key — es el identificador canónico, no colisiona entre versiones v1/v2/v3.
> - **Otras fuentes sin ID nativo** (RSS TechCrunch, USPTO): SHA1 de la URL del item como ID.
> - **NO usar SHA1 de título+abstract**: los primeros 100-200 chars de papers similares o versiones del mismo paper pueden ser idénticos, produciendo colisiones silenciosas.
>
> **✅ RESUELTO (v3.1):** Fuente de earnings releases via SEC EDGAR 8-K Item 2.02. Ver Sección 6.2 para implementación. No transcripts completos (de pago) — el press release de resultados es suficiente para detectar menciones tecnológicas de management.

---

## 3. Arquitectura Real con Claude CLI y MCP

> **❌ ERROR CRÍTICO heredado de v1, parcialmente corregido en v2 pero sin alternativa concreta:** La sintaxis `claude --mcp server1,server2` NO existe. El v2 lo señaló pero no ofreció la arquitectura correcta. El v3 la especifica.

### 3.1 Cómo funciona realmente Claude CLI con MCP

```
# Configuración (una sola vez)
# ~/.claude/settings.json  ← MCPs disponibles globalmente
# O: .mcp.json en el directorio del proyecto ← MCPs del proyecto

# Ejecución no-interactiva (para cron/scheduler)
claude -p "Tu prompt aquí" --output-format text > output.md

# Ejecución con output JSON estructurado
claude -p "Tu prompt aquí" --output-format json

# Claude CLI cargará automáticamente los MCPs configurados
# No hay flags --mcp en runtime
```

**Configuración `.mcp.json` de ejemplo para FutureAnalysis:**

```json
{
  "mcpServers": {
    "fetch": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-fetch"]
    },
    "filesystem": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "/path/to/futureanalysis/data"]
    },
    "sqlite": {
      "command": "npx",
      "args": ["-y", "mcp-server-sqlite", "--db-path", "/path/to/futureanalysis/fa.db"]
    },
    "tavily": {
      "command": "npx",
      "args": ["-y", "tavily-mcp"],
      "env": { "TAVILY_API_KEY": "${TAVILY_API_KEY}" }
    }
  }
}
```

> **✅ v3:** Estos 4 MCPs son suficientes para el MVP. Fetch cubre arXiv API, USPTO, GitHub, Papers with Code, y cualquier RSS. Filesystem lee/escribe JSON locales. SQLite persiste scores. Tavily cubre búsqueda web de noticias.

### 3.2 Arquitectura real del sistema

```
┌─────────────────────────────────────────────────────────────────┐
│  SCHEDULER (cron diario / semanal)                              │
│  cron: 0 7 * * 1-5  →  cd /futureanalysis && ./run_daily.sh    │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                    ┌──────────▼──────────┐
                    │   run_daily.sh      │
                    │  claude -p $(cat    │
                    │  prompts/daily.md)  │
                    │  --output-format    │
                    │  text > reports/    │
                    │  $(date +%Y%m%d).md │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────────────────────────────┐
                    │   CLAUDE CLI SESSION (único contexto)        │
                    │                                              │
                    │  ┌─────────────────────────────────────┐    │
                    │  │  PROMPT MAESTRO (daily.md)          │    │
                    │  │  - Define 4 personas analista       │    │
                    │  │  - Instrucciones de flujo           │    │
                    │  │  - Output format JSON               │    │
                    │  └──────────────┬──────────────────────┘    │
                    │                 │                            │
                    │    ┌────────────┼────────────┐              │
                    │    ▼            ▼            ▼              │
                    │  [fetch MCP] [sqlite MCP] [tavily MCP]      │
                    │  arXiv API   Load prev    News search        │
                    │  USPTO API   scores       Tech trends        │
                    │  GitHub API  Write new                       │
                    │                scores                        │
                    └────────────────┬────────────────────────────┘
                                     │
                    ┌────────────────▼────────────────────────────┐
                    │   OUTPUT                                     │
                    │   reports/YYYYMMDD.md  ← informe humano     │
                    │   data/scores.db        ← SQLite histórico  │
                    │   data/trends.json      ← tendencias activas│
                    └─────────────────────────────────────────────┘
```

> **✅ v3:** Arquitectura realista para un solo developer. Sin microservicios, sin Kubernetes, sin Redis. Un cron + un script bash + Claude CLI con MCPs estándar.
>
> **❌ ELIMINADO intencionalmente:** Los 9 MCPs custom del v1/v2 (web-scraper-mcp, analyst-sim-mcp, etc.). El único MCP custom que podría valer la pena más adelante es un `polygon-mcp` wrapper sobre tu integración existente. Todo lo demás lo hace Claude CLI con `fetch` + buenos prompts.
>
> **⚠️ IMPORTANTE:** El "equipo de analistas" son **personas en el prompt maestro**, no procesos separados. Un solo contexto Claude CLI puede perfectamente simular perspectivas múltiples con secciones diferenciadas. Hacerlo via API calls separados multiplica el coste por 4x sin beneficio real a este nivel de madurez.

---

## 4. El Prompt Maestro (Componente Central — Ausente en v1 y v2)

> **❌ CRÍTICO no resuelto en v2:** "Los system prompts de cada analista NO EXISTEN en el documento." El v2 lo señaló correctamente pero no ofreció estructura. El v3 provee la plantilla.

### 4.1 Estructura del prompt diario

```markdown
# FutureAnalysis Daily Run — {FECHA}

## Contexto del sistema
Eres un sistema de análisis de tendencias tecnológicas para un inversor en renta variable US.
Tu universo es el S&P 500 y NASDAQ Composite.
Horizonte de predicción: 3-18 meses.

## Datos de sesión anterior
[INSERTAR: últimas 10 tendencias activas desde data/trends.json]
[INSERTAR: top 5 scores actuales desde data/scores.db]

## Fase 1 — Discovery (usar fetch MCP)
Consultar y resumir novedades relevantes de las últimas 24h:
1. arXiv API: https://export.arxiv.org/search/?query=...&start=0&max_results=20
2. GitHub Trending: https://api.github.com/search/repositories?q=...
3. Papers with Code: https://paperswithcode.com/api/v1/papers/?...
4. USPTO: [query de patentes de la semana]

Criterio de relevancia: potencial de impacto comercial en 3-18 meses.
Eliminar duplicados por similitud de título/tema.
Output: lista de max 15 eventos/tendencias con fuente y URL.

## Fase 2 — Análisis multidimensional
Para cada tendencia identificada, analiza desde 4 perspectivas:

**[ANALISTA TÉCNICO]** — Madurez tecnológica (TRL 1-9), obstáculos técnicos, time-to-market
**[ANALISTA ECONÓMICO]** — Impacto en costos/ingresos sectoriales, tamaño de mercado, pricing power
**[ANALISTA GEOPOLÍTICO]** — Regulación, subsidios, concentración geográfica (China-US), supply chain
**[ANALISTA CONTRARIAN]** — ¿Qué asume el consenso que podría estar equivocado? Riesgos de hype.

## Fase 3 — Scoring de empresas (S&P 500 + NASDAQ)
Para las 3-5 tendencias con mayor score de madurez+impacto:
- Identificar empresas beneficiadas (exposure: alta/media/baja) y perjudicadas
- Actualizar score en SQLite via sqlite MCP
- Escalar score de 0-100 donde: 50=neutral, 75+=bullish signal, 25-=bearish signal

## Fase 4 — Output estructurado
Genera el informe en formato Markdown con secciones:
1. Executive Summary (5 líneas)
2. Tendencias emergentes nuevas
3. Cambios de score significativos (Δ > 10 puntos)
4. Alertas de umbral (score > 80 o < 20)
5. Escenarios destacados con empresas afectadas
6. Notas para revisión humana

Guarda el JSON de scores via sqlite MCP antes de terminar.
```

> **✅ v3:** Este prompt maestro reemplaza los 9 MCPs custom del v1/v2. Es más barato de mantener, más fácil de iterar, y produce output comparable.
>
> **⚠️ IMPORTANTE:** Este prompt necesitará 5-10 iteraciones manuales antes de ser útil. El v1/v2 asumía que simplemente funcionaría. No funciona así. Planificar 2-3 semanas de ajuste de prompts en Phase 0.

### 4.2 Queries por categoría — `data/queries.json`

Los queries no van inline en el prompt maestro (lo haría superar ~2000 palabras). El prompt referencia `{INSERTAR queries.json}` y el script los inyecta en tiempo de ejecución.

```json
{
  "categories": [
    {
      "name": "AI/ML",
      "arxiv": "cat:cs.AI+OR+cat:cs.LG&sortBy=submittedDate&sortOrder=descending",
      "github": "q=machine+learning+OR+llm+OR+transformer&sort=stars&order=desc&per_page=20",
      "uspto": "patent_date:[NOW-7DAYS+TO+NOW]&q=\"machine+learning\"+OR+\"large+language+model\""
    },
    {
      "name": "Quantum Computing",
      "arxiv": "cat:quant-ph+OR+cat:cs.ET&sortBy=submittedDate&sortOrder=descending",
      "github": "q=quantum+computing+OR+qiskit+OR+cirq&sort=stars&order=desc&per_page=20",
      "uspto": "patent_date:[NOW-7DAYS+TO+NOW]&q=\"quantum+computing\"+OR+\"qubit\""
    },
    {
      "name": "Gene Editing / Biotech",
      "arxiv": "cat:q-bio.GN+OR+cat:q-bio.QM&sortBy=submittedDate&sortOrder=descending",
      "github": "q=crispr+OR+gene+editing+OR+bioinformatics&sort=stars&order=desc&per_page=20",
      "uspto": "patent_date:[NOW-7DAYS+TO+NOW]&q=\"CRISPR\"+OR+\"gene+editing\"+OR+\"mRNA\""
    },
    {
      "name": "Clean Energy",
      "arxiv": "cat:eess.SY+OR+cat:physics.app-ph&sortBy=submittedDate&sortOrder=descending",
      "github": "q=solar+energy+OR+battery+OR+grid+storage&sort=stars&order=desc&per_page=20",
      "uspto": "patent_date:[NOW-7DAYS+TO+NOW]&q=\"solid+state+battery\"+OR+\"perovskite+solar\""
    },
    {
      "name": "Advanced Semiconductors",
      "arxiv": "cat:cs.AR+OR+cat:eess.SP&sortBy=submittedDate&sortOrder=descending",
      "github": "q=chip+design+OR+RISC-V+OR+neuromorphic&sort=stars&order=desc&per_page=20",
      "uspto": "patent_date:[NOW-7DAYS+TO+NOW]&q=\"semiconductor\"+AND+(\"3nm\"+OR+\"packaging\"+OR+\"chiplet\")"
    }
  ]
}
```

> **⚠️ Verificar antes de usar:** Los endpoints de arXiv Export API (`export.arxiv.org/search/`) y USPTO PatentsView (`api.patentsview.org/patents/query`) pueden tener cambios de sintaxis. Hacer una llamada manual de prueba con `fetch` MCP antes de meterlos en cron.
>
> **Phase:** P0 — crear el archivo manualmente antes de la primera ejecución.

---

## 5. Flujo de Trabajo Completo (Revisado)

### 5.1 Discovery — Correcciones al v2

> **⚠️ PROBLEMA del v2:** "'Claude resume' - ¿cuál Claude?" — Resuelto: es Claude CLI en la sesión. El prompt maestro (sección 4) incluye instrucciones de resumen.
>
> **❌ FALTA aún:** Estrategia de deduplicación. Implementar hash SHA1 de (título + primeros 100 chars abstract) como ID único antes de almacenar en SQLite. Si hash ya existe en DB → skip.

### 5.2 Generación de hipótesis — Correcciones al v2

**Resolución de conflictos entre analistas** (❌ FALTA en v2):

```markdown
Si hay conflicto entre perspectivas (ej. Técnico dice TRL=7, Geopolítico dice "bloqueado"):
- El conflicto es la señal, no el ruido
- Output: "CONFLICTO DETECTADO — tendencia bloqueada temporalmente, monitorear trigger regulatorio"
- Score freeze: mantener score anterior hasta resolución
- Flag manual review en el informe
```

> **⚠️ PROBLEMA no resuelto:** Las probabilidades de escenario (50/25/25) siguen siendo arbitrarias. Propuesta v3: no usar probabilidades explícitas hasta tener al menos 6 meses de histórico. En Phase 0 y 1, usar solo intensidad: BEARISH / NEUTRAL / BULLISH / STRONG_BULLISH. Más simple, igual de útil, no da falsa precisión.

### 5.3 Construcción de escenarios — Correcciones al v2

> **❌ FALTA del v2 abordado:** Metodología para intensidad (–3 a +3).

**Criterios de intensidad de exposure:**

| Nivel | Criterio |
|-------|----------|
| +3 (CORE) | La tecnología ES el producto principal de la empresa (ej. IONQ en cuántica) |
| +2 (HIGH) | La tecnología impacta >30% del revenue o mejora >20% márgenes |
| +1 (MEDIUM) | La tecnología es un enabler pero no core |
| 0 (NEUTRAL) | Impacto tangencial |
| -1 (EXPOSED) | La tecnología desplaza una línea de producto menor |
| -2 (THREATENED) | La tecnología amenaza >30% del negocio actual |
| -3 (DISRUPTED) | La tecnología hace obsoleto el modelo de negocio principal |

> **✅ v3:** Esta escala es auditable. Claude puede justificar cada asignación con evidencia de la fuente.

### 5.4 Mapeo a empresas — El problema central

> **❌ CRÍTICO del v2, confirmado en v3:** La "Base de datos de empresas" no puede construirse automáticamente de forma fiable. Opciones:

**Opción A (recomendada para MVP):** Universo inicial pequeño y manual
- Seleccionar 50-100 empresas curadas del S&P 500 con exposición tecnológica clara
- Para cada empresa: 3-5 keywords tecnológicas asignadas manualmente
- Claude actualiza exposure scores, no los crea desde cero
- Tiempo estimado: 4-6 horas de trabajo inicial de curación

**Opción B (escalable, para Phase 2):** Generación automática
- Usar fetch MCP para leer 10-Ks de SEC EDGAR (sección "Risk Factors" y "Business")
- Claude extrae automáticamente tecnologías mencionadas y crea el mapping
- Requiere validación humana de muestra (10-20%) antes de usar en producción
- Tiempo estimado: 2-3 días de desarrollo + validación

**Estrategia de actualización del universo (✅ RESUELTO v3.1):**

Schema de `companies.json` con columnas de staleness:
```json
{
  "companies": [
    {
      "ticker": "NVDA",
      "name": "NVIDIA Corporation",
      "keywords": ["GPU", "CUDA", "AI inference", "data center"],
      "keywords_version": 1,
      "last_validated": "2026-05-14",
      "cik": "0001045810"
    }
  ]
}
```

Empresa marcada como **stale** si `last_validated` > 100 días. El script semanal detecta y avisa:
```python
# fragmento en run_weekly.sh
import json, datetime
with open("data/companies.json") as f:
    data = json.load(f)
today = datetime.date.today()
stale = [c["ticker"] for c in data["companies"]
         if (today - datetime.date.fromisoformat(c["last_validated"])).days > 100]
if stale:
    print(f"[STALE] Empresas para re-validar: {', '.join(stale)}")
```

Re-validación via `prompts/company_update.md` (prompt incluido en Sección 6.2). Genera diff JSON para revisión humana — **nunca auto-merge**. Un pivot mal detectado invalida scores históricos silenciosamente.

**Phase:** P1 (schema desde el inicio). Lógica stale en P1. Prompt re-validación en P2.

### 5.5 Scoring Engine — Definición matemática

> **❌ CRÍTICO del v2, resuelto en v3:** La fórmula `f(...)` necesita implementación concreta para Phase 1.

**Fórmula propuesta Phase 1 (simple y auditable):**

```python
# Weighted average con pesos fijos iniciales (revisables con backtesting)
Score(t) = round(
    0.25 * S_hype(t)       +   # menciones ponderadas por autoridad de fuente
    0.35 * S_analistas(t)  +   # promedio de scores de las 4 perspectivas
    0.25 * S_escenario(t)  +   # exposición en escenarios activos
    0.15 * S_tecnico(t)        # momentum técnico (RSI/precio relativo vs sector)
)

# Donde cada S_x ∈ [0, 100]
# S_hype: clip(50 + α × (log(m_t) - μ_90d) / σ_90d, 0, 100)
#         α calibrado para que ±2σ mapee a [10,90]
#         cold-start (<90d historia): usar σ cross-sectional del día en lugar de σ histórico
# S_analistas: promedio de scores individuales (ver regla de conflicto más abajo)
# S_escenario: clip(intensidad_exposure × p_proxy × 20 + 50, 0, 100)
#   p_proxy en Phase 0-1 (sin probabilidades calibradas):
#     BEARISH → 0.25, NEUTRAL → 0.50, BULLISH → 0.75, STRONG_BULLISH → 1.00
#   Verificación de rango: intensidad=+3, p=1.0 → clip(3×1×20+50,0,100) = 100 ✓
#                          intensidad=-3, p=1.0 → clip(-3×1×20+50,0,100) = 0 ✓
# S_tecnico: puede usar datos de Polygon.io de tu plataforma existente
```

**Regla de conflicto en S_analistas:**
- Conflicto definido como: `max(scores_individuales) - min(scores_individuales) > 50 puntos`
- Si hay conflicto: S_analistas = 50 (neutral), flag `analistas_conflicto=True` en el output
- Si no hay conflicto: S_analistas = promedio aritmético de los 4 scores individuales
- El score congelado en conflicto se marca como `CONFLICTO — sin valor predictivo en este ciclo`, no se presenta como score vigente

> **⚠️ IMPORTANTE:** Esta fórmula es un punto de partida, no la fórmula óptima. El v2 tenía razón en que necesita backtesting. Pero necesitas una fórmula concreta para poder validar. Implementa esta, mide correlación con precios 6 meses, luego ajusta pesos.
>
> **✅ BIEN del v2:** Feedback loop (correlación Pearson mensual) bien concebido. Añadir también Spearman dado que la relación puede ser monotónica pero no lineal (igual que en MacroSentinel usas Spearman).

---

## 6. Automatización Real — Reemplazo de Sección 6 del v1

> **❌ ERROR CRÍTICO del v1 eliminado:** La sección 6 original con `claude --mcp` no existe. Reemplazada completamente.

**Estructura de archivos del proyecto:**

```
futureanalysis/
├── .mcp.json                    # Configuración MCP del proyecto
├── .env                         # API keys (TAVILY_API_KEY, POLYGON_API_KEY)
├── prompts/
│   ├── daily.md                 # Prompt maestro diario (Sección 4.1)
│   ├── weekly_summary.md        # Prompt para informe semanal consolidado
│   └── company_update.md        # Prompt para actualizar mapping de empresa específica
├── scripts/
│   ├── run_daily.sh             # Ejecuta ciclo diario
│   ├── run_weekly.sh            # Genera informe semanal + backtest mensual
│   └── seed_companies.sh        # Inicializa DB con universo de empresas
├── data/
│   ├── fa.db                    # SQLite: scores históricos, tendencias, empresas
│   ├── companies.json           # Universo de empresas con keywords tecnológicas
│   └── trends.json              # Tendencias activas (cache para contexto)
└── reports/
    └── YYYYMMDD.md              # Informes diarios generados
```

**Script run_daily.sh:**

```bash
#!/bin/bash
set -euo pipefail

# Determinar directorio del proyecto (compatible Windows/WSL y Unix)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Cargar variables de entorno
source "${PROJECT_DIR}/.env"

# Fecha para el informe
DATE=$(date +%Y%m%d)

# Actualizar contexto con últimas tendencias (manejo explícito de fallo)
if sqlite3 "${PROJECT_DIR}/data/fa.db" \
  "SELECT json_group_array(json_object('ticker',ticker,'score',score,'trend',trend_name)) 
   FROM scores WHERE date = (SELECT MAX(date) FROM scores) LIMIT 10;" \
  > "${PROJECT_DIR}/data/trends.json" 2>/dev/null; then
  echo "[$(date)] trends.json actualizado"
else
  echo "[]" > "${PROJECT_DIR}/data/trends.json"
  echo "[$(date)] WARNING: fa.db no disponible, usando contexto vacío"
fi

# Construir prompt con contexto dinámico (via Python para evitar injection y problemas de quoting)
python3 - <<'PYEOF'
import os, json, sys
project_dir = os.environ.get('PROJECT_DIR', os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
date_str = os.environ.get('DATE', '')

with open(f"{project_dir}/prompts/daily.md") as f:
    prompt = f.read()

try:
    with open(f"{project_dir}/data/trends.json") as f:
        trends_raw = f.read(1000)  # limit seguro
except:
    trends_raw = "[]"

prompt = prompt.replace("{FECHA}", date_str)
prompt = prompt.replace("{TENDENCIAS_ACTIVAS}", trends_raw)

with open(f"/tmp/fa_prompt_{date_str}.md", "w") as f:
    f.write(prompt)
PYEOF

export PROJECT_DIR DATE

# Ejecutar Claude CLI (prompt desde archivo, no inline — evita ARG_MAX y quoting)
cd "${PROJECT_DIR}"
claude -p "$(cat /tmp/fa_prompt_${DATE}.md)" --output-format text > "/tmp/fa_report_${DATE}.md"

# Validar output mínimo antes de guardar
REPORT_SIZE=$(wc -c < "/tmp/fa_report_${DATE}.md")
if [ "$REPORT_SIZE" -lt 500 ]; then
  echo "[$(date)] ERROR: reporte demasiado corto (${REPORT_SIZE} bytes) — posible error de Claude. Ver /tmp/fa_report_${DATE}.md"
  exit 1
fi

mv "/tmp/fa_report_${DATE}.md" "${PROJECT_DIR}/reports/${DATE}.md"
rm -f "/tmp/fa_prompt_${DATE}.md"

echo "[$(date)] ✅ FutureAnalysis report generado: reports/${DATE}.md (${REPORT_SIZE} bytes)"
```

---

### 6.2 Scripts adicionales (v3.1)

**Script `run_weekly_filings.sh` — earnings releases via SEC EDGAR:**

```bash
#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
source "${PROJECT_DIR}/.env"

# Solo correr durante earnings season: semanas 2-5 de cada trimestre
WEEK_OF_MONTH=$(( ($(date +%d) - 1) / 7 + 1 ))
if [ "$WEEK_OF_MONTH" -lt 2 ] || [ "$WEEK_OF_MONTH" -gt 5 ]; then
  echo "[$(date)] Fuera de earnings season, skip."
  exit 0
fi

DATE=$(date +%Y%m%d)
START=$(date -d "7 days ago" +%Y-%m-%d)
END=$(date +%Y-%m-%d)

cd "${PROJECT_DIR}"
claude -p "$(cat prompts/filings_scan.md | sed "s/{START}/$START/g" | sed "s/{END}/$END/g")" \
  --output-format text >> "reports/filings_${DATE}.md"

echo "[$(date)] ✅ Filings scan completado: reports/filings_${DATE}.md"
```

**Prompt `prompts/filings_scan.md`:**

```markdown
Consulta la SEC EDGAR full-text search para 8-K entre {START} y {END}.
Para cada keyword de la lista, busca con fetch MCP:
https://efts.sec.gov/LATEST/search-index?q={KEYWORD}&dateRange=custom&startdt={START}&enddt={END}&forms=8-K

Keywords: "artificial intelligence", "quantum", "CRISPR", "solid state battery", "chiplet"

Para cada 8-K encontrado de una empresa en nuestro universo (ver data/companies.json):
- Registrar en SQLite tabla `filings_mentions`: ticker, filing_date, keyword, url_filing, snippet
- Flag si la mención es en contexto positivo (adopción) vs negativo (riesgo/competencia)

Output: lista de empresas con menciones tecnológicas nuevas esta semana, ordenadas por relevancia.
```

**Prompt `prompts/company_update.md` — re-validación de empresa stale:**

```markdown
Para el ticker {TICKER} (CIK: {CIK}):
1. Busca el último 10-K en SEC EDGAR con fetch MCP:
   https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={CIK}&type=10-K&dateb=&owner=include&count=1
2. Lee la sección "Business" y "Risk Factors"
3. Extrae las tecnologías mencionadas como estratégicas o como riesgo
4. Compara con keywords actuales: {KEYWORDS_ACTUALES}
5. Output formato JSON ÚNICAMENTE:
   {"ticker": "...", "keywords_nuevas": [...], "keywords_obsoletas": [...], "razon": "..."}

NO actualices la base de datos. Solo genera el diff para revisión humana.
```

> Tras revisión humana, aplicar manualmente:
> ```bash
> sqlite3 fa.db "UPDATE companies SET keywords=..., last_validated='$(date +%Y-%m-%d)', keywords_version=keywords_version+1 WHERE ticker='NVDA'"
> ```

> **⚠️ Windows:** Ejecutar via Task Scheduler como `wsl bash /mnt/c/projects/FutureTrends/scripts/run_daily.sh` en lugar de cron nativo de WSL, para evitar que WSL no esté corriendo en background. La variable `PROJECT_DIR` se calcula dinámicamente desde `BASH_SOURCE[0]` — no hardcodear rutas.

> **⚠️ LIMITACIÓN CONOCIDA:** `claude -p` con prompts muy largos puede tener comportamiento inconsistente. Si el prompt maestro supera ~2000 palabras, mejor usar `claude -p "$(cat prompts/daily.md)"` con el archivo directamente, o la bandera `--input-file` si está disponible en tu versión de Claude CLI. Verificar con `claude --help`.
>
> **✅ v3:** Sin Lambda, sin Redis, sin Docker. Un bash script + cron es suficiente para Phase 0 y Phase 1. Añadir infraestructura solo si la validación lo justifica.

---

## 7. Stack Técnico, Costos y Feasibility

> **❌ CRÍTICO del v2, completamente ausente en v1:** Estimación de costos. Especialmente importante aquí porque el perfil del builder es retail investor con licencia MAX.

### 7.1 Análisis de costos reales

| Componente | Coste | Notas |
|------------|-------|-------|
| Claude CLI (diario) | **$0 extra** | Incluido en MAX license (fair use) |
| Claude API para analyst-sim separado | ❌ **NO USAR** | Coste innecesario; usar personas en prompt |
| arXiv API | $0 | Free, sin límite razonable |
| GitHub API (autenticado) | $0 | 5,000 req/hora |
| Papers with Code API | $0 | Free |
| USPTO Patent API | $0 | Free (PatentsView o PEDS) |
| Tavily MCP | ~$0-$5/mes | Free tier: 1,000 búsquedas/mes; suficiente para uso diario |
| Polygon.io | ✅ Ya disponible | Reutilizar de tu plataforma IB |
| Crunchbase API (free tier) | $0 | Limitado: 200 req/mes; suficiente para semanal |
| SQLite + filesystem local | $0 | Sin cloud DB en Phase 0/1 |
| Cron scheduler | $0 | Linux nativo |
| **Total Phase 0-1** | **~$0-5/mes extra** | — |

> **✅ v3:** Con estas elecciones, FutureAnalysis puede operar con coste marginal ~$0 sobre tu MAX license existente hasta que demuestre valor.
>
> **❌ COSTE OCULTO no mencionado en ninguna versión:** Tiempo. La curación inicial de la base de empresas (Opción A) son 4-6 horas. El ajuste de prompts son 2-3 semanas. El backtesting requiere construir el dataset histórico. Planificar 20-30 horas de trabajo total antes de tener un sistema que funcione en producción.

### 7.2 Feasibility del concepto central

> **❌ CRÍTICO del v2, no resuelto:** "No hay validación de que esto sea posible."

Esta es la pregunta más importante del spec y ninguna versión la responde con honestidad. Vamos a hacerlo ahora:

**¿Puede un sistema de scoring de tendencias tecnológicas predecir precios de acciones?**

**Evidencia a favor:**
- Los fondos temáticos (ARK, KROP, BOTZ) demuestran que hay alpha en identificar adoptores tempranos
- La investigación cuantitativa en "alternative data" muestra que señales no-precio tienen valor predictivo a 3-12 meses
- El período de aceleración tecnológica (TRL 5→7) históricamente precede re-ratings de múltiplos

**Evidencia en contra:**
- El mercado descuenta tendencias rápidamente cuando son ampliamente conocidas
- Las señales de hype (arXiv papers) pueden ser contrarias: el peak de papers suele coincidir con el peak del ciclo de expectativas (Gartner hype cycle)
- Requiere N estadísticamente significativo: 18-24 meses de histórico para tener confianza

**Conclusión práctica para v3:** El concepto es plausible pero no demostrado para este caso específico. Por eso el enfoque de **validation gate architecture** (igual que en tu FCI/HMM y SmartMoney Tracker) es correcto: construir en shadow mode, medir correlación vs precios durante 6 meses, solo integrar si métricas superan umbrales.

**Gate de integración sugerido:**
- Spearman correlation Score vs ΔPrecio(30d) ≥ 0.25 (IC positivo demostrado)
- **N ≥ 65** empresas evaluadas con al menos 30 días de historia (N=50 no alcanza p<0.05 con ρ=0.25; N=65 sí)
- Top quintil del score outperforms bottom quintil por ≥ 5% en **retorno relativo al índice**, igual-ponderado, en 90 días
- Las 65 empresas del gate deben seleccionarse **antes de ver los scores** (pre-registro con timestamp) para evitar selección implícita

**Validación en cada output (Phase 0-1):**
Todos los informes deben incluir en el encabezado:
```
VALIDATION_STATUS: UNVALIDATED
Los scores en este informe no han superado el gate estadístico de Phase 2.
No usar para decisiones de tamaño de posición.
```
Este header se elimina solo cuando el gate de Phase 2 esté superado.

---

## 8. NUEVO — Integración con Infraestructura Existente

> **❌ OMISIÓN TOTAL en v1 y v2:** FutureAnalysis no es un sistema standalone. Para que tenga valor real, necesita conectarse a lo que ya tienes.

### 8.1 Diagrama de integración

```
MacroSentinel          FCI/HMM              SmartMoney
(macro sentiment)   (conditions + regime)  (institutional flows)
       │                   │                      │
       └───────────────────┼──────────────────────┘
                           │
                    ┌──────▼──────┐
                    │  FAS (85    │
                    │  símbolos)  │
                    │  Valuation  │
                    │  Earnings   │
                    │  CANSLIM    │
                    └──────┬──────┘
                           │
               ┌───────────▼───────────┐
               │   FutureAnalysis      │
               │   (tech trend layer)  │
               │   Score: 0-100        │
               │   Horizon: 3-18m      │
               └───────────┬───────────┘
                           │
               ┌───────────▼───────────┐
               │  IB Platform          │
               │  Stock Universe Filter│
               │  "Thematic Momentum"  │
               │  gate (shadow mode)   │
               └───────────────────────┘
```

### 8.2 Puntos de integración concretos

**Integración con FAS:**
- FAS puntúa 85 símbolos en Valuation + Earnings + CANSLIM (DB: `C:\projects\trading-platform\data\fundamentals.db`)
- FutureAnalysis añade un 4to sub-score: `S_tech_exposure` (exposición temática)
- FAS composite grade puede incluir FutureAnalysis como tiebreaker entre símbolos con scores similares
- **Implementación:** FutureAnalysis mantiene `tech_score` en su propia DB (`fa.db`, tabla `tech_scores`, columnas: `ticker TEXT, score INTEGER, trend_name TEXT, date TEXT, confidence INTEGER`). FAS consume via JSON export o query directa a `fa.db` — **NO escribir en `fundamentals.db`** (dependencia inversa que acopla los sistemas).
- **Universo:** operar sobre los 85 símbolos de FAS como universo inicial. Si FutureAnalysis añade tickers fuera de FAS, no tendrán contraparte Valuation/Earnings/CANSLIM — excluirlos del composite hasta que FAS los incorpore.

**Integración con SmartMoney Tracker:**
- SmartMoney detecta flujos institucionales en un ticker/sector
- FutureAnalysis explica POR QUÉ (qué tendencia tecnológica está impulsando el flujo)
- **Señal de convicción válida:** `FINRA_SHORT_DIVERGENCE (CONDITIONAL_LIVE)` en ticker X + `FutureAnalysis_score > 75` en ticker X
- **⚠️ CRÍTICO:** `STRONG_ACCUMULATION` y `MODERATE_ACCUMULATION` están en **shadow_mode=1 permanente** (edge empíricamente falsificado — MedExcess negativo en todos los cap tiers). NO usar acumulación institucional como gate de convicción.
- **Implementación:** Alert cuando FINRA_SHORT_DIVERGENCE (shadow_signals donde signal_type='FINRA_SHORT_DIVERGENCE' AND shadow_mode=0) coincide con ticker de score alto en FutureAnalysis

**Integración con IB Platform:**
- FutureAnalysis en shadow mode inicialmente (igual que SmartMoney y FCI)
- Gate de activación: gate de integración de sección 7.2
- En producción: FutureAnalysis_score > 75 añade ticker a "thematic watchlist" para revisión humana antes de trade

> **⚠️ PRIORIDAD:** Esta sección de integración debería haberse discutido en la Sección 1 (Objetivos). El objetivo real no es "sistema autónomo de tendencias" sino "capa temática que mejora la selección de acciones en tu plataforma IB existente". Eso cambia todo el scope.

---

## 9. NUEVO — Roadmap por Fases con Gates

> **❌ FALTA del v2:** Timeline realista. Aquí está.

### Phase 0: Proof of Concept (Semanas 1-2)
**Objetivo:** Validar que Claude CLI puede generar análisis temático útil antes de construir infraestructura.

**Entregables:**
- [ ] Prompt maestro v1 (manual, sin automatización)
- [ ] 3 ejecuciones manuales con arXiv + GitHub Trending
- [ ] 10 tickers evaluados manualmente con scoring de intensidad
- [ ] Comparación subjetiva vs tu research actual: ¿añade valor?

**Coste:** ~2-4 horas. Si no añade valor obvio, **STOP**.

**Gate P0→P1:** El análisis generado te parece más útil que lo que harías manualmente en el mismo tiempo.

### Phase 1: MVP Automatizado (Semanas 3-6)
**Objetivo:** Pipeline automatizado básico con persistencia.

**Entregables:**
- [ ] `.mcp.json` configurado con fetch + sqlite + filesystem + tavily
- [ ] Script `run_daily.sh` funcional
- [ ] DB SQLite con schema de scores e historial
- [ ] Universo inicial de 50 empresas curadas con keywords
- [ ] Cron configurado (lunes-viernes 7:00)
- [ ] Primer informe semanal generado automáticamente

**Coste:** ~15-20 horas de desarrollo. Coste operativo: ~$0-5/mes.

**Gate P1→P2:** 30 días de ejecución continua sin fallos críticos. Informes subjetivamente útiles.

### Phase 2: Validación Cuantitativa (Meses 2-6)
**Objetivo:** Medir correlación estadística. Eliminar o confirmar el concepto.

**Entregables:**
- [ ] 6 meses de histórico de scores
- [ ] Cálculo mensual de Spearman correlation
- [ ] Comparación top-quintil vs bottom-quintil de scores
- [ ] SEC 10-K scraping para ampliar universo a 150+ empresas

**Gate P2→P3:** Métricas de sección 7.2 superadas. Si no → rediseño de fórmula o STOP.

### Phase 3: Integración en Producción (Mes 7+)
**Objetivo:** FutureAnalysis como capa activa en IB platform.

**Condición:** Sólo si Phase 2 valida el concepto. No construir antes.

---

## 10. Secciones Omitidas — Priorización para Solo Developer Retail

> **v2 identificó correctamente A-G de omisiones. v3 prioriza según perfil real.**

### Crítico para este perfil:

**A. Costos:** ✅ Resuelto en Sección 7.1 — coste ~$0 con arquitectura propuesta.

**G. Legal:** En España bajo MiFID II: añadir disclaimer en todos los informes generados: *"Este análisis es información de apoyo a decisiones personales de inversión. No constituye consejo financiero ni recomendación de inversión. Elaborado por sistema automatizado sin supervisión regulada."* Es suficiente para uso personal.

**Licencias de datos:** arXiv (Creative Commons), GitHub (público), Papers with Code (MIT). El scraping de USPTO y feeds RSS públicos está permitido para uso personal. No requiere acuerdos empresariales.

### No crítico para Phase 0-1 (diferir):

**A. Seguridad:** Sistema local en tu máquina Windows, sin exposición a internet. API keys en `.env` con `.gitignore`. Suficiente para Phase 0-1. Añadir gestión de secretos si mueves a cloud (Phase 3+).

**B. Observabilidad:** Logging básico (`tee -a logs/daily.log`) en `run_daily.sh` es suficiente para Phase 0-1. Sin Prometheus, sin ELK stack.

**D. Escalabilidad:** 50-150 empresas × 3-5 tendencias = trivial para SQLite. No es un problema hasta Phase 3.

**E. Testing:** Unit tests para el scoring SQL son útiles pero no bloqueantes en Phase 0. Prioritizar en Phase 1 para la fórmula de scoring.

**F. UI:** Los informes Markdown son suficientes para uso personal. Un Streamlit dashboard (ya tienes experiencia con esto) puede añadirse en Phase 2 si el sistema es útil. No construir UI antes de validar el concepto.

---

## 11. Conclusión y Recomendación de Próximo Paso

**Lo que está bien:**
- Visión clara y diferenciada respecto a herramientas de inversión convencionales
- Flujo de trabajo conceptualmente sólido
- Correctamente identificado como proyecto de largo plazo con validación gradual

**Lo que hay que cambiar fundamentalmente:**
- Arquitectura: de "9 MCPs custom" a "4 MCPs estándar + prompt maestro" (más simple, más barato, más mantenible)
- Analyst-sim: de "API calls separados" a "personas en contexto único Claude CLI" (elimina coste variable)
- Scope inicial: de "sistema completo" a "Phase 0 manual en 2 días" con gate de validación
- Posicionamiento: de "sistema standalone" a "capa temática integrada en IB platform"

**Próximo paso concreto (esta semana):**
1. Escribir prompt maestro v1 (basarte en plantilla de Sección 4.1)
2. Ejecutar manualmente 3 veces con arXiv + GitHub Trending de los últimos 7 días
3. Evaluar si el output te parece útil vs tu research manual actual
4. Si sí → proceder a Phase 1. Si no → pivotar la hipótesis antes de construir.

**Coste del próximo paso:** 2-4 horas de tu tiempo. $0 adicional sobre tu MAX license.

---

*Documento v3.1 — Revisión editorial: Claude Sonnet 4.6*
*Fecha v3: 2026-05-14 | Fecha v3.1: 2026-05-21*
*Basado en: FutureAnalysis v2 annotated (MiniMax Agent) + contexto de proyecto específico*
*v3.1: Resueltos 3 CRÍTICOs pendientes — queries por categoría (4.2), EDGAR earnings (6.2), actualización universo (5.4)*
