import sqlite3

# Connect (or create if it doesn’t exist)
conn = sqlite3.connect("finnish.db")
cur = conn.cursor()

# ===== Core tables =====
cur.execute('''
    CREATE TABLE IF NOT EXISTS parts_of_speech (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL
    );
''')

cur.execute('''
    CREATE TABLE IF NOT EXISTS words (
        id INTEGER PRIMARY KEY,
        word TEXT UNIQUE NOT NULL,
        pos_id INTEGER REFERENCES parts_of_speech(id)
    );
''')

cur.execute('''
    CREATE TABLE IF NOT EXISTS meanings (
        id INTEGER PRIMARY KEY,
        word_id INTEGER NOT NULL REFERENCES words(id),
        meaning_number INTEGER,
        notes TEXT
    );
''')

cur.execute('''
    CREATE TABLE IF NOT EXISTS translations (
        id INTEGER PRIMARY KEY,
        meaning_id INTEGER NOT NULL REFERENCES meanings(id),
        translation_text TEXT NOT NULL,
        translation_number INTEGER
    );
''')

cur.execute('''
    CREATE TABLE IF NOT EXISTS examples (
        id INTEGER PRIMARY KEY,
        meaning_id INTEGER NOT NULL REFERENCES meanings(id),
        example_text TEXT NOT NULL,
        example_translation_text TEXT
    );
''')

# ===== Relations =====
cur.execute('''
    CREATE TABLE IF NOT EXISTS relation_types (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL UNIQUE,
        applies_to TEXT CHECK(applies_to IN ('word', 'meaning')) NOT NULL,
        bidirectional INTEGER DEFAULT 1 CHECK(bidirectional IN (0, 1))
    );
''')

cur.execute('''
    CREATE TABLE IF NOT EXISTS word_relations (
        id INTEGER PRIMARY KEY,
        word1_id INTEGER NOT NULL REFERENCES words(id),
        word2_id INTEGER NOT NULL REFERENCES words(id),
        relation_type_id INTEGER NOT NULL REFERENCES relation_types(id),
        UNIQUE(word1_id, word2_id, relation_type_id)
    );
''')

cur.execute('''
    CREATE TABLE IF NOT EXISTS meaning_relations (
        id INTEGER PRIMARY KEY,
        meaning1_id INTEGER NOT NULL REFERENCES meanings(id),
        meaning2_id INTEGER NOT NULL REFERENCES meanings(id),
        relation_type_id INTEGER NOT NULL REFERENCES relation_types(id),
        UNIQUE(meaning1_id, meaning2_id, relation_type_id)
    );
''')

# ===== Insert initial data =====
parts_of_speech = [
    ('noun',),
    ('verb',),
    ('adjective',),
    ('adverb',),
    ('preposition',),
    ('postposition',),
    ('numeral',),
    ('other',)
]
cur.executemany('INSERT OR IGNORE INTO parts_of_speech (name) VALUES (?)', parts_of_speech)

relation_types = [
    ('synonym', 'meaning', 1),
    ('antonym', 'meaning', 1),
    ('same root', 'word', 1),
    ('compound of', 'word', 1),
    ('derived from', 'word', 1),
    ('part of', 'word', 1)
]
cur.executemany('INSERT OR IGNORE INTO relation_types (name, applies_to, bidirectional) VALUES (?, ?, ?)', relation_types)

conn.commit()
conn.close()

print("Database initialized successfully.")

