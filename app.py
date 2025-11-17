from flask import Flask, session, redirect, url_for, request, render_template, flash, jsonify
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

    # Fetch parts of speech for the form
    cur.execute("SELECT id, name FROM parts_of_speech ORDER BY name")
    pos_list = [dict(pos) for pos in cur.fetchall()]

    if request.method == 'POST':
        word_text = request.form.get('word', '').strip()
        if not word_text:
            flash("Word cannot be empty.", "error")
        else:
            # Check if the word already exists
            cur.execute("SELECT id FROM words WHERE word = ?", (word_text,))
            if cur.fetchone():
                flash(f"Word '{word_text}' already exists.", "warning")
                conn.close()
                return render_template('admin_add_word.html', pos_list=pos_list)

            # Insert the word
            cur.execute("INSERT INTO words (word) VALUES (?)", (word_text,))
            conn.commit()
            word_id = cur.lastrowid

            # Insert meanings
            meaning_numbers = request.form.getlist('meaning_number[]')
            for idx, m_num in enumerate(meaning_numbers):
                m_num_int = int(m_num)

                # POS per meaning
                pos_id = request.form.get(f"pos_id_{m_num}")  # NEW

                notes = request.form.get(f"meaning_notes_{m_num}", "").strip() or None
                definition = request.form.get(f"definition_{m_num}", "").strip() or None

                # Insert meaning
                cur.execute(
                    "INSERT INTO meanings (word_id, meaning_number, notes, definition, pos_id) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (word_id, m_num_int, notes, definition, pos_id)
                )
                conn.commit()
                meaning_id = cur.lastrowid

                # Insert translations
                translations = request.form.getlist(f'translations_{m_num}[]')
                for t_idx, t in enumerate(translations, start=1):
                    t = t.strip()
                    if t:
                        cur.execute(
                            "INSERT INTO translations (meaning_id, translation_text, translation_number) "
                            "VALUES (?, ?, ?)",
                            (meaning_id, t, t_idx)
                        )

                # Insert examples
                example_texts = request.form.getlist(f'examples_{m_num}[]')
                example_trans = request.form.getlist(f'examples_trans_{m_num}[]')
                for ex_text, ex_trans in zip(example_texts, example_trans):
                    ex_text = ex_text.strip()
                    ex_trans = ex_trans.strip() or None
                    if ex_text:
                        cur.execute(
                            "INSERT INTO examples (meaning_id, example_text, example_translation_text) "
                            "VALUES (?, ?, ?)",
                            (meaning_id, ex_text, ex_trans)
                        )
                conn.commit()

            flash(f"Word '{word_text}' added successfully!", "success")
            conn.close()
            return redirect(url_for('admin_dashboard'))

    conn.close()
    return render_template('admin_add_word.html', pos_list=pos_list)



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

    # Fetch POS list
    cur.execute("SELECT id, name FROM parts_of_speech ORDER BY name")
    pos_list = [dict(p) for p in cur.fetchall()]

    # Fetch meanings with POS
    cur.execute("SELECT m.*, p.name as pos_name FROM meanings m "
                "LEFT JOIN parts_of_speech p ON m.pos_id = p.id "
                "WHERE m.word_id=? ORDER BY p.name, m.meaning_number", (word_id,))
    meanings_rows = cur.fetchall()

    # Group meanings by POS
    meanings_by_pos = {}
    for m in meanings_rows:
        pos_name = m['pos_name'] or 'Other'
        if pos_name not in meanings_by_pos:
            meanings_by_pos[pos_name] = []
        meaning_id = m['id']

        # Translations
        cur.execute("SELECT translation_text FROM translations WHERE meaning_id=? ORDER BY translation_number", (meaning_id,))
        translations = [t['translation_text'] for t in cur.fetchall()]

        # Examples
        cur.execute("SELECT example_text, example_translation_text FROM examples WHERE meaning_id=?", (meaning_id,))
        examples = [(e['example_text'], e['example_translation_text']) for e in cur.fetchall()]

        meanings_by_pos[pos_name].append({
            'id': m['id'],
            'meaning_number': m['meaning_number'],
            'notes': m['notes'],
            'definition': m['definition'],
            'translations': translations,
            'examples': examples
        })

    # Handle POST (update word only)
    if request.method == 'POST':
        new_word = request.form.get('word', '').strip()
        # Check for duplicates
        cur.execute("SELECT id FROM words WHERE word=? AND id != ?", (new_word, word_id))
        if cur.fetchone():
            flash(f"The word '{new_word}' already exists.", "error")
            conn.close()
            return redirect(url_for('admin_edit_word', word_id=word_id))

        cur.execute("UPDATE words SET word=? WHERE id=?", (new_word, word_id))
        conn.commit()
        flash(f"Word '{new_word}' updated successfully!", "success")
        conn.close()
        return redirect(url_for('admin_dashboard'))

    conn.close()
    return render_template('admin_edit_word.html', word=word, meanings_by_pos=meanings_by_pos, pos_list=pos_list)




