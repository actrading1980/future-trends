#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

source "${PROJECT_DIR}/.env" 2>/dev/null || true

# Solo correr durante earnings season: semanas 2-5 de cada trimestre
WEEK_OF_MONTH=$(( ($(date +%d) - 1) / 7 + 1 ))
if [ "$WEEK_OF_MONTH" -lt 2 ] || [ "$WEEK_OF_MONTH" -gt 5 ]; then
  echo "[$(date)] Fuera de ventana earnings season (semana $WEEK_OF_MONTH), skip."
  exit 0
fi

DATE=$(date +%Y%m%d)
START=$(date -d "7 days ago" +%Y-%m-%d 2>/dev/null || date -v-7d +%Y-%m-%d)
END=$(date +%Y-%m-%d)

echo "[$(date)] === Filings scan $START → $END ==="

cd "${PROJECT_DIR}"
claude -p "$(sed "s/{START}/$START/g; s/{END}/$END/g" prompts/filings_scan.md)" \
  --output-format text >> "reports/filings_${DATE}.md"

echo "[$(date)] ✅ Filings scan: reports/filings_${DATE}.md"
