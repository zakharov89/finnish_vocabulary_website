import sqlite3

# ===== Database helpers =====
def list_categories(cur):
    cur.execute("SELECT id, name, parent_id FROM categories ORDER BY name")
    rows = cur.fetchall()
    if not rows:
        print("No categories found.")
    else:
        print("\nCategories:")
        for row in rows:
            parent = row['parent_id'] if row['parent_id'] else "-"
            print(f"{row['id']}: {row['name']} (Parent ID: {parent})")
    return rows

def create_category(cur, conn):
    name = input("Enter new category name: ").strip()
    if not name:
        return
    parent = input("Parent category ID (or leave blank): ").strip()
    parent_id = int(parent) if parent else None
    cur.execute("INSERT INTO categories (name, parent_id) VALUES (?, ?)", (name, parent_id))
    conn.commit()
    print(f"Category '{name}' created with ID {cur.lastrowid}")

def modify_category(cur, conn):
    list_categories(cur)
    cat_id = input("Enter category ID to modify: ").strip()
    if not cat_id.isdigit():
        print("Invalid ID.")
        return
    cat_id = int(cat_id)
    
    new_name = input("Enter new name (leave blank to keep current): ").strip()
    new_parent = input("Enter new parent ID (leave blank to keep current, 0 for no parent): ").strip()
    
    if new_parent == "0":
        new_parent_id = None
    elif new_parent == "":
        new_parent_id = None
    else:
        new_parent_id = int(new_parent)
    
    if new_name:
        cur.execute("UPDATE categories SET name = ? WHERE id = ?", (new_name, cat_id))
    if new_parent:
        cur.execute("UPDATE categories SET parent_id = ? WHERE id = ?", (new_parent_id, cat_id))
    conn.commit()
    print("Category updated.")

def delete_category(cur, conn):
    list_categories(cur)
    cat_id = input("Enter category ID to delete: ").strip()
    if not cat_id.isdigit():
        print("Invalid ID.")
        return
    cat_id = int(cat_id)
    
    # Check if any words assigned
    cur.execute("SELECT COUNT(*) FROM word_categories WHERE category_id = ?", (cat_id,))
    count = cur.fetchone()[0]
    if count > 0:
        confirm = input(f"{count} words are assigned to this category. Are you sure? (y/n): ").strip().lower()
        if confirm != 'y':
            print("Deletion cancelled.")
            return
    
    cur.execute("DELETE FROM word_categories WHERE category_id = ?", (cat_id,))
    cur.execute("DELETE FROM categories WHERE id = ?", (cat_id,))
    conn.commit()
    print("Category deleted.")

# ===== Main menu =====
def main():
    conn = sqlite3.connect("finnish.db")
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    
    while True:
        print("\n=== Category Management ===")
        print("1. List categories")
        print("2. Create category")
        print("3. Modify category")
        print("4. Delete category")
        print("5. Exit")
        choice = input("Choose an option: ").strip()
        
        if choice == "1":
            list_categories(cur)
        elif choice == "2":
            create_category(cur, conn)
        elif choice == "3":
            modify_category(cur, conn)
        elif choice == "4":
            delete_category(cur, conn)
        elif choice == "5":
            break
        else:
            print("Invalid choice. Try again.")
    
    conn.close()

if __name__ == "__main__":
    main()
