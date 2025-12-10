import os
import sqlite3
import csv

DB_PATH = "finnish.db"
TSV_DIR = "collocations_tsv"   # folder where <word>.tsv files live


def get_word_id(cur, word_form):
    """
    Look up a word_id in 'words' table by exact word form.
    Returns None if not found.
    """
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

    - If an existing row is found, we may update freq/pmi/surface_form.
    - Otherwise we insert a new row.
    """
    cur.execute("""
        SELECT id, freq, pmi, surface_form
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

        new_freq = old_freq
        new_pmi = old_pmi
        new_surface = old_surface
        changed = False

        # update freq / pmi by taking max when present
        if freq is not None:
            if old_freq is None or freq > old_freq:
                new_freq = freq
                changed = True

        if pmi is not None:
            if old_pmi is None or pmi > old_pmi:
                new_pmi = pmi
                changed = True

        # surface_form: only set if we have a non-empty value and previous was empty/null
        if surface_form:
            if not old_surface:
                new_surface = surface_form
                changed = True

        if changed:
            cur.execute("""
                UPDATE word_collocations
                SET freq = ?, pmi = ?, surface_form = ?
                WHERE id = ?
            """, (new_freq, new_pmi, new_surface, colloc_id))

        return colloc_id, False, changed

    # No existing row: insert new
    cur.execute("""
        INSERT INTO word_collocations
            (word_id, other_word_id, other_form, direction, freq, pmi, surface_form, source)
        VALUES
            (?, ?, ?, ?, ?, ?, ?, 'subtitles')
    """, (word_id, other_word_id, other_form, direction, freq, pmi, surface_form))

    return cur.lastrowid, True, False


def insert_corpus_example(cur, word_id, collocation_id, example_text):
    """
    Insert example_text into corpus_examples linked to the given collocation.
    - word_id: main word (e.g. 'hyvä')
    - collocation_id: word_collocations.id
    Marks is_primary=1 if this is the first example for this collocation.
    Avoids duplicate example_text for the same collocation.
    """
    example_text = example_text.strip()
    if not example_text:
        return None

    # Already exists for this collocation?
    cur.execute("""
        SELECT id
        FROM corpus_examples
        WHERE collocation_id = ?
          AND example_text = ?
    """, (collocation_id, example_text))
    row = cur.fetchone()
    if row:
        return row["id"]

    # Is there already a primary example?
    cur.execute("""
        SELECT COUNT(*)
        FROM corpus_examples
        WHERE collocation_id = ?
          AND is_primary = 1
    """, (collocation_id,))
    has_primary = cur.fetchone()[0] > 0

    is_primary = 0 if has_primary else 1

    cur.execute("""
        INSERT INTO corpus_examples
            (word_id, meaning_id, example_text, example_translation_text,
             source, collocation_id, is_primary)
        VALUES
            (?, NULL, ?, NULL, 'subtitles', ?, ?)
    """, (word_id, example_text, collocation_id, is_primary))

    return cur.lastrowid


def main():
    # --- Ask for lemma and build TSV path ---
    lemma = input("Enter lemma to import collocations for (e.g. 'hyvä'): ").strip()
    if not lemma:
        print("No lemma entered, aborting.")
        return

    tsv_path = os.path.join(TSV_DIR, f"{lemma}.tsv")

    if not os.path.exists(tsv_path):
        print(f"TSV file not found: {tsv_path}")
        print("Make sure the file exists (export it first with your collocation script).")
        return

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

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

            # Get or create collocation row (now with surface_form)
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

            # Insert example into corpus_examples, linked via collocation_id
            if example_sentence:
                ex_id = insert_corpus_example(
                    cur,
                    word_id=word_id,
                    collocation_id=colloc_id,
                    example_text=example_sentence,
                )
                if ex_id is not None:
                    inserted_examples += 1

    conn.commit()
    conn.close()

    print("Done.")
    print(f"  New collocations inserted:             {new_collocs}")
    print(f"  Existing collocations updated (stats): {updated_collocs}")
    print(f"  Examples inserted into corpus_examples:{inserted_examples}")
    print(f"  Skipped (main word missing in DB):     {skipped_no_word}")
    print(f"  Skipped total (any reason):            {skipped_total}")


if __name__ == "__main__":
    main()
