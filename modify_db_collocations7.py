import sqlite3

DB_PATH = "finnish.db"

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

print("Starting fix for word_collocations / corpus_examples...")

# Turn off FK checks during migration
cur.execute("PRAGMA foreign_keys = OFF;")
conn.commit()

try:
    # ---------------------------------------------------------
    # 1) Copy data from word_collocations_old -> word_collocations
    # ---------------------------------------------------------
    # Check if new table is empty
    cur.execute("SELECT COUNT(*) AS cnt FROM word_collocations;")
    new_count = cur.fetchone()["cnt"]
    print(f"word_collocations currently has {new_count} rows.")

    if new_count == 0:
        print("Copying data from word_collocations_old to word_collocations...")
        cur.execute("""
            INSERT INTO word_collocations (
                id,
                word_id,
                other_word_id,
                other_form,
                surface_form,
                direction,
                freq,
                pmi,
                show_in_app,
                show_examples,
                source
            )
            SELECT
                id,
                word_id,
                other_word_id,
                other_form,
                surface_form,
                direction,
                freq,
                pmi,
                COALESCE(show_in_app, 0)   AS show_in_app,
                COALESCE(show_examples, 1) AS show_examples,
                source
            FROM word_collocations_old
        """)
        conn.commit()
        print("Copy done.")
    else:
        print("word_collocations is not empty; skipping copy step to avoid duplicates.")

    # ---------------------------------------------------------
    # 2) Rebuild corpus_examples so collocation_id references word_collocations
    # ---------------------------------------------------------
    print("Rebuilding corpus_examples to reference word_collocations...")

    # Rename old table
    cur.execute("ALTER TABLE corpus_examples RENAME TO corpus_examples_old;")

    # Create new corpus_examples with proper FK
    cur.execute("""
        CREATE TABLE corpus_examples (
            id INTEGER PRIMARY KEY,
            word_id INTEGER NOT NULL,
            meaning_id INTEGER,
            example_text TEXT NOT NULL,
            example_translation_text TEXT,
            source TEXT NOT NULL DEFAULT 'subtitles',
            collocation_id INTEGER REFERENCES word_collocations(id),
            is_primary INTEGER NOT NULL DEFAULT 0
                CHECK (is_primary IN (0,1)),
            hidden INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY(word_id)   REFERENCES words(id),
            FOREIGN KEY(meaning_id) REFERENCES meanings(id)
        )
    """)

    # Copy data over
    cur.execute("""
        INSERT INTO corpus_examples (
            id,
            word_id,
            meaning_id,
            example_text,
            example_translation_text,
            source,
            collocation_id,
            is_primary,
            hidden
        )
        SELECT
            id,
            word_id,
            meaning_id,
            example_text,
            example_translation_text,
            source,
            collocation_id,
            is_primary,
            hidden
        FROM corpus_examples_old
    """)
    conn.commit()

    # Drop old backup table
    cur.execute("DROP TABLE corpus_examples_old;")
    conn.commit()
    print("corpus_examples rebuilt.")

    # ---------------------------------------------------------
    # 3) Drop word_collocations_old
    # ---------------------------------------------------------
    print("Dropping word_collocations_old...")
    cur.execute("DROP TABLE word_collocations_old;")
    conn.commit()
    print("word_collocations_old dropped.")

except Exception as e:
    print("ERROR during migration:", e)
    print("Rolling back...")
    conn.rollback()

finally:
    cur.execute("PRAGMA foreign_keys = ON;")
    conn.commit()
    conn.close()
    print("Done.")

import sqlite3

conn = sqlite3.connect("finnish.db")
cur = conn.cursor()

# Hide all collocations in the app
cur.execute("""
    UPDATE word_collocations
    SET show_in_app = 0
""")

# Optionally ensure examples are allowed to show when a collocation is enabled
cur.execute("""
    UPDATE word_collocations
    SET show_examples = 1
    WHERE show_examples IS NULL
""")

conn.commit()
conn.close()
print("All collocations set to show_in_app = 0.")
