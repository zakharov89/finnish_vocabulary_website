import sqlite3

DB_PATH = "finnish.db"

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

# 1) Add the sort_order column if it doesn't exist yet
cur.execute("""
    ALTER TABLE word_collocations
    ADD COLUMN sort_order INTEGER
""")

conn.commit()

# 2) Optionally initialize sort_order per word based on current freq / pmi
#    (so that existing behaviour is roughly preserved)
cur.execute("""
    SELECT id, word_id, freq, pmi
    FROM word_collocations
    ORDER BY word_id, freq DESC, pmi DESC, id ASC
""")

rows = cur.fetchall()

current_word = None
position = 1
for colloc_id, word_id, freq, pmi in rows:
    if word_id != current_word:
        current_word = word_id
        position = 1
    cur.execute(
        "UPDATE word_collocations SET sort_order = ? WHERE id = ?",
        (position, colloc_id),
    )
    position += 1

conn.commit()
conn.close()
print("Added sort_order and initialised per word_id.")
