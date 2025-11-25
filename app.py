from flask import Flask, session, redirect, url_for, request, render_template, flash, jsonify
import sqlite3
import os
from dotenv import load_dotenv
from functools import lru_cache, wraps


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

@app.route('/home')
def home():
    return render_template('home.html', title="Home")

@app.route('/')
def root():
    return redirect(url_for('home'))

@app.route('/levels', methods=['GET', 'POST'])
def levels():
    # Choosing levels

    conn = sqlite3.connect("finnish.db")
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Load levels dynamically
    cur.execute("SELECT id, name FROM levels ORDER BY id")
    levels = cur.fetchall()

    # If user submitted form
    if request.method == "POST":
        selected = request.form.getlist("levels")  # list of strings
        selected = [int(x) for x in selected]      # convert to ints

        # save to session
        session["selected_levels"] = selected

        flash("Level preferences updated!", "success")
        return redirect(url_for("levels"))

    # Pre-fill form with selected levels
    selected_levels = session.get("selected_levels", [])

    conn.close()

    return render_template("levels.html", levels=levels, selected_levels=selected_levels)

@app.route('/set_levels', methods=['POST'])
def set_levels():
    data = request.get_json()
    # convert to ints, default empty list if none
    selected = [int(lvl) for lvl in data.get("levels", [])]
    session["selected_levels"] = selected
    return jsonify(success=True)

@app.route('/about')
def about():
    return render_template('about.html', title="About")

@app.route('/search', methods=['GET'])
def search():

    query = request.args.get('query', '').strip()
    mode = request.args.get('mode', 'finnish')

    results = []

    if query:
        conn = sqlite3.connect("finnish.db")
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        # ---------- FINNISH MODE ----------
        if mode == 'finnish':
            cur.execute("""
                SELECT word
                FROM words
                WHERE word LIKE ?
                ORDER BY word
                LIMIT 20
            """, (f"{query}%",))
            results = cur.fetchall()

        # ---------- TRANSLATION MODE ----------
        elif mode == 'translation':
            cur.execute("""
                SELECT DISTINCT w.word, t.translation_text
                FROM words w
                JOIN meanings m ON m.word_id = w.id
                JOIN translations t ON t.meaning_id = m.id
                WHERE t.translation_text LIKE ?
                ORDER BY t.translation_text   -- order by translation
                LIMIT 20
            """, (f"{query}%",))
            results = cur.fetchall()

        # ---------- CATEGORY MODE ----------
        elif mode == 'category':
            cur.execute("""
                SELECT name
                FROM categories
                WHERE name LIKE ?
                ORDER BY name
                LIMIT 20
            """, (f"{query}%",))
            results = cur.fetchall()

        conn.close()

    return render_template(
        'search.html',
        query=query,
        results=results,
        mode=mode
    )

@app.route("/api/search_suggest")
def search_suggest():
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify({"results": []})

    conn = sqlite3.connect("finnish.db")
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    like = q + "%"

    # 1) Words: search Finnish word and (optionally) translations
    cur.execute("""
        SELECT id, word
        FROM words
        WHERE word LIKE ?
        ORDER BY word COLLATE NOCASE
        LIMIT 10
    """, (like,))
    word_rows = cur.fetchall()

    # 2) Categories: search category names
    cur.execute("""
        SELECT id, name
        FROM categories
        WHERE name LIKE ?
        ORDER BY name COLLATE NOCASE
        LIMIT 10
    """, (like,))
    cat_rows = cur.fetchall()

    conn.close()

    results = []

    for w in word_rows:
        results.append({
            "type": "word",
            "label": w["word"],
            "url": url_for("show_word", word_name=w["word"])
        })

    for c in cat_rows:
        results.append({
            "type": "category",
            "label": c["name"],
            "url": url_for("show_category", category_name=c["name"])
        })

    return jsonify({"results": results})

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
        cur.execute("""
            SELECT word
            FROM words
            WHERE word LIKE ?
            ORDER BY word
            LIMIT 10
        """, (f"{query}%",))
        # plain strings
        suggestions = [row['word'] for row in cur.fetchall()]

    elif mode == 'translation':
        cur.execute("""
            SELECT DISTINCT w.word, t.translation_text
            FROM words w
            JOIN meanings m ON m.word_id = w.id
            JOIN translations t ON t.meaning_id = m.id
            WHERE t.translation_text LIKE ?
            ORDER BY t.translation_text     -- order by translation here too
            LIMIT 10
        """, (f"{query}%",))
        # objects with both word + translation
        suggestions = [
            {
                "word": row["word"],
                "translation": row["translation_text"]
            }
            for row in cur.fetchall()
        ]

    elif mode == 'category':
        cur.execute("""
            SELECT name
            FROM categories
            WHERE name LIKE ?
            ORDER BY name
            LIMIT 10
        """, (f"{query}%",))
        # plain strings
        suggestions = [row['name'] for row in cur.fetchall()]

    conn.close()
    return jsonify(suggestions)

