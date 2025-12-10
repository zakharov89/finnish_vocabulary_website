import sqlite3
import os

# Paths to your corpora
LEMMA_CORPUS_PATH   = r"C:/Projects/Collocations/subtitles_lemmas_clean.txt"
SURFACE_CORPUS_PATH = r"C:/Projects/Collocations/subtitles_surface.txt"

DB_PATH = "finnish.db"

# Limit how many examples we keep per collocation
MAX_EXAMPLES_PER_COLLOC = 10


def load_collocations(cur):
    """
    Load collocations from the DB and build index by lemma bigram.

    Returns:
        collocs_by_bigram: dict[(l1, l2)] -> list[colloc_dict]
        existing_counts:   dict[colloc_id] -> current number of examples
    """
    # We need the main lemma from words.word and the other lemma from other_form
    cur.execute("""
        SELECT
            wc.id           AS colloc_id,
            w.word          AS main_lemma,
            wc.other_form   AS other_lemma,
            wc.direction    AS direction
        FROM word_collocations wc
        JOIN words w ON wc.word_id = w.id
        WHERE wc.source = 'subtitles'
    """)
    rows = cur.fetchall()

    collocs_by_bigram = {}

    for r in rows:
        colloc_id   = r["colloc_id"]
        main_lemma  = r["main_lemma"]
        other_lemma = r["other_lemma"]
        direction   = r["direction"]

        if not main_lemma or not other_lemma:
            continue

        # For direction:
        #   R: main_lemma first, other_lemma second  (main, other)
        #   L: other_lemma first, main_lemma second  (other, main)
        #   B: accept both directions
        bigrams = []
        if direction in ("R", "B"):
            bigrams.append((main_lemma, other_lemma))
        if direction in ("L", "B"):
            bigrams.append((other_lemma, main_lemma))

        for big in bigrams:
            collocs_by_bigram.setdefault(big, []).append({
                "id": colloc_id,
                "main_lemma": main_lemma,
                "other_lemma": other_lemma,
                "direction": direction,
            })

    # Count existing examples per collocation
    cur.execute("""
        SELECT collocation_id, COUNT(*) AS cnt
        FROM corpus_examples
        WHERE collocation_id IS NOT NULL
        GROUP BY collocation_id
    """)
    existing_counts = {row["collocation_id"]: row["cnt"] for row in cur.fetchall()}

    return collocs_by_bigram, existing_counts


def already_have_example(cur, colloc_id, sentence_text):
    """
    Check if we already have this exact example_text for this collocation.
    """
    cur.execute("""
        SELECT 1
        FROM corpus_examples
        WHERE collocation_id = ?
          AND example_text = ?
        LIMIT 1
    """, (colloc_id, sentence_text))
    return cur.fetchone() is not None


def get_word_id(cur, lemma):
    """
    Find word_id by lemma for word_id in corpus_examples.
    If not found, returns None.
    """
    cur.execute("SELECT id FROM words WHERE word = ?", (lemma,))
    row = cur.fetchone()
    return row["id"] if row else None


def process_corpus(collocs_by_bigram, existing_counts):
    """
    Go through lemma & surface corpora line by line and
    insert extra examples for collocations when we see their bigrams.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    total_inserted = 0
    line_no = 0

    # We'll open both files and iterate them in parallel
    with open(LEMMA_CORPUS_PATH, "r", encoding="utf-8") as f_lem, \
         open(SURFACE_CORPUS_PATH, "r", encoding="utf-8") as f_surf:

        for lem_line, surf_line in zip(f_lem, f_surf):
            line_no += 1
            if line_no % 500_000 == 0:
                print(f"[corpus] Processed {line_no} sentences... (inserted {total_inserted} new examples)")

            lem_tokens = lem_line.strip().split()
            surf_tokens = surf_line.strip().split()

            if not lem_tokens:
                continue

            # Truncate mismatched lines just in case
            if len(lem_tokens) != len(surf_tokens):
                length = min(len(lem_tokens), len(surf_tokens))
                lem_tokens = lem_tokens[:length]
                surf_tokens = surf_tokens[:length]

            sentence_text = " ".join(surf_tokens).strip()
            if not sentence_text:
                continue

            # For each bigram in this sentence, see if it's a known collocation bigram
            for i in range(len(lem_tokens) - 1):
                l1 = lem_tokens[i]
                l2 = lem_tokens[i + 1]
                big = (l1, l2)

                if big not in collocs_by_bigram:
                    continue

                for colloc in collocs_by_bigram[big]:
                    colloc_id = colloc["id"]

                    # Check if we've reached the max examples for this colloc
                    current_count = existing_counts.get(colloc_id, 0)
                    if current_count >= MAX_EXAMPLES_PER_COLLOC:
                        continue

                    # Skip if this exact sentence is already stored
                    if already_have_example(cur, colloc_id, sentence_text):
                        continue

                    # We use word_id = main_lemma if it exists in words table; otherwise NULL
                    main_lemma = colloc["main_lemma"]
                    word_id = get_word_id(cur, main_lemma)

                    cur.execute("""
                        INSERT INTO corpus_examples
                            (word_id, meaning_id, example_text, example_translation_text,
                             source, collocation_id, is_primary)
                        VALUES
                            (?, NULL, ?, NULL, 'subtitles', ?, 0)
                    """, (word_id, sentence_text, colloc_id))

                    existing_counts[colloc_id] = current_count + 1
                    total_inserted += 1

            # Commit occasionally so we don't lose work
            if line_no % 100_000 == 0:
                conn.commit()

    conn.commit()
    conn.close()
    print(f"[done] Inserted {total_inserted} new examples into corpus_examples.")


def main():
    if not os.path.exists(LEMMA_CORPUS_PATH) or not os.path.exists(SURFACE_CORPUS_PATH):
        print("Lemma or surface corpus file not found. Check paths in the script.")
        return

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    print("Loading collocations from DB...")
    collocs_by_bigram, existing_counts = load_collocations(cur)
    conn.close()

    if not collocs_by_bigram:
        print("No collocations found in word_collocations (source='subtitles'). Nothing to do.")
        return

    print(f"Loaded {len(collocs_by_bigram)} lemma bigram keys.")
    print("Scanning corpus for more examples...")
    process_corpus(collocs_by_bigram, existing_counts)


if __name__ == "__main__":
    main()
