#!/usr/bin/env python3
"""Detecta empresas con keywords_version stale (>100 días sin validar)."""
import json, datetime, sys
from pathlib import Path

PROJECT_DIR = Path(__file__).parent.parent
companies_path = PROJECT_DIR / "data" / "companies.json"

with open(companies_path) as f:
    data = json.load(f)

today = datetime.date.today()
stale = []
for c in data["companies"]:
    last = c.get("last_validated", "")
    if not last:
        stale.append((c["ticker"], "nunca validada"))
        continue
    days = (today - datetime.date.fromisoformat(last)).days
    if days > 100:
        stale.append((c["ticker"], f"{days} días"))

if stale:
    print(f"[STALE] {len(stale)} empresas para re-validar:")
    for ticker, reason in stale:
        print(f"  {ticker}: {reason}")
    sys.exit(1)
else:
    print(f"[OK] Todas las empresas validadas en los últimos 100 días.")
    sys.exit(0)
