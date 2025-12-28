import sqlite3

DB_PATH = "finnish.db"

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

# Add show_in_app to word_collocations
try:
    cur.execute("""
        ALTER TABLE word_collocations
        ADD COLUMN show_in_app INTEGER NOT NULL DEFAULT 1
    """)
    print("Added column word_collocations.show_in_app")
except sqlite3.OperationalError as e:
    print("Skipping show_in_app:", e)

# Add show_examples to word_collocations
try:
    cur.execute("""
        ALTER TABLE word_collocations
        ADD COLUMN show_examples INTEGER NOT NULL DEFAULT 1
    """)
    print("Added column word_collocations.show_examples")
except sqlite3.OperationalError as e:
    print("Skipping show_examples:", e)

# Add hidden to corpus_examples (optional but useful)
try:
    cur.execute("""
        ALTER TABLE corpus_examples
        ADD COLUMN hidden INTEGER NOT NULL DEFAULT 0
    """)
    print("Added column corpus_examples.hidden")
except sqlite3.OperationalError as e:
    print("Skipping hidden:", e)

conn.commit()
conn.close()
print("Done updating DB.")
