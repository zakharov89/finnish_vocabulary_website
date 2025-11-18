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
        return redirect(url_for('admin_edit_word', word_id=word_id))

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
        """, (f"{query}%",))
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

    # Fetch category
    cur.execute("SELECT * FROM categories WHERE id = ?", (category_id,))
    category = cur.fetchone()
    if not category:
        conn.close()
        flash("Category not found.", "danger")
        return redirect(url_for("admin_dashboard"))

    if request.method == "POST":
   

        # --- SAVE REPRESENTATIVE MEANINGS ---
        for key, value in request.form.items():
            if key.startswith("rep_meaning_"):
                word_id = int(key.replace("rep_meaning_", ""))
                meaning_id = int(value) if value else None

                cur.execute("""
                    UPDATE word_categories
                    SET meaning_id = ?
                    WHERE word_id = ? AND category_id = ?
                """, (meaning_id, word_id, category_id))

                # Update sort order
        for key, value in request.form.items():
            if key.startswith("sort_order_"):
                word_id = int(key.split("_")[-1])
                sort_order = int(value)
                cur.execute("""
                    UPDATE word_categories
                    SET sort_order = ?
                    WHERE word_id = ? AND category_id = ?
                """, (sort_order, word_id, category_id))

        conn.commit()
        flash("Meaning choices and order saved.", "success")
        conn.close()
        return redirect(url_for("admin_category_meanings", category_id=category_id))

    # ------- GET MODE -------
    # Fetch words in category including sort_order
    cur.execute("""
        SELECT wc.word_id,
               w.word,
               wc.meaning_id,
               wc.sort_order
        FROM word_categories wc
        JOIN words w ON wc.word_id = w.id
        WHERE wc.category_id = ?
        ORDER BY wc.sort_order, w.word
    """, (category_id,))
    words = [dict(w) for w in cur.fetchall()]

    # Fetch meanings for each word
    for w in words:
        # All meanings of the word
        cur.execute("""
            SELECT m.id,
                   m.meaning_number,
                   p.name AS pos_name,
                   GROUP_CONCAT(t.translation_text, ', ') AS translations
            FROM meanings m
            LEFT JOIN parts_of_speech p ON m.pos_id = p.id
            LEFT JOIN translations t ON t.meaning_id = m.id
            WHERE m.word_id = ?
            GROUP BY m.id
            ORDER BY m.meaning_number
        """, (w['word_id'],))
        w['meanings'] = [dict(m) for m in cur.fetchall()]

        # Representative meaning translations
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


# ----- List all words -----
@app.route("/admin/words")
@admin_required
def admin_list_words():
    page = int(request.args.get("page", 1))
    per_page = 50  # number of words per page
    offset = (page - 1) * per_page

    conn = sqlite3.connect("finnish.db")
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM words")
    total = cur.fetchone()[0]

    cur.execute(
        "SELECT id, word FROM words ORDER BY word COLLATE NOCASE ASC  LIMIT ? OFFSET ?",
        (per_page, offset)
    )
    words = cur.fetchall()
    conn.close()

    total_pages = (total + per_page - 1) // per_page

    return render_template(
        "admin_list_words.html",
        words=words,
        page=page,
        total_pages=total_pages
    )



# ----- List all categories -----
@app.route("/admin/categories")
@admin_required
def admin_list_categories():
    page = int(request.args.get("page", 1))
    per_page = 50
    offset = (page - 1) * per_page

    conn = sqlite3.connect("finnish.db")
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM categories")
    total = cur.fetchone()[0]

    cur.execute(
        "SELECT id, name FROM categories ORDER BY name COLLATE NOCASE ASC LIMIT ? OFFSET ?",
        (per_page, offset)
    )
    categories = cur.fetchall()
    conn.close()

    total_pages = (total + per_page - 1) // per_page

    return render_template(
        "admin_list_categories.html",
        categories=categories,
        page=page,
        total_pages=total_pages
    )









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

    # ---- Fetch the word ----
    cur.execute("SELECT id, word FROM words WHERE word = ?", (word_name,))
    row_word = cur.fetchone()
    if not row_word:
        conn.close()
        return render_template("word.html", meanings_by_pos=None, word_name=None)

    word_id = row_word['id']
    word_name = row_word['word']

    # ---- Fetch meanings + POS + translations + examples ----
    cur.execute("""
        SELECT 
            m.id AS meaning_id,
            m.meaning_number,
            m.definition,
            m.notes,
            p.name AS pos_name,
            t.translation_text,
            e.example_text,
            e.example_translation_text
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

    # ---- Fetch categories ----
    cur.execute("""
        SELECT c.name
        FROM categories c
        JOIN word_categories wc ON wc.category_id = c.id
        WHERE wc.word_id = ?
        ORDER BY c.name
    """, (word_id,))
    categories = [r["name"] for r in cur.fetchall()]

    # If no meanings at all
    if not rows:
        conn.close()
        return render_template(
            "word.html", 
            meanings_by_pos=None, 
            word_name=word_name, 
            categories=categories
        )

    # ---- Organize meanings ----
    meanings_by_pos = {}
    for r in rows:
        pos = r["pos_name"] or "other"
        meanings_by_pos.setdefault(pos, [])

        meaning = next((m for m in meanings_by_pos[pos] if m["id"] == r["meaning_id"]), None)
        if meaning is None:
            meaning = {
                "id": r["meaning_id"],
                "meaning_number": r["meaning_number"],
                "definition": r["definition"],
                "notes": r["notes"],
                "translations": [],
                "examples": []
            }
            meanings_by_pos[pos].append(meaning)

        if r["translation_text"] and r["translation_text"] not in meaning["translations"]:
            meaning["translations"].append(r["translation_text"])

        if r["example_text"]:
            meaning["examples"].append({
                "text": r["example_text"],
                "translation": r["example_translation_text"]
            })

    # ---- Through-numbering ----
    counter = 1
    for pos_block in meanings_by_pos.values():
        for m in pos_block:
            m["display_number"] = counter
            counter += 1

    # ============================================================
    # WORD RELATIONS (only outgoing)
    # ============================================================

    cur.execute("""
        SELECT 
            wr.id,
            rt.name AS relation_type,
            w2.word AS target_word
        FROM word_relations wr
        JOIN relation_types rt ON wr.relation_type_id = rt.id
        JOIN words w2 ON wr.word2_id = w2.id
        WHERE wr.word1_id = ?
        ORDER BY rt.name, w2.word
    """, (word_id,))
    word_rel_rows = cur.fetchall()

    word_relations = {}
    for r in word_rel_rows:
        rt = r["relation_type"]
        word_relations.setdefault(rt, []).append({
            "target_word": r["target_word"]
        })



    # ============================================================
    # MEANING RELATIONS (only outgoing)
    # ============================================================
    # Get all meaning IDs for this word
    meaning_ids = [m["id"] for plist in meanings_by_pos.values() for m in plist]

   # ============================================================
    # MEANING RELATIONS (only outgoing)
    # ============================================================
    cur.execute("""
        SELECT 
            mr.id,
            mr.meaning1_id,
            mr.meaning2_id,
            rt.name AS relation_type,
            w2.word AS target_word,
            m2.meaning_number AS target_meaning_number
        FROM meaning_relations mr
        JOIN relation_types rt ON mr.relation_type_id = rt.id
        JOIN meanings m2 ON mr.meaning2_id = m2.id
        JOIN words w2 ON m2.word_id = w2.id
        WHERE mr.meaning1_id IN ({})
        ORDER BY rt.name, w2.word, m2.meaning_number
    """.format(",".join("?" * len(meaning_ids))), meaning_ids)

    meaning_rel_rows = cur.fetchall()

    meaning_relations = {}

    for r in meaning_rel_rows:
        m1 = r["meaning1_id"]
        rt = r["relation_type"]

        meaning_relations.setdefault(m1, {})
        meaning_relations[m1].setdefault(rt, [])

        meaning_relations[m1][rt].append({
            "target_word": r["target_word"],
            "target_number": r["target_meaning_number"]
        })


    conn.close()

    return render_template(
        "word.html",
        word_name=word_name,
        meanings_by_pos=meanings_by_pos,
        categories=categories,
        word_relations=word_relations,
        meaning_relations=meaning_relations
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










@app.route("/admin/relation-types")
@admin_required
def admin_relation_types():
    conn = sqlite3.connect("finnish.db")
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM relation_types ORDER BY name")
    relation_types = cur.fetchall()
    conn.close()
    return render_template("admin_relation_types.html", relation_types=relation_types)


@app.post("/admin/relation-types/add")
@admin_required
def admin_add_relation_type():
    name = request.form["name"].strip()
    applies_to = request.form["applies_to"]
    bidirectional = 1 if "bidirectional" in request.form else 0
    conn = sqlite3.connect("finnish.db")
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO relation_types (name, applies_to, bidirectional) VALUES (?, ?, ?)",
            (name, applies_to, bidirectional)
        )
        conn.commit()
        flash("Relation type added.", "success")
    except sqlite3.IntegrityError:
        flash("Relation type already exists.", "danger")
    conn.close()
    return redirect(url_for("admin_relation_types"))


