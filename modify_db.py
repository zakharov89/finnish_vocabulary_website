import sqlite3

# Connect to SQLite
conn = sqlite3.connect("finnish.db")
cur = conn.cursor()

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
categories = [
    ('Nature', None),
    ('Trees', 1),
    ('Animals', 1),
]

cur.executemany('INSERT OR IGNORE INTO categories (name, parent_id) VALUES (?, ?)', categories)

conn.commit()
conn.close()

print("Categories tables created successfully.")
