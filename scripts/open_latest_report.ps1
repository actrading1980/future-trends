# FutureAnalysis - Open Latest Report as HTML
# Finds the most recent YYYYMMDD.md, injects tickers, renders as HTML

$ProjectDir = "C:\projects\FutureTrends"
$ReportsDir = "$ProjectDir\reports"
$CompaniesFile = "$ProjectDir\data\companies.json"

# Find latest report (YYYYMMDD.md format)
$latest = Get-ChildItem $ReportsDir -Filter "????????.md" |
    Sort-Object Name -Descending |
    Select-Object -First 1

if (-not $latest) {
    [System.Windows.Forms.MessageBox]::Show("No hay reportes generados aun.", "FutureTrends")
    exit 1
}

$markdown = [System.IO.File]::ReadAllText($latest.FullName, [System.Text.Encoding]::UTF8)
$reportDate = $latest.BaseName

# Build name->ticker map from companies.json
$companies = (Get-Content $CompaniesFile -Raw -Encoding utf8 | ConvertFrom-Json).companies

# Sort by name length descending to match longest names first (avoid partial matches)
$sorted = $companies | Sort-Object { $_.name.Length } -Descending

foreach ($c in $sorted) {
    $name = [regex]::Escape($c.name)
    $ticker = $c.ticker
    # Replace only the first occurrence NOT already on a line starting with the ticker
    $replaced = $false
    $markdown = [regex]::Replace($markdown, $name, {
        param($m)
        if ($replaced) { return $m.Value }
        # Check if this match is on a line that starts with the ticker (table row)
        $lineStart = $markdown.LastIndexOf("`n", $m.Index)
        $lineStart = if ($lineStart -lt 0) { 0 } else { $lineStart + 1 }
        $linePrefix = $markdown.Substring($lineStart, [Math]::Min(20, $m.Index - $lineStart))
        if ($linePrefix -match "^\|?\s*\*{0,2}$([regex]::Escape($ticker))\*{0,2}\s*\|") {
            return $m.Value  # already identified by ticker on this line
        }
        $replaced = $true
        "$($m.Value) (**$ticker**)"
    })
}

# Encode markdown as JSON string for safe embedding in JS
$jsonMarkdown = '"' + $markdown.Replace('\','\\').Replace('"','\"').Replace("`r`n",'\n').Replace("`n",'\n').Replace("`r",'\n') + '"'

$html = @"
<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>FutureTrends - $reportDate</title>
  <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
      background: #0f1117;
      color: #e6edf3;
      padding: 40px 20px;
    }
    #report { max-width: 900px; margin: 0 auto; }
    h1 { font-size: 1.8em; color: #58a6ff; margin-bottom: 24px; border-bottom: 1px solid #30363d; padding-bottom: 12px; }
    h2 { font-size: 1.3em; color: #79c0ff; margin: 32px 0 12px; }
    h3 { font-size: 1.1em; color: #d2a8ff; margin: 24px 0 8px; }
    p  { line-height: 1.7; margin-bottom: 12px; color: #c9d1d9; }
    ul, ol { margin: 8px 0 12px 24px; }
    li { line-height: 1.7; color: #c9d1d9; margin-bottom: 4px; }
    strong { color: #f0f6fc; }
    em { color: #8b949e; }
    code { background: #161b22; border: 1px solid #30363d; padding: 2px 6px; border-radius: 4px; font-family: 'Cascadia Code', 'Consolas', monospace; font-size: 0.88em; color: #79c0ff; }
    pre { background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 16px; overflow-x: auto; margin: 12px 0; }
    pre code { background: none; border: none; padding: 0; color: #e6edf3; }
    table { width: 100%; border-collapse: collapse; margin: 16px 0; font-size: 0.9em; }
    th { background: #161b22; color: #79c0ff; padding: 10px 14px; text-align: left; border: 1px solid #30363d; }
    td { padding: 9px 14px; border: 1px solid #30363d; color: #c9d1d9; }
    tr:nth-child(even) td { background: #161b22; }
    blockquote { border-left: 3px solid #30363d; padding: 8px 16px; margin: 12px 0; color: #8b949e; }
    hr { border: none; border-top: 1px solid #30363d; margin: 28px 0; }
    #meta { font-size: 0.8em; color: #6e7681; margin-bottom: 32px; }
  </style>
</head>
<body>
  <div id="report">
    <div id="meta">FutureTrends Intelligence System - Report $reportDate</div>
    <div id="content"></div>
  </div>
  <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
  <script>
    const md = MARKDOWN_JSON;
    document.getElementById('content').innerHTML = marked.parse(md);
  </script>
</body>
</html>
"@

$html = $html -replace 'MARKDOWN_JSON', $jsonMarkdown

# Write to temp file and open
$tmpHtml = "$env:TEMP\futuretrends_$reportDate.html"
[System.IO.File]::WriteAllText($tmpHtml, $html, [System.Text.UTF8Encoding]::new($false))
Start-Process $tmpHtml
