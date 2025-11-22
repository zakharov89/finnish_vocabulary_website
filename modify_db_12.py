import sqlite3

conn = sqlite3.connect("finnish.db")
cur = conn.cursor()

# Rename the level
cur.execute("""
    UPDATE levels
    SET name = 'Unassigned'
    WHERE name = 'No level'
""")

conn.commit()
conn.close()

print("Renamed 'No level' to 'Unassigned'.")
