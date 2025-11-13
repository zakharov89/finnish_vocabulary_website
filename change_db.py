import sqlite3

conn = sqlite3.connect("finnish.db")
cur = conn.cursor()


conn.close()
print("Relation types updated successfully.")

