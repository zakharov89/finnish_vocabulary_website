import sqlite3

conn = sqlite3.connect("finnish.db")
cur = conn.cursor()

def add_column_if_missing(table_name, column_name, column_def):
    cur.execute(f"PRAGMA table_info({table_name});")
    columns = [col[1] for col in cur.fetchall()]
    if column_name not in columns:
        cur.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_def};")
        print(f"Added '{column_name}' column to {table_name}")
        return True
    else:
        print(f"'{column_name}' column already exists in {table_name}")
        return False

# =========================
# Words table
# =========================
if add_column_if_missing('words', 'language', "TEXT NOT NULL DEFAULT 'fi'"):
    pass  # Default handled by column definition

if add_column_if_missing('words', 'created_at', "TEXT"):
    cur.execute("UPDATE words SET created_at = datetime('now') WHERE created_at IS NULL;")

if add_column_if_missing('words', 'updated_at', "TEXT"):
    cur.execute("UPDATE words SET updated_at = datetime('now') WHERE updated_at IS NULL;")

# Trigger for words.updated_at
try:
    cur.execute("""
        CREATE TRIGGER IF NOT EXISTS trigger_update_words_updated_at
        AFTER UPDATE ON words
        FOR EACH ROW
        BEGIN
            UPDATE words SET updated_at = datetime('now') WHERE id = OLD.id;
        END;
    """)
    print("Created trigger for words.updated_at")
except sqlite3.OperationalError as e:
    print("Trigger for words.updated_at already exists or error:", e)

# =========================
# Categories table
# =========================
if add_column_if_missing('categories', 'language', "TEXT NOT NULL DEFAULT 'fi'"):
    pass

if add_column_if_missing('categories', 'created_at', "TEXT"):
    cur.execute("UPDATE categories SET created_at = datetime('now') WHERE created_at IS NULL;")

if add_column_if_missing('categories', 'updated_at', "TEXT"):
    cur.execute("UPDATE categories SET updated_at = datetime('now') WHERE updated_at IS NULL;")

# Trigger for categories.updated_at
try:
    cur.execute("""
        CREATE TRIGGER IF NOT EXISTS trigger_update_categories_updated_at
        AFTER UPDATE ON categories
        FOR EACH ROW
        BEGIN
            UPDATE categories SET updated_at = datetime('now') WHERE id = OLD.id;
        END;
    """)
    print("Created trigger for categories.updated_at")
except sqlite3.OperationalError as e:
    print("Trigger for categories.updated_at already exists or error:", e)

cur.execute(""" ALTER TABLE categories ADD COLUMN sort_order INTEGER DEFAULT 0; """)


conn.commit()
conn.close()
print("Migration complete!")
