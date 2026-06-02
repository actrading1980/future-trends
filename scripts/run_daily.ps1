# FutureAnalysis - Daily Run
# Ejecutado por Windows Task Scheduler lunes-viernes 7:00 AM

$ProjectDir = "C:\projects\FutureTrends"
$Date       = Get-Date -Format "yyyyMMdd"
$DateIso    = Get-Date -Format "yyyy-MM-dd"
$Date7d     = (Get-Date).AddDays(-7).ToString("yyyy-MM-dd")
$LogFile    = "$ProjectDir\logs\scheduler.log"
$ReportFile = "$ProjectDir\reports\$Date.md"
$TmpPrompt  = "$env:TEMP\fa_prompt_$Date.md"

function Log($msg) {
    $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    "$ts $msg" | Tee-Object -FilePath $LogFile -Append
}

Log "=== FutureAnalysis daily run $Date ==="

# 1. Cargar variables de entorno desde .env
$EnvFile = "$ProjectDir\.env"
if (Test-Path $EnvFile) {
    Get-Content $EnvFile | ForEach-Object {
        if ($_ -match '^(\w+)=(.+)$') {
            [System.Environment]::SetEnvironmentVariable($matches[1], $matches[2], 'Process')
        }
    }
    Log "INFO: .env cargado"
} else {
    Log "ERROR: .env no encontrado en $EnvFile"
    exit 1
}

# 2. Exportar tendencias activas desde SQLite
$TrendsFile = "$ProjectDir\data\trends.json"
$SqliteResult = python3 -c "
import sqlite3, json
try:
    db = sqlite3.connect(r'$ProjectDir\data\fa.db')
    rows = db.execute('''SELECT json_group_array(json_object(
        ''ticker'',ticker,''score'',score,''trend'',trend_name))
        FROM tech_scores WHERE date=(SELECT MAX(date) FROM tech_scores) LIMIT 10''').fetchone()[0]
    db.close()
    print(rows)
except: print('[]')
" 2>$null

$trendsContent = if ($SqliteResult) { $SqliteResult } else { "[]" }
[System.IO.File]::WriteAllText($TrendsFile, $trendsContent, [System.Text.Encoding]::UTF8)
Log "INFO: trends.json actualizado"

# 3. Construir prompt con contexto dinamico
$PromptTemplate = Get-Content "$ProjectDir\prompts\daily.md" -Raw -Encoding utf8
$Trends  = Get-Content $TrendsFile -Raw -Encoding utf8
$Queries = Get-Content "$ProjectDir\data\queries.json" -Raw -Encoding utf8

# Cargar notas de seguimiento activas desde DB
$NotesScript = @"
import sqlite3
from datetime import date
db = sqlite3.connect(r'C:\projects\FutureTrends\data\fa.db')
today = date.today().isoformat()
auto = db.execute('''SELECT ticker, note FROM review_notes WHERE resolve_trigger='auto' AND resolved=0 AND (expires IS NULL OR expires >= ?)''', (today,)).fetchall()
manual = db.execute('''SELECT ticker, note FROM review_notes WHERE resolve_trigger='manual' AND resolved=0''').fetchall()
db.close()
def fmt(rows):
    if not rows: return '(ninguna)'
    return chr(10).join(f'- [{r[0] or "general"}] {r[1]}' for r in rows)
print('AUTO|||' + fmt(auto) + '|||MANUAL|||' + fmt(manual))
"@
$NotesRaw = python3 -c $NotesScript 2>$null
$NotesAuto   = if ($NotesRaw -match 'AUTO\|\|\|(.+)\|\|\|MANUAL') { $matches[1] } else { '(ninguna)' }
$NotesManual = if ($NotesRaw -match 'MANUAL\|\|\|(.+)$')          { $matches[1] } else { '(ninguna)' }
Log "INFO: notas carry-forward cargadas"

$Prompt = $PromptTemplate `
    -replace '\{FECHA\}',              $DateIso `
    -replace '\{TENDENCIAS_ACTIVAS\}', ($Trends       -replace '\\','\\') `
    -replace '\{QUERIES\}',            ($Queries      -replace '\\','\\') `
    -replace '\{FECHA_7D\}',           $Date7d `
    -replace '\{NOTAS_AUTO\}',         ($NotesAuto    -replace '\\','\\') `
    -replace '\{NOTAS_MANUAL\}',       ($NotesManual  -replace '\\','\\')

[System.IO.File]::WriteAllText($TmpPrompt, $Prompt, [System.Text.Encoding]::UTF8)
Log "INFO: prompt generado ($($Prompt.Length) chars)"

# 4. Ejecutar Claude CLI
Set-Location $ProjectDir
Log "INFO: ejecutando Claude CLI..."

$TmpReport = "$env:TEMP\fa_report_$Date.md"
$PromptContent = Get-Content $TmpPrompt -Raw -Encoding utf8

