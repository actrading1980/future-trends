# FutureAnalysis - Generate HTML reports and deploy to GitHub/Cloudflare Pages
param([string]$ReportFile, [string]$ProjectDir)

$CompaniesFile   = "$ProjectDir\data\companies.json"
$OutputHtml      = "$ProjectDir\reports\index.html"
$reportDate      = (Get-Item $ReportFile).BaseName
$ComparativeFile = "$ProjectDir\reports\comparative_$reportDate.md"
$ComparativeHtml = "$ProjectDir\reports\comparative.html"

$companies = (Get-Content $CompaniesFile -Raw -Encoding utf8 | ConvertFrom-Json).companies
$sorted    = $companies | Sort-Object { $_.name.Length } -Descending

$CSS = @"
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #0f1117; color: #e6edf3; padding: 40px 20px; }
    #report { max-width: 900px; margin: 0 auto; }
    nav { display: flex; gap: 16px; margin-bottom: 28px; }
    nav a { color: #58a6ff; text-decoration: none; font-size: 0.9em; padding: 6px 14px; border: 1px solid #30363d; border-radius: 6px; }
    nav a:hover { background: #161b22; }
    nav a.active { background: #1f6feb; border-color: #1f6feb; color: #fff; }
    h1 { font-size: 1.8em; color: #58a6ff; margin-bottom: 24px; border-bottom: 1px solid #30363d; padding-bottom: 12px; }
    h2 { font-size: 1.3em; color: #79c0ff; margin: 32px 0 12px; }
    h3 { font-size: 1.1em; color: #d2a8ff; margin: 24px 0 8px; }
    p  { line-height: 1.7; margin-bottom: 12px; color: #c9d1d9; }
    ul, ol { margin: 8px 0 12px 24px; }
    li { line-height: 1.7; color: #c9d1d9; margin-bottom: 4px; }
    strong { color: #f0f6fc; }
    em { color: #8b949e; }
    code { background: #161b22; border: 1px solid #30363d; padding: 2px 6px; border-radius: 4px; font-family: 'Cascadia Code','Consolas',monospace; font-size: 0.88em; color: #79c0ff; }
    pre { background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 16px; overflow-x: auto; margin: 12px 0; }
    pre code { background: none; border: none; padding: 0; color: #e6edf3; }
    table { width: 100%; border-collapse: collapse; margin: 16px 0; font-size: 0.9em; }
    th { background: #161b22; color: #79c0ff; padding: 10px 14px; text-align: left; border: 1px solid #30363d; }
    td { padding: 9px 14px; border: 1px solid #30363d; color: #c9d1d9; }
    tr:nth-child(even) td { background: #161b22; }
    blockquote { border-left: 3px solid #30363d; padding: 8px 16px; margin: 12px 0; color: #8b949e; }
    hr { border: none; border-top: 1px solid #30363d; margin: 28px 0; }
    #meta { font-size: 0.8em; color: #6e7681; margin-bottom: 20px; }
"@

function ConvertTo-JsonMarkdown($md) {
    '"' + $md.Replace('\','\\').Replace('"','\"').Replace("`r`n",'\n').Replace("`n",'\n').Replace("`r",'\n') + '"'
}

function InjectTickers($markdown) {
    foreach ($c in $sorted) {
        $name    = [regex]::Escape($c.name)
        $ticker  = $c.ticker
        $replaced = $false
        $markdown = [regex]::Replace($markdown, $name, {
            param($m)
            if ($replaced) { return $m.Value }
            $lineStart  = $markdown.LastIndexOf("`n", $m.Index)
            $lineStart  = if ($lineStart -lt 0) { 0 } else { $lineStart + 1 }
            $linePrefix = $markdown.Substring($lineStart, [Math]::Min(20, $m.Index - $lineStart))
            if ($linePrefix -match "^\|?\s*\*{0,2}$([regex]::Escape($ticker))\*{0,2}\s*\|") {
                return $m.Value
            }
            $replaced = $true
            "$($m.Value) (**$ticker**)"
        })
    }
    return $markdown
}

function Build-Html($title, $jsonMd, $activeTab, $css) {
    $classReport      = if ($activeTab -eq 'report')      { ' class="active"' } else { '' }
    $classComparative = if ($activeTab -eq 'comparative') { ' class="active"' } else { '' }
    @"
<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>$title</title>
  <style>$css</style>
</head>
<body>
  <div id="report">
    <div id="meta">FutureTrends Intelligence System &mdash; $reportDate</div>
    <nav>
      <a href="index.html"$classReport>Informe</a>
      <a href="comparative.html"$classComparative>Comparativo</a>
    </nav>
    <div id="content"></div>
  </div>
  <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
  <script>
    document.getElementById('content').innerHTML = marked.parse(MD_JSON);
  </script>
</body>
</html>
"@
}

# --- Generar index.html (reporte principal) ---
$mdMain    = InjectTickers ([System.IO.File]::ReadAllText($ReportFile, [System.Text.Encoding]::UTF8))
$jsonMain  = ConvertTo-JsonMarkdown $mdMain
$htmlMain  = (Build-Html "FutureTrends - $reportDate" $jsonMain 'report' $CSS) -replace 'MD_JSON', $jsonMain
[System.IO.File]::WriteAllText($OutputHtml, $htmlMain, [System.Text.UTF8Encoding]::new($false))
Write-Output "HTML principal generado: reports\index.html"

# --- Generar comparative.html ---
if (Test-Path $ComparativeFile) {
    $mdComp   = [System.IO.File]::ReadAllText($ComparativeFile, [System.Text.Encoding]::UTF8)
    $jsonComp = ConvertTo-JsonMarkdown $mdComp
    $htmlComp = (Build-Html "FutureTrends - Comparativo $reportDate" $jsonComp 'comparative' $CSS) -replace 'MD_JSON', $jsonComp
    [System.IO.File]::WriteAllText($ComparativeHtml, $htmlComp, [System.Text.UTF8Encoding]::new($false))
    Write-Output "HTML comparativo generado: reports\comparative.html"
}

# --- Git commit y push ---
Set-Location $ProjectDir
git add "reports/index.html" "reports/comparative.html" "reports/$reportDate.md" "reports/comparative_$reportDate.md" 2>&1 | Out-Null
$diff = git diff --cached --quiet 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Output "Sin cambios en git, skip push"
    exit 0
}
git commit -m "Report $reportDate" 2>&1 | Out-Null
git push 2>&1 | Out-Null
Write-Output "Publicado en GitHub -> Cloudflare Pages"