@app.route('/admin/edit_meaning/<int:meaning_id>', methods=['GET', 'POST'])
@admin_required
def admin_edit_meaning(meaning_id):
    conn = sqlite3.connect("finnish.db")
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Fetch the meaning
    cur.execute("SELECT * FROM meanings WHERE id=?", (meaning_id,))
    meaning = cur.fetchone()
    if not meaning:
        flash("Meaning not found.", "error")
        conn.close()
        return redirect(url_for('admin_dashboard'))
    meaning = dict(meaning)
    word_id = meaning['word_id']

    # Count total meanings for this word
    cur.execute("SELECT COUNT(*) AS cnt FROM meanings WHERE word_id=?", (word_id,))
    meanings_count = cur.fetchone()['cnt']

    # Fetch POS list
    cur.execute("SELECT id, name FROM parts_of_speech ORDER BY name")
    pos_list = cur.fetchall()

    # Fetch translations
    cur.execute("SELECT translation_text, translation_number FROM translations WHERE meaning_id=? ORDER BY translation_number", (meaning_id,))
    translations = cur.fetchall()

    # Fetch examples
    cur.execute("SELECT example_text, example_translation_text FROM examples WHERE meaning_id=?", (meaning_id,))
    examples = cur.fetchall()

    if request.method == 'POST':
        # Update POS, definition, notes
        pos_id = request.form.get('pos_id')
        definition = request.form.get('definition', '').strip() or None
        notes = request.form.get('notes', '').strip() or None
        cur.execute("UPDATE meanings SET pos_id=?, definition=?, notes=? WHERE id=?", (pos_id, definition, notes, meaning_id))

        # Update translations
        cur.execute("DELETE FROM translations WHERE meaning_id=?", (meaning_id,))
        new_translations = request.form.getlist('translations[]')
        for idx, t in enumerate(new_translations, start=1):
            t = t.strip()
            if t:
                cur.execute("INSERT INTO translations (meaning_id, translation_text, translation_number) VALUES (?, ?, ?)", (meaning_id, t, idx))

        # Update examples
        cur.execute("DELETE FROM examples WHERE meaning_id=?", (meaning_id,))
        new_examples = request.form.getlist('examples[]')
        new_examples_trans = request.form.getlist('examples_trans[]')
        for ex, ex_trans in zip(new_examples, new_examples_trans):
            ex = ex.strip()
            ex_trans = ex_trans.strip() or None
            if ex:
                cur.execute("INSERT INTO examples (meaning_id, example_text, example_translation_text) VALUES (?, ?, ?)", (meaning_id, ex, ex_trans))

        conn.commit()
        conn.close()
        flash("Meaning updated successfully!", "success")
        return redirect(url_for('admin_edit_word', word_id=word_id))

    conn.close()
    return render_template(
        'admin_edit_meaning.html',
        meaning=meaning,
        translations=translations,
        examples=examples,
        pos_list=pos_list,
        meanings_count=meanings_count  # <--- pass this to template
    )