try {
    [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
    $PromptContent = [System.IO.File]::ReadAllText($TmpPrompt, [System.Text.Encoding]::UTF8)
    $Output = $PromptContent | claude --output-format text --dangerously-skip-permissions 2>&1
    $OutputText = ($Output | ForEach-Object { "$_" }) -join [Environment]::NewLine
    [System.IO.File]::WriteAllText($TmpReport, $OutputText, [System.Text.Encoding]::UTF8)
} catch {
    Log "ERROR: Claude CLI fallo - $_"
    exit 1
}

# 5. Validar output minimo
$ReportSize = (Get-Item $TmpReport -ErrorAction SilentlyContinue).Length
if (-not $ReportSize -or $ReportSize -lt 3000) {
    Log "ERROR: reporte demasiado corto ($ReportSize bytes) - ver $TmpReport"
    exit 1
}

# 6. Guardar informe definitivo
Move-Item $TmpReport $ReportFile -Force
Remove-Item $TmpPrompt -Force -ErrorAction SilentlyContinue

Log "OK: informe guardado en reports\$Date.md ($ReportSize bytes)"

# 7. Segunda llamada: extraer scores del informe en formato CSV
$TmpScorePrompt = "$env:TEMP\fa_scoreprompt_$Date.md"
$ScoreHeader = "Lee este informe de analisis de inversiones y extrae TODOS los scores mencionados. Devuelve SOLO un bloque CSV con este formato exacto, sin texto adicional:`nSCORES_CSV_START`nTICKER,SCORE,SCENARIO,INTENSIDAD`n(una linea por empresa)`nSCORES_CSV_END`n`nInforme:`n"
$ScorePromptContent = $ScoreHeader + (Get-Content $ReportFile -Raw -Encoding utf8)
[System.IO.File]::WriteAllText($TmpScorePrompt, $ScorePromptContent, [System.Text.Encoding]::UTF8)

Log "INFO: extrayendo scores via segunda llamada Claude..."
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$ScorePromptContent = [System.IO.File]::ReadAllText($TmpScorePrompt, [System.Text.Encoding]::UTF8)
$ScoreOutput = $ScorePromptContent | claude --output-format text --dangerously-skip-permissions 2>&1
$ScoreText = ($ScoreOutput | ForEach-Object { "$_" }) -join [Environment]::NewLine
Remove-Item $TmpScorePrompt -Force -ErrorAction SilentlyContinue

# Append score block temporarily for parsing (se elimina despues)
[System.IO.File]::AppendAllText($ReportFile, "`n`n$ScoreText", [System.Text.Encoding]::UTF8)

# 8. Parsear scores del informe y persistir en DB
$ParseScript = @"
import re, sqlite3

report_path = r'REPORT_PATH'
date = 'REPORT_DATE'

text = open(report_path, encoding='utf-8').read()

# Extract structured CSV block between SCORES_CSV_START and SCORES_CSV_END
m = re.search(r'SCORES_CSV_START\s*\n(.*?)SCORES_CSV_END', text, re.DOTALL)
if not m:
    print('WARN: bloque SCORES_CSV no encontrado en el reporte')
    raise SystemExit(0)

db = sqlite3.connect(r'C:\projects\FutureTrends\data\fa.db')
valid = {r[0] for r in db.execute('SELECT ticker FROM companies').fetchall()}

inserted = 0
for line in m.group(1).strip().splitlines():
    parts = [p.strip() for p in line.split(',')]
    if len(parts) < 3:
        continue
    ticker, score, scenario = parts[0], parts[1], parts[2]
    intensity = int(parts[3]) if len(parts) > 3 else 0
    if ticker not in valid:
        continue
    score = int(score)
    if score < 0 or score > 100:
        continue
    if scenario not in ('BULLISH','STRONG_BULLISH','NEUTRAL','BEARISH'):
        scenario = 'BULLISH' if score >= 70 else ('BEARISH' if score < 30 else 'NEUTRAL')
    db.execute('INSERT OR REPLACE INTO tech_scores (ticker, score, trend_name, intensity, scenario, conflicto, date, prompt_version) VALUES (?,?,?,?,?,?,?,?)',
        (ticker, score, 'daily_run', intensity, scenario, 0, date, 'v2'))
    inserted += 1

db.commit()
db.close()
print(f'DB_SAVED: {inserted} registros insertados en tech_scores')

# Eliminar bloque CSV del .md (los datos ya estan en la DB)
clean = re.sub(r'\n+SCORES_CSV_START.*?SCORES_CSV_END\n*', '', text, flags=re.DOTALL)
open(report_path, 'w', encoding='utf-8').write(clean)
"@

$ParseScript = $ParseScript -creplace 'REPORT_PATH', ($ReportFile -replace '\\', '/')
$ParseScript = $ParseScript -creplace 'REPORT_DATE', $DateIso
$ParseResult = python3 -c $ParseScript 2>&1
Log "INFO: $ParseResult"

# 9. Guardar precios de cierre del dia
Log "INFO: descargando precios de cierre..."
$PriceResult = python3 "$ProjectDir\scripts\fetch_prices.py" $DateIso 2>&1
Log "INFO: $PriceResult"

# 10. Extraer y clasificar notas de seccion 7 (carry-forward)
Log "INFO: extrayendo notas de revision..."
$NotesResult = python3 "$ProjectDir\scripts\extract_notes.py" $ReportFile $DateIso 2>&1
Log "INFO: $NotesResult"

# 11. Generar informe comparativo
Log "INFO: generando comparativo..."
$CompResult = python3 "$ProjectDir\scripts\generate_comparative.py" $DateIso 2>&1
Log "INFO: $CompResult"

# 11. Generar HTML y publicar en Cloudflare Pages via GitHub
Log "INFO: desplegando reporte..."
$DeployResult = powershell.exe -ExecutionPolicy Bypass -File "$ProjectDir\scripts\deploy_report.ps1" -ReportFile $ReportFile -ProjectDir $ProjectDir 2>&1
Log "INFO: deploy: $DeployResult"

Log "=== Run completado ==="
