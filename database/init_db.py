
import sqlite3

conn = sqlite3.connect("trade_history.db")

cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS trades(
id INTEGER PRIMARY KEY AUTOINCREMENT,
trade_date TEXT,
trade_time TEXT,
symbol TEXT,
side TEXT,
entry REAL,
exit REAL,
score INTEGER,
profit REAL,
reason TEXT
)
""")

conn.commit()
conn.close()

print("Database Ready")
