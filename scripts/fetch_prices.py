"""
fetch_prices.py — descarga precios de cierre ajustados para todas las empresas del universo
y los persiste en la tabla prices(ticker, date, close, source).
Se ejecuta tras cada run diario desde run_daily.ps1.
"""
import sqlite3
import json
import sys
from datetime import date, timedelta

DB_PATH   = r"C:\projects\FutureTrends\data\fa.db"
CO_PATH   = r"C:\projects\FutureTrends\data\companies.json"

def ensure_table(db):
    db.execute("""
        CREATE TABLE IF NOT EXISTS prices (
            ticker TEXT NOT NULL,
            date   TEXT NOT NULL,
            close  REAL NOT NULL,
            source TEXT NOT NULL DEFAULT 'yfinance',
            PRIMARY KEY (ticker, date)
        )
    """)
    db.commit()

def tickers_from_companies():
    with open(CO_PATH, encoding="utf-8") as f:
        return [c["ticker"] for c in json.load(f)["companies"]]

def fetch_and_store(db, tickers, target_date: str):
    try:
        import yfinance as yf
    except ImportError:
        print("ERROR: yfinance no instalado — pip install yfinance")
        sys.exit(1)

    # Descarga el rango target_date .. target_date+1 (yfinance excluye end)
    end = (date.fromisoformat(target_date) + timedelta(days=1)).isoformat()
    data = yf.download(
        tickers,
        start=target_date,
        end=end,
        auto_adjust=True,
        progress=False,
        threads=True,
    )

    if data.empty:
        print(f"WARN: yfinance no devolvió datos para {target_date} (mercado cerrado?)")
        return 0

    # data["Close"] es un DataFrame multi-columna cuando hay >1 ticker
    close = data["Close"] if "Close" in data.columns else data

    inserted = 0
    for ticker in tickers:
        if ticker not in close.columns:
            continue
        series = close[ticker].dropna()
        if series.empty:
            continue
        price = float(series.iloc[-1])
        row_date = series.index[-1].date().isoformat()
        db.execute(
            "INSERT OR REPLACE INTO prices (ticker, date, close, source) VALUES (?,?,?,?)",
            (ticker, row_date, price, "yfinance"),
        )
        inserted += 1

    db.commit()
    return inserted

def main():
    target_date = sys.argv[1] if len(sys.argv) > 1 else date.today().isoformat()

    db = sqlite3.connect(DB_PATH)
    ensure_table(db)

    tickers = tickers_from_companies()
    n = fetch_and_store(db, tickers, target_date)
    db.close()

    if n:
        print(f"PRICES_SAVED: {n} cierres guardados para {target_date}")
    else:
        print(f"PRICES_SKIP: sin datos de mercado para {target_date}")

if __name__ == "__main__":
    main()
