import sqlite3

DB_PATH = "finnish.db"

def column_exists(cur, table_name, column_name):
    cur.execute(f"PRAGMA table_info({table_name})")
    cols = [row[1] for row in cur.fetchall()]  # row[1] = name
    return column_name in cols

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

print("Running migration: link corpus_examples to word_collocations...")

# 1) Add collocation_id to corpus_examples if missing
if not column_exists(cur, "corpus_examples", "collocation_id"):
    cur.execute("""
        ALTER TABLE corpus_examples
        ADD COLUMN collocation_id INTEGER REFERENCES word_collocations(id)
    """)
    print("✓ Added column corpus_examples.collocation_id")
else:
    print("• Column corpus_examples.collocation_id already exists, skipping.")

# 2) Add is_primary to corpus_examples if missing
if not column_exists(cur, "corpus_examples", "is_primary"):
    cur.execute("""
        ALTER TABLE corpus_examples
        ADD COLUMN is_primary INTEGER NOT NULL DEFAULT 0
            CHECK (is_primary IN (0,1))
    """)
    print("✓ Added column corpus_examples.is_primary")
else:
    print("• Column corpus_examples.is_primary already exists, skipping.")

conn.commit()
conn.close()

print("Migration completed.")
