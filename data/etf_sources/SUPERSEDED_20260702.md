# Selección 2026-07-02 — SUPERSEDED

`universe_selection_20260702_SUPERSEDED.json` (61 aceptados, universo resultante 112) queda archivada, no borrada.

**Por qué se reemplaza:** la fuente (`raw_holdings_20260702.json`) venía de stockanalysis.com, limitado a 25 holdings visibles por ETF sin suscripción. SMH, IGV e ICLN son fondos ponderados por capitalización — un corte a los primeros 25 por peso no es una muestra del tema, es sistemáticamente el tramo mega/large-cap de cada categoría. Eso reduce la dispersión cross-sectional de retornos idiosincráticos que el gate necesita y elimina el segmento de mid-caps donde un sistema temático tiene más probabilidad de aportar señal. Además, con N=112 el IC detectable (≈0.055) queda por encima del umbral del gate (0.05) — indetectable en 12 meses, no solo "un poco menos de margen".

**Filtros también corregidos en el reemplazo:**
- `VOLUME_FLOOR_SHR` (acciones) → `DOLLAR_ADV_FLOOR` (precio × volumen, $15M/día) — un floor en acciones penaliza precios altos y deja pasar chicharros de precio bajo.
- Sin regla de recorte a objetivo — el reemplazo añade cuota fija por categoría, ranking por dollar ADV (no por cap ni peso del ETF, para no reintroducir el sesgo large-cap).

**Reemplazo:** holdings completos de los emisores (CSV descargado manualmente, no scraping — los sitios de VanEck/iShares/State Street/Defiance bloquean fetch automatizado, verificado 2026-07-02 con 403/redirect-loop), fecha a determinar cuando los CSV estén disponibles en `data/etf_sources/raw_holdings_YYYYMMDD.json`.