@app.route('/word/<word_name>')
def show_word(word_name):
    conn = sqlite3.connect("finnish.db")
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # ---- Fetch the word ----
    cur.execute("""
        SELECT w.id, w.word, w.level, l.name AS level_name
        FROM words w
        LEFT JOIN levels l ON w.level = l.id
        WHERE w.word = ?
    """, (word_name,))
    row_word = cur.fetchone()

    if not row_word:
        conn.close()
        return render_template("word.html", meanings_by_pos=None, word_name=None)

    word_id = row_word['id']
    word_name = row_word['word']
    word_level_id = row_word['level']
    word_level_name = row_word["level_name"]

    # ---- Fetch meanings + POS + translations + examples ----
    cur.execute("""
        SELECT 
            m.id   AS meaning_id,
            m.meaning_number,
            m.definition,
            m.notes,
            p.name AS pos_name,
            t.translation_text,
            e.id   AS example_id,
            e.example_text,
            e.example_translation_text
        FROM meanings m
        LEFT JOIN parts_of_speech p ON m.pos_id = p.id
        LEFT JOIN translations t    ON t.meaning_id = m.id
        LEFT JOIN examples e        ON e.meaning_id = m.id
        WHERE m.word_id = ?
        ORDER BY p.name ASC, m.meaning_number ASC
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

        meaning = next(
            (m for m in meanings_by_pos[pos] if m["id"] == r["meaning_id"]),
            None
        )
        if meaning is None:
            meaning = {
                "id": r["meaning_id"],
                "meaning_number": r["meaning_number"],
                "definition": r["definition"],
                "notes": r["notes"],
                "translations": [],
                "examples": [],
                "seen_example_ids": set(),  # for de-duplication
            }
            meanings_by_pos[pos].append(meaning)

        # translations
        if r["translation_text"] and r["translation_text"] not in meaning["translations"]:
            meaning["translations"].append(r["translation_text"])

        # examples (avoid duplicates caused by JOIN)
        if r["example_text"]:
            ex_id = r["example_id"]
            if ex_id not in meaning["seen_example_ids"]:
                meaning["examples"].append({
                    "text": r["example_text"],
                    "translation": r["example_translation_text"]
                })
                meaning["seen_example_ids"].add(ex_id)

    # remove helper set before passing to template
    for pos_block in meanings_by_pos.values():
        for m in pos_block:
            m.pop("seen_example_ids", None)

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
        JOIN words w2          ON wr.word2_id = w2.id
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
    meaning_ids = [m["id"] for plist in meanings_by_pos.values() for m in plist]

    if meaning_ids:
        cur.execute("""
            SELECT 
                mr.id,
                mr.meaning1_id,
                mr.meaning2_id,
                rt.name AS relation_type,
                w2.word AS target_word,
                m2.meaning_number AS target_meaning_number,
                t2.translation_text AS target_translation
            FROM meaning_relations mr
            JOIN relation_types rt ON mr.relation_type_id = rt.id
            JOIN meanings m2       ON mr.meaning2_id = m2.id
            JOIN words   w2        ON m2.word_id = w2.id
            LEFT JOIN translations t2 ON t2.meaning_id = m2.id
            WHERE mr.meaning1_id IN ({})
            ORDER BY rt.name, w2.word, m2.meaning_number, t2.translation_number
        """.format(",".join("?" * len(meaning_ids))), meaning_ids)

        meaning_rel_rows = cur.fetchall()
    else:
        meaning_rel_rows = []

    meaning_relations = {}
    for r in meaning_rel_rows:
        m1 = r["meaning1_id"]
        rt = r["relation_type"]
        target_word = r["target_word"]
        target_num  = r["target_meaning_number"]
        target_tr   = r["target_translation"]

        # ensure structure: meaning_relations[meaning1_id][relation_type] = [entries...]
        meaning_relations.setdefault(m1, {})
        group = meaning_relations[m1].setdefault(rt, [])

        # find or create entry for (target_word, target_num)
        entry = None
        for e in group:
            if e["target_word"] == target_word and e["target_number"] == target_num:
                entry = e
                break

        if entry is None:
            entry = {
                "target_word": target_word,
                "target_number": target_num,
                "translations": []
            }
            group.append(entry)

        # add translation if present and not duplicate
        if target_tr and target_tr not in entry["translations"]:
            entry["translations"].append(target_tr)


    conn.close()

    return render_template(
        "word.html",
        word_name=word_name,
        meanings_by_pos=meanings_by_pos,
        categories=categories,
        word_relations=word_relations,
        meaning_relations=meaning_relations,
        word_level_id=word_level_id,
        word_level_name=word_level_name
    )

def handle_level_post(default_redirect):
    if request.method == "POST":
        selected = request.form.getlist("levels")
        selected_levels = [int(x) for x in selected] if selected else []
        session["selected_levels"] = selected_levels
        return redirect(default_redirect)
    return None

@app.route('/words/table', methods=['GET', 'POST'])
def words_table():
    redirect_response = handle_level_post(url_for('words_table'))
    if redirect_response:
        return redirect_response
    words, levels, selected_levels = get_words_from_db()
    levels_dict = {lvl["id"]: lvl["name"] for lvl in levels}
    return render_template(
        "words_table.html",
        words=words,
        levels=levels,
        selected_levels=selected_levels,
        levels_dict=levels_dict,
    )

@app.route('/words/cards', methods=['GET', 'POST'])
def words_cards():
    redirect_response = handle_level_post(url_for('words_cards'))
    if redirect_response:
        return redirect_response
    words, levels, selected_levels = get_words_from_db()
    levels_dict = {lvl["id"]: lvl["name"] for lvl in levels}
    return render_template(
        "words_cards.html",
        words=words,
        levels=levels,
        selected_levels=selected_levels,
        levels_dict=levels_dict,
    )

@app.route('/words/flashcards', methods=['GET', 'POST'])
def words_flashcards():
    redirect_response = handle_level_post(url_for('words_flashcards'))
    if redirect_response:
        return redirect_response
    words, levels, selected_levels = get_words_from_db()
    levels_dict = {lvl["id"]: lvl["name"] for lvl in levels}
    return render_template(
        "words_flashcards.html",
        words=words,
        levels=levels,
        selected_levels=selected_levels,
        levels_dict=levels_dict,
    )

@app.route('/words/flashcards/ajax', methods=['POST'])
def words_flashcards_ajax():
    data = request.get_json() or {}
    raw_levels = data.get("levels", [])

    selected_levels = []
    for x in raw_levels:
        try:
            selected_levels.append(int(x))
        except (TypeError, ValueError):
            continue

    words, levels, _ = get_words_from_db(selected_levels=selected_levels)
    levels_dict = {lvl["id"]: lvl["name"] for lvl in levels}

    html = render_template("partials/words_flashcards.html",
                           words=words,
                           levels_dict=levels_dict)
    return jsonify({"html": html, "selected_levels": selected_levels})

def get_words_from_db(selected_levels=None):
    conn = sqlite3.connect("finnish.db")
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # 1) Load all levels
    cur.execute("SELECT id, name FROM levels ORDER BY id")
    levels = cur.fetchall()
    all_level_ids = [row["id"] for row in levels]

    # 2) Decide selected_levels:
    #    - if passed as argument, use it (after validation) and store in session
    #    - else read from session, falling back to all levels (first time),
    #      and allowing empty afterwards if user deselected all.
    if selected_levels is not None:
        normalized = []
        for x in selected_levels:
            try:
                val = int(x)
            except (TypeError, ValueError):
                continue
            if val in all_level_ids:
                normalized.append(val)
        # if nothing valid was passed, default to ALL
        if not normalized:
            normalized = all_level_ids
        selected_levels = normalized
        session["selected_levels"] = selected_levels
    else:
        stored = session.get("selected_levels")  # no default
        normalized = []
        if stored is None:
            # first time: all levels
            normalized = all_level_ids
        else:
            for x in stored:
                try:
                    val = int(x)
                except (TypeError, ValueError):
                    continue
                if val in all_level_ids:
                    normalized.append(val)
            # Here we allow normalized to be [] (user may have deselected all)
        selected_levels = normalized
        session["selected_levels"] = selected_levels

    words = []

    if selected_levels:
        # 3) Fetch words filtered by selected_levels (include level!)
        placeholders = ",".join("?" for _ in selected_levels)
        cur.execute(f"""
            SELECT w.id, w.word, w.level
            FROM words w
            WHERE w.level IN ({placeholders})
            ORDER BY LOWER(w.word)
        """, selected_levels)

        words_raw = cur.fetchall()

        # 4) Enrich each word with translations (your existing logic)
        for w in words_raw:
            cur.execute("""
                SELECT DISTINCT t.translation_text
                FROM translations t
                JOIN meanings m ON m.id = t.meaning_id
                WHERE m.word_id = ?
                ORDER BY m.meaning_number, t.translation_number
            """, (w["id"],))

            all_translations = [row["translation_text"] for row in cur.fetchall()]
            total_count = len(all_translations)

            max_display = 3
            max_total_len = 40

            display_translations = []
            current_len = 0

            for t in all_translations:
                if not display_translations:
                    display_translations.append(t)
                    current_len += len(t)
                else:
                    if len(display_translations) >= max_display:
                        break
                    projected_len = current_len + 2 + len(t)  # ", "
                    if projected_len > max_total_len:
                        break
                    display_translations.append(t)
                    current_len = projected_len

            words.append({
                "id": w["id"],
                "word": w["word"],
                "level": w["level"],
                "translations": display_translations,
                "total_translations": total_count,
            })

    conn.close()
    return words, levels, selected_levels

@app.route('/levels/ajax', methods=['POST'])
def handle_levels_ajax():
    data = request.get_json()
    selected = data.get("levels", [])
    # Store selected levels in session as integers
    try:
        session["selected_levels"] = [int(x) for x in selected]
    except ValueError:
        session["selected_levels"] = []
    return jsonify({"success": True, "selected_levels": session["selected_levels"]})

@app.route('/levels/update_view', methods=['POST'])
def update_view():
    data = request.get_json() or {}
    raw_levels = data.get("levels", [])

    selected_levels = []
    for x in raw_levels:
        try:
            val = int(x)
        except (TypeError, ValueError):
            continue
        selected_levels.append(val)

    session["selected_levels"] = selected_levels

    view = data.get("view", "cards")
    words, levels, _ = get_words_from_db()
    levels_dict = {lvl["id"]: lvl["name"] for lvl in levels}

    if view == "cards":
        html = render_template("partials/words_cards.html",
                               words=words,
                               levels_dict=levels_dict)
    elif view == "table":
        html = render_template("partials/words_table.html",
                               words=words,
                               levels_dict=levels_dict)
    else:
        html = render_template("partials/words_flashcards.html",
                               words=words,
                               levels_dict=levels_dict)

    return jsonify({"html": html, "current_view": view, "selected_levels": selected_levels})

def get_all_levels(cur):
    cur.execute("SELECT id, name FROM levels ORDER BY id")
    return cur.fetchall()

def get_selected_levels(cur):
    """
    Returns (selected_level_ids, levels_rows).
    - Reads from session["selected_levels"] if present/valid
    - Otherwise uses all levels.
    """
    levels = get_all_levels(cur)
    all_ids = [row["id"] for row in levels]

    stored = session.get("selected_levels")
    if stored:
        # Keep only valid IDs that actually exist
        try:
            selected = [int(x) for x in stored if int(x) in all_ids]
        except (TypeError, ValueError):
            selected = []
        if selected:
            return selected, levels

    # Default: all levels selected
    return all_ids, levels

def resolve_selected_levels(cur):
    """
    Load levels from DB and return (levels_rows, selected_level_ids),
    using session["selected_levels"] if present/valid,
    else all levels. IMPORTANT: if the user has explicitly
    selected NONE, we allow [].
    """
    cur.execute("SELECT id, name FROM levels ORDER BY id")
    levels = cur.fetchall()
    all_level_ids = [row["id"] for row in levels]

    stored = session.get("selected_levels")  # may be None or list
    if stored is None:
        # first time: default to all levels
        normalized = all_level_ids
    else:
        normalized = []
        for x in stored:
            try:
                val = int(x)
            except (TypeError, ValueError):
                continue
            if val in all_level_ids:
                normalized.append(val)
        # IMPORTANT: do NOT force fallback here.
        # If user cleared all levels, normalized can be [].

    session["selected_levels"] = normalized
    return levels, normalized

def get_descendant_category_ids(all_rows, root_id):
    """
    Given all category rows and a root category_id,
    return a list of all descendant category ids (children, grandchildren, ...).
    """
    children_by_parent = {}
    for row in all_rows:
        parent = row["parent_id"]
        cid = row["id"]
        children_by_parent.setdefault(parent, []).append(cid)

    descendants = []

    def dfs(cat_id):
        for child_id in children_by_parent.get(cat_id, []):
            descendants.append(child_id)
            dfs(child_id)

    dfs(root_id)
    return descendants

from functools import lru_cache

def get_categories_with_counts(cur, level_ids):
    """
    Returns parent_id -> [category dicts], each dict has:
        id, name, parent_id, sort_order, count

    `count` = number of *distinct* words in this topic AND all its descendants,
    filtered by the given level_ids. No double-counting if the same word appears
    in multiple subtopics.
    """

    # 1) Load all categories
    cur.execute("""
        SELECT
            id,
            name,
            parent_id,
            COALESCE(sort_order, 0) AS sort_order
        FROM categories
        ORDER BY parent_id, sort_order, name
    """)
    rows = cur.fetchall()

    by_id = {}
    children_by_parent = {}

    for row in rows:
        cat = dict(row)
        cat["count"] = 0    # we'll compute this below
        cid = cat["id"]
        by_id[cid] = cat

        parent_id = cat["parent_id"]
        children_by_parent.setdefault(parent_id, []).append(cid)

    # 2) Direct word sets per category: cat_id -> set(word_id)
    words_by_cat = {}

    if level_ids:
        placeholders = ",".join("?" * len(level_ids))
        cur.execute(f"""
            SELECT
                wc.category_id AS category_id,
                w.id           AS word_id
            FROM word_categories wc
            JOIN words w ON w.id = wc.word_id
            WHERE w.level IN ({placeholders})
        """, level_ids)

        for row in cur.fetchall():
            cid = row["category_id"]
            wid = row["word_id"]
            words_by_cat.setdefault(cid, set()).add(wid)

    # 3) Recursively gather word sets up the tree (with caching)
    @lru_cache(maxsize=None)
    def gather_words(cat_id):
        merged = set(words_by_cat.get(cat_id, set()))
        for child_id in children_by_parent.get(cat_id, []):
            merged |= gather_words(child_id)
        return merged

    # 4) Fill in counts
    for cid, cat in by_id.items():
        word_set = gather_words(cid)
        cat["count"] = len(word_set)

    # 5) Build parent -> children mapping for template
    categories_dict = {}
    for cid, cat in by_id.items():
        parent = cat["parent_id"]
        categories_dict.setdefault(parent, []).append(cat)

    # 6) Sort children: non-empty first, then sort_order, then name
    for parent_id, children in categories_dict.items():
        children.sort(
            key=lambda c: (
                c["count"] == 0,        # non-empty (False) before empty (True)
                c.get("sort_order", 0),
                c["name"].lower(),
            )
        )

    return categories_dict


@app.route('/categories')
def categories():
    conn = sqlite3.connect("finnish.db")
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    levels, selected_levels = resolve_selected_levels(cur)

    categories_dict = get_categories_with_counts(cur, selected_levels)

    conn.close()

    return render_template(
        "categories.html",
        categories=categories_dict,
        levels=levels,
        selected_levels=selected_levels,
    )

@app.route('/categories/filter', methods=['POST'])
def filter_categories():
    data = request.get_json() or {}
    raw_levels = data.get("levels", [])

    selected_levels = []
    for x in raw_levels:
        try:
            selected_levels.append(int(x))
        except (TypeError, ValueError):
            continue

    conn = sqlite3.connect("finnish.db")
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("SELECT id FROM levels ORDER BY id")
    all_level_ids = [row["id"] for row in cur.fetchall()]
    # keep only valid IDs
    selected_levels = [lvl for lvl in selected_levels if lvl in all_level_ids]
    # DO NOT fallback to all_level_ids here – empty is allowed
    session["selected_levels"] = selected_levels

    categories_dict = get_categories_with_counts(cur, selected_levels)

    conn.close()

    html = render_template("partials/categories_grid.html", categories=categories_dict)
    return jsonify({"html": html})

@app.route('/categories/<category_name>')
def show_category(category_name):
    # view = table / cards / flashcards
    view = request.args.get("view", "table")

    # include_subs: "1" (default) or "0"
    include_subs_arg = request.args.get("include_subs", "1")
    include_subs = (include_subs_arg != "0")

    conn = sqlite3.connect("finnish.db")
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # --- Load all categories (with sort_order) ---
    #   sort top-level and children by sort_order, then name
    cur.execute("""
        SELECT
            id,
            name,
            parent_id,
            COALESCE(sort_order, 0) AS sort_order
        FROM categories
        ORDER BY parent_id,
                 sort_order,
                 name
    """)
    all_rows = cur.fetchall()

    # Find current topic
    cur.execute("SELECT id, name, parent_id FROM categories WHERE name = ?", (category_name,))
    category = cur.fetchone()
    if not category:
        conn.close()
        return f"Topic '{category_name}' not found."
    category_id = category["id"]

    # --- Fetch all levels (once) ---
    cur.execute("SELECT id, name FROM levels ORDER BY id")
    levels = cur.fetchall()
    all_level_ids = [lvl["id"] for lvl in levels]
    levels_dict = {lvl["id"]: lvl["name"] for lvl in levels}

    # --- Normalize selected levels from session ---
    stored = session.get("selected_levels")
    selected_levels = []
    if stored is None:
        selected_levels = all_level_ids.copy()
    else:
        for x in stored:
            try:
                val = int(x)
            except (TypeError, ValueError):
                continue
            if val in all_level_ids:
                selected_levels.append(val)

    session["selected_levels"] = selected_levels

    # ---- Build topic tree WITH counts (per selected levels) ----
    effective_levels = selected_levels if selected_levels else all_level_ids
    categories_dict = get_categories_with_counts(cur, effective_levels)
    # Direct subtopics of this topic (each has 'count' and should already be ordered
    # by sort_order inside get_categories_with_counts)
    subcategories = categories_dict.get(category_id, [])

    # ----- Words for this category (+ optional subcategories) -----
    words_with_translations = []

    if include_subs:
        descendants = get_descendant_category_ids(all_rows, category_id)
        category_ids_for_words = [category_id] + descendants
    else:
        category_ids_for_words = [category_id]

    if selected_levels and category_ids_for_words:
        placeholders_levels = ",".join("?" for _ in selected_levels)
        placeholders_cats = ",".join("?" for _ in category_ids_for_words)

        sql = f"""
            SELECT
                w.id               AS word_id,
                w.word             AS word,
                w.level            AS level,
                MIN(wc.meaning_id) AS meaning_id,

                -- parent category first, then subcategories
                MIN(
                    CASE
                        WHEN wc.category_id = ? THEN 0
                        ELSE 1
                    END
                ) AS cat_priority,

                -- smallest category sort_order among categories this word is in
                MIN(c.sort_order)  AS cat_sort_order,

                -- smallest word sort_order among those categories
                MIN(wc.sort_order) AS word_sort_order

            FROM words w
            JOIN word_categories wc ON w.id = wc.word_id
            JOIN categories c       ON c.id = wc.category_id
            WHERE wc.category_id IN ({placeholders_cats})
              AND w.level      IN ({placeholders_levels})
            GROUP BY w.id, w.word, w.level
            ORDER BY
                cat_priority,       -- parent words first, then subcategories
                cat_sort_order,     -- order of subcategories under the parent
                word_sort_order,    -- manual order within each category
                LOWER(w.word)       -- tie-breaker
        """

        params = [category_id] + category_ids_for_words + selected_levels
        cur.execute(sql, params)
        words = cur.fetchall()

        for w in words:
            meaning_id = w["meaning_id"]

            if meaning_id:
                cur.execute("""
                    SELECT translation_text
                    FROM translations
                    WHERE meaning_id = ?
                    ORDER BY translation_number
                    LIMIT 5
                """, (meaning_id,))
            else:
                cur.execute("""
                    SELECT t.translation_text
                    FROM meanings m
                    JOIN translations t ON t.meaning_id = m.id
                    WHERE m.word_id = ?
                    ORDER BY m.meaning_number, t.translation_number
                    LIMIT 5
                """, (w["word_id"],))

            translations = [row["translation_text"] for row in cur.fetchall()]

            words_with_translations.append({
                "id": w["word_id"],
                "word": w["word"],
                "level": w["level"],
                "translations": translations
            })
    else:
        words_with_translations = []

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
        categories=categories_dict,
        levels=levels,
        levels_dict=levels_dict,
        selected_levels=selected_levels,
        view=view,
        include_subs=include_subs,
    )


@app.route('/categories/<category_name>/update_view', methods=['POST'])
def category_update_view(category_name):
    data = request.get_json() or {}
    view = data.get("view", "table")
    include_subs = data.get("include_subs", 0)
    try:
        include_subs = bool(int(include_subs))
    except (TypeError, ValueError):
        include_subs = bool(include_subs)

    conn = sqlite3.connect("finnish.db")
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # 1) Find the current category
    cur.execute("SELECT id, name, parent_id FROM categories WHERE name = ?", (category_name,))
    category = cur.fetchone()
    if not category:
        conn.close()
        return jsonify({"words_html": "", "subtopics_html": ""})

    category_id = category["id"]

    # 2) Resolve levels from session (reuse your helper)
    levels, selected_levels = resolve_selected_levels(cur)

    # 3) Get categories with counts for these levels
    categories_dict = get_categories_with_counts(cur, selected_levels)

    # Subtopics for this category (with up-to-date counts)
    subcategories = categories_dict.get(category_id, [])

    # 4) Build list of category_ids used for word fetching
    category_ids = [category_id]

    if include_subs:
        # collect descendant category ids as well
        # build children map from categories_dict
        children_map = {}
        for parent_id, childs in categories_dict.items():
            for c in childs:
                children_map.setdefault(parent_id, []).append(c["id"])

        from collections import deque
        queue = deque([category_id])
        seen = set([category_id])

        while queue:
            cid = queue.popleft()
            for child_id in children_map.get(cid, []):
                if child_id not in seen:
                    seen.add(child_id)
                    queue.append(child_id)

        category_ids = list(seen)

    # 5) Fetch words for these category_ids and levels
    words_with_translations = []

    if selected_levels and category_ids:
        level_placeholders = ",".join("?" for _ in selected_levels)
        cat_placeholders = ",".join("?" for _ in category_ids)

        sql = f"""
            SELECT
                w.id               AS word_id,
                w.word             AS word,
                w.level            AS level,
                MIN(wc.meaning_id) AS meaning_id,

                MIN(
                    CASE
                        WHEN wc.category_id = ? THEN 0
                        ELSE 1
                    END
                ) AS cat_priority,
                MIN(c.sort_order)  AS cat_sort_order,
                MIN(wc.sort_order) AS word_sort_order

            FROM words w
            JOIN word_categories wc ON w.id = wc.word_id
            JOIN categories c       ON c.id = wc.category_id
            WHERE wc.category_id IN ({cat_placeholders})
              AND w.level      IN ({level_placeholders})
            GROUP BY w.id, w.word, w.level
            ORDER BY
                cat_priority,
                cat_sort_order,
                word_sort_order,
                LOWER(w.word)
        """

        # first ? is for CASE WHEN wc.category_id = ?
        params = [category_id] + category_ids + selected_levels
        cur.execute(sql, params)
        words = cur.fetchall()


        for w in words:
            meaning_id = w["meaning_id"]
            if meaning_id:
                cur.execute("""
                    SELECT translation_text
                    FROM translations
                    WHERE meaning_id = ?
                    ORDER BY translation_number
                    LIMIT 5
                """, (meaning_id,))
            else:
                cur.execute("""
                    SELECT t.translation_text
                    FROM meanings m
                    JOIN translations t ON t.meaning_id = m.id
                    WHERE m.word_id = ?
                    ORDER BY m.meaning_number, t.translation_number
                    LIMIT 5
                """, (w["word_id"],))
            translations = [row["translation_text"] for row in cur.fetchall()]

            words_with_translations.append({
                "id": w["word_id"],
                "word": w["word"],
                "level": w["level"],
                "translations": translations,
            })

    conn.close()

    # 6) Render partials
    if view == "table":
        words_html = render_template("partials/words_table.html", words=words_with_translations)
    elif view == "cards":
        words_html = render_template("partials/words_cards.html", words=words_with_translations)
    else:
        words_html = render_template("partials/words_flashcards.html", words=words_with_translations)

    subtopics_html = render_template(
        "partials/category_subtopics.html",
        subcategories=subcategories,
        categories=categories_dict,
    )

    return jsonify({
        "words_html": words_html,
        "subtopics_html": subtopics_html,
    })

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

    # Counts
    cur.execute("SELECT COUNT(*) AS count FROM words")
    total_words = cur.fetchone()["count"]

    cur.execute("SELECT COUNT(*) AS count FROM categories")
    total_categories = cur.fetchone()["count"]

    # Recent words (last 10)
    cur.execute("SELECT id, word FROM words ORDER BY id DESC LIMIT 10")
    recent_words = cur.fetchall()

    # Recent categories (last 10)
    cur.execute("SELECT id, name FROM categories ORDER BY id DESC LIMIT 10")
    recent_categories = cur.fetchall()

    # 🔹 Autocomplete source: all words with IDs
    cur.execute("SELECT id, word FROM words ORDER BY word COLLATE NOCASE")
    all_words_full = cur.fetchall()          # [{id, word}, ...]

    # 🔹 Autocomplete source: all categories with IDs
    cur.execute("SELECT id, name FROM categories ORDER BY name COLLATE NOCASE")
    all_categories_full = cur.fetchall()     # [{id, name}, ...]

    conn.close()

    return render_template(
        "admin_dashboard.html",
        total_words=total_words,
        total_categories=total_categories,
        recent_words=recent_words,
        recent_categories=recent_categories,

        # needed for autocomplete
        all_words_full=all_words_full,
        all_categories_full=all_categories_full,

        # also provide name-only lists if needed
        all_words=[w["word"] for w in all_words_full],
        all_categories=[c["name"] for c in all_categories_full],
    )


@app.route('/admin/add_word', methods=['GET', 'POST'])
@admin_required
def admin_add_word():
    conn = sqlite3.connect("finnish.db")
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("SELECT id, name FROM levels ORDER BY id")
    levels = cur.fetchall()

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
                return render_template('admin_add_word.html', pos_list=pos_list, levels=levels)
            level = int(request.form.get("level", 0))

            # Insert the word
            cur.execute(
            "INSERT INTO words (word, level, created_at, updated_at) VALUES (?, ?, datetime('now'), datetime('now'))",
            (word_text, level)
        )

            conn.commit()
            word_id = cur.lastrowid

            # Insert meanings
            meaning_numbers = request.form.getlist('meaning_number[]')
            for idx, m_num in enumerate(meaning_numbers):
                m_num_int = int(m_num)

                # POS per meaning
                pos_id = request.form.get(f"pos_id_{m_num}")
                pos_id = int(pos_id) if pos_id else None


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
    return render_template('admin_add_word.html', pos_list=pos_list, levels=levels)

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

    # Fetch levels
    cur.execute("SELECT id, name FROM levels ORDER BY id")
    levels = cur.fetchall()

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
        level_id = int(request.form.get("level", 0))
        
        # Check for duplicates
        cur.execute("SELECT id FROM words WHERE word=? AND id != ?", (new_word, word_id))
        if cur.fetchone():
            flash(f"The word '{new_word}' already exists.", "error")
            conn.close()
            return redirect(url_for('admin_edit_word', word_id=word_id))

        cur.execute("UPDATE words SET word = ?, level = ?, updated_at = datetime('now') WHERE id = ?", (new_word, level_id, word_id))
        conn.commit()
        flash(f"Word '{new_word}' updated successfully!", "success")
        conn.close()
        return redirect(url_for('admin_edit_word', word_id=word_id))

    conn.close()
    return render_template('admin_edit_word.html', word=word, levels=levels, meanings_by_pos=meanings_by_pos, pos_list=pos_list)

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

        cur.execute("UPDATE words SET updated_at = datetime('now') WHERE id=?", (word_id,))
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
        meanings_count=meanings_count  
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
        cur.execute("UPDATE words SET updated_at = datetime('now') WHERE id=?", (word_id,))
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
    cur.execute("UPDATE words SET updated_at = datetime('now') WHERE id=?", (word_id,))
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
        cur.execute("INSERT INTO categories (name, parent_id, created_at, updated_at) VALUES (?, ?, datetime('now'), datetime('now'))", (name, parent_id))

        
        category_id = cur.lastrowid

        conn.commit()
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
    conn = sqlite3.connect("finnish.db", timeout=10)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Fetch category info
    cur.execute("SELECT * FROM categories WHERE id = ?", (category_id,))
    category = cur.fetchone()
    if not category:
        conn.close()
        flash("Category not found.", "danger")
        return redirect(url_for("admin_dashboard"))

    # Fetch this category's parent (if any)
    parent_category = None
    if category["parent_id"]:
        cur.execute("SELECT id, name FROM categories WHERE id = ?", (category["parent_id"],))
        parent_category = cur.fetchone()

    # Fetch possible parent options (exclude self)
    cur.execute("SELECT id, name FROM categories WHERE id != ? ORDER BY name", (category_id,))
    all_categories = cur.fetchall()

    # Parts of speech
    cur.execute("SELECT id, name FROM parts_of_speech ORDER BY name")
    pos_list = cur.fetchall()

    # Levels
    cur.execute("SELECT id, name FROM levels ORDER BY id")
    levels = cur.fetchall()

    action = request.form.get("action")

    if action:
        # -----------------------
        # Update category (name + parent)
        # -----------------------
        if action == "update_category":
            name = request.form.get("name", "").strip()
            parent_id = request.form.get("parent_id") or None

            # Convert empty string to None explicitly
            if parent_id == "":
                parent_id = None

            # Check duplicate name (excluding current category)
            cur.execute("SELECT id FROM categories WHERE name = ? AND id != ?", (name, category_id))
            if cur.fetchone():
                flash(f"Another category with the name '{name}' already exists.", "danger")
                conn.close()
                return redirect(url_for("admin_edit_category", category_id=category_id))

            # Proceed with update
            cur.execute(
                "UPDATE categories SET name = ?, parent_id = ?, updated_at = datetime('now') WHERE id = ?",
                (name, parent_id, category_id),
            )
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

            level_id = int(request.form.get("level", 0))
            cur.execute(
                "INSERT INTO words (word, level, created_at, updated_at) "
                "VALUES (?, ?, datetime('now'), datetime('now'))",
                (word_text, level_id),
            )
            conn.commit()
            word_id = cur.lastrowid

            # Insert meanings
            meaning_numbers = request.form.getlist("meaning_number[]")
            for m_num in meaning_numbers:
                pos_id = request.form.get(f"pos_id_{m_num}")
                notes = request.form.get(f"meaning_notes[]")
                definition = request.form.get(f"definition_{m_num}", "").strip() or None

                cur.execute(
                    "INSERT INTO meanings (word_id, meaning_number, pos_id, notes, definition) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (word_id, int(m_num), pos_id, notes, definition),
                )
                conn.commit()
                cur.execute(
                    "SELECT id FROM meanings WHERE word_id = ? AND meaning_number = ?",
                    (word_id, int(m_num)),
                )
                meaning_id = cur.fetchone()["id"]

                # Insert translations
                translations = request.form.getlist(f"translations_{m_num}[]")
                for idx, t in enumerate(translations, 1):
                    t = t.strip()
                    if t:
                        cur.execute(
                            "INSERT INTO translations (meaning_id, translation_text, translation_number) "
                            "VALUES (?, ?, ?)",
                            (meaning_id, t, idx),
                        )

                # Insert examples
                examples = request.form.getlist(f"examples_{m_num}[]")
                examples_trans = request.form.getlist(f"examples_trans_{m_num}[]")
                for ex, ex_tr in zip(examples, examples_trans):
                    if ex.strip():
                        cur.execute(
                            "INSERT INTO examples (meaning_id, example_text, example_translation_text) "
                            "VALUES (?, ?, ?)",
                            (meaning_id, ex.strip(), ex_tr.strip() or None),
                        )

            # Assign to category
            cur.execute(
                "INSERT INTO word_categories (word_id, category_id) VALUES (?, ?)",
                (word_id, category_id),
            )
            cur.execute(
                "UPDATE categories SET updated_at = datetime('now') WHERE id = ?",
                (category_id,),
            )
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
            cur.execute(
                "SELECT 1 FROM word_categories WHERE word_id = ? AND category_id = ?",
                (existing_word_id, category_id),
            )
            if cur.fetchone():
                flash("This word is already in the category.", "warning")
                conn.close()
                return redirect(url_for("admin_edit_category", category_id=category_id))

            cur.execute(
                "INSERT INTO word_categories (word_id, category_id) VALUES (?, ?)",
                (existing_word_id, category_id),
            )
            cur.execute(
                "UPDATE categories SET updated_at = datetime('now') WHERE id = ?",
                (category_id,),
            )
            conn.commit()
            conn.close()
            flash("Word added to category.", "success")
            return redirect(url_for("admin_edit_category", category_id=category_id))

    # --- GET branch or after actions ---

    # Search existing words
    search_query = request.args.get("word_query", "").strip()
    search_results = []
    if search_query:
        cur.execute(
            "SELECT id, word FROM words WHERE word LIKE ? ORDER BY word",
            (f"{search_query}%",),
        )
        search_results = cur.fetchall()

    # Words in this category
    cur.execute(
        """
        SELECT w.id, w.word
        FROM words w
        JOIN word_categories wc ON w.id = wc.word_id
        WHERE wc.category_id = ?
        ORDER BY w.word
        """,
        (category_id,),
    )
    category_words = cur.fetchall()

        # Direct subcategories of this category
    cur.execute(
        """
        SELECT id, name
        FROM categories
        WHERE parent_id = ?
        ORDER BY sort_order, name
        """,
        (category_id,),
    )
    subcategories = cur.fetchall()

    # 👉 NEW: fetch all words for autocomplete in "Add Existing Word"
    cur.execute("SELECT id, word FROM words ORDER BY word")
    all_words = cur.fetchall()

    conn.close()
    return render_template(
        "admin_edit_category.html",
        category=category,
        parent_category=parent_category,
        all_categories=all_categories,
        category_words=category_words,
        pos_list=pos_list,
        search_query=search_query,
        search_results=search_results,
        levels=levels,
        subcategories=subcategories,
        all_words=all_words,   # 👉 pass to template
    )


@app.route("/admin/categories/<int:category_id>/remove_word/<int:word_id>", methods=["POST"])
@admin_required
def admin_remove_word_from_category(category_id, word_id):
    conn = sqlite3.connect("finnish.db")
    cur = conn.cursor()
    
    # Remove word from category
    cur.execute("DELETE FROM word_categories WHERE word_id=? AND category_id=?", (word_id, category_id))
    cur.execute("UPDATE categories SET updated_at = datetime('now') WHERE id = ?", (category_id,))
    conn.commit()
    conn.close()
    
    flash("Word removed from category.", "success")
    return redirect(url_for("admin_edit_category", category_id=category_id) + "#words-section")

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

@app.route("/admin/categories/order", methods=["GET", "POST"])
@admin_required
def admin_order_categories():
    conn = sqlite3.connect("finnish.db")
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    if request.method == "POST":
        # Update sort_order for each category that has a value in the form
        cur.execute("SELECT id FROM categories")
        ids = [row["id"] for row in cur.fetchall()]

        for cat_id in ids:
            key = f"order_{cat_id}"
            if key in request.form:
                raw = request.form[key].strip()
                if raw == "":
                    # you can choose to treat empty as 0
                    sort_val = 0
                else:
                    try:
                        sort_val = int(raw)
                    except ValueError:
                        sort_val = 0
                cur.execute(
                    "UPDATE categories SET sort_order = ? WHERE id = ?",
                    (sort_val, cat_id),
                )

        conn.commit()
        conn.close()
        flash("Category order updated.", "success")
        return redirect(url_for("admin_order_categories"))

    # GET: show all categories with parent info, ordered by parent then sort_order
    cur.execute("""
        SELECT
            c.id,
            c.name,
            c.parent_id,
            COALESCE(c.sort_order, 0) AS sort_order,
            p.name AS parent_name
        FROM categories c
        LEFT JOIN categories p ON c.parent_id = p.id
        ORDER BY
            CASE WHEN p.name IS NULL THEN 0 ELSE 1 END,
            parent_name,
            sort_order,
            c.name
    """)
    categories = cur.fetchall()
    conn.close()

    return render_template("admin_order_categories.html", categories=categories)

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

    # --- Insert reverse if bidirectional ---
    cur.execute("SELECT bidirectional FROM relation_types WHERE id = ?", (reltype,))
    bidirectional = cur.fetchone()[0]  # 1 = True, 0 = False
    if bidirectional:
        # Avoid inserting duplicate
        cur.execute("""
            SELECT id FROM meaning_relations
            WHERE meaning1_id = ? AND meaning2_id = ? AND relation_type_id = ?
        """, (m2_id, m1_id, reltype))
        if not cur.fetchone():
            cur.execute("""
                INSERT INTO meaning_relations (meaning1_id, meaning2_id, relation_type_id)
                VALUES (?, ?, ?)
            """, (m2_id, m1_id, reltype))

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
    # app.run(host="0.0.0.0", port=5000, debug=True)
    app.run(debug=True)
