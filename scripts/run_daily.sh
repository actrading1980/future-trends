#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

source "${PROJECT_DIR}/.env" 2>/dev/null || true

DATE=$(date +%Y%m%d)
DATE_ISO=$(date +%Y-%m-%d)
DATE_7D=$(date -d "7 days ago" +%Y-%m-%d 2>/dev/null || date -v-7d +%Y-%m-%d)  # Linux / macOS

echo "[$(date)] === FutureAnalysis daily run $DATE ==="

# 1. Exportar tendencias activas desde SQLite
if command -v sqlite3 &>/dev/null && [ -f "${PROJECT_DIR}/data/fa.db" ]; then
  sqlite3 "${PROJECT_DIR}/data/fa.db" \
    "SELECT json_group_array(json_object('ticker',ticker,'score',score,'trend',trend_name))
     FROM tech_scores WHERE date = (SELECT MAX(date) FROM tech_scores) LIMIT 10;" \
    > "${PROJECT_DIR}/data/trends.json" 2>/dev/null || echo "[]" > "${PROJECT_DIR}/data/trends.json"
else
  echo "[]" > "${PROJECT_DIR}/data/trends.json"
  echo "[$(date)] INFO: fa.db no existe aún — usando contexto vacío"
fi

# 2. Construir prompt con contexto dinámico
export PROJECT_DIR DATE DATE_ISO DATE_7D
python3 - <<'PYEOF'
import os, json

project_dir = os.environ['PROJECT_DIR']
date_str    = os.environ['DATE']
date_iso    = os.environ['DATE_ISO']
date_7d     = os.environ['DATE_7D']

with open(f"{project_dir}/prompts/daily.md") as f:
    prompt = f.read()

try:
    with open(f"{project_dir}/data/trends.json") as f:
        trends_raw = f.read(2000)
except:
    trends_raw = "[]"

try:
    with open(f"{project_dir}/data/queries.json") as f:
        queries_raw = f.read(3000)
except:
    queries_raw = "{}"

prompt = prompt.replace("{FECHA}",             date_iso)
prompt = prompt.replace("{TENDENCIAS_ACTIVAS}", trends_raw)
prompt = prompt.replace("{QUERIES}",            queries_raw)
prompt = prompt.replace("{FECHA_7D}",           date_7d)

with open(f"/tmp/fa_prompt_{date_str}.md", "w") as f:
    f.write(prompt)

print(f"[INFO] Prompt generado: {len(prompt)} chars")
PYEOF

# 3. Ejecutar Claude CLI
cd "${PROJECT_DIR}"
echo "[$(date)] Ejecutando Claude CLI..."
claude -p "$(cat /tmp/fa_prompt_${DATE}.md)" --output-format text > "/tmp/fa_report_${DATE}.md"

# 4. Validar output
REPORT_SIZE=$(wc -c < "/tmp/fa_report_${DATE}.md")
if [ "$REPORT_SIZE" -lt 500 ]; then
  echo "[$(date)] ERROR: reporte demasiado corto (${REPORT_SIZE} bytes). Ver /tmp/fa_report_${DATE}.md"
  exit 1
fi

# 5. Guardar informe
mv "/tmp/fa_report_${DATE}.md" "${PROJECT_DIR}/reports/${DATE}.md"
rm -f "/tmp/fa_prompt_${DATE}.md"

echo "[$(date)] ✅ Informe guardado: reports/${DATE}.md (${REPORT_SIZE} bytes)"
echo "[$(date)] === FutureAnalysis daily run completado ==="
