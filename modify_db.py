import sqlite3
from datetime import datetime


# Connect to SQLite
conn = sqlite3.connect("finnish.db")
cur = conn.cursor()


cur.execute("UPDATE relation_types SET bidirectional = 0 WHERE name IN ('compound of', 'part of', 'derived from')")


# ===== Create categories table =====
cur.execute('''
    CREATE TABLE IF NOT EXISTS categories (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        parent_id INTEGER REFERENCES categories(id)
    );
''')

# ===== Create word_categories table =====
cur.execute('''
    CREATE TABLE IF NOT EXISTS word_categories (
        id INTEGER PRIMARY KEY,
        word_id INTEGER NOT NULL REFERENCES words(id),
        category_id INTEGER NOT NULL REFERENCES categories(id),
        UNIQUE(word_id, category_id)
    );
''')

cur.execute('''CREATE UNIQUE INDEX IF NOT EXISTS idx_word_meaning ON meanings(word_id, meaning_number);''')

cur.execute(''' ALTER TABLE categories RENAME TO categories_old;''')
cur.execute('''CREATE TABLE categories (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    parent_id INTEGER REFERENCES categories(id)
);''')
cur.execute('''INSERT OR IGNORE INTO categories (id, name, parent_id)
SELECT id, name, parent_id FROM categories_old;''')
cur.execute('''DROP TABLE categories_old;''')

# ===== Insert some example categories =====
cur.execute("INSERT OR IGNORE INTO categories (name, parent_id) VALUES ('Nature', NULL)")
cur.execute("INSERT OR IGNORE INTO categories (name, parent_id) VALUES ('Trees', (SELECT id FROM categories WHERE name='Nature'))")
cur.execute("INSERT OR IGNORE INTO categories (name, parent_id) VALUES ('Animals', (SELECT id FROM categories WHERE name='Nature'))")




conn.commit()
conn.close()

print("Categories tables created successfully.")


conn = sqlite3.connect("finnish.db")
cur = conn.cursor()

# Safe ALTER TABLEs — skip if column already exists
def safe_add_column(table, column, definition, post_update=None):
    try:
        cur.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
        print(f"Added column {column} to {table}")
        if post_update:
            cur.execute(post_update)
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e).lower():
            print(f"Column {column} already exists in {table}, skipping.")
        else:
            raise

safe_add_column("meanings", "definition", "TEXT")
safe_add_column("translations", "language", "TEXT DEFAULT 'en'")
safe_add_column("words", "created_at", "TEXT", post_update=f"""
    UPDATE words SET created_at = '{datetime.utcnow().isoformat()}'
    WHERE created_at IS NULL
""")
safe_add_column("words", "updated_at", "TEXT")
safe_add_column("words", "language_code", "TEXT DEFAULT 'fi'")
safe_add_column("categories", "description", "TEXT")

conn.commit()
conn.close()

print("✅ Database updated successfully.")
