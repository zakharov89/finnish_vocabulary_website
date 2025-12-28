import sqlite3

conn = sqlite3.connect("finnish.db")
cur = conn.cursor()

print("Running database migration for collocations + corpus examples...")

# -----------------------------------------------------------
# 1. Create word_collocations table
# -----------------------------------------------------------
cur.execute("""
CREATE TABLE IF NOT EXISTS word_collocations (
    id INTEGER PRIMARY KEY,
    word_id        INTEGER NOT NULL,
    other_word_id  INTEGER,
    other_form     TEXT NOT NULL,
    direction      TEXT NOT NULL DEFAULT 'B'
                    CHECK (direction IN ('L','R','B')),
    freq           INTEGER,
    pmi            REAL,
    example_sentence TEXT,
    source         TEXT NOT NULL DEFAULT 'subtitles',
    FOREIGN KEY(word_id)       REFERENCES words(id),
    FOREIGN KEY(other_word_id) REFERENCES words(id)
)
""")
print("✓ word_collocations table ensured.")

# Indexes for speed
cur.execute("""
CREATE INDEX IF NOT EXISTS idx_word_collocations_word
    ON word_collocations(word_id)
""")
cur.execute("""
CREATE INDEX IF NOT EXISTS idx_word_collocations_other_word
    ON word_collocations(other_word_id)
""")
print("✓ word_collocations indexes ensured.")

# -----------------------------------------------------------
# 2. Create corpus_examples table
# -----------------------------------------------------------
cur.execute("""
CREATE TABLE IF NOT EXISTS corpus_examples (
    id INTEGER PRIMARY KEY,
    word_id INTEGER NOT NULL,
    meaning_id INTEGER,
    example_text TEXT NOT NULL,
    example_translation_text TEXT,
    source TEXT NOT NULL DEFAULT 'subtitles',
    FOREIGN KEY(word_id)   REFERENCES words(id),
    FOREIGN KEY(meaning_id) REFERENCES meanings(id)
)
""")
print("✓ corpus_examples table ensured.")

# Indexes
cur.execute("""
CREATE INDEX IF NOT EXISTS idx_corpus_examples_word
    ON corpus_examples(word_id)
""")
cur.execute("""
CREATE INDEX IF NOT EXISTS idx_corpus_examples_meaning
    ON corpus_examples(meaning_id)
""")
print("✓ corpus_examples indexes ensured.")

# -----------------------------------------------------------

conn.commit()
conn.close()

print("Migration completed successfully.")
