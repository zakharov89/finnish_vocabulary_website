import sqlite3

conn = sqlite3.connect("finnish.db")
cur = conn.cursor()

# Print the schema for the whole database
cur.execute("SELECT sql FROM sqlite_master WHERE type='table';")
for row in cur.fetchall():
    print(row[0])

conn.close()
