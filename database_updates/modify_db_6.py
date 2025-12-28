import sqlite3

DB_PATH = "finnish.db"

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

# 1️⃣ Add the optional meaning_id column to word_categories
try:
    cur.execute("ALTER TABLE word_categories ADD COLUMN meaning_id INTEGER REFERENCES meanings(id)")
    print("Added meaning_id column to word_categories.")
except sqlite3.OperationalError as e:
    if "duplicate column name" in str(e).lower():
        print("meaning_id column already exists, skipping.")
    else:
        raise

# 2️⃣ Drop the old word_categories_meaning table if it exists
cur.execute("DROP TABLE IF EXISTS word_category_meaning")
print("Dropped word_category_meaning table (if it existed).")

conn.commit()
conn.close()
print("Migration complete.")
