import sqlite3

DB_PATH = "finnish.db"

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

# Make row access nicer if you want to debug
conn.row_factory = sqlite3.Row

print("Starting migration of word_collocations...")

# 1) Turn off foreign key checks during migration
cur.execute("PRAGMA foreign_keys = OFF;")
conn.commit()

try:
    # 2) Rename old table
    print("Renaming existing word_collocations to word_collocations_old...")
    cur.execute("ALTER TABLE word_collocations RENAME TO word_collocations_old;")

    # 3) Create new table with the desired schema
    print("Creating new word_collocations table...")
    cur.execute("""
        CREATE TABLE word_collocations (
            id INTEGER PRIMARY KEY,
            word_id        INTEGER NOT NULL,
            other_word_id  INTEGER,
            other_form     TEXT NOT NULL,
            surface_form   TEXT,
            direction      TEXT NOT NULL DEFAULT 'B'
                             CHECK (direction IN ('L','R','B')),
            freq           INTEGER,
            pmi            REAL,
            show_in_app    INTEGER NOT NULL DEFAULT 0,
            show_examples  INTEGER NOT NULL DEFAULT 1,
            source         TEXT NOT NULL DEFAULT 'subtitles',
            FOREIGN KEY(word_id)       REFERENCES words(id),
            FOREIGN KEY(other_word_id) REFERENCES words(id)
        );
    """)

    # 4) Copy data from old table into new one.
    # We use COALESCE to ensure defaults:
    #   - show_in_app   → 0 if NULL / missing
    #   - show_examples → 1 if NULL / missing
    #   - surface_form  → can stay NULL
    print("Copying data from word_collocations_old...")

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
            -- surface_form might not exist in very old schemas, so use NULL if missing
            CASE
                WHEN instr(sql, 'surface_form') > 0 THEN surface_form
                ELSE NULL
            END AS surface_form,
            direction,
            freq,
            pmi,
            COALESCE(show_in_app, 0)   AS show_in_app,
            COALESCE(show_examples, 1) AS show_examples,
            source
        FROM word_collocations_old
    """)
    # ^ NOTE:
    # If you get an error about "no such column: surface_form" or show_in_app/show_examples,
    # it means your old table truly didn't have them yet.
    # In that case use a simpler SELECT (see comment below).

    conn.commit()

    # 5) Drop old table
    print("Dropping word_collocations_old...")
    cur.execute("DROP TABLE word_collocations_old;")
    conn.commit()

    print("Migration completed successfully.")

except Exception as e:
    print("ERROR during migration:", e)
    print("Rolling back...")
    conn.rollback()
finally:
    # Turn foreign keys back on
    cur.execute("PRAGMA foreign_keys = ON;")
    conn.commit()
    conn.close()
    print("Done.")
