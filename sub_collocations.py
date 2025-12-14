import os
import math
import pickle
from collections import Counter
import gzip
import csv

# ============================
# CONFIG
# ============================

LEMMA_CORPUS_PATH   = r"C:/Projects/Collocations/subtitles_lemmas_clean.txt"
SURFACE_CORPUS_PATH = r"C:/Projects/Collocations/subtitles_surface.txt"
VRT_ROOT = r"C:/Projects/Collocations/opensub-fi-2017-src"

CACHE_LEMMA_UNIGRAMS = "sub_cache_lemma_unigrams.pkl"
CACHE_LEMMA_BIGRAMS  = "sub_cache_lemma_bigrams.pkl"

# NEW VERSIONED CACHE NAME (prevents loading old tuple-format caches)
CACHE_BIGRAM_SURF    = "sub_cache_bigram_surface_v2.pkl"

CACHE_LEMMA_POS      = "sub_cache_lemma_pos.pkl"

DEFAULT_MIN_BIGRAM_FREQ   = 20
DEFAULT_MIN_UNIGRAM_FREQ  = 200
DEFAULT_TOP_N             = 30

EXPORT_TOP_N                = 50
EXPORT_MIN_BIGRAM_FREQ      = 2
EXPORT_MIN_UNIGRAM_FREQ     = 20
EXPORT_REQUIRE_POSITIVE_PMI = True

TSV_OUTPUT_DIR = "collocations_tsv"

# Max length in characters for exported surface_form
MAX_SURFACE_FORM_LEN = 80

# Keep only top-N surface variants per lemma bigram to keep cache small
MAX_SURFACE_VARIANTS_PER_BIGRAM = 8

# Lowercase surface forms on export?
LOWERCASE_SURFACE_ON_EXPORT = True

# ============================
# POS code mapping
# ============================

POS_CODE_TO_UPOS = {
    "N": "NOUN",
    "P": "PROPN",
    "V": "VERB",
    "A": "ADJ",
    "D": "ADV",
    "O": "PRON",
    "R": "ADP",
    "T": "DET",
    "M": "NUM",
    "U": "AUX",
    "C": "CCONJ",
    "S": "SCONJ",
    "I": "INTJ",
    "X": "X",
}

UPOS_TO_POS_CODE = {upos: code for code, upos in POS_CODE_TO_UPOS.items()}

# ============================
# FUNCTION WORD FILTERING
# ============================

FUNCTION_UPOS = {"PRON", "DET", "AUX", "CCONJ", "SCONJ"}

FUNCTION_LEMMA_STOPLIST = {
    "ei",

    "minä", "sinä", "hän", "me", "te", "he",
    "minun", "sinun", "hänen", "meidän", "teidän", "heidän",
    "tämä", "tuo", "se", "nämä", "nuo",
    "jokin", "joku", "joka", "jotka", "kukaan", "mikään", "moni",
    "itse",

    "mitä", "mikä", "miksi", "missä", "milloin", "miten", "kuka",

    "ja", "mutta", "tai", "sekä",
    "että", "jotta",
    "kun", "jos",
    "koska", "sillä",
    "vaikka", "vaan", "vai",

    "voida", "pitää", "täytyä", "saada", "pystyä", "aikoa",

    "nyt", "sitten", "niin", "vain", "juuri",
    "edes", "ikinä", "koskaan", "ehkä",

    "kanssa", "ilman", "kautta",
}

def is_function_word(lemma, lemma_pos):
    if lemma in FUNCTION_LEMMA_STOPLIST:
        return True
    if lemma_pos is None:
        return False
    upos = lemma_pos.get(lemma)
    if upos is None:
        return False
    return upos in FUNCTION_UPOS

# ============================
# CACHE HELPERS
# ============================

def save_cache(obj, path):
    with open(path, "wb") as f:
        pickle.dump(obj, f, protocol=pickle.HIGHEST_PROTOCOL)

def load_cache(path):
    with open(path, "rb") as f:
        return pickle.load(f)

