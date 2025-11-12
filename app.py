from flask import Flask, session, redirect, url_for, request, render_template, flash
import sqlite3
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev_key")

ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD")



@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session['admin_logged_in'] = True
            return redirect(url_for('admin_dashboard'))
        else:
            flash("Invalid credentials.", "danger")

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('admin_logged_in', None)
    # Clear all flashed messages
    session.pop('_flashes', None)
    flash("Logged out.", "info")
    return redirect(url_for('login'))



# ----- Admin-only decorator -----
from functools import wraps

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('admin_logged_in'):
            flash("Admin login required.", "warning")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


@app.route("/admin")
@admin_required
def admin_dashboard():
    conn = sqlite3.connect("finnish.db")
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Counts for summary
    cur.execute("SELECT COUNT(*) as count FROM words")
    total_words = cur.fetchone()["count"]

    cur.execute("SELECT COUNT(*) as count FROM categories")
    total_categories = cur.fetchone()["count"]

    # Recent words (last 10 added)
    cur.execute("SELECT word, id FROM words ORDER BY id DESC LIMIT 10")
    recent_words = cur.fetchall()

    # Recent categories (last 10 added)
    cur.execute("SELECT name, id FROM categories ORDER BY id DESC LIMIT 10")
    recent_categories = cur.fetchall()

    conn.close()
    
    return render_template(
        "admin_dashboard.html",
        total_words=total_words,
        total_categories=total_categories,
        recent_words=recent_words,
        recent_categories=recent_categories
    )

@app.route('/admin/add_word', methods=['GET', 'POST'])
@admin_required
def admin_add_word():
    conn = sqlite3.connect("finnish.db")
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Fetch parts of speech and categories for dropdowns
    cur.execute("SELECT id, name FROM parts_of_speech ORDER BY name")
    pos_list = cur.fetchall()

    cur.execute("SELECT id, name FROM categories ORDER BY name")
    categories = cur.fetchall()

    if request.method == 'POST':
        word_text = request.form.get('word', '').strip()
        pos_id = request.form.get('pos_id')
        selected_category_id = request.form.get('category_id')  # optional

        if not word_text:
            flash("Word cannot be empty.", "error")
        else:
            # Insert word
            cur.execute("INSERT OR IGNORE INTO words (word, pos_id) VALUES (?, ?)", (word_text, pos_id))
            conn.commit()

            cur.execute("SELECT id FROM words WHERE word = ?", (word_text,))
            word_id = cur.fetchone()['id']

            # Assign to category if selected
            if selected_category_id:
                cur.execute("INSERT OR IGNORE INTO word_categories (word_id, category_id) VALUES (?, ?)",
                            (word_id, selected_category_id))
                conn.commit()

            # Insert meanings + translations + examples
            meaning_numbers = request.form.getlist('meaning_number[]')
            for i, m_num in enumerate(meaning_numbers):
                notes = request.form.getlist('meaning_notes[]')[i] or None
                cur.execute("INSERT INTO meanings (word_id, meaning_number, notes) VALUES (?, ?, ?)",
                            (word_id, int(m_num), notes))
                conn.commit()

                cur.execute("SELECT id FROM meanings WHERE word_id=? AND meaning_number=?", (word_id, int(m_num)))
                meaning_id = cur.fetchone()['id']

                # Translations
                translations = request.form.getlist(f'translations_{m_num}[]')
                for idx, t in enumerate(translations, start=1):
                    t = t.strip()
                    if t:
                        cur.execute("INSERT INTO translations (meaning_id, translation_text, translation_number) VALUES (?, ?, ?)",
                                    (meaning_id, t, idx))
                conn.commit()

                # Examples
                example_texts = request.form.getlist(f'examples_{m_num}[]')
                example_translations = request.form.getlist(f'examples_trans_{m_num}[]')
                for ex_text, ex_trans in zip(example_texts, example_translations):
                    ex_text = ex_text.strip()
                    ex_trans = ex_trans.strip() or None
                    if ex_text:
                        cur.execute(
                            "INSERT INTO examples (meaning_id, example_text, example_translation_text) VALUES (?, ?, ?)",
                            (meaning_id, ex_text, ex_trans)
                        )
                conn.commit()

            flash(f"Word '{word_text}' added successfully!", "success")
            conn.close()
            return redirect(url_for('admin_dashboard'))

    conn.close()
    return render_template('admin_add_word.html', pos_list=pos_list, categories=categories)



