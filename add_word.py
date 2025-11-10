import sqlite3

# Connect to the database
conn = sqlite3.connect("finnish.db")
cur = conn.cursor()

def get_pos_id():
    # List available parts of speech
    cur.execute("SELECT id, name FROM parts_of_speech")
    pos_list = cur.fetchall()
    for pos in pos_list:
        print(f"{pos[0]}: {pos[1]}")
    
    pos_id = int(input("Enter part of speech ID: "))
    return pos_id

def add_word():
    word = input("Enter the Finnish word: ").strip()
    pos_id = get_pos_id()

    # Insert word, ignore if it already exists
    cur.execute("INSERT OR IGNORE INTO words (word, pos_id) VALUES (?, ?)", (word, pos_id))
    conn.commit()

    # Get word id
    cur.execute("SELECT id FROM words WHERE word = ?", (word,))
    word_id = cur.fetchone()[0]

    meaning_number = 1
    while True:
        add_meaning = input(f"Do you want to enter meaning #{meaning_number}? (y/n): ").strip().lower()
        if add_meaning != 'y':
            break

        # Insert new meaning
        cur.execute("INSERT INTO meanings (word_id, meaning_number, notes) VALUES (?, ?, ?)",
                    (word_id, meaning_number, None))
        conn.commit()

        cur.execute("SELECT id FROM meanings WHERE word_id = ? AND meaning_number = ?", (word_id, meaning_number))
        meaning_id = cur.fetchone()[0]

        # Translations for this meaning
        translations = input("Enter translations separated by commas: ").strip().split(",")
        for idx, t in enumerate(translations, start=1):
            t = t.strip()
            if t:
                cur.execute(
                    "INSERT INTO translations (meaning_id, translation_text, translation_number) VALUES (?, ?, ?)",
                    (meaning_id, t, idx)
                )
        conn.commit()

        # Examples for this meaning
        while True:
            ex = input("Enter an example sentence (or leave empty to stop): ").strip()
            if not ex:
                break
            cur.execute(
                "INSERT INTO examples (meaning_id, example_text) VALUES (?, ?)",
                (meaning_id, ex)
            )
            conn.commit()

        meaning_number += 1

    print(f"Word '{word}' added successfully!")

if __name__ == "__main__":
    add_word()
    conn.close()
