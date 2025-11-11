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


# ----- Modify relations -----
def modify_relations(entity_type, entity_id):
    """
    entity_type: 'word' or 'meaning'
    entity_id: id of the word or meaning
    """
    while True:
        # Fetch current relations
        if entity_type == 'word':
            cur.execute("""
                SELECT wr.id, w2.word AS related_word, rt.name AS relation_type
                FROM word_relations wr
                JOIN words w2 ON wr.word2_id = w2.id
                JOIN relation_types rt ON wr.relation_type_id = rt.id
                WHERE wr.word1_id = ?
                ORDER BY rt.name
            """, (entity_id,))
        else:  # meaning
            cur.execute("""
                SELECT mr.id, w2.word AS related_word, rt.name AS relation_type
                FROM meaning_relations mr
                JOIN meanings m2 ON mr.meaning2_id = m2.id
                JOIN words w2 ON m2.word_id = w2.id
                JOIN relation_types rt ON mr.relation_type_id = rt.id
                WHERE mr.meaning1_id = ?
                ORDER BY rt.name
            """, (entity_id,))

        relations = cur.fetchall()
        print("\nCurrent relations:")
        if not relations:
            print("  (none)")
        else:
            for r in relations:
                print(f"{r['id']}: {r['relation_type']} -> {r['related_word']}")

        # Ask for action
        action = input("Choose action: (a)dd, (d)elete, (b)ack: ").strip().lower()

        if action == 'a':
            # ----- Show relation types -----
            cur.execute("SELECT id, name, bidirectional FROM relation_types WHERE applies_to=?", (entity_type,))
            types = cur.fetchall()
            print("Available relation types:")
            for t in types:
                print(f"{t['id']}: {t['name']} (bidirectional: {'yes' if t['bidirectional'] else 'no'})")

            rt_input = input("Enter relation type ID (or leave empty to cancel): ").strip()
            if not rt_input:
                print("Cancelled.")
                continue
            try:
                rt_id = int(rt_input)
            except ValueError:
                print("Invalid number. Try again.")
                continue

            rt_row = next((t for t in types if t['id'] == rt_id), None)
            if not rt_row:
                print("Invalid relation type ID.")
                continue
            bidirectional = rt_row['bidirectional']

            # ----- Word or Meaning relation -----
            target_word = input("Enter the word for the related entity: ").strip()

            if entity_type == 'word':
                cur.execute("SELECT id FROM words WHERE word=?", (target_word,))
                related = cur.fetchone()
                if not related:
                    print("Word not found.")
                    continue
                related_id = related[0]

                # Insert relation
                cur.execute("""
                    INSERT OR IGNORE INTO word_relations (word1_id, word2_id, relation_type_id)
                    VALUES (?, ?, ?)
                """, (entity_id, related_id, rt_id))
                if bidirectional:
                    cur.execute("""
                        INSERT OR IGNORE INTO word_relations (word1_id, word2_id, relation_type_id)
                        VALUES (?, ?, ?)
                    """, (related_id, entity_id, rt_id))

            else:  # meaning
                # Fetch meanings for the target word
                cur.execute("""
                    SELECT m.id, m.meaning_number, m.notes
                    FROM meanings m
                    JOIN words w ON m.word_id = w.id
                    WHERE w.word=?
                    ORDER BY m.meaning_number
                """, (target_word,))
                target_meanings = cur.fetchall()
                if not target_meanings:
                    print("No meanings found for that word.")
                    continue

                print("Available meanings for this word:")
                for m in target_meanings:
                    cur.execute("""
                        SELECT translation_text
                        FROM translations
                        WHERE meaning_id=?
                        ORDER BY translation_number
                    """, (m['id'],))
                    translations = [t['translation_text'] for t in cur.fetchall()]
                    print(f"{m['id']}: {', '.join(translations)} ({m['notes'] or ''})")

                related_id = int(input("Enter the ID of the meaning to link: "))

                # Insert relation
                cur.execute("""
                    INSERT OR IGNORE INTO meaning_relations (meaning1_id, meaning2_id, relation_type_id)
                    VALUES (?, ?, ?)
                """, (entity_id, related_id, rt_id))
                if bidirectional:
                    cur.execute("""
                        INSERT OR IGNORE INTO meaning_relations (meaning1_id, meaning2_id, relation_type_id)
                        VALUES (?, ?, ?)
                    """, (related_id, entity_id, rt_id))

            conn.commit()
            print("Relation added.")

        elif action == 'd':
            rid = int(input("Enter relation ID to delete: "))
            if entity_type == 'word':
                cur.execute("DELETE FROM word_relations WHERE id=?", (rid,))
            else:
                cur.execute("DELETE FROM meaning_relations WHERE id=?", (rid,))
            conn.commit()
            print("Relation deleted.")

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

        # Main menu for word-level actions
        choice = input("\nSelect meaning number to modify, (p)art of speech, (n)ew meaning, (r)elations for the word, (q)uit: ").strip().lower()

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
        elif choice == 'r':
            # Word-level relations
            modify_relations('word', word_id)
        else:
            # Meaning-level menu
            try:
                meaning_number = int(choice)
                meaning = next((m for m in meanings if m['meaning_number'] == meaning_number), None)
                if not meaning:
                    print("Invalid meaning number.")
                    continue
                meaning_id = meaning['id']

                sub_choice = input("Modify (t)ranslations, (e)xamples, (r)elations, (d)elete meaning, or (b)ack: ").strip().lower()

                if sub_choice == 't':
                    modify_translations(meaning_id)
                elif sub_choice == 'e':
                    modify_examples(meaning_id)
                elif sub_choice == 'r':
                    modify_relations('meaning', meaning_id)
                elif sub_choice == 'd':
                    cur.execute("DELETE FROM meanings WHERE id = ?", (meaning_id,))
                    conn.commit()
                    renumber_meanings(word_id)
                elif sub_choice == 'b':
                    continue
                else:
                    print("Invalid option.")
            except ValueError:
                print("Invalid input.")


if __name__ == "__main__":
    modify_word()
    conn.close()
