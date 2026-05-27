# FutureAnalysis — SEC EDGAR Filings Scan
# Periodo: {START} a {END}

Consulta la SEC EDGAR full-text search para 8-K entre {START} y {END}.

Para cada keyword de la lista, busca con fetch MCP:
`https://efts.sec.gov/LATEST/search-index?q={KEYWORD}&dateRange=custom&startdt={START}&enddt={END}&forms=8-K`

Keywords a buscar:
- "artificial intelligence"
- "machine learning"
- "quantum computing"
- "CRISPR"
- "solid state battery"
- "chiplet"
- "autonomous driving"
- "large language model"

Para cada 8-K encontrado:
1. Verifica si el ticker del emisor está en nuestro universo (data/companies.json)
2. Si está: extrae el snippet relevante (máx 200 chars) y clasifica el contexto:
   - ADOPTION: management menciona adopción activa o inversión en la tecnología
   - RISK: se menciona como riesgo competitivo o amenaza
   - NEUTRAL: mención informativa sin posicionamiento claro
3. Output formato tabla:

| Ticker | Empresa | Filing Date | Keyword | Contexto | Snippet |
|--------|---------|-------------|---------|----------|---------|

Si no hay menciones relevantes en el universo esta semana: indicar "Sin menciones relevantes en universo curado."
