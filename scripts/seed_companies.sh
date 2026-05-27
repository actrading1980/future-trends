#!/bin/bash
# Inicializa la DB con el universo de empresas desde companies.json
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
DB="${PROJECT_DIR}/data/fa.db"

# Crear schema
sqlite3 "$DB" < "${SCRIPT_DIR}/init_db.sql"
echo "[INFO] Schema creado en $DB"

# Importar empresas desde companies.json
python3 - <<'PYEOF'
import json, sqlite3, os

project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
db_path     = os.path.join(project_dir, "data", "fa.db")
json_path   = os.path.join(project_dir, "data", "companies.json")

with open(json_path) as f:
    data = json.load(f)

conn = sqlite3.connect(db_path)
cur  = conn.cursor()

for c in data["companies"]:
    cur.execute("""
        INSERT OR REPLACE INTO companies (ticker, name, keywords, keywords_version, last_validated, cik)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        c["ticker"], c["name"],
        json.dumps(c["keywords"]),
        c.get("keywords_version", 1),
        c.get("last_validated", ""),
        c.get("cik", "")
    ))

conn.commit()
conn.close()
print(f"[INFO] {len(data['companies'])} empresas importadas a fa.db")
PYEOF

echo "[✅] DB inicializada: $DB"
