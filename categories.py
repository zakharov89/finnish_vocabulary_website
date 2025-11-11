import sqlite3


# ===== Database functions =====
def create_category(cur, conn, name, parent_id=None):
    """Create a new category and return its ID."""
    cur.execute(
        "INSERT INTO categories (name, parent_id) VALUES (?, ?)",
        (name, parent_id)
    )
    conn.commit()
    return cur.lastrowid

def search_words(cur, query):
    """Search for words starting with the query."""
    cur.execute(
        "SELECT id, word FROM words WHERE word LIKE ? ORDER BY word",
        (f"{query}%",)
    )
    return cur.fetchall()

def assign_word_to_category(cur, conn, word_id, category_id):
    """Assign a word to a category."""
    cur.execute(
        "INSERT OR IGNORE INTO word_categories (word_id, category_id) VALUES (?, ?)",
        (word_id, category_id)
    )
    conn.commit()

def remove_word_from_category(cur, conn, word_id, category_id):
    """Remove a word from a category without deleting the word itself."""
    cur.execute(
        "DELETE FROM word_categories WHERE word_id = ? AND category_id = ?",
        (word_id, category_id)
    )
    conn.commit()


def choose_word(cur):
    """Ask user to search and select a word."""
    while True:
        query = input("Enter a Finnish word (or part of it, blank to stop): ").strip()
        if not query:
            return None

        results = search_words(cur, query)
        if not results:
            print("No matching words found.")
            continue

        print("\nMatching words:")
        for i, row in enumerate(results, 1):
            print(f"{i}: {row['word']}")

        choice = input("Select the number of the word to assign (or blank to search again): ").strip()
        if not choice:
            continue
        try:
            index = int(choice) - 1
            if 0 <= index < len(results):
                return results[index]['id'], results[index]['word']
            else:
                print("Invalid selection.")
        except ValueError:
            print("Enter a valid number.")

def choose_category(cur, conn):
    """Ask user to choose a category or create a new one, with suggestions."""
    
    # Fetch existing categories
    cur.execute("SELECT id, name FROM categories ORDER BY name")
    categories = cur.fetchall()
    
    if categories:
        print("\nExisting categories:")
        for cat in categories:
            print(f"{cat['id']}: {cat['name']}")
    else:
        print("No categories exist yet.")
    
    # Ask user
    name_or_id = input("Enter category name or ID (leave blank to skip): ").strip()
    if not name_or_id:
        return None, None

    # Check if input is an integer (ID)
    try:
        category_id = int(name_or_id)
        # Verify ID exists
        cur.execute("SELECT name FROM categories WHERE id = ?", (category_id,))
        row = cur.fetchone()
        if row:
            return category_id, row['name']
        else:
            print("No category with that ID.")
            return choose_category(cur, conn)
    except ValueError:
        # Treat as name
        name = name_or_id
        # Check if category already exists
        cur.execute("SELECT id FROM categories WHERE name = ?", (name,))
        row = cur.fetchone()
        if row:
            return row['id'], name
        else:
            # Create new category
            parent = input("Parent category ID (or leave blank): ").strip()
            parent_id = int(parent) if parent else None
            new_id = create_category(cur, conn, name, parent_id)
            print(f"Created new category '{name}' with ID {new_id}")
            return new_id, name


# ===== Main interactive loop =====
def main():
    conn = sqlite3.connect("finnish.db")
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    print("=== Category Assignment ===")
    while True:
        word_choice = choose_word(cur)
        if not word_choice:
            print("Exiting.")
            break
        word_id, word_text = word_choice

        category_choice = choose_category(cur, conn)
        if not category_choice:
            print("No category chosen. Skipping word.\n")
            continue
        category_id, category_name = category_choice

        assign_word_to_category(cur, conn, word_id, category_id)
        print(f"Word '{word_text}' assigned to category '{category_name}' successfully.\n")

    conn.close()

if __name__ == "__main__":
    main()