@app.post("/admin/relation-types/<int:type_id>/delete")
@admin_required
def admin_delete_relation_type(type_id):
    conn = sqlite3.connect("finnish.db")
    cur = conn.cursor()
    # Check if type is used
    cur.execute("SELECT COUNT(*) FROM word_relations WHERE relation_type_id = ?", (type_id,))
    if cur.fetchone()[0] > 0:
        flash("Cannot delete: used in word relations.", "danger")
        return redirect(url_for("admin_relation_types"))
    cur.execute("SELECT COUNT(*) FROM meaning_relations WHERE relation_type_id = ?", (type_id,))
    if cur.fetchone()[0] > 0:
        flash("Cannot delete: used in meaning relations.", "danger")
        return redirect(url_for("admin_relation_types"))
    cur.execute("DELETE FROM relation_types WHERE id = ?", (type_id,))
    conn.commit()
    conn.close()
    flash("Relation type deleted.", "success")
    return redirect(url_for("admin_relation_types"))


@app.route("/admin/words/<word_name>/relations")
@admin_required
def admin_word_relations(word_name):
    conn = sqlite3.connect("finnish.db")
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Fetch word info
    cur.execute("SELECT * FROM words WHERE word = ?", (word_name,))
    word = cur.fetchone()
    if not word:
        conn.close()
        flash(f"Word '{word_name}' not found.", "danger")
        return redirect(url_for("admin_dashboard"))

    word_id = word["id"]

    # Fetch word relations for this word
    cur.execute("""
        SELECT wr.id, w1.word AS word1, w2.word AS word2, rt.name AS type
        FROM word_relations wr
        JOIN words w1 ON wr.word1_id = w1.id
        JOIN words w2 ON wr.word2_id = w2.id
        JOIN relation_types rt ON wr.relation_type_id = rt.id
        WHERE w1.id = ? OR w2.id = ?
        ORDER BY rt.name, w1.word, w2.word
    """, (word_id, word_id))
    word_relations = cur.fetchall()

    # Fetch meaning relations for this word
    cur.execute("""
        SELECT mr.id,
               m1.meaning_number AS mnum1,
               m2.meaning_number AS mnum2,
               w2.word AS other_word,
               rt.name AS type
        FROM meaning_relations mr
        JOIN meanings m1 ON mr.meaning1_id = m1.id
        JOIN meanings m2 ON mr.meaning2_id = m2.id
        JOIN words w2 ON (m2.word_id = w2.id)
        JOIN relation_types rt ON mr.relation_type_id = rt.id
        WHERE m1.word_id = ? OR m2.word_id = ?
        ORDER BY rt.name, mnum1
    """, (word_id, word_id))
    meaning_relations = cur.fetchall()

    conn.close()
    return render_template(
        "admin_word_relations.html",
        word=word,
        word_relations=word_relations,
        meaning_relations=meaning_relations
    )



