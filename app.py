from flask import Flask, render_template
import sqlite3

app = Flask(__name__)

@app.route('/')
def home():
    return 'Tervetuloa!'

@app.route('/about')
def about():
    return 'This is a Finnish learning site'

@app.route('/word/<word_name>')
def show_word(word_name):
    # Connect to SQLite
    conn = sqlite3.connect("finnish.db")
    conn.row_factory = sqlite3.Row  # Access columns by name
    cur = conn.cursor()

    # Fetch word info and part of speech
    cur.execute("""
        SELECT w.id AS word_id, w.word, p.name AS pos_name
        FROM words w
        LEFT JOIN parts_of_speech p ON w.pos_id = p.id
        WHERE w.word = ?
    """, (word_name,))
    
    word_row = cur.fetchone()
    if not word_row:
        conn.close()
        return f"No data found for word: {word_name}"

    word_id = word_row['word_id']
    pos_name = word_row['pos_name']

    # Fetch meanings for the word
    cur.execute("""
        SELECT m.id AS meaning_id, m.meaning_number, m.notes
        FROM meanings m
        WHERE m.word_id = ?
        ORDER BY m.meaning_number
    """, (word_id,))
    
    meanings_rows = cur.fetchall()

    # Collect translations and examples for each meaning
    meanings = []
    for row in meanings_rows:
        meaning_id = row['meaning_id']

        # Translations
        cur.execute("""
            SELECT translation_text
            FROM translations
            WHERE meaning_id = ?
            ORDER BY translation_number
        """, (meaning_id,))
        translations = [t['translation_text'] for t in cur.fetchall()]

        # Examples
        cur.execute("""
            SELECT example_text
            FROM examples
            WHERE meaning_id = ?
        """, (meaning_id,))
        examples = [e['example_text'] for e in cur.fetchall()]

        meanings.append({
            'meaning_number': row['meaning_number'],
            'notes': row['notes'],
            'translations': translations,
            'examples': examples
        })

    conn.close()

    if not meanings:
        return f"No data found for word: {word_name}"

    return render_template('word.html', word_name=word_name, pos_name=pos_name, meanings=meanings)

if __name__ == '__main__':
    app.run(debug=True)

