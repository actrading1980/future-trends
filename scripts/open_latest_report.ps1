# FutureAnalysis - Open latest report
# Abre el index.html generado por deploy_report.ps1 (ya tiene ticker injection y nav tabs)

$IndexHtml = "C:\projects\FutureTrends\reports\index.html"

if (-not (Test-Path $IndexHtml)) {
    Add-Type -AssemblyName System.Windows.Forms
    [System.Windows.Forms.MessageBox]::Show("No hay reporte generado aun. Ejecuta run_daily.ps1 primero.", "FutureTrends")
    exit 1
}

Start-Process $IndexHtml