@app.route('/admin/edit_word/<int:word_id>', methods=['GET', 'POST'])
@admin_required
def admin_edit_word(word_id):
    conn = sqlite3.connect("finnish.db")
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Fetch the word
    cur.execute("SELECT * FROM words WHERE id = ?", (word_id,))
    word = cur.fetchone()
    if not word:
        flash("Word not found.", "error")
        conn.close()
        return redirect(url_for('admin_dashboard'))

    word = dict(word)

    # Fetch categories and POS
    cur.execute("SELECT id, name FROM categories ORDER BY name")
    categories = cur.fetchall()
    cur.execute("SELECT id, name FROM parts_of_speech ORDER BY name")
    pos_list = cur.fetchall()

    # Fetch assigned category
    cur.execute("SELECT category_id FROM word_categories WHERE word_id = ?", (word_id,))
    word_categories = [row['category_id'] for row in cur.fetchall()]
    word['category_ids'] = word_categories

    # Fetch meanings
    cur.execute("SELECT * FROM meanings WHERE word_id = ? ORDER BY meaning_number", (word_id,))
    meanings_rows = cur.fetchall()
    meanings = []
    for m in meanings_rows:
        meaning_id = m['id']

        # Translations
        cur.execute("SELECT translation_text FROM translations WHERE meaning_id = ? ORDER BY translation_number", (meaning_id,))
        translations = [t['translation_text'] for t in cur.fetchall()]

        # Examples
        cur.execute("SELECT example_text, example_translation_text FROM examples WHERE meaning_id = ?", (meaning_id,))
        examples = [(e['example_text'], e['example_translation_text']) for e in cur.fetchall()]

        meanings.append({
            'meaning_number': m['meaning_number'],
            'notes': m['notes'],
            'translations': translations,
            'examples': examples
        })

    if request.method == 'POST':
        # Update word text and POS
        new_word = request.form.get('word', '').strip()
        new_pos_id = request.form.get('pos_id')
        cur.execute("UPDATE words SET word = ?, pos_id = ? WHERE id = ?", (new_word, new_pos_id, word_id))
        conn.commit()

        # Update category (clear old and insert new)
        cur.execute("DELETE FROM word_categories WHERE word_id = ?", (word_id,))
        category_id = request.form.get('category_id')
        if category_id:
            cur.execute("INSERT INTO word_categories (word_id, category_id) VALUES (?, ?)", (word_id, category_id))
        conn.commit()

        # Delete existing meanings + translations + examples
        cur.execute("SELECT id FROM meanings WHERE word_id = ?", (word_id,))
        meaning_ids = [row['id'] for row in cur.fetchall()]
        for mid in meaning_ids:
            cur.execute("DELETE FROM translations WHERE meaning_id = ?", (mid,))
            cur.execute("DELETE FROM examples WHERE meaning_id = ?", (mid,))
        cur.execute("DELETE FROM meanings WHERE word_id = ?", (word_id,))
        conn.commit()

        # Insert updated meanings
        meaning_numbers = request.form.getlist('meaning_number[]')
        for i, m_num in enumerate(meaning_numbers):
            notes = request.form.getlist('meaning_notes[]')[i] or None
            cur.execute("INSERT INTO meanings (word_id, meaning_number, notes) VALUES (?, ?, ?)",
                        (word_id, int(m_num), notes))
            conn.commit()
            cur.execute("SELECT id FROM meanings WHERE word_id=? AND meaning_number=?", (word_id, int(m_num)))
            meaning_id = cur.fetchone()['id']

            # Translations
            translations = request.form.getlist(f'translations_{m_num}[]')
            for idx, t in enumerate(translations, start=1):
                t = t.strip()
                if t:
                    cur.execute("INSERT INTO translations (meaning_id, translation_text, translation_number) VALUES (?, ?, ?)",
                                (meaning_id, t, idx))
            conn.commit()

            # Examples
            example_texts = request.form.getlist(f'examples_{m_num}[]')
            example_translations = request.form.getlist(f'examples_trans_{m_num}[]')
            for ex_text, ex_trans in zip(example_texts, example_translations):
                ex_text = ex_text.strip()
                ex_trans = ex_trans.strip() or None
                if ex_text:
                    cur.execute(
                        "INSERT INTO examples (meaning_id, example_text, example_translation_text) VALUES (?, ?, ?)",
                        (meaning_id, ex_text, ex_trans)
                    )
            conn.commit()

        flash(f"Word '{new_word}' updated successfully!", "success")
        conn.close()
        return redirect(url_for('admin_dashboard'))

    conn.close()
    return render_template('admin_edit_word.html', word=word, pos_list=pos_list, categories=categories, meanings=meanings)