# ============================
# COUNTING: UNIGRAMS + BIGRAMS
# ============================

def _trim_top_surface_variants(entry, max_keep):
    """
    entry["surf_counts"] is a dict {(s1,s2): count}
    Keep only top max_keep by count. Also drop examples for removed keys.
    """
    surf_counts = entry["surf_counts"]
    if len(surf_counts) <= max_keep:
        return

    items = sorted(surf_counts.items(), key=lambda x: -x[1])
    keep_keys = set(k for k, _ in items[:max_keep])

    # drop old keys
    for k in list(surf_counts.keys()):
        if k not in keep_keys:
            del surf_counts[k]

    ex_map = entry["example_for_surface"]
    for k in list(ex_map.keys()):
        if k not in keep_keys:
            del ex_map[k]

def build_counts(lemma_path, surface_path):
    """
    Build:
      - lemma_unigrams: Counter[lemma] -> freq
      - lemma_bigrams: Counter[(l1, l2)] -> freq
      - bigram_surface: dict[(l1, l2)] -> {
            "surf_counts": dict[(s1,s2)] -> count,
            "example_for_surface": dict[(s1,s2)] -> example_sentence (one sentence that contains that exact surface)
        }

    IMPORTANT: we keep only top-N surface variants per lemma bigram to keep cache small.
    """
    def is_content_lemma(tok: str) -> bool:
        return any(ch.isalnum() for ch in tok)

    lemma_unigrams = Counter()
    lemma_bigrams = Counter()
    bigram_surface = {}

    total_lines = 0

    with open(lemma_path, "r", encoding="utf-8") as f_lem, \
         open(surface_path, "r", encoding="utf-8") as f_surf:

        for lem_line, surf_line in zip(f_lem, f_surf):
            total_lines += 1
            if total_lines % 500_000 == 0:
                print(f"[build_counts] Processed {total_lines} lines...", flush=True)

            lem_tokens = lem_line.strip().split()
            surf_tokens = surf_line.strip().split()
            if not lem_tokens:
                continue

            if len(lem_tokens) != len(surf_tokens):
                length = min(len(lem_tokens), len(surf_tokens))
                lem_tokens = lem_tokens[:length]
                surf_tokens = surf_tokens[:length]

            surface_sentence = " ".join(surf_tokens)
            surface_sentence_low = surface_sentence.lower()

            # unigrams
            for lem in lem_tokens:
                if not is_content_lemma(lem):
                    continue
                lemma_unigrams[lem] += 1

            # bigrams + surface variants
            for i in range(len(lem_tokens) - 1):
                l1 = lem_tokens[i]
                l2 = lem_tokens[i + 1]
                if not (is_content_lemma(l1) and is_content_lemma(l2)):
                    continue

                bigram = (l1, l2)
                lemma_bigrams[bigram] += 1

                s1 = surf_tokens[i] if i < len(surf_tokens) else ""
                s2 = surf_tokens[i + 1] if (i + 1) < len(surf_tokens) else ""
                surf_key = (s1, s2)

                entry = bigram_surface.get(bigram)
                if entry is None:
                    entry = {"surf_counts": {}, "example_for_surface": {}}
                    bigram_surface[bigram] = entry

                # update count
                d = entry["surf_counts"]
                d[surf_key] = d.get(surf_key, 0) + 1

                # store an example ONLY if the sentence actually contains this exact surface bigram
                # (prevents mismatches)
                if surf_key not in entry["example_for_surface"]:
                    bigram_str = f"{s1} {s2}".strip().lower()
                    if bigram_str and bigram_str in surface_sentence_low:
                        entry["example_for_surface"][surf_key] = surface_sentence

                # trim occasionally (cheap guard against explosion)
                if len(entry["surf_counts"]) > MAX_SURFACE_VARIANTS_PER_BIGRAM * 2:
                    _trim_top_surface_variants(entry, MAX_SURFACE_VARIANTS_PER_BIGRAM)

    # final trim pass
    for entry in bigram_surface.values():
        _trim_top_surface_variants(entry, MAX_SURFACE_VARIANTS_PER_BIGRAM)

    print("[build_counts] Done.")
    print("  Total lines:   ", total_lines)
    print("  Total tokens:  ", sum(lemma_unigrams.values()))
    print("  Unique lemmas: ", len(lemma_unigrams))
    print("  Unique bigrams:", len(lemma_bigrams))
    print("  Surface cache bigrams:", len(bigram_surface))

    return lemma_unigrams, lemma_bigrams, bigram_surface

