import sqlite3

DB = "finnish.db"   # <- change if your DB has a different name

conn = sqlite3.connect(DB)
cur = conn.cursor()

print("=== STARTING MIGRATION ===")

# 1. Add pos_id to meanings (if not exists)
try:
    cur.execute("ALTER TABLE meanings ADD COLUMN pos_id INTEGER REFERENCES parts_of_speech(id);")
    print("Added meanings.pos_id")
except sqlite3.OperationalError:
    print("meanings.pos_id already exists, skipping")

# 2. Copy existing POS from words → meanings
print("Copying word POS into meanings...")
cur.execute("""
    UPDATE meanings
    SET pos_id = (
        SELECT pos_id FROM words WHERE words.id = meanings.word_id
    )
    WHERE pos_id IS NULL;
""")
print("POS copied to meanings.")

# 3. Create word_category_meaning table
cur.execute("""
CREATE TABLE IF NOT EXISTS word_category_meaning (
    id INTEGER PRIMARY KEY,
    word_id INTEGER NOT NULL REFERENCES words(id),
    category_id INTEGER NOT NULL REFERENCES categories(id),
    meaning_id INTEGER NOT NULL REFERENCES meanings(id),
    UNIQUE(word_id, category_id, meaning_id)
);
""")
print("Created table: word_category_meaning")

# 4. Add index for fast lookups
cur.execute("CREATE INDEX IF NOT EXISTS idx_wcm_word ON word_category_meaning(word_id);")
cur.execute("CREATE INDEX IF NOT EXISTS idx_wcm_category ON word_category_meaning(category_id);")
cur.execute("CREATE INDEX IF NOT EXISTS idx_wcm_meaning ON word_category_meaning(meaning_id);")
print("Indexes created.")

# 5. Remove pos_id from words table (safe version)
print("Checking if words.pos_id can be dropped...")

cur.execute("""DROP TABLE IF EXISTS category_word_translations;""")

cur.execute("PRAGMA table_info(words);")
cols = [row[1] for row in cur.fetchall()]
if "pos_id" in cols:
    print("Dropping words.pos_id...")

    # SQLite cannot drop columns directly → recreate table
    cur.executescript("""
        PRAGMA foreign_keys=off;

        CREATE TABLE words_new (
            id INTEGER PRIMARY KEY,
            word TEXT UNIQUE NOT NULL
        );

        INSERT INTO words_new (id, word)
        SELECT id, word FROM words;

        DROP TABLE words;
        ALTER TABLE words_new RENAME TO words;

        PRAGMA foreign_keys=on;
    """)

    print("words.pos_id removed.")
else:
    print("words.pos_id is already absent, skipping.")

conn.commit()
conn.close()

print("=== MIGRATION COMPLETED SUCCESSFULLY ===")
