import sqlite3

# Define the definitive POS list
pos_list = [
    "noun", "verb", "adjective", "adverb", "pronoun",
    "preposition", "postposition", "conjunction",
    "interjection", "phrase", "proper noun", "numeral"
]

conn = sqlite3.connect("finnish.db")
cur = conn.cursor()

# Step 1: Remove duplicate names (keep lowest id)
cur.execute("""
    DELETE FROM parts_of_speech
    WHERE id NOT IN (
        SELECT MIN(id)
        FROM parts_of_speech
        GROUP BY name
    )
""")

# Step 2: Rename table and create new one with UNIQUE constraint
cur.execute("ALTER TABLE parts_of_speech RENAME TO parts_of_speech_old")

cur.execute("""
CREATE TABLE parts_of_speech (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
)
""")

# Step 3: Copy old rows
cur.execute("""
INSERT INTO parts_of_speech (id, name)
SELECT id, name FROM parts_of_speech_old
""")

# Step 4: Drop old table
cur.execute("DROP TABLE parts_of_speech_old")

# Step 5: Insert full POS list (ignores duplicates)
for pos in pos_list:
    cur.execute("INSERT OR IGNORE INTO parts_of_speech (name) VALUES (?)", (pos,))

conn.commit()
conn.close()

print("parts_of_speech table updated successfully!")

