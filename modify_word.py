import sqlite3

conn = sqlite3.connect("finnish.db")
conn.row_factory = sqlite3.Row
cur = conn.cursor()

# ----- Helper functions -----
def get_word_id(word):
    cur.execute("SELECT id FROM words WHERE word = ?", (word,))
    row = cur.fetchone()
    return row['id'] if row else None

def list_meanings(word_id):
    cur.execute("SELECT id, meaning_number, notes FROM meanings WHERE word_id = ? ORDER BY meaning_number", (word_id,))
    return cur.fetchall()

def list_translations(meaning_id):
    cur.execute("SELECT id, translation_text FROM translations WHERE meaning_id = ? ORDER BY translation_number", (meaning_id,))
    return cur.fetchall()

def list_examples(meaning_id):
    cur.execute("""
        SELECT id, example_text, example_translation_text
        FROM examples
        WHERE meaning_id = ?
    """, (meaning_id,))
    return cur.fetchall()


# ----- Renumbering -----
def renumber_meanings(word_id):
    cur.execute("SELECT id FROM meanings WHERE word_id = ? ORDER BY meaning_number", (word_id,))
    rows = cur.fetchall()
    for idx, row in enumerate(rows, start=1):
        cur.execute("UPDATE meanings SET meaning_number = ? WHERE id = ?", (idx, row['id']))
    conn.commit()

def renumber_translations(meaning_id):
    cur.execute("SELECT id FROM translations WHERE meaning_id = ? ORDER BY translation_number", (meaning_id,))
    rows = cur.fetchall()
    for idx, row in enumerate(rows, start=1):
        cur.execute("UPDATE translations SET translation_number = ? WHERE id = ?", (idx, row['id']))
    conn.commit()

# ----- Modify translations -----
def modify_translations(meaning_id):
    while True:
        translations = list_translations(meaning_id)
        print("\nTranslations:")
        for t in translations:
            print(f"{t['id']}: {t['translation_text']}")
        action = input("Choose action: (e)dit, (d)elete, (a)dd, (b)ack: ").strip().lower()
        if action == 'e':
            tid = int(input("Enter translation id to edit: "))
            new_text = input("Enter new text: ").strip()
            cur.execute("UPDATE translations SET translation_text = ? WHERE id = ?", (new_text, tid))
            conn.commit()
        elif action == 'd':
            tid = int(input("Enter translation id to delete: "))
            cur.execute("DELETE FROM translations WHERE id = ?", (tid,))
            conn.commit()
            renumber_translations(meaning_id)
        elif action == 'a':
            new_text = input("Enter new translation: ").strip()
            cur.execute("INSERT INTO translations (meaning_id, translation_text, translation_number) VALUES (?, ?, ?)",
                        (meaning_id, new_text, len(translations) + 1))
            conn.commit()
        elif action == 'b':
            break

# ----- Modify examples -----
def modify_examples(meaning_id):
    while True:
        examples = list_examples(meaning_id)
        print("\nExamples:")
        for e in examples:
            translation_display = f" -> {e['example_translation_text']}" if e['example_translation_text'] else ""
            print(f"{e['id']}: {e['example_text']}{translation_display}")

        action = input("Choose action: (e)dit, (d)elete, (a)dd, (b)ack: ").strip().lower()

        if action == 'e':
            eid = int(input("Enter example id to edit: "))
            new_text = input("Enter new text (leave blank to keep current): ").strip()
            new_translation = input("Enter new translation (leave blank to keep current): ").strip()
            cur.execute("""
                UPDATE examples
                SET example_text = COALESCE(NULLIF(?, ''), example_text),
                    example_translation_text = COALESCE(NULLIF(?, ''), example_translation_text)
                WHERE id = ?
            """, (new_text, new_translation, eid))
            conn.commit()

        elif action == 'd':
            eid = int(input("Enter example id to delete: "))
            cur.execute("DELETE FROM examples WHERE id = ?", (eid,))
            conn.commit()

        elif action == 'a':
            new_text = input("Enter new example: ").strip()
            if new_text:
                new_translation = input("Enter translation (or leave empty): ").strip() or None
                cur.execute(
                    "INSERT INTO examples (meaning_id, example_text, example_translation_text) VALUES (?, ?, ?)",
                    (meaning_id, new_text, new_translation)
                )
                conn.commit()

        elif action == 'b':
            break