@app.route('/admin/edit_word_search', methods=['GET'])
@admin_required
def admin_edit_word_search():
    query = request.args.get('word_query', '').strip()
    if not query:
        flash("Please enter a word to search.", "warning")
        return redirect(url_for('admin_dashboard'))

    conn = sqlite3.connect("finnish.db")
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    # Prefix search using LIKE
    cur.execute("SELECT id, word FROM words WHERE word LIKE ? ORDER BY word LIMIT 10", (f"{query}%",))
    results = cur.fetchall()
    conn.close()

    if not results:
        flash(f"No words found starting with '{query}'.", "info")
        return redirect(url_for('admin_dashboard'))

    return render_template("admin_edit_word_search.html", results=results, query=query)



@app.route('/admin/delete_word/<int:word_id>', methods=['POST'])
@admin_required
def admin_delete_word(word_id):
    conn = sqlite3.connect("finnish.db")
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Fetch the word for feedback
    cur.execute("SELECT word FROM words WHERE id = ?", (word_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
        flash("Word not found.", "error")
        return redirect(url_for('admin_dashboard'))

    word_text = row['word']

    # Delete related data first due to foreign keys
    cur.execute("DELETE FROM meaning_relations WHERE meaning1_id IN (SELECT id FROM meanings WHERE word_id=?)", (word_id,))
    cur.execute("DELETE FROM meaning_relations WHERE meaning2_id IN (SELECT id FROM meanings WHERE word_id=?)", (word_id,))
    cur.execute("DELETE FROM word_relations WHERE word1_id=? OR word2_id=?", (word_id, word_id))
    cur.execute("DELETE FROM translations WHERE meaning_id IN (SELECT id FROM meanings WHERE word_id=?)", (word_id,))
    cur.execute("DELETE FROM examples WHERE meaning_id IN (SELECT id FROM meanings WHERE word_id=?)", (word_id,))
    cur.execute("DELETE FROM meanings WHERE word_id=?", (word_id,))
    cur.execute("DELETE FROM word_categories WHERE word_id=?", (word_id,))
    cur.execute("DELETE FROM words WHERE id=?", (word_id,))

    conn.commit()
    conn.close()

    flash(f"Word '{word_text}' deleted successfully!", "success")
    return redirect(url_for('admin_dashboard'))




@app.route("/admin/add_category", methods=["GET", "POST"])
@admin_required
def admin_add_category():
    if request.method == "POST":
        name = request.form["name"].strip()
        parent_id = request.form.get("parent_id") or None

        conn = sqlite3.connect("finnish.db", timeout=5)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        cur.execute("INSERT INTO categories (name, parent_id) VALUES (?, ?)", (name, parent_id))
        conn.commit()
        category_id = cur.lastrowid
        conn.close()

        return redirect(url_for("admin_add_words_to_category", category_id=category_id))

    # GET should supply categories for parent dropdown
    conn = sqlite3.connect("finnish.db", timeout=5)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT id, name FROM categories ORDER BY name")
    categories = cur.fetchall()
    conn.close()

    return render_template("admin_add_category.html", categories=categories)


@app.route("/admin/add_words_to_category/<int:category_id>", methods=["GET", "POST"])
@admin_required
def admin_add_words_to_category(category_id):
    conn = sqlite3.connect("finnish.db", timeout=5)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Get category info
    cur.execute("SELECT * FROM categories WHERE id = ?", (category_id,))
    category = cur.fetchone()
    if not category:
        conn.close()
        flash("Category not found.", "danger")
        return redirect(url_for("admin_dashboard"))

    # Fetch parts of speech for the inline new-word form
    cur.execute("SELECT id, name FROM parts_of_speech ORDER BY name")
    pos_list = cur.fetchall()

    # Handle adding an existing word (single quick insert)
    if request.method == "POST" and request.form.get("existing_word_id"):
        word_id = int(request.form["existing_word_id"])
        cur.execute(
            "INSERT OR IGNORE INTO word_categories (word_id, category_id) VALUES (?, ?)",
            (word_id, category_id)
        )
        conn.commit()
        flash("Word added to category.", "success")
        conn.close()
        return redirect(url_for("admin_add_words_to_category", category_id=category_id))

    # Handle adding a new word (batch inserts, commit once at end)
    if request.method == "POST" and request.form.get("new_word"):
        try:
            word = request.form["new_word"].strip()
            pos_id = int(request.form["pos_id"])

            # Insert word if not exists
            cur.execute("INSERT OR IGNORE INTO words (word, pos_id) VALUES (?, ?)", (word, pos_id))
            cur.execute("SELECT id FROM words WHERE word = ?", (word,))
            word_id_row = cur.fetchone()
            word_id = word_id_row["id"]

            # We'll accumulate inserts and commit once at the end
            # Handle meanings, translations, examples
            meaning_numbers = request.form.getlist("meaning_number[]")
            for m_num in meaning_numbers:
                notes = request.form.get(f"meaning_notes[]")  # fallback if using same list; optional adjust
                # insert meaning
                cur.execute(
                    "INSERT INTO meanings (word_id, meaning_number, notes) VALUES (?, ?, ?)",
                    (word_id, int(m_num), request.form.getlist('meaning_notes[]')[int(m_num)-1] if request.form.getlist('meaning_notes[]') else None)
                )
                # fetch meaning id
                cur.execute(
                    "SELECT id FROM meanings WHERE word_id = ? AND meaning_number = ?",
                    (word_id, int(m_num))
                )
                meaning_id = cur.fetchone()["id"]

                # Translations
                translations = request.form.getlist(f"translations_{m_num}[]")
                for idx, t in enumerate(translations, 1):
                    t = t.strip()
                    if t:
                        cur.execute(
                            "INSERT INTO translations (meaning_id, translation_text, translation_number) VALUES (?, ?, ?)",
                            (meaning_id, t, idx)
                        )

                # Examples
                example_texts = request.form.getlist(f"examples_{m_num}[]")
                example_trans = request.form.getlist(f"examples_trans_{m_num}[]")
                for ex, ex_tr in zip(example_texts, example_trans):
                    ex = ex.strip()
                    if ex:
                        cur.execute(
                            "INSERT INTO examples (meaning_id, example_text, example_translation_text) VALUES (?, ?, ?)",
                            (meaning_id, ex, ex_tr.strip() or None)
                        )

            # Assign to category
            cur.execute(
                "INSERT OR IGNORE INTO word_categories (word_id, category_id) VALUES (?, ?)",
                (word_id, category_id)
            )

            # Commit once
            conn.commit()
            flash(f"New word '{word}' added and assigned to category.", "success")
        except Exception as e:
            conn.rollback()
            flash(f"Error adding word: {e}", "danger")
        finally:
            conn.close()

        return redirect(url_for("admin_add_words_to_category", category_id=category_id))

    # GET request → show search form; use 'search' as query param (keep consistent with template)
    search_query = request.args.get("search", "").strip()
    search_results = []
    if search_query:
        cur.execute(
            "SELECT id, word FROM words WHERE word LIKE ? ORDER BY word LIMIT 50",
            (f"{search_query}%",)
        )
        search_results = cur.fetchall()

    conn.close()
    return render_template(
        "admin_add_words_to_category.html",
        category=category,
        pos_list=pos_list,
        search_query=search_query,
        search_results=search_results
    )


@app.route("/admin/categories/search")
@admin_required
def admin_search_category():
    query = request.args.get("query", "").strip()
    conn = sqlite3.connect("finnish.db")
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    if query:
        cur.execute("SELECT id, name FROM categories WHERE name LIKE ? ORDER BY name", (f"%{query}%",))
        results = cur.fetchall()
    else:
        results = []

    conn.close()
    return render_template("admin_category_search.html", query=query, results=results)


@app.route("/admin/categories/<int:category_id>/edit", methods=["GET", "POST"])
@admin_required
def admin_edit_category(category_id):
    conn = sqlite3.connect("finnish.db")
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Fetch category info
    cur.execute("SELECT * FROM categories WHERE id = ?", (category_id,))
    category = cur.fetchone()
    if not category:
        flash("Category not found.", "danger")
        conn.close()
        return redirect(url_for("admin_dashboard"))


    # Handle POST for updating category
    if request.method == "POST":
        name = request.form.get("name").strip()
        parent_id = request.form.get("parent_id") or None
        cur.execute("UPDATE categories SET name = ?, parent_id = ? WHERE id = ?", (name, parent_id, category_id))
        conn.commit()
        flash("Category updated.", "success")
        return redirect(url_for("admin_dashboard"))

    # GET: show edit form
    cur.execute("SELECT id, name FROM categories")
    all_categories = cur.fetchall()  # For parent selection
    conn.close()

    return render_template("admin_edit_category.html", category=category, all_categories=all_categories)




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