# ============================
# POS FROM VRT
# ============================

def build_lemma_pos_from_vrt(vrt_root):
    lemma_pos = {}
    file_count = 0
    line_count = 0

    for root, dirs, files in os.walk(vrt_root):
        for fname in files:
            fn = fname.lower()
            if not (fn.endswith(".vrt") or fn.endswith(".vrt.gz")):
                continue

            path = os.path.join(root, fname)
            file_count += 1
            print(f"[POS] Reading {path}")

            if fn.endswith(".gz"):
                f = gzip.open(path, "rt", encoding="utf-8", errors="ignore")
            else:
                f = open(path, "r", encoding="utf-8", errors="ignore")

            with f:
                for raw in f:
                    line_count += 1
                    if line_count % 1_000_000 == 0:
                        print(f"[POS] {line_count} lines processed...", flush=True)

                    line = raw.strip()
                    if not line or line.startswith("<"):
                        continue

                    parts = line.split("\t")
                    if len(parts) < 4:
                        continue

                    lemma_raw = parts[2].lower()
                    lemma_clean = lemma_raw.replace("#", "")
                    upos = parts[3]

                    if lemma_clean and lemma_clean not in lemma_pos:
                        lemma_pos[lemma_clean] = upos

    print("[POS] Done.")
    print("  Files processed:        ", file_count)
    print("  Unique lemmas with POS: ", len(lemma_pos))

    return lemma_pos

# ============================
# PMI
# ============================

def compute_totals(lemma_unigrams, lemma_bigrams):
    total_tokens = sum(lemma_unigrams.values())
    total_bigrams = sum(lemma_bigrams.values())
    return total_tokens, total_bigrams

def pmi(l1, l2, freq12, lemma_unigrams, total_tokens, total_bigrams):
    f1 = lemma_unigrams.get(l1, 0)
    f2 = lemma_unigrams.get(l2, 0)
    if f1 == 0 or f2 == 0:
        return None

    p12 = freq12 / total_bigrams
    p1 = f1 / total_tokens
    p2 = f2 / total_tokens

    if p12 <= 0 or p1 <= 0 or p2 <= 0:
        return None

    return math.log(p12 / (p1 * p2))

# ============================
# POS HELPERS
# ============================

def print_pos_help():
    print("\nPOS codes:")
    print("  N = NOUN      P = PROPN     V = VERB      A = ADJ")
    print("  D = ADV       O = PRON      R = ADP       T = DET")
    print("  M = NUM       U = AUX       C = CCONJ     S = SCONJ")
    print("  I = INTJ      X = X")
    print("You can use these one-letter codes, or full UPOS names (e.g. ADJ, NOUN).\n")

def parse_pos_code_or_upos(s):
    s = s.strip().upper()
    if not s:
        return None
    if len(s) == 1 and s in POS_CODE_TO_UPOS:
        return POS_CODE_TO_UPOS[s]
    known_upos = set(POS_CODE_TO_UPOS.values())
    if s in known_upos:
        return s
    return None

def parse_pos_list(s):
    if not s:
        return None
    items = []
    for part in s.split(","):
        tag = parse_pos_code_or_upos(part)
        if tag is not None:
            items.append(tag)
    return set(items) if items else None

def parse_pos_pattern(s):
    if not s or "+" not in s:
        return None
    left, right = [p.strip() for p in s.split("+", 1)]
    up1 = parse_pos_code_or_upos(left)
    up2 = parse_pos_code_or_upos(right)
    if up1 is None or up2 is None:
        return None
    return (up1, up2)

