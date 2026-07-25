import sqlite3

db = sqlite3.connect("optionflow.db")

cur = db.cursor()

print("=" * 50)
print("TABLES")
print("=" * 50)

cur.execute("SELECT name FROM sqlite_master WHERE type='table'")

tables = cur.fetchall()

for t in tables:
    print(t[0])

print("=" * 50)

for t in tables:

    print("\nTABLE :", t[0])

    cur.execute(f"PRAGMA table_info({t[0]})")

    for c in cur.fetchall():
        print(c)

db.close()
