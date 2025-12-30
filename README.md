# Finnish Vocabulary Learning Website

The project is currently hosted on PythonAnywhere:
https://zakhar9.pythonanywhere.com

This project is a personal language-learning website designed to make Finnish vocabulary clearer,
more structured, and more usable in real contexts.

This is an evolving project and is actively being developed.

---

## What the site offers

- **Finnish words with multiple meanings and translations**
- **Difficulty levels (1–5)** to help structure learning
- **Topic categories and subcategories**
- **Multiple study views**:
  - table view
  - card view
  - flashcards
- **Word relationships** (e.g. shared roots, related meanings)
- **Usage-based word combinations** (see below)

---

## Levels and difficulty

Each word is assigned a difficulty level from **1 to 5**. These are not official CEFR levels, but a practical heuristic:

- **Level 1** – very common, essential vocabulary
- **Level 2** – common everyday words
- **Level 3** – intermediate vocabulary
- **Level 4** – less common or more specific words
- **Level 5** – advanced, abstract, or formal vocabulary
- **+** – words not yet ranked

The selected level filter stays active as you navigate the site.

---

## Word combinations and usage

In addition to single words, the project explores **common word combinations**. 
These combinations are extracted automatically from a large Finnish subtitle corpus
and ranked based on frequency.

Some word combinations include example sentences taken from real subtitles.
Examples are added gradually.

---

## Data sources

- **Wiktionary**  
  Basic translations are taken from Wiktionary.  
  Wiktionary content is licensed under **CC BY-SA 4.0**.

- **OpenSubtitles (Finnish)**  
  Usage data and example sentences are extracted from Finnish subtitles.
  Subtitles are used only for statistical analysis and short illustrative examples.

---

## Technical overview

- Backend: Python (Flask), SQLite
- Data processing: Python 
- Frontend: HTML, CSS, JavaScript
- Admin interface for managing words, meanings, combinations, and examples

Large corpora and intermediate data files are not included in this repository.

---



## License

The project code is released under an open-source license.
Third-party data sources retain their original licenses.