def shorten(text, max_len=140):
    text = text.strip()
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."

# ============================
# SURFACE FORM HELPER (FIXED)
# ============================

def choose_representative_surface(entry, max_len_chars=None):
    """
    Choose a surface (s1,s2) AND an example sentence that contains that exact surface.
    No fallback to an example from another variant (prevents lemma/surface mismatch).

    Returns: (s1, s2, example_sentence) or ("", "", "") if no safe match found.
    """
    if not entry or not isinstance(entry, dict):
        return "", "", ""

    surf_counts = entry.get("surf_counts") or {}
    examples = entry.get("example_for_surface") or {}
    if not surf_counts or not examples:
        return "", "", ""

    items = list(surf_counts.items())  # [((s1,s2), count), ...]
    items.sort(key=lambda x: (-x[1], len(f"{x[0][0]} {x[0][1]}".strip())))

    def fits_len(s1, s2):
        if max_len_chars is None:
            return True
        return len(f"{s1} {s2}".strip()) <= max_len_chars

    for (s1, s2), _cnt in items:
        if not fits_len(s1, s2):
            continue
        sent = examples.get((s1, s2))
        if not sent:
            continue
        bigram = f"{s1} {s2}".strip().lower()
        if bigram and bigram in sent.lower():
            return s1, s2, sent

    return "", "", ""

# ============================
# COLLOCATIONS
# ============================

def top_global_collocations(
    lemma_unigrams,
    lemma_bigrams,
    bigram_surface,
    lemma_pos=None,
    skip_propn_pairs=True,
    min_bigram_freq=DEFAULT_MIN_BIGRAM_FREQ,
    min_unigram_freq=DEFAULT_MIN_UNIGRAM_FREQ,
    top_n=50,
    require_positive_pmi=True,
    pos_pattern=None,
):
    total_tokens, total_bigrams = compute_totals(lemma_unigrams, lemma_bigrams)
    results = []

    for (l1, l2), freq12 in lemma_bigrams.items():
        if freq12 < min_bigram_freq:
            continue

        f1 = lemma_unigrams.get(l1, 0)
        f2 = lemma_unigrams.get(l2, 0)
        if f1 < min_unigram_freq or f2 < min_unigram_freq:
            continue

        pos1 = lemma_pos.get(l1) if lemma_pos is not None else None
        pos2 = lemma_pos.get(l2) if lemma_pos is not None else None

        if skip_propn_pairs and lemma_pos is not None:
            if pos1 == "PROPN" and pos2 == "PROPN":
                continue

        if lemma_pos is not None:
            if is_function_word(l1, lemma_pos) or is_function_word(l2, lemma_pos):
                continue

        if pos_pattern is not None and lemma_pos is not None:
            wanted1, wanted2 = pos_pattern
            if pos1 != wanted1 or pos2 != wanted2:
                continue

        val = pmi(l1, l2, freq12, lemma_unigrams, total_tokens, total_bigrams)
        if val is None:
            continue
        if require_positive_pmi and val <= 0:
            continue

        entry = bigram_surface.get((l1, l2))
        s1, s2, sent = choose_representative_surface(entry, max_len_chars=MAX_SURFACE_FORM_LEN)
        if not s1 or not s2 or not sent:
            continue

        results.append((val, freq12, l1, l2, s1, s2, sent))

    results.sort(key=lambda x: (-x[0], -x[1]))
    return results[:top_n]