@app.post("/admin/word-relations/add")
@admin_required
def admin_add_word_relation():
    word1 = request.form["word1"].strip()
    word2 = request.form["word2"].strip()
    reltype = int(request.form["relation_type_id"])

    conn = sqlite3.connect("finnish.db")
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Resolve word IDs
    cur.execute("SELECT id FROM words WHERE word = ?", (word1,))
    w1 = cur.fetchone()
    cur.execute("SELECT id FROM words WHERE word = ?", (word2,))
    w2 = cur.fetchone()

    if not w1 or not w2:
        flash("One of the words does not exist.", "danger")
        return redirect(url_for("admin_relations_search"))

    # Check if relation already exists
    cur.execute("""
        SELECT id FROM word_relations
        WHERE word1_id = ? AND word2_id = ? AND relation_type_id = ?
    """, (w1["id"], w2["id"], reltype))
    if cur.fetchone():
        flash("This word relation already exists.", "warning")
        conn.close()
        return redirect(url_for("admin_relations_search"))

    # Insert relation
    cur.execute("""
        INSERT INTO word_relations (word1_id, word2_id, relation_type_id)
        VALUES (?, ?, ?)
    """, (w1["id"], w2["id"], reltype))

    # If bidirectional, also insert the opposite
    cur.execute("SELECT bidirectional FROM relation_types WHERE id = ?", (reltype,))
    if cur.fetchone()["bidirectional"]:
        # Check reverse relation exists first
        cur.execute("""
            SELECT id FROM word_relations
            WHERE word1_id = ? AND word2_id = ? AND relation_type_id = ?
        """, (w2["id"], w1["id"], reltype))
        if not cur.fetchone():
            cur.execute("""
                INSERT INTO word_relations (word1_id, word2_id, relation_type_id)
                VALUES (?, ?, ?)
            """, (w2["id"], w1["id"], reltype))

    conn.commit()
    conn.close()
    flash("Word relation added.", "success")
    return redirect(url_for("admin_relations_search"))



