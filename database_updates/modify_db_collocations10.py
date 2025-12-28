import sqlite3

DB_PATH = "finnish.db"
conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

print("Deleting ALL subtitles collocations and examples...")

# 1) Delete examples linked to any subtitles-collocation
cur.execute("""
    DELETE FROM corpus_examples
    WHERE collocation_id IN (
        SELECT id FROM word_collocations
        WHERE source = 'subtitles'
    )
""")

# 2) Delete standalone subtitles examples
cur.execute("""
    DELETE FROM corpus_examples
    WHERE source = 'subtitles'
""")

# 3) Delete collocations themselves
cur.execute("""
    DELETE FROM word_collocations
    WHERE source = 'subtitles'
""")

conn.commit()
conn.close()

print("Global subtitles cleanup complete.")