@app.route('/admin/add_meaning/<int:word_id>', methods=['GET', 'POST'])
@admin_required
def admin_add_meaning(word_id):
    conn = sqlite3.connect("finnish.db")
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Fetch word
    cur.execute("SELECT * FROM words WHERE id=?", (word_id,))
    word = cur.fetchone()
    if not word:
        flash("Word not found.", "error")
        conn.close()
        return redirect(url_for('admin_dashboard'))

    # Fetch POS list
    cur.execute("SELECT id, name FROM parts_of_speech ORDER BY name")
    pos_list = cur.fetchall()

    if request.method == 'POST':
        # Determine next meaning_number
        cur.execute("SELECT MAX(meaning_number) AS max_num FROM meanings WHERE word_id=?", (word_id,))
        row = cur.fetchone()
        next_number = (row['max_num'] or 0) + 1

        definition = request.form.get('definition', '').strip() or None
        notes = request.form.get('notes', '').strip() or None
        pos_id = request.form.get('pos_id')  # New POS selection

        # Insert meaning with pos_id
        cur.execute(
            "INSERT INTO meanings (word_id, meaning_number, definition, notes, pos_id) VALUES (?, ?, ?, ?, ?)",
            (word_id, next_number, definition, notes, pos_id)
        )
        conn.commit()

        # Insert translations and examples as before...
        meaning_id = cur.lastrowid
        translations = request.form.getlist('translations[]')
        for idx, t in enumerate(translations, start=1):
            t = t.strip()
            if t:
                cur.execute(
                    "INSERT INTO translations (meaning_id, translation_text, translation_number) VALUES (?, ?, ?)",
                    (meaning_id, t, idx)
                )

        examples = request.form.getlist('examples[]')
        examples_trans = request.form.getlist('examples_trans[]')
        for ex, ex_trans in zip(examples, examples_trans):
            ex = ex.strip()
            ex_trans = ex_trans.strip() or None
            if ex:
                cur.execute(
                    "INSERT INTO examples (meaning_id, example_text, example_translation_text) VALUES (?, ?, ?)",
                    (meaning_id, ex, ex_trans)
                )

        conn.commit()
        conn.close()
        flash("Meaning added successfully!", "success")
        return redirect(url_for('admin_edit_word', word_id=word_id))

    conn.close()
    return render_template('admin_add_meaning.html', word=word, pos_list=pos_list)







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