@app.post("/admin/word-relations/<int:rel_id>/delete")
@admin_required
def admin_delete_word_relation(rel_id):
    conn = sqlite3.connect("finnish.db")
    cur = conn.cursor()
    cur.execute("DELETE FROM word_relations WHERE id = ?", (rel_id,))
    conn.commit()
    conn.close()
    flash("Word relation deleted.", "success")
    return redirect(url_for("admin_relations_search"))


@app.post("/admin/add_meaning_relation")
@admin_required
def admin_add_meaning_relation():
    m1_id = request.form.get("meaning1")
    m2_id = request.form.get("meaning2")
    reltype = request.form.get("relation_type_id")

    if not m1_id or not m2_id:
        flash("Please select both meanings.", "danger")
        return redirect(url_for("admin_relations_search"))

    conn = sqlite3.connect("finnish.db")
    cur = conn.cursor()

    # Verify these meaning IDs exist
    cur.execute("SELECT id FROM meanings WHERE id = ?", (m1_id,))
    if not cur.fetchone():
        flash("Invalid meaning 1.", "danger")
        conn.close()
        return redirect(url_for("admin_relations_search"))

    cur.execute("SELECT id FROM meanings WHERE id = ?", (m2_id,))
    if not cur.fetchone():
        flash("Invalid meaning 2.", "danger")
        conn.close()
        return redirect(url_for("admin_relations_search"))

    # Check if the relation already exists
    cur.execute("""
        SELECT id FROM meaning_relations
        WHERE meaning1_id = ? AND meaning2_id = ? AND relation_type_id = ?
    """, (m1_id, m2_id, reltype))
    if cur.fetchone():
        flash("This meaning relation already exists.", "warning")
        conn.close()
        return redirect(url_for("admin_relations_search"))

    # Insert the meaning relation
    cur.execute("""
        INSERT INTO meaning_relations (meaning1_id, meaning2_id, relation_type_id)
        VALUES (?, ?, ?)
    """, (m1_id, m2_id, reltype))

    conn.commit()
    conn.close()
    flash("Meaning relation added.", "success")
    return redirect(url_for("admin_relations_search"))




@app.post("/admin/meaning-relations/<int:rel_id>/delete")
@admin_required
def admin_delete_meaning_relation(rel_id):
    conn = sqlite3.connect("finnish.db")
    cur = conn.cursor()
    cur.execute("DELETE FROM meaning_relations WHERE id = ?", (rel_id,))
    conn.commit()
    conn.close()
    flash("Meaning relation deleted.", "success")
    return redirect(url_for("admin_relations_search"))




