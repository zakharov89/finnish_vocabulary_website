import sqlite3

DB_PATH = "finnish.db"

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

# See what we have
cur.execute("PRAGMA table_info(word_collocations)")
cols = [row[1] for row in cur.fetchall()]
print("Existing columns in word_collocations:", cols)

if "collocation_translation" not in cols:
    print("Adding collocation_translation column...")
    cur.execute("""
        ALTER TABLE word_collocations
        ADD COLUMN collocation_translation TEXT
    """)
    conn.commit()
    print("Column collocation_translation added.")
else:
    print("collocation_translation already exists, nothing to do.")

conn.close()
print("Done.")
