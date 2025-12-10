import sqlite3

conn = sqlite3.connect("finnish.db")
cur = conn.cursor()

# Check if column exists
cur.execute("PRAGMA table_info(word_collocations)")
cols = [row[1] for row in cur.fetchall()]

if "surface_form" not in cols:
    cur.execute("""
        ALTER TABLE word_collocations
        ADD COLUMN surface_form TEXT
    """)
    print("Added surface_form to word_collocations.")
else:
    print("surface_form already exists — no change made.")

conn.commit()
conn.close()
print("Migration completed.")
