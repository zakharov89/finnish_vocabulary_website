import sqlite3

# Connect
conn = sqlite3.connect("finnish.db")
cur = conn.cursor()

# 1. Create levels table
cur.execute('''
CREATE TABLE IF NOT EXISTS levels (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
)
''')

# 2. Insert 5 levels if they don’t exist
levels = [(1, "Level 1"), (2, "Level 2"), (3, "Level 3"), (4, "Level 4"), (5, "Level 5")]
for lid, lname in levels:
    cur.execute("INSERT OR IGNORE INTO levels (id, name) VALUES (?, ?)", (lid, lname))

# 3. Rename old words table
cur.execute("ALTER TABLE words RENAME TO words_old")

# 4. Create new words table with foreign key
cur.execute('''
CREATE TABLE words (
    id INTEGER PRIMARY KEY,
    word TEXT NOT NULL,
    level INTEGER NOT NULL DEFAULT 1,
    created_at TEXT,
    updated_at TEXT,
    FOREIGN KEY(level) REFERENCES levels(id)
)
''')

# 5. Copy data
cur.execute('''
INSERT INTO words (id, word, level, created_at, updated_at)
SELECT id, word, level, created_at, updated_at FROM words_old
''')

# 6. Drop old table
cur.execute("DROP TABLE words_old")

conn.commit()
conn.close()
print("Migration completed successfully.")
