-- FutureAnalysis DB schema
-- Ejecutar: sqlite3 data/fa.db < scripts/init_db.sql

CREATE TABLE IF NOT EXISTS tech_scores (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker      TEXT    NOT NULL,
    score       INTEGER NOT NULL CHECK(score BETWEEN 0 AND 100),
    trend_name  TEXT    NOT NULL,
    intensity   INTEGER CHECK(intensity BETWEEN -3 AND 3),
    scenario    TEXT    CHECK(scenario IN ('BEARISH','NEUTRAL','BULLISH','STRONG_BULLISH')),
    conflicto   INTEGER DEFAULT 0,
    date        TEXT    NOT NULL,
    created_at  TEXT    DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS trends (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT    NOT NULL,
    category        TEXT    NOT NULL,
    first_seen      TEXT    NOT NULL,
    last_seen       TEXT    NOT NULL,
    peak_score      INTEGER,
    status          TEXT    DEFAULT 'active' CHECK(status IN ('active','monitoring','stale')),
    source_url      TEXT,
    arxiv_id        TEXT    UNIQUE
);

CREATE TABLE IF NOT EXISTS filings_mentions (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker       TEXT NOT NULL,
    filing_date  TEXT NOT NULL,
    keyword      TEXT NOT NULL,
    context_type TEXT CHECK(context_type IN ('ADOPTION','RISK','NEUTRAL')),
    url_filing   TEXT,
    snippet      TEXT,
    created_at   TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS companies (
    ticker           TEXT PRIMARY KEY,
    name             TEXT NOT NULL,
    keywords         TEXT,  -- JSON array serializado
    keywords_version INTEGER DEFAULT 1,
    last_validated   TEXT,
    cik              TEXT
);

-- Índices para queries frecuentes
CREATE INDEX IF NOT EXISTS idx_scores_ticker_date ON tech_scores(ticker, date);
CREATE INDEX IF NOT EXISTS idx_scores_date        ON tech_scores(date);
CREATE INDEX IF NOT EXISTS idx_trends_status      ON trends(status);
CREATE INDEX IF NOT EXISTS idx_filings_ticker     ON filings_mentions(ticker, filing_date);
