# FutureAnalysis — Company Keywords Update
# Ticker: {TICKER} | CIK: {CIK}

Para el ticker {TICKER} (CIK: {CIK}):

1. Busca el último 10-K disponible en SEC EDGAR con fetch MCP:
   `https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={CIK}&type=10-K&dateb=&owner=include&count=1&output=atom`

2. Accede al documento y lee la sección "Business" (Item 1) y "Risk Factors" (Item 1A).

3. Extrae las tecnologías mencionadas como:
   - Estratégicas (inversión activa, producto principal, ventaja competitiva)
   - Amenazas (tecnologías competidoras mencionadas como riesgo)

4. Keywords actuales asignadas: {KEYWORDS_ACTUALES}

5. Genera el diff en formato JSON ÚNICAMENTE (sin texto adicional):

```json
{
  "ticker": "{TICKER}",
  "filing_date": "YYYY-MM-DD",
  "keywords_nuevas": ["keyword1", "keyword2"],
  "keywords_obsoletas": ["keyword_vieja"],
  "keywords_mantener": ["keyword_vigente"],
  "razon": "Explicación de 1-2 líneas de los cambios detectados",
  "confianza": "alta|media|baja"
}
```

NO actualices ninguna base de datos. Este output es solo para revisión humana.
