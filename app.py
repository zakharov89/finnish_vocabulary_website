from flask import Flask, render_template, request
import sqlite3

app = Flask(__name__)

@app.route('/', methods=['GET'])
def home():
    query = request.args.get('query', '').strip()  # get the query from the URL

    results = []
    if query:  # only search if something was entered
        conn = sqlite3.connect("finnish.db")
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        cur.execute("""
            SELECT word FROM words
            WHERE word LIKE ?
            ORDER BY word
            LIMIT 20
        """, (f"{query}%",))
        results = [row['word'] for row in cur.fetchall()]

        conn.close()

    return render_template('home.html', query=query, results=results)

@app.route('/about')
def about():
    return render_template('about.html', title="About")


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
            SELECT example_text, example_translation_text
            FROM examples
            WHERE meaning_id = ?
        """, (meaning_id,))
        examples = [
            {'text': e['example_text'], 'translation': e['example_translation_text']}
            for e in cur.fetchall()
        ]

        # Meaning-level relations
        cur.execute("""
            SELECT mr.meaning2_id, rt.name AS relation_type, w.word AS related_word
            FROM meaning_relations mr
            JOIN relation_types rt ON mr.relation_type_id = rt.id
            JOIN meanings m2 ON mr.meaning2_id = m2.id
            JOIN words w ON m2.word_id = w.id
            WHERE mr.meaning1_id = ?
        """, (meaning_id,))
        relations = [{'type': r['relation_type'], 'word': r['related_word']} for r in cur.fetchall()]

        meanings.append({
            'meaning_number': row['meaning_number'],
            'notes': row['notes'],
            'translations': translations,
            'examples': examples,
            'relations': relations  
        })

    # Word-level relations
    cur.execute("""
        SELECT wr.word2_id, rt.name AS relation_type, w2.word AS related_word
        FROM word_relations wr
        JOIN relation_types rt ON wr.relation_type_id = rt.id
        JOIN words w2 ON wr.word2_id = w2.id
        WHERE wr.word1_id = ?
    """, (word_id,))
    word_relations = [{'type': r['relation_type'], 'word': r['related_word']} for r in cur.fetchall()]

    # --- Fetch categories ---
    cur.execute("""
        SELECT c.id, c.name
        FROM categories c
        JOIN word_categories wc ON c.id = wc.category_id
        WHERE wc.word_id = ?
        ORDER BY c.name
    """, (word_id,))
    categories = cur.fetchall()

    conn.close()

    if not meanings:
        return f"No data found for word: {word_name}"

    return render_template(
        'word.html', 
        word_name=word_name, 
        pos_name=pos_name, 
        meanings=meanings,
        word_relations=word_relations,
        categories=categories  
    )






@app.route('/categories')
def categories():
    conn = sqlite3.connect("finnish.db")
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Fetch all categories
    cur.execute("SELECT id, name, parent_id FROM categories ORDER BY name")
    rows = cur.fetchall()

    # Organize into parent-child dict
    categories_dict = {}
    for row in rows:
        if row['parent_id']:
            categories_dict.setdefault(row['parent_id'], []).append(row)
        else:
            categories_dict.setdefault(None, []).append(row)

    conn.close()
    return render_template('categories.html', categories=categories_dict)


@app.route('/categories/<category_name>')
def show_category(category_name):
    conn = sqlite3.connect("finnish.db")
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Fetch the category itself
    cur.execute("SELECT id, name, parent_id FROM categories WHERE name = ?", (category_name,))
    category = cur.fetchone()
    if not category:
        return f"Category '{category_name}' not found."

    # Fetch words
    cur.execute("""
        SELECT w.id, w.word
        FROM words w
        JOIN word_categories wc ON w.id = wc.word_id
        WHERE wc.category_id = ?
        ORDER BY w.word
    """, (category['id'],))
    words = cur.fetchall()

    words_with_translations = []

    for w in words:
        cur.execute("""
            SELECT t.translation_text
            FROM meanings m
            JOIN translations t ON m.id = t.meaning_id
            WHERE m.word_id = ?
            ORDER BY m.meaning_number, t.translation_number
            LIMIT 3
        """, (w['id'],))
        translations = [t['translation_text'] for t in cur.fetchall()]

        words_with_translations.append({
            'word': w['word'],
            'translations': translations
        })


    # Fetch subcategories
    cur.execute("SELECT id, name FROM categories WHERE parent_id = ? ORDER BY name", (category['id'],))
    subcategories = cur.fetchall()

    # Fetch parent (if any)
    parent = None
    if category['parent_id']:
        cur.execute("SELECT name FROM categories WHERE id = ?", (category['parent_id'],))
        parent = cur.fetchone()

    conn.close()

    return render_template(
        "category.html",
        category=category,
        words=words_with_translations,
        subcategories=subcategories,
        parent=parent
    )









if __name__ == '__main__':
    app.run(debug=True)

