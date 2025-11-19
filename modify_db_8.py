import sqlite3

conn = sqlite3.connect("finnish.db")
cur = conn.cursor()

# Add level column (default to 1)
cur.execute("""
    ALTER TABLE words
    ADD COLUMN level INTEGER DEFAULT 1
""")

conn.commit()
conn.close()
print("Added 'level' column to words table.")
