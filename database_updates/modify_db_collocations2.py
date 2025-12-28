import sqlite3

DB_PATH = "finnish.db"

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

print("Removing example_sentence from word_collocations...")

# 1. Read current schema
cur.execute("PRAGMA table_info(word_collocations)")
cols = cur.fetchall()
col_names = [c[1] for c in cols]

if "example_sentence" not in col_names:
    print("• Column example_sentence already removed, nothing to do.")
    conn.close()
    exit()

# 2. Create new table without example_sentence
cur.execute("""
    CREATE TABLE word_collocations_new (
        id INTEGER PRIMARY KEY,
        word_id        INTEGER NOT NULL,
        other_word_id  INTEGER,
        other_form     TEXT NOT NULL,
        direction      TEXT NOT NULL DEFAULT 'B'
                        CHECK (direction IN ('L','R','B')),
        freq           INTEGER,
        pmi            REAL,
        source         TEXT NOT NULL DEFAULT 'subtitles',
        FOREIGN KEY(word_id)       REFERENCES words(id),
        FOREIGN KEY(other_word_id) REFERENCES words(id)
    )
""")

# 3. Copy data except example_sentence
cur.execute("""
    INSERT INTO word_collocations_new
        (id, word_id, other_word_id, other_form, direction, freq, pmi, source)
    SELECT
        id, word_id, other_word_id, other_form, direction, freq, pmi, source
    FROM word_collocations
""")

# 4. Replace tables
cur.execute("DROP TABLE word_collocations")
cur.execute("ALTER TABLE word_collocations_new RENAME TO word_collocations")

conn.commit()
conn.close()

print("✓ Column example_sentence removed successfully.")


