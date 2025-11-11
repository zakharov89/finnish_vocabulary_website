import sqlite3

conn = sqlite3.connect("finnish.db")
cur = conn.cursor()

cur.execute("UPDATE relation_types SET bidirectional = 0 WHERE name IN ('compound of', 'part of', 'derived from')")
conn.commit()

conn.close()
print("Relation types updated successfully.")