# ----- Modify part of speech -----
def choose_pos():
    cur.execute("SELECT id, name FROM parts_of_speech")
    pos_list = cur.fetchall()
    print("\nParts of speech:")
    for pos in pos_list:
        print(f"{pos['id']}: {pos['name']}")
    pos_id = int(input("Enter the new part of speech ID: "))
    return pos_id

# ----- Main modification flow -----
def modify_word():
    word = input("Enter the Finnish word to modify: ").strip()

    # Fetch word info with POS
    cur.execute("""
        SELECT w.id AS word_id, w.word, p.name AS pos_name
        FROM words w
        LEFT JOIN parts_of_speech p ON w.pos_id = p.id
        WHERE w.word = ?
    """, (word,))
    word_row = cur.fetchone()
    if not word_row:
        print("Word not found.")
        return

    word_id = word_row['word_id']
    pos_name = word_row['pos_name']
    print(f"\nModifying word: {word} (Current part of speech: {pos_name})")

    while True:
        meanings = list_meanings(word_id)
        print(f"\nMeanings for word: {word} (POS: {pos_name})")
        for m in meanings:
            translations = [t['translation_text'] for t in list_translations(m['id'])]
            examples = [e['example_text'] for e in list_examples(m['id'])]
            print(f"{m['meaning_number']}. Translations: {', '.join(translations)}; Examples: {', '.join(examples)}")

        choice = input("\nSelect meaning number to modify, (p)art of speech, (n)ew meaning, (q)uit: ").strip().lower()

        if choice == 'q':
            break
        elif choice == 'p':
            new_pos_id = choose_pos()
            cur.execute("UPDATE words SET pos_id = ? WHERE id = ?", (new_pos_id, word_id))
            conn.commit()
            cur.execute("SELECT p.name AS pos_name FROM words w LEFT JOIN parts_of_speech p ON w.pos_id = p.id WHERE w.id = ?", (word_id,))
            pos_name = cur.fetchone()['pos_name']
            print(f"Part of speech updated to: {pos_name}")
        elif choice == 'n':
            # Add new meaning
            new_meaning_number = len(meanings) + 1
            cur.execute("INSERT INTO meanings (word_id, meaning_number, notes) VALUES (?, ?, ?)", (word_id, new_meaning_number, None))
            conn.commit()
            cur.execute("SELECT id FROM meanings WHERE word_id = ? AND meaning_number = ?", (word_id, new_meaning_number))
            meaning_id = cur.fetchone()['id']
            print(f"Adding translations and examples for meaning #{new_meaning_number}")
            modify_translations(meaning_id)
            modify_examples(meaning_id)
        else:
            try:
                meaning_number = int(choice)
                meaning = next((m for m in meanings if m['meaning_number'] == meaning_number), None)
                if not meaning:
                    print("Invalid meaning number.")
                    continue
                meaning_id = meaning['id']
                sub_choice = input("Modify (t)ranslations, (e)xamples, (d)elete meaning, or (b)ack: ").strip().lower()
                if sub_choice == 't':
                    modify_translations(meaning_id)
                elif sub_choice == 'e':
                    modify_examples(meaning_id)
                elif sub_choice == 'd':
                    cur.execute("DELETE FROM meanings WHERE id = ?", (meaning_id,))
                    conn.commit()
                    renumber_meanings(word_id)
            except ValueError:
                print("Invalid input.")

if __name__ == "__main__":
    modify_word()
    conn.close()