@app.route("/admin/delete_meaning/<int:meaning_id>", methods=["POST"])
@admin_required
def admin_delete_meaning(meaning_id):
    conn = sqlite3.connect("finnish.db")
    cur = conn.cursor()
    # Find word_id for redirect
    cur.execute("SELECT word_id FROM meanings WHERE id=?", (meaning_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
        flash("Meaning not found.", "error")
        return redirect(url_for("admin_dashboard"))

    word_id = row[0]
    # Delete meaning
    cur.execute("DELETE FROM examples WHERE meaning_id=?", (meaning_id,))
    cur.execute("DELETE FROM translations WHERE meaning_id=?", (meaning_id,))
    cur.execute("DELETE FROM meanings WHERE id=?", (meaning_id,))
    conn.commit()
    conn.close()
    flash("Meaning deleted successfully.", "success")
    return redirect(url_for("admin_edit_word", word_id=word_id))








@app.route("/admin/add_category", methods=["GET", "POST"])
@admin_required
def admin_add_category():
    if request.method == "POST":
        name = request.form["name"].strip()

        parent_id = request.form.get("parent_id") or None

        conn = sqlite3.connect("finnish.db", timeout=5)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        
                # Check for duplicates first
        cur.execute("SELECT id FROM categories WHERE name = ?", (name,))
        if cur.fetchone():
            flash(f"Category '{name}' already exists.", "danger")
            conn.close()
            return redirect(url_for("admin_add_category"))

        # Insert if not exists
        cur.execute("INSERT INTO categories (name, parent_id) VALUES (?, ?)", (name, parent_id))

        conn.commit()
        category_id = cur.lastrowid
        conn.close()

        # Now redirect to edit page (which also handles adding words)
        flash(f"Category '{name}' created successfully. You can now add words.", "success")
        return redirect(url_for("admin_edit_category", category_id=category_id))

    # GET → show creation form with possible parent categories
    conn = sqlite3.connect("finnish.db", timeout=5)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT id, name FROM categories ORDER BY name")
    categories = cur.fetchall()
    conn.close()

    return render_template("admin_add_category.html", categories=categories)





@app.route("/admin/categories/search")
@admin_required
def admin_search_category():
    query = request.args.get("query", "").strip()

    results = []
    if query:
        conn = sqlite3.connect("finnish.db")
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("""
            SELECT id, name
            FROM categories
            WHERE name LIKE ?
            ORDER BY name
        """, (f"%{query}%",))
        results = cur.fetchall()
        conn.close()

    return render_template(
        "admin_search_category.html",
        query=query,
        results=results
    )







@app.route("/admin/categories/<int:category_id>/edit", methods=["GET", "POST"])
@admin_required
def admin_edit_category(category_id):
    conn = sqlite3.connect("finnish.db", timeout=10)  # longer timeout
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Fetch category info
    cur.execute("SELECT * FROM categories WHERE id = ?", (category_id,))
    category = cur.fetchone()
    if not category:
        conn.close()
        flash("Category not found.", "danger")
        return redirect(url_for("admin_dashboard"))

    # Fetch parent options and POS
    cur.execute("SELECT id, name FROM categories WHERE id != ?", (category_id,))
    all_categories = cur.fetchall()
    cur.execute("SELECT id, name FROM parts_of_speech ORDER BY name")
    pos_list = cur.fetchall()

    action = request.form.get("action")
    if action:
        if action == "update_category":
            name = request.form.get("name", "").strip()
            parent_id = request.form.get("parent_id") or None
            # Check duplicate name (excluding current category)
            cur.execute("SELECT id FROM categories WHERE name = ? AND id != ?", (name, category_id))
            if cur.fetchone():
                flash(f"Another category with the name '{name}' already exists.", "danger")
                conn.close()
                return redirect(url_for("admin_edit_category", category_id=category_id))

            # Proceed with update
            cur.execute("UPDATE categories SET name = ?, parent_id = ? WHERE id = ?", (name, parent_id, category_id))

            conn.commit()
            conn.close()
            flash("Category updated successfully.", "success")
            return redirect(url_for("admin_edit_category", category_id=category_id))

        # -----------------------
        # Add new word to category
        # -----------------------
        elif action == "add_new_word":
            word_text = request.form.get("new_word", "").strip()
            if not word_text:
                flash("Word cannot be empty.", "danger")
                conn.close()
                return redirect(url_for("admin_edit_category", category_id=category_id))

            # Check if word already exists in database
            cur.execute("SELECT id FROM words WHERE word = ?", (word_text,))
            if cur.fetchone():
                flash(f"The word '{word_text}' already exists in the database.", "warning")
                conn.close()
                return redirect(url_for("admin_edit_category", category_id=category_id))

            # Insert the new word with a dummy pos_id (can be NULL)
            cur.execute("INSERT INTO words (word) VALUES (?)", (word_text,))
            conn.commit()
            word_id = cur.lastrowid

            # Insert meanings
            meaning_numbers = request.form.getlist("meaning_number[]")
            for m_num in meaning_numbers:
                pos_id = request.form.get(f"pos_id_{m_num}")  # <-- now per meaning
                notes = request.form.get(f"meaning_notes[]")  # same for all meanings if multiple? can adjust
                definition = request.form.get(f"definition_{m_num}", '').strip() or None

                cur.execute(
                    "INSERT INTO meanings (word_id, meaning_number, pos_id, notes, definition) VALUES (?, ?, ?, ?, ?)",
                    (word_id, int(m_num), pos_id, notes, definition)
                )
                conn.commit()
                cur.execute("SELECT id FROM meanings WHERE word_id=? AND meaning_number=?", (word_id, int(m_num)))
                meaning_id = cur.fetchone()["id"]

                # Insert translations
                translations = request.form.getlist(f"translations_{m_num}[]")
                for idx, t in enumerate(translations, 1):
                    t = t.strip()
                    if t:
                        cur.execute(
                            "INSERT INTO translations (meaning_id, translation_text, translation_number) VALUES (?, ?, ?)",
                            (meaning_id, t, idx)
                        )

                # Insert examples
                examples = request.form.getlist(f"examples_{m_num}[]")
                examples_trans = request.form.getlist(f"examples_trans_{m_num}[]")
                for ex, ex_tr in zip(examples, examples_trans):
                    if ex.strip():
                        cur.execute(
                            "INSERT INTO examples (meaning_id, example_text, example_translation_text) VALUES (?, ?, ?)",
                            (meaning_id, ex.strip(), ex_tr.strip() or None)
                        )

            # Assign to category
            cur.execute("INSERT INTO word_categories (word_id, category_id) VALUES (?, ?)", (word_id, category_id))
            conn.commit()
            conn.close()
            flash(f"New word '{word_text}' added and assigned to category.", "success")
            return redirect(url_for("admin_edit_category", category_id=category_id))



        # -----------------------
        # Add existing word to category
        # -----------------------
        elif action == "add_existing":
            existing_word_id = int(request.form["existing_word_id"])
            
            # Check if the word is already in this category
            cur.execute("SELECT 1 FROM word_categories WHERE word_id=? AND category_id=?", (existing_word_id, category_id))
            if cur.fetchone():
                flash("This word is already in the category.", "warning")
                conn.close()
                return redirect(url_for("admin_edit_category", category_id=category_id))

            cur.execute("INSERT INTO word_categories (word_id, category_id) VALUES (?, ?)", (existing_word_id, category_id))
            conn.commit()
            conn.close()
            flash("Existing word added to category.", "success")
            return redirect(url_for("admin_edit_category", category_id=category_id))



    # Fetch category words and search results
    search_query = request.args.get("word_query", "").strip()
    search_results = []
    if search_query:
        cur.execute("SELECT id, word FROM words WHERE word LIKE ? ORDER BY word", (f"{search_query}%",))
        search_results = cur.fetchall()

    cur.execute("""
        SELECT w.id, w.word
        FROM words w
        JOIN word_categories wc ON w.id = wc.word_id
        WHERE wc.category_id = ?
        ORDER BY w.word
    """, (category_id,))
    category_words = cur.fetchall()

    conn.close()
    return render_template(
        "admin_edit_category.html",
        category=category,
        all_categories=all_categories,
        category_words=category_words,
        pos_list=pos_list,
        search_query=search_query,
        search_results=search_results
    )


@app.route("/admin/categories/<int:category_id>/remove_word/<int:word_id>", methods=["POST"])
@admin_required
def admin_remove_word_from_category(category_id, word_id):
    conn = sqlite3.connect("finnish.db")
    cur = conn.cursor()
    
    # Remove word from category
    cur.execute("DELETE FROM word_categories WHERE word_id=? AND category_id=?", (word_id, category_id))
    conn.commit()
    conn.close()
    
    flash("Word removed from category.", "success")
    return redirect(url_for("admin_edit_category", category_id=category_id))



@app.route("/admin/categories/<int:category_id>/delete", methods=["POST"])
@admin_required
def admin_delete_category(category_id):
    conn = sqlite3.connect("finnish.db", timeout=5)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Check if category exists
    cur.execute("SELECT name FROM categories WHERE id = ?", (category_id,))
    category = cur.fetchone()
    if not category:
        conn.close()
        flash("Category not found.", "danger")
        return redirect(url_for("admin_dashboard"))

    # Delete relationships first to avoid foreign key errors
    cur.execute("DELETE FROM word_categories WHERE category_id = ?", (category_id,))
    cur.execute("DELETE FROM categories WHERE id = ?", (category_id,))
    conn.commit()
    conn.close()

    flash(f"Category '{category['name']}' deleted successfully.", "success")
    return redirect(url_for("admin_dashboard"))






@app.route("/admin/categories/<int:category_id>/meanings", methods=["GET", "POST"])
@admin_required
def admin_category_meanings(category_id):
    conn = sqlite3.connect("finnish.db")
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Fetch category info
    cur.execute("SELECT * FROM categories WHERE id = ?", (category_id,))
    category = cur.fetchone()
    if not category:
        conn.close()
        flash("Category not found.", "danger")
        return redirect(url_for("admin_dashboard"))

    if request.method == "POST":
        # Save representative meanings
        for key, meaning_id in request.form.items():
            if key.startswith("rep_meaning_"):
                word_id = int(key.split("_")[-1])
                if meaning_id:
                    cur.execute("""
                        UPDATE word_categories
                        SET meaning_id = ?
                        WHERE word_id = ? AND category_id = ?
                    """, (meaning_id, word_id, category_id))
                else:
                    cur.execute("""
                        UPDATE word_categories
                        SET meaning_id = NULL
                        WHERE word_id = ? AND category_id = ?
                    """, (word_id, category_id))
        conn.commit()
        flash("Representative meanings updated.", "success")

    # Fetch words in the category
    cur.execute("""
        SELECT wc.word_id, w.word, wc.meaning_id
        FROM word_categories wc
        JOIN words w ON wc.word_id = w.id
        WHERE wc.category_id = ?
        ORDER BY wc.sort_order, w.word
    """, (category_id,))
    words = [dict(w) for w in cur.fetchall()]

    # Fetch meanings for each word
    for w in words:
        cur.execute("""
            SELECT m.id, m.meaning_number, p.name AS pos_name,
                   GROUP_CONCAT(t.translation_text, ', ') AS translations
            FROM meanings m
            LEFT JOIN parts_of_speech p ON m.pos_id = p.id
            LEFT JOIN translations t ON t.meaning_id = m.id
            WHERE m.word_id = ?
            GROUP BY m.id
            ORDER BY m.meaning_number
        """, (w['word_id'],))
        w['meanings'] = [dict(m) for m in cur.fetchall()]

        # If a representative meaning is selected, fetch translations
        if w['meaning_id']:
            cur.execute("""
                SELECT GROUP_CONCAT(t.translation_text, ' | ') AS rep_translations
                FROM translations t
                WHERE t.meaning_id = ?
            """, (w['meaning_id'],))
            row = cur.fetchone()
            w['rep_translations'] = row['rep_translations'] if row else None
        else:
            w['rep_translations'] = None

    conn.close()
    return render_template(
        "admin_category_meanings.html",
        category=dict(category),
        words=words
    )




@app.route("/admin/set_main_meaning", methods=["POST"])
@admin_required
def admin_set_main_meaning():
    data = request.get_json()
    word_id = data.get("word_id")
    meaning_id = data.get("meaning_id")

    if not word_id or not meaning_id:
        return jsonify({"status": "error", "message": "Missing data"}), 400

    conn = sqlite3.connect("finnish.db")
    cur = conn.cursor()

    # upsert word_category_meaning table
    cur.execute("""
        INSERT INTO word_category_meaning (word_id, meaning_id)
        VALUES (?, ?)
        ON CONFLICT(word_id) DO UPDATE SET meaning_id=excluded.meaning_id
    """, (word_id, meaning_id))

    conn.commit()
    conn.close()
    return jsonify({"status": "ok"})










@app.route('/', methods=['GET'])
def home():
    query = request.args.get('query', '').strip()
    mode = request.args.get('mode', 'finnish')
    results = []

    if query:
        conn = sqlite3.connect("finnish.db")
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        if mode == 'finnish':
            cur.execute("""
                SELECT word FROM words
                WHERE word LIKE ?
                ORDER BY word
                LIMIT 20
            """, (f"{query}%",))
            results = [row['word'] for row in cur.fetchall()]

        elif mode == 'translation':
            cur.execute("""
                SELECT DISTINCT w.word
                FROM words w
                JOIN meanings m ON m.word_id = w.id
                JOIN translations t ON t.meaning_id = m.id
                WHERE t.translation_text LIKE ?
                ORDER BY w.word
                LIMIT 20
            """, (f"{query}%",))
            results = [row['word'] for row in cur.fetchall()]

        conn.close()

    return render_template('home.html', query=query, results=results, mode=mode)

@app.route('/autocomplete', methods=['GET'])
def autocomplete():
    query = request.args.get('query', '').strip()
    mode = request.args.get('mode', 'finnish')

    if not query:
        return jsonify([])

    conn = sqlite3.connect("finnish.db")
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    if mode == 'finnish':
        cur.execute("SELECT word FROM words WHERE word LIKE ? ORDER BY word LIMIT 10", (f"{query}%",))
        suggestions = [row['word'] for row in cur.fetchall()]
    elif mode == 'translation':
        cur.execute("""
            SELECT DISTINCT w.word
            FROM words w
            JOIN meanings m ON m.word_id = w.id
            JOIN translations t ON t.meaning_id = m.id
            WHERE t.translation_text LIKE ?
            ORDER BY w.word
            LIMIT 10
        """, (f"{query}%",))
        suggestions = [row['word'] for row in cur.fetchall()]
    elif mode == 'category':
        cur.execute("""
            SELECT name FROM categories
            WHERE name LIKE ?
            ORDER BY name
            LIMIT 10
        """, (f"{query}%",))
        suggestions = [row['name'] for row in cur.fetchall()]

    conn.close()
    return jsonify(suggestions)




@app.route('/about')
def about():
    return render_template('about.html', title="About")


@app.route('/word/<word_name>')
def show_word(word_name):
    conn = sqlite3.connect("finnish.db")
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Fetch word (by name)
    cur.execute("SELECT id, word FROM words WHERE word = ?", (word_name,))
    word_row = cur.fetchone()
    if not word_row:
        conn.close()
        return render_template("word.html", meanings_by_pos=None, word_name=None)

    word_id = word_row['id']
    word_name = word_row['word']

    # Fetch meanings + POS + translations + examples
    cur.execute("""
        SELECT 
            m.id, m.meaning_number, m.definition, m.notes,
            m.pos_id, p.name AS pos_name,
            t.translation_text,
            e.example_text, e.example_translation_text
        FROM meanings m
        LEFT JOIN parts_of_speech p ON m.pos_id = p.id
        LEFT JOIN translations t ON t.meaning_id = m.id
        LEFT JOIN examples e ON e.meaning_id = m.id
        WHERE m.word_id = ?
        ORDER BY 
            CASE p.name
                WHEN 'adjective' THEN 1
                WHEN 'noun' THEN 2
                WHEN 'verb' THEN 3
                WHEN 'adverb' THEN 4
                ELSE 5
            END,
            m.meaning_number
    """, (word_id,))

    rows = cur.fetchall()

 # Fetch categories the word belongs to
    cur.execute("""
        SELECT c.name
        FROM categories c
        JOIN word_categories wc ON c.id = wc.category_id
        WHERE wc.word_id = ?
        ORDER BY c.name
    """, (word_id,))
    categories = [row['name'] for row in cur.fetchall()]

    conn.close()

    if not rows:
        return render_template("word.html", meanings_by_pos=None, word_name=word_name, categories=None)

    # Organize meanings by POS
    meanings_by_pos = {}
    for row in rows:
        pos_name = row['pos_name'] or 'other'
        if pos_name not in meanings_by_pos:
            meanings_by_pos[pos_name] = []

        meaning = next((m for m in meanings_by_pos[pos_name] if m['id'] == row['id']), None)
        if not meaning:
            meaning = {
                'id': row['id'],
                'meaning_number': row['meaning_number'],
                'definition': row['definition'],
                'notes': row['notes'],
                'translations': [],
                'examples': []
            }
            meanings_by_pos[pos_name].append(meaning)

        if row['translation_text'] and row['translation_text'] not in meaning['translations']:
            meaning['translations'].append(row['translation_text'])

        if row['example_text']:
            meaning['examples'].append({
                'text': row['example_text'],
                'translation': row['example_translation_text']
            })

    # ---- THROUGH-NUMBERING ----
    counter = 1
    for pos in meanings_by_pos.values():
        for meaning in pos:
            meaning['display_number'] = counter
            counter += 1
   

    return render_template("word.html", word_name=word_name, meanings_by_pos=meanings_by_pos, categories=categories)




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

    # Load all categories into memory
    cur.execute("SELECT id, name, parent_id FROM categories ORDER BY name")
    all_rows = cur.fetchall()
    categories_dict = {}
    for row in all_rows:
        parent = row['parent_id']
        categories_dict.setdefault(parent, []).append(row)

    # Load current category
    cur.execute("SELECT id, name, parent_id FROM categories WHERE name = ?", (category_name,))
    category = cur.fetchone()
    if not category:
        return f"Category '{category_name}' not found."
    category_id = category["id"]

    # Subcategories
    subcategories = categories_dict.get(category_id, [])

    # Fetch all words in the category including selected meaning_id
    cur.execute("""
        SELECT w.id AS word_id, w.word, wc.meaning_id
        FROM words w
        JOIN word_categories wc ON w.id = wc.word_id
        WHERE wc.category_id = ?
        ORDER BY wc.sort_order, w.word
    """, (category_id,))
    words = cur.fetchall()

    words_with_translations = []

    for w in words:
        meaning_id = w["meaning_id"]

        if meaning_id:
            # Use representative meaning
            cur.execute("""
                SELECT t.translation_text
                FROM translations t
                WHERE t.meaning_id = ?
                ORDER BY t.translation_number
                LIMIT 3
            """, (meaning_id,))
        else:
            # Fallback: use first meaning of the word
            cur.execute("""
                SELECT t.translation_text
                FROM meanings m
                JOIN translations t ON t.meaning_id = m.id
                WHERE m.word_id = ?
                ORDER BY m.meaning_number, t.translation_number
                LIMIT 3
            """, (w["word_id"],))

        translations = [row["translation_text"] for row in cur.fetchall()]

        words_with_translations.append({
            "word": w["word"],
            "translations": translations
        })

    # Parent breadcrumb
    parent = None
    if category["parent_id"]:
        for r in all_rows:
            if r["id"] == category["parent_id"]:
                parent = r
                break

    conn.close()

    return render_template(
        "category.html",
        category=category,
        subcategories=subcategories,
        words=words_with_translations,
        parent=parent,
        categories=categories_dict
    )




@app.route("/admin/words/<int:word_id>/relations", methods=["GET", "POST"])
@admin_required
def admin_word_relations(word_id):
    conn = sqlite3.connect("finnish.db")
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Fetch the word
    cur.execute("SELECT * FROM words WHERE id = ?", (word_id,))
    word = cur.fetchone()
    if not word:
        flash("Word not found.", "danger")
        conn.close()
        return redirect(url_for("admin_dashboard"))

    # Fetch relation types for dropdown
    cur.execute("SELECT * FROM relation_types WHERE applies_to='word' ORDER BY name")
    relation_types = cur.fetchall()

    # Handle POST
    if request.method == "POST":
        action = request.form.get("action")
        related_word_id = int(request.form.get("related_word_id"))
        relation_type_id = int(request.form.get("relation_type_id"))

        # Insert or remove relation
        if action == "add_relation":
            # Check if bidirectional
            cur.execute("SELECT bidirectional FROM relation_types WHERE id=?", (relation_type_id,))
            bidirectional = cur.fetchone()["bidirectional"]

            # Insert main relation
            cur.execute("""
                INSERT OR IGNORE INTO word_relations (word1_id, word2_id, relation_type_id)
                VALUES (?, ?, ?)
            """, (word_id, related_word_id, relation_type_id))
            # Insert reverse if bidirectional
            if bidirectional:
                cur.execute("""
                    INSERT OR IGNORE INTO word_relations (word1_id, word2_id, relation_type_id)
                    VALUES (?, ?, ?)
                """, (related_word_id, word_id, relation_type_id))
            flash("Relation added successfully!", "success")
        elif action == "remove_relation":
            cur.execute("""
                DELETE FROM word_relations WHERE word1_id=? AND word2_id=? AND relation_type_id=?
            """, (word_id, related_word_id, relation_type_id))
            # Remove reverse if bidirectional
            cur.execute("SELECT bidirectional FROM relation_types WHERE id=?", (relation_type_id,))
            bidirectional = cur.fetchone()["bidirectional"]
            if bidirectional:
                cur.execute("""
                    DELETE FROM word_relations WHERE word1_id=? AND word2_id=? AND relation_type_id=?
                """, (related_word_id, word_id, relation_type_id))
            flash("Relation removed successfully!", "success")

        conn.commit()
        return redirect(url_for("admin_word_relations", word_id=word_id))

    # Fetch existing relations for display
    cur.execute("""
        SELECT wr.id, w2.id AS word2_id, w2.word, rt.name AS relation_name, rt.id AS relation_type_id
        FROM word_relations wr
        JOIN words w2 ON wr.word2_id = w2.id
        JOIN relation_types rt ON wr.relation_type_id = rt.id
        WHERE wr.word1_id=?
        ORDER BY rt.name, w2.word
    """, (word_id,))
    relations = cur.fetchall()

    # Fetch all other words for dropdown
    cur.execute("SELECT id, word FROM words WHERE id != ?", (word_id,))
    all_words = cur.fetchall()

    conn.close()
    return render_template(
        "admin_word_relations.html",
        word=word,
        relations=relations,
        all_words=all_words,
        relation_types=relation_types
    )






if __name__ == '__main__':
    app.run(debug=True)