@app.route("/admin/relations/search", methods=["GET", "POST"])
@admin_required
def admin_relations_search():
    query = ""
    word_relations = []
    meaning_relations = []

    # Fetch relation types for the selects
    conn = sqlite3.connect("finnish.db")
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM relation_types ORDER BY name")
    relation_types = cur.fetchall()

    if request.method == "POST":
        query = request.form.get("query", "").strip()
    else:
        query = request.args.get("q", "").strip()

    if query:
        # Word relations
        cur.execute("""
            SELECT wr.id, w1.word AS word1, w2.word AS word2, rt.name AS relation_type
            FROM word_relations wr
            JOIN words w1 ON wr.word1_id = w1.id
            JOIN words w2 ON wr.word2_id = w2.id
            JOIN relation_types rt ON wr.relation_type_id = rt.id
            WHERE w1.word LIKE ? OR w2.word LIKE ?
            ORDER BY w1.word, w2.word
            LIMIT 200
        """, (f"{query}%", f"{query}%"))
        word_relations = cur.fetchall()

        # Meaning relations
        cur.execute("""
            SELECT mr.id, m1.id AS meaning1_id, m2.id AS meaning2_id,
                   w1.word AS word1, m1.meaning_number AS mnum1,
                   w2.word AS word2, m2.meaning_number AS mnum2,
                   rt.name AS relation_type
            FROM meaning_relations mr
            JOIN meanings m1 ON mr.meaning1_id = m1.id
            JOIN meanings m2 ON mr.meaning2_id = m2.id
            JOIN words w1 ON m1.word_id = w1.id
            JOIN words w2 ON m2.word_id = w2.id
            JOIN relation_types rt ON mr.relation_type_id = rt.id
            WHERE w1.word LIKE ? OR w2.word LIKE ?
            ORDER BY w1.word, m1.meaning_number
            LIMIT 200
        """, (f"{query}%", f"{query}%"))
        meaning_relations = cur.fetchall()

    conn.close()

    return render_template(
        "admin_relations_search.html",
        query=query,
        word_relations=word_relations,
        meaning_relations=meaning_relations,
        relation_types=relation_types  # pass them to the template
    )


@app.route("/word_meanings")
def word_meanings():
    word = request.args.get("word", "").strip()

    if not word:
        return jsonify([])

    conn = sqlite3.connect("finnish.db")
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Get the word ID
    cur.execute("SELECT id FROM words WHERE word = ?", (word,))
    w = cur.fetchone()

    if not w:
        conn.close()
        return jsonify([])

    # Get meanings for this word
    cur.execute("""
        SELECT id, meaning_number, notes
        FROM meanings
        WHERE word_id = ?
        ORDER BY meaning_number
    """, (w["id"],))
    meanings = cur.fetchall()

    results = []

    for m in meanings:
        # Fetch translations for each meaning
        cur.execute("""
            SELECT translation_text
            FROM translations
            WHERE meaning_id = ?
            ORDER BY translation_number
        """, (m["id"],))
        translations = [row["translation_text"] for row in cur.fetchall()]

        results.append({
            "id": m["id"],
            "meaning_number": m["meaning_number"],
            "notes": m["notes"],
            "translations": translations
        })

    conn.close()
    return jsonify(results)


@app.route("/admin/relations/words")
@admin_required
def admin_word_relations_list():
    conn = sqlite3.connect("finnish.db")
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("""
        SELECT wr.id, w1.word AS word1, w2.word AS word2, rt.name AS relation_type
        FROM word_relations wr
        JOIN words w1 ON wr.word1_id = w1.id
        JOIN words w2 ON wr.word2_id = w2.id
        JOIN relation_types rt ON wr.relation_type_id = rt.id
        ORDER BY rt.name, w1.word, w2.word
    """)
    word_relations = cur.fetchall()
    conn.close()

    return render_template("admin_word_relations_list.html", word_relations=word_relations)


@app.route("/admin/relations/meanings")
@admin_required
def admin_meaning_relations_list():
    conn = sqlite3.connect("finnish.db")
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("""
        SELECT mr.id, m1.id AS meaning1_id, m2.id AS meaning2_id,
               w1.word AS word1, m1.meaning_number AS mnum1,
               w2.word AS word2, m2.meaning_number AS mnum2,
               rt.name AS relation_type
        FROM meaning_relations mr
        JOIN meanings m1 ON mr.meaning1_id = m1.id
        JOIN meanings m2 ON mr.meaning2_id = m2.id
        JOIN words w1 ON m1.word_id = w1.id
        JOIN words w2 ON m2.word_id = w2.id
        JOIN relation_types rt ON mr.relation_type_id = rt.id
        ORDER BY rt.name, w1.word, mnum1
    """)
    meaning_relations = cur.fetchall()
    conn.close()

    return render_template("admin_meaning_relations_list.html", meaning_relations=meaning_relations)



if __name__ == '__main__':
    app.run(debug=True)
