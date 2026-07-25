import sqlite3

DB = "database/trade_history.db"

con = sqlite3.connect(DB)
cur = con.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS historical_price(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT,
    timeframe TEXT,
    dt TEXT,
    open REAL,
    high REAL,
    low REAL,
    close REAL,
    volume REAL,
    oi REAL
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS live_price(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT,
    dt TEXT,
    ltp REAL,
    volume REAL,
    oi REAL
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS signals(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dt TEXT,
    symbol TEXT,
    side TEXT,
    score INTEGER,
    confidence REAL,
    reason TEXT,
    scenario TEXT
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS trades(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entry_time TEXT,
    exit_time TEXT,
    symbol TEXT,
    side TEXT,
    entry REAL,
    exit REAL,
    pnl REAL
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS market_scenario(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dt TEXT,
    symbol TEXT,
    scenario TEXT,
    probability REAL
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS research_result(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    research_id TEXT,
    title TEXT,
    result TEXT,
    winrate REAL,
    created_at TEXT
)
""")

con.commit()
con.close()

print("DATABASE READY")
