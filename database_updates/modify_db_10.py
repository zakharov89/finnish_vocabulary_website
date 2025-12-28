import sqlite3

# Connect
conn = sqlite3.connect("finnish.db")
cur = conn.cursor()


levels = [(0, "No level")]
for lid, lname in levels:
    cur.execute("INSERT OR IGNORE INTO levels (id, name) VALUES (?, ?)", (lid, lname))


conn.commit()
conn.close()
print("Migration completed successfully.")
