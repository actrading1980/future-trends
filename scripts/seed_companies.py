import sqlite3, json
from pathlib import Path

project = Path(__file__).parent.parent
db_path = project / "data" / "fa.db"
sql_path = project / "scripts" / "init_db.sql"
json_path = project / "data" / "companies.json"

db = sqlite3.connect(db_path)
db.executescript(sql_path.read_text(encoding="utf-8"))
db.commit()

companies = json.loads(json_path.read_text())["companies"]
for c in companies:
    db.execute(
        "INSERT OR REPLACE INTO companies (ticker, name, keywords, keywords_version, last_validated, cik) VALUES (?,?,?,?,?,?)",
        (c["ticker"], c["name"], json.dumps(c["keywords"]), c.get("keywords_version", 1), c.get("last_validated", ""), c.get("cik", ""))
    )
db.commit()
db.close()
print(f"OK: {len(companies)} empresas importadas a fa.db")
