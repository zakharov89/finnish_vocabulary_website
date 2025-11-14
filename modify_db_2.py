import sqlite3

# Connect to SQLite
conn = sqlite3.connect("finnish.db")
cur = conn.cursor()

# Add sort_order column to word_categories
cur.execute("""
ALTER TABLE word_categories
ADD COLUMN sort_order INTEGER DEFAULT 0
""")

# Create category_word_translations table
cur.execute("""
CREATE TABLE IF NOT EXISTS category_word_translations (
    id INTEGER PRIMARY KEY,
    word_category_id INTEGER NOT NULL REFERENCES word_categories(id),
    translation_id INTEGER NOT NULL REFERENCES translations(id),
    UNIQUE(word_category_id, translation_id)
)
""")

# Commit changes and close connection
conn.commit()
conn.close()
