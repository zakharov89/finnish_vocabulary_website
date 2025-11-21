#!/usr/bin/env python3
import sqlite3
import shutil
import os
from datetime import datetime

DB_PATH = "finnish.db"


def backup_database(path: str) -> str:
    if not os.path.exists(path):
        raise FileNotFoundError(f"Database not found at: {path}")

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"finnish_backup_before_schema_fix_{ts}.db"
    shutil.copy2(path, backup_name)
    print(f"[+] Backup created: {backup_name}")
    return backup_name


def get_table_sql(cur, table_name: str) -> str | None:
    cur.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,),
    )
    row = cur.fetchone()
    return row[0] if row and row[0] else None


def migrate_meanings(conn: sqlite3.Connection) -> None:
    cur = conn.cursor()
    sql = get_table_sql(cur, "meanings")
    if not sql:
        print("[!] Table 'meanings' does not exist. Skipping.")
        return

    if '"words_old"' not in sql and '"parts_of_speech_old"' not in sql:
        print("[=] 'meanings' already looks migrated (no *_old refs). Skipping.")
        return

    print("[*] Migrating 'meanings' table...")

    # Create new table with correct foreign keys
    cur.execute(
        """
        CREATE TABLE meanings_new (
            id INTEGER PRIMARY KEY,
            word_id INTEGER NOT NULL REFERENCES words(id),
            meaning_number INTEGER,
            notes TEXT,
            definition TEXT,
            pos_id INTEGER REFERENCES parts_of_speech(id)
        );
        """
    )

    # Copy data
    cur.execute(
        """
        INSERT INTO meanings_new (id, word_id, meaning_number, notes, definition, pos_id)
        SELECT id, word_id, meaning_number, notes, definition, pos_id
        FROM meanings;
        """
    )

    # Drop old and rename
    cur.execute("DROP TABLE meanings;")
    cur.execute("ALTER TABLE meanings_new RENAME TO meanings;")

    print("[+] 'meanings' migrated.")


def migrate_word_relations(conn: sqlite3.Connection) -> None:
    cur = conn.cursor()
    sql = get_table_sql(cur, "word_relations")
    if not sql:
        print("[!] Table 'word_relations' does not exist. Skipping.")
        return

    if '"words_old"' not in sql:
        print("[=] 'word_relations' already looks migrated (no words_old ref). Skipping.")
        return

    print("[*] Migrating 'word_relations' table...")

    # New table with correct FKs
    cur.execute(
        """
        CREATE TABLE word_relations_new (
            id INTEGER PRIMARY KEY,
            word1_id INTEGER NOT NULL REFERENCES words(id),
            word2_id INTEGER NOT NULL REFERENCES words(id),
            relation_type_id INTEGER NOT NULL REFERENCES relation_types(id),
            UNIQUE(word1_id, word2_id, relation_type_id)
        );
        """
    )

    # Copy data
    cur.execute(
        """
        INSERT INTO word_relations_new (id, word1_id, word2_id, relation_type_id)
        SELECT id, word1_id, word2_id, relation_type_id
        FROM word_relations;
        """
    )

    # Drop old and rename
    cur.execute("DROP TABLE word_relations;")
    cur.execute("ALTER TABLE word_relations_new RENAME TO word_relations;")

    print("[+] 'word_relations' migrated.")


def migrate_word_categories(conn: sqlite3.Connection) -> None:
    cur = conn.cursor()
    sql = get_table_sql(cur, "word_categories")
    if not sql:
        print("[!] Table 'word_categories' does not exist. Skipping.")
        return

    if '"words_old"' not in sql:
        print("[=] 'word_categories' already looks migrated (no words_old ref). Skipping.")
        return

    print("[*] Migrating 'word_categories' table...")

    # New table with correct FKs
    cur.execute(
        """
        CREATE TABLE word_categories_new (
            id INTEGER PRIMARY KEY,
            word_id INTEGER NOT NULL REFERENCES words(id),
            category_id INTEGER NOT NULL REFERENCES categories(id),
            sort_order INTEGER DEFAULT 0,
            meaning_id INTEGER REFERENCES meanings(id),
            UNIQUE(word_id, category_id)
        );
        """
    )

    # Copy data
    cur.execute(
        """
        INSERT INTO word_categories_new (id, word_id, category_id, sort_order, meaning_id)
        SELECT id, word_id, category_id, sort_order, meaning_id
        FROM word_categories;
        """
    )

    # Drop old and rename
    cur.execute("DROP TABLE word_categories;")
    cur.execute("ALTER TABLE word_categories_new RENAME TO word_categories;")

    print("[+] 'word_categories' migrated.")


def print_summary_schemas(conn: sqlite3.Connection) -> None:
    cur = conn.cursor()
    print("\n[Schema after migration]\n")

    for table in ("meanings", "word_relations", "word_categories"):
        sql = get_table_sql(cur, table)
        if sql:
            print(f"{table}:\n{sql}\n")
        else:
            print(f"{table}: (missing)\n")


def main():
    # 1) Backup
    backup_database(DB_PATH)

    # 2) Connect and migrate
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.cursor()
        # Disable FK checks during table rebuild
        cur.execute("PRAGMA foreign_keys = OFF;")

        # Wrap in a transaction
        conn.execute("BEGIN;")

        migrate_meanings(conn)
        migrate_word_relations(conn)
        migrate_word_categories(conn)

        # Commit all changes
        conn.commit()

        # Re-enable FK checks
        cur.execute("PRAGMA foreign_keys = ON;")

        print_summary_schemas(conn)
        print("[✓] Migration completed successfully.")

    except Exception as e:
        conn.rollback()
        print("[!] Migration failed, rolled back changes.")
        print("Error:", e)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
