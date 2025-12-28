# Finnish Vocabulary Learning Website

This project is a personal language-learning website designed to make Finnish vocabulary clearer,
more structured, and more usable in real contexts.

The focus is on **how words are actually used**, not just isolated dictionary definitions.
The site combines dictionary-style information with usage data and interactive study tools.

This is an evolving project and is actively being developed.

---

## ✨ What the site offers

- **Finnish words with multiple meanings and translations**
- **Difficulty levels (1–5, plus unranked)** to help structure learning
- **Topic categories and subcategories**
- **Multiple study views**:
  - table view
  - card view
  - flashcards
- **Word relationships** (e.g. shared roots, related meanings)
- **Usage-based word combinations** (see below)

Some features are still in progress and are marked accordingly in the interface.

---

## 🧠 Levels and difficulty

Each word is assigned a difficulty level from **1 to 5**, based on frequency, general usefulness,
and learner experience. These are **not official CEFR levels**, but a practical heuristic:

- **Level 1** – very common, essential vocabulary
- **Level 2** – common everyday words
- **Level 3** – intermediate vocabulary
- **Level 4** – less common or more specific words
- **Level 5** – advanced, abstract, or formal vocabulary
- **+** – words not yet ranked

The selected level filter stays active as you navigate the site.

---

## 📌 Word combinations and usage

In addition to single words, the project explores **common word combinations**
(e.g. adjective–noun, verb–object pairs).

These combinations are extracted automatically from a large Finnish subtitle corpus
and ranked using statistical association measures.
They are intended as **usage hints**, not fixed idioms.

### Example sentences

Some word combinations include example sentences taken from real subtitles.
These examples:

- reflect **authentic spoken Finnish**
- may be informal or conversational
- are not manually curated textbook examples

Examples are added gradually and may be hidden by default.
They are primarily meant to show **natural context**, not perfect model sentences.

---

## 📚 Data sources

- **Wiktionary**  
  Basic definitions and translations are derived from Wiktionary.  
  Wiktionary content is licensed under **CC BY-SA 4.0**.

- **OpenSubtitles (Finnish)**  
  Usage data and example sentences are extracted from Finnish subtitles.
  Subtitles are used only for statistical analysis and short illustrative examples.

---

## 🛠️ Technical overview

- Backend: Python (Flask), SQLite
- Data processing: Python (corpus analysis, statistics)
- Frontend: HTML templates, CSS, minimal JavaScript
- Admin interface for managing words, meanings, combinations, and examples

Large corpora and intermediate data files are **not included** in this repository.

---

## 🚧 Project status

This project is a work in progress.

Planned or ongoing improvements include:
- better search
- improved flashcards
- clearer grouping of word combinations
- selective curation of examples
- additional usage data

The goal is not to build a perfect dictionary, but a **practical learning tool**
that improves over time.

---

## 📄 License

The project code is released under an open-source license.
Third-party data sources retain their original licenses.
