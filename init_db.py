import sqlite3

conn = sqlite3.connect('finnish.db')
conn.execute('PRAGMA foreign_keys = ON;')
cur = conn.cursor()

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
            example_text TEXT NOT NULL
    );
''')


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

cur.executemany('INSERT INTO parts_of_speech (name) VALUES (?)', parts_of_speech)



words = [
    ('omena', 1),  # 1 = noun
    ('ilma', 1)    # 1 = noun
]

cur.executemany("INSERT INTO words (word, pos_id) VALUES (?, ?)", words)
conn.commit()



cur.execute("SELECT id, word FROM words")
word_ids = {row[1]: row[0] for row in cur.fetchall()}  # {'omena': 1, 'ilma': 2}

meanings = [
    (word_ids['omena'], 1, None),  # meaning_number = 1, notes = None
    (word_ids['ilma'], 1, None),   # "air"
    (word_ids['ilma'], 2, None)    # "weather"
]

cur.executemany("INSERT INTO meanings (word_id, meaning_number, notes) VALUES (?, ?, ?)", meanings)
conn.commit()



cur.execute("SELECT id, word_id, meaning_number FROM meanings")
meaning_ids = {(row[1], row[2]): row[0] for row in cur.fetchall()}  
# {(1,1): 1, (2,1): 2, (2,2): 3}

translations = [
    (meaning_ids[(word_ids['omena'],1)], 'apple', 1),
    (meaning_ids[(word_ids['ilma'],1)], 'air', 1),
    (meaning_ids[(word_ids['ilma'],2)], 'weather', 1)
]

cur.executemany("INSERT INTO translations (meaning_id, translation_text, translation_number) VALUES (?, ?, ?)", translations)
conn.commit()



examples = [
    (meaning_ids[(word_ids['omena'],1)], 'Syön omenaa.'),
    (meaning_ids[(word_ids['omena'],1)], 'Omena on punainen'),
    (meaning_ids[(word_ids['ilma'],2)], 'Millainen ilma tänään on?')
]

cur.executemany("INSERT INTO examples (meaning_id, example_text) VALUES (?, ?)", examples)
conn.commit()




conn.commit()
conn.close()