def collocates_for_lemma(
    target,
    lemma_unigrams,
    lemma_bigrams,
    bigram_surface,
    lemma_pos=None,
    min_bigram_freq=DEFAULT_MIN_BIGRAM_FREQ,
    min_unigram_freq=DEFAULT_MIN_UNIGRAM_FREQ,
    top_n=30,
    allowed_other_pos=None,
    direction="both",
    require_positive_pmi=True,
    surface_substring=None,
):
    if target not in lemma_unigrams:
        print(f"'{target}' not found in lemma vocabulary.")
        return []

    total_tokens, total_bigrams = compute_totals(lemma_unigrams, lemma_bigrams)
    collocates = []
    sub = surface_substring.lower() if surface_substring else None

    for (l1, l2), freq12 in lemma_bigrams.items():
        if freq12 < min_bigram_freq:
            continue

        if direction == "right":
            if l1 != target:
                continue
            other = l2
        elif direction == "left":
            if l2 != target:
                continue
            other = l1
        else:
            if l1 != target and l2 != target:
                continue
            other = l2 if l1 == target else l1

        if lemma_unigrams.get(other, 0) < min_unigram_freq:
            continue

        if lemma_pos is not None and is_function_word(other, lemma_pos):
            continue

        if allowed_other_pos is not None and lemma_pos is not None:
            pos_other = lemma_pos.get(other)
            if pos_other not in allowed_other_pos:
                continue

        val = pmi(l1, l2, freq12, lemma_unigrams, total_tokens, total_bigrams)
        if val is None:
            continue
        if require_positive_pmi and val <= 0:
            continue

        entry = bigram_surface.get((l1, l2))
        s1, s2, sent = choose_representative_surface(entry, max_len_chars=MAX_SURFACE_FORM_LEN)
        if not s1 or not s2 or not sent:
            continue

        if sub is not None:
            if sub not in s1.lower() and sub not in s2.lower():
                continue

        collocates.append((other, val, freq12, l1, l2, s1, s2, sent))

    collocates.sort(key=lambda x: (-x[2], -x[1]))
    return collocates[:top_n]

# ============================
# TSV EXPORT
# ============================

def ensure_tsv_dir():
    os.makedirs(TSV_OUTPUT_DIR, exist_ok=True)

def export_collocations_to_tsv(
    target,
    lemma_unigrams,
    lemma_bigrams,
    bigram_surface,
    lemma_pos=None,
):
    if target not in lemma_unigrams:
        print(f"'{target}' not found in lemma vocabulary, cannot export TSV.")
        return

    ensure_tsv_dir()
    out_path = os.path.join(TSV_OUTPUT_DIR, f"{target}.tsv")

    results = collocates_for_lemma(
        target,
        lemma_unigrams,
        lemma_bigrams,
        bigram_surface,
        lemma_pos=lemma_pos,
        min_bigram_freq=EXPORT_MIN_BIGRAM_FREQ,
        min_unigram_freq=EXPORT_MIN_UNIGRAM_FREQ,
        top_n=EXPORT_TOP_N,
        allowed_other_pos=None,
        direction="both",
        require_positive_pmi=EXPORT_REQUIRE_POSITIVE_PMI,
        surface_substring=None,
    )

    if not results:
        print(f"No collocates found for '{target}' with export thresholds.")
        return

    with open(out_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, delimiter="\t")
        writer.writerow([
            "word",
            "other_form",
            "surface_form",
            "direction",
            "freq",
            "pmi",
            "example_sentence",
        ])

        for other, pmi_val, freq, l1, l2, s1, s2, sent in results:
            if l1 == target and l2 == other:
                direction = "R"
            elif l2 == target and l1 == other:
                direction = "L"
            else:
                direction = "B"

            surface_form = f"{s1} {s2}".strip()
            if LOWERCASE_SURFACE_ON_EXPORT:
                surface_form = surface_form.lower()

            writer.writerow([
                target,
                other,
                surface_form,
                direction,
                freq,
                f"{pmi_val:.4f}",
                sent.strip(),
            ])

    print(f"Exported {len(results)} collocations for '{target}' to: {out_path}")

# ============================
# MAIN
# ============================

