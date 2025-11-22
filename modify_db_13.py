import sqlite3

conn = sqlite3.connect("finnish.db")
cur = conn.cursor()

# Make sure level 0 exists and is called "Unassigned"
cur.execute("""
    UPDATE levels
    SET name = '+'
    WHERE id = 0
""")

# For all other levels, set the name to the numeric string of id
cur.execute("""
    UPDATE levels
    SET name = CAST(id AS TEXT)
    WHERE id > 0
""")

conn.commit()
conn.close()
print("Levels updated: 0 -> '+', others -> '1','2','3',...")
