import sqlite3
from categories import choose_category, assign_word_to_category

# Connect to DB
conn = sqlite3.connect("finnish.db")
conn.row_factory = sqlite3.Row
cur = conn.cursor()


def get_pos_id():
    cur.execute("SELECT id, name FROM parts_of_speech")
    pos_list = cur.fetchall()
    for pos in pos_list:
        print(f"{pos['id']}: {pos['name']}")
    while True:
        try:
            pos_id = int(input("Enter part of speech ID: "))
            if any(p['id'] == pos_id for p in pos_list):
                return pos_id
            else:
                print("Invalid ID. Try again.")
        except ValueError:
            print("Enter a valid number.")


def add_word_to_db():
    """Add a new word with meanings, translations, examples, return word_id and text."""
    word = input("Enter the Finnish word (blank to stop): ").strip()
    if not word:
        return None, None

    pos_id = get_pos_id()

    cur.execute("INSERT OR IGNORE INTO words (word, pos_id) VALUES (?, ?)", (word, pos_id))
    conn.commit()
    cur.execute("SELECT id FROM words WHERE word = ?", (word,))
    word_id = cur.fetchone()['id']

    meaning_number = 1
    while True:
        add_meaning = input(f"Do you want to enter meaning #{meaning_number}? (y/n): ").strip().lower()
        if add_meaning != 'y':
            break

        cur.execute("INSERT INTO meanings (word_id, meaning_number, notes) VALUES (?, ?, ?)",
                    (word_id, meaning_number, None))
        conn.commit()
        cur.execute("SELECT id FROM meanings WHERE word_id = ? AND meaning_number = ?", (word_id, meaning_number))
        meaning_id = cur.fetchone()['id']

        # Translations
        translations = input("Enter translations separated by commas: ").strip().split(",")
        for idx, t in enumerate(translations, start=1):
            t = t.strip()
            if t:
                cur.execute(
                    "INSERT INTO translations (meaning_id, translation_text, translation_number) VALUES (?, ?, ?)",
                    (meaning_id, t, idx)
                )
        conn.commit()

        # Examples
        while True:
            ex_text = input("Enter an example sentence (or leave empty to stop): ").strip()
            if not ex_text:
                break
            ex_translation = input("Enter translation (or leave empty to skip): ").strip() or None
            cur.execute(
                "INSERT INTO examples (meaning_id, example_text, example_translation_text) VALUES (?, ?, ?)",
                (meaning_id, ex_text, ex_translation)
            )
            conn.commit()

        meaning_number += 1

    return word_id, word


def add_words_to_category():
    """Interactive: select category and add multiple words (new or existing) to it."""
    print("=== Category Selection ===")
    category_id, category_name = choose_category(cur, conn)
    if not category_id:
        print("No category selected. Exiting.")
        return

    while True:
        print(f"\nAdding words to category '{category_name}'")
        word_id, word_text = add_word_to_db()
        if not word_id:
            print("No more words. Exiting.")
            break

        assign_word_to_category(cur, conn, word_id, category_id)
        print(f"Word '{word_text}' added and assigned to category '{category_name}'.")


if __name__ == "__main__":
    add_words_to_category()
    conn.close()