def main():
    # 1) counts
    if (os.path.exists(CACHE_LEMMA_UNIGRAMS) and
        os.path.exists(CACHE_LEMMA_BIGRAMS) and
        os.path.exists(CACHE_BIGRAM_SURF)):
        print("Loading cached counts...")
        lemma_unigrams = load_cache(CACHE_LEMMA_UNIGRAMS)
        lemma_bigrams  = load_cache(CACHE_LEMMA_BIGRAMS)
        bigram_surface = load_cache(CACHE_BIGRAM_SURF)
        print("Loaded from cache.")
        print("  Unique lemmas:  ", len(lemma_unigrams))
        print("  Unique bigrams: ", len(lemma_bigrams))
        print("  Surface cache bigrams:", len(bigram_surface))
    else:
        print("Building counts from corpus...")
        lemma_unigrams, lemma_bigrams, bigram_surface = build_counts(
            LEMMA_CORPUS_PATH,
            SURFACE_CORPUS_PATH,
        )
        print("Saving caches...")
        save_cache(lemma_unigrams, CACHE_LEMMA_UNIGRAMS)
        save_cache(lemma_bigrams,  CACHE_LEMMA_BIGRAMS)
        save_cache(bigram_surface, CACHE_BIGRAM_SURF)
        print("Caches saved.")

    # 2) POS
    if os.path.exists(CACHE_LEMMA_POS):
        print("Loading cached lemma POS...")
        lemma_pos = load_cache(CACHE_LEMMA_POS)
    else:
        print("Building lemma POS map from VRT...")
        lemma_pos = build_lemma_pos_from_vrt(VRT_ROOT)
        print("Saving lemma POS cache...")
        save_cache(lemma_pos, CACHE_LEMMA_POS)

    total_tokens, total_bigrams = compute_totals(lemma_unigrams, lemma_bigrams)
    print("\nCorpus summary:")
    print("  Total tokens:    ", total_tokens)
    print("  Total bigrams:   ", total_bigrams)
    print("  Vocabulary size: ", len(lemma_unigrams))
    print("  Bigram types:    ", len(lemma_bigrams))
    print("  Lemmas with POS: ", len(lemma_pos))

    print_pos_help()

    print("Commands:")
    print("  • Enter a lemma (e.g. hyvä, mennä, katsoa) to see its collocates")
    print("  • Enter 'TOP' to see top global collocations")
    print("  • Enter 'TSV' to export top 50 collocates for a lemma to TSV")
    print("  • Enter empty line to quit.")

    while True:
        raw = input("\nLemma or command: ").strip()
        if not raw:
            break

        cmd = raw.upper()

        if cmd == "TSV":
            target = input("Lemma to export (e.g. hyvä): ").strip()
            if not target:
                print("No lemma given.")
                continue
            export_collocations_to_tsv(
                target,
                lemma_unigrams,
                lemma_bigrams,
                bigram_surface,
                lemma_pos=lemma_pos,
            )
            continue

        if cmd == "TOP":
            try:
                n_str = input("How many top collocations? [default=50]: ").strip()
                top_n = int(n_str) if n_str else 50
            except ValueError:
                top_n = 50

            try:
                mbf_str = input(
                    f"Minimum bigram frequency [default={DEFAULT_MIN_BIGRAM_FREQ}]: "
                ).strip()
                min_bigram_freq = int(mbf_str) if mbf_str else DEFAULT_MIN_BIGRAM_FREQ
            except ValueError:
                min_bigram_freq = DEFAULT_MIN_BIGRAM_FREQ

            try:
                muf_str = input(
                    f"Minimum unigram frequency [default={DEFAULT_MIN_UNIGRAM_FREQ}]: "
                ).strip()
                min_unigram_freq = int(muf_str) if muf_str else DEFAULT_MIN_UNIGRAM_FREQ
            except ValueError:
                min_unigram_freq = DEFAULT_MIN_UNIGRAM_FREQ

            skip_pp_input = input("Skip PROPN–PROPN pairs? [Y/n]: ").strip().lower()
            skip_propn_pairs = (skip_pp_input != "n")

            pos_pat_str = input(
                "POS pattern filter for bigrams (e.g. A+N, ADJ+NOUN, empty for none): "
            ).strip().upper()
            pos_pattern = parse_pos_pattern(pos_pat_str) if pos_pat_str else None

            results = top_global_collocations(
                lemma_unigrams,
                lemma_bigrams,
                bigram_surface,
                lemma_pos=lemma_pos,
                skip_propn_pairs=skip_propn_pairs,
                min_bigram_freq=min_bigram_freq,
                min_unigram_freq=min_unigram_freq,
                top_n=top_n,
                require_positive_pmi=True,
                pos_pattern=pos_pattern,
            )

            if not results:
                print("No collocations found with these thresholds.")
                continue

            print(f"\nTop {len(results)} global collocations:")
            for pmi_val, freq, l1, l2, s1, s2, sent in results:
                example_bigram = f"{s1} {s2}".strip()
                print(
                    f"{l1:<15} {l2:<15}  "
                    f"PMI={pmi_val:6.2f}  freq={freq:7d}  "
                    f"example='{example_bigram}'"
                )
                print(f"    sentence: {shorten(sent)}")

            continue

        # lemma mode
        target = raw
        if target not in lemma_unigrams:
            print(f"'{target}' not found in lemma vocabulary (or too rare).")
            continue

        try:
            mbf_str = input(f"Minimum bigram frequency [default={DEFAULT_MIN_BIGRAM_FREQ}]: ").strip()
            min_bigram_freq = int(mbf_str) if mbf_str else DEFAULT_MIN_BIGRAM_FREQ
        except ValueError:
            min_bigram_freq = DEFAULT_MIN_BIGRAM_FREQ

        try:
            muf_str = input(f"Minimum collocate unigram frequency [default={DEFAULT_MIN_UNIGRAM_FREQ}]: ").strip()
            min_unigram_freq = int(muf_str) if muf_str else DEFAULT_MIN_UNIGRAM_FREQ
        except ValueError:
            min_unigram_freq = DEFAULT_MIN_UNIGRAM_FREQ

        try:
            top_str = input(f"How many collocates to show? [default={DEFAULT_TOP_N}]: ").strip()
            top_n = int(top_str) if top_str else DEFAULT_TOP_N
        except ValueError:
            top_n = DEFAULT_TOP_N

        dir_str = input("Direction [L=left, R=right, B=both, default=B]: ").strip().lower()
        if not dir_str:
            direction = "both"
        else:
            c = dir_str[0]
            if c == "l":
                direction = "left"
            elif c == "r":
                direction = "right"
            else:
                direction = "both"

        surface_sub = input("Surface substring filter (optional, e.g. 'hyv'): ").strip()
        if not surface_sub:
            surface_sub = None

        coll_pos_str = input("Restrict collocate POS (e.g. N,P or ADJ,NOUN, empty for none): ").strip().upper()
        allowed_other_pos = parse_pos_list(coll_pos_str) if coll_pos_str else None

        results = collocates_for_lemma(
            target,
            lemma_unigrams,
            lemma_bigrams,
            bigram_surface,
            lemma_pos=lemma_pos,
            min_bigram_freq=min_bigram_freq,
            min_unigram_freq=min_unigram_freq,
            top_n=top_n,
            allowed_other_pos=allowed_other_pos,
            direction=direction,
            require_positive_pmi=True,
            surface_substring=surface_sub,
        )

        if not results:
            print("No collocates satisfying the filters.")
            continue

        print(
            f"\nBest collocates for lemma '{target}' "
            f"(min_bigram_freq={min_bigram_freq}, "
            f"min_unigram_freq={min_unigram_freq}, "
            f"direction={direction}, "
            f"surface_filter={surface_sub!r}, "
            f"coll_POS={allowed_other_pos}):"
        )

        for other, pmi_val, freq, l1, l2, s1, s2, sent in results:
            example_bigram = f"{s1} {s2}".strip()
            print(
                f"  {target:<15} + {other:<15}  "
                f"PMI={pmi_val:6.2f}  bigram_freq={freq:7d}  "
                f"example='{example_bigram}'"
            )
            print(f"      sentence: {shorten(sent)}")

if __name__ == "__main__":
    main()
