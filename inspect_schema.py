import sqlite3

conn = sqlite3.connect("finnish.db")
cur = conn.cursor()

# Show all table names
cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
print("Tables:")
for (name,) in cur.fetchall():
    print(" -", name)

print("\nSchemas:\n")
cur.execute("SELECT sql FROM sqlite_master WHERE type='table'")
for (sql,) in cur.fetchall():
    print(sql)
    print()
