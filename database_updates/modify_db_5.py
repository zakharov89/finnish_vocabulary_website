import sqlite3

DB_PATH = "finnish.db"

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

print("Starting migration of word_categories table...")

try:
    # 1️⃣ Create new table with correct foreign key
    cur.execute("""
        CREATE TABLE IF NOT EXISTS word_categories_new (
            id INTEGER PRIMARY KEY,
            word_id INTEGER NOT NULL REFERENCES words(id),
            category_id INTEGER NOT NULL REFERENCES categories(id),
            sort_order INTEGER DEFAULT 0,
            UNIQUE(word_id, category_id)
        );
    """)
    print("Created new table: word_categories_new")

    # 2️⃣ Copy data from old table
    cur.execute("""
        INSERT INTO word_categories_new (id, word_id, category_id, sort_order)
        SELECT id, word_id, category_id, sort_order FROM word_categories;
    """)
    print("Copied data from old word_categories table")

    # 3️⃣ Drop old table
    cur.execute("DROP TABLE word_categories;")
    print("Dropped old word_categories table")

    # 4️⃣ Rename new table
    cur.execute("ALTER TABLE word_categories_new RENAME TO word_categories;")
    print("Renamed word_categories_new to word_categories")

    conn.commit()
    print("Migration completed successfully!")

except sqlite3.Error as e:
    print("Migration failed:", e)
    conn.rollback()

finally:
    conn.close()
