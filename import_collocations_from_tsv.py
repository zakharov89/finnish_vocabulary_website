import os
import sqlite3
import csv


# ----------------------------
# PATHS
# ----------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# If this script is in your project root next to finnish.db:
ROOT_DIR = BASE_DIR

# If you moved it to Finnish learning website/scripts/, then use:
# ROOT_DIR = os.path.abspath(os.path.join(BASE_DIR, ".."))

DB_PATH = os.path.join(ROOT_DIR, "finnish.db")
TSV_DIR = os.path.join(ROOT_DIR, "collocations_tsv")


def ensure_indexes(cur):
    # Prevent duplicate examples per collocation
    cur.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_examples_colloc_text
        ON corpus_examples(collocation_id, example_text)
    """)


def get_word_id(cur, word_form):
    cur.execute("SELECT id FROM words WHERE word = ?", (word_form,))
    row = cur.fetchone()
    return row["id"] if row else None


def get_or_create_collocation(cur,
                              word_id,
                              other_word_id,
                              other_form,
                              surface_form,
                              direction,
                              freq,
                              pmi):
    """
    Find or create a row in word_collocations for (word_id, other_form, direction).
    Returns (collocation_id, created, updated_stats).
    """

    cur.execute("""
        SELECT id, freq, pmi, surface_form, other_word_id
        FROM word_collocations
        WHERE word_id = ?
          AND other_form = ?
          AND direction = ?
    """, (word_id, other_form, direction))
    row = cur.fetchone()

    if row:
        colloc_id = row["id"]
        old_freq = row["freq"]
        old_pmi = row["pmi"]
        old_surface = row["surface_form"] if row["surface_form"] is not None else ""
        old_other_word_id = row["other_word_id"]

        new_freq = old_freq
        new_pmi = old_pmi
        new_surface = old_surface
        changed = False

        # Option A: overwrite with latest when provided (predictable)
        if freq is not None and freq != old_freq:
            new_freq = freq
            changed = True

        if pmi is not None and pmi != old_pmi:
            new_pmi = pmi
            changed = True

        # surface_form: set if we have a non-empty value and previous was empty/null
        if surface_form and not old_surface:
            new_surface = surface_form
            changed = True

        # other_word_id: fill it in later if previously NULL
        if other_word_id is not None and old_other_word_id is None:
            cur.execute("""
                UPDATE word_collocations
                SET other_word_id = ?
                WHERE id = ?
            """, (other_word_id, colloc_id))
            changed = True

        if changed:
            cur.execute("""
                UPDATE word_collocations
                SET freq = ?, pmi = ?, surface_form = ?
                WHERE id = ?
            """, (new_freq, new_pmi, new_surface, colloc_id))

        return colloc_id, False, changed

    # Insert new
    cur.execute("""
        INSERT INTO word_collocations
            (word_id, other_word_id, other_form, direction, freq, pmi,
             surface_form, source, show_examples)
        VALUES
            (?, ?, ?, ?, ?, ?, ?, 'subtitles', 0)
    """, (word_id, other_word_id, other_form, direction, freq, pmi, surface_form))

    return cur.lastrowid, True, False


def insert_corpus_example(cur, word_id, collocation_id, example_text):
    """
    Insert example_text into corpus_examples linked to collocation_id.
    Uses INSERT OR IGNORE + unique index for speed/dedupe.
    Sets is_primary=1 only for the first example for that collocation.
    """
    example_text = (example_text or "").strip()
    if not example_text:
        return False

    # Determine primary flag
    cur.execute("""
        SELECT COUNT(*)
        FROM corpus_examples
        WHERE collocation_id = ?
    """, (collocation_id,))
    has_any = cur.fetchone()[0] > 0
    is_primary = 0 if has_any else 1

    cur.execute("""
        INSERT OR IGNORE INTO corpus_examples
            (word_id, meaning_id, example_text, example_translation_text,
             source, collocation_id, is_primary)
        VALUES
            (?, NULL, ?, NULL, 'subtitles', ?, ?)
    """, (word_id, example_text, collocation_id, is_primary))

    return cur.rowcount == 1


def main():
    lemma = input("Enter lemma to import collocations for (e.g. 'hyvä'): ").strip()
    if not lemma:
        print("No lemma entered, aborting.")
        return

    tsv_path = os.path.join(TSV_DIR, f"{lemma}.tsv")
    if not os.path.exists(tsv_path):
        print(f"TSV file not found: {tsv_path}")
        print("Make sure the file exists (export it first with your collocation script).")
        return

    if not os.path.exists(DB_PATH):
        print(f"DB not found: {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    ensure_indexes(cur)

    print(f"Importing collocations from: {tsv_path}")

    new_collocs = 0
    updated_collocs = 0
    inserted_examples = 0
    skipped_no_word = 0
    skipped_total = 0

    with open(tsv_path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f, delimiter="\t")

        for row in reader:
            word_form = (row.get("word") or "").strip()
            other_form = (row.get("other_form") or "").strip()
            surface_form = (row.get("surface_form") or "").strip()
            direction = (row.get("direction") or "B").strip().upper() or "B"
            freq_str = (row.get("freq") or "").strip()
            pmi_str = (row.get("pmi") or "").strip()
            example_sentence = (row.get("example_sentence") or "").strip()

            if not word_form or not other_form:
                skipped_total += 1
                continue

            # Parse numbers safely
            try:
                freq = int(freq_str) if freq_str else None
            except ValueError:
                freq = None

            try:
                pmi = float(pmi_str) if pmi_str else None
            except ValueError:
                pmi = None

            # Look up main word_id
            word_id = get_word_id(cur, word_form)
            if word_id is None:
                skipped_no_word += 1
                skipped_total += 1
                continue

            # Look up other_word_id (may be None if not in dictionary)
            other_word_id = get_word_id(cur, other_form)

            colloc_id, created, updated = get_or_create_collocation(
                cur,
                word_id=word_id,
                other_word_id=other_word_id,
                other_form=other_form,
                surface_form=surface_form,
                direction=direction,
                freq=freq,
                pmi=pmi,
            )

            if created:
                new_collocs += 1
            elif updated:
                updated_collocs += 1

            # IMPORTANT: this runs for every TSV row -> supports multiple examples
            if example_sentence:
                if insert_corpus_example(cur, word_id, colloc_id, example_sentence):
                    inserted_examples += 1

    conn.commit()
    conn.close()

    print("Done.")
    print(f"  New collocations inserted:             {new_collocs}")
    print(f"  Existing collocations updated:         {updated_collocs}")
    print(f"  Examples inserted into corpus_examples:{inserted_examples}")
    print(f"  Skipped (main word missing in DB):     {skipped_no_word}")
    print(f"  Skipped total (any reason):            {skipped_total}")


if __name__ == "__main__":
    main()
