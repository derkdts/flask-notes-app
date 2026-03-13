import sqlite3
import os

DB_PATH = 'notes.db'

def migrate():
    if not os.path.exists(DB_PATH):
        print("Database not found.")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # Check if user_id column exists
        cursor.execute("PRAGMA table_info(notes)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'user_id' not in columns:
            print("Adding user_id column to notes table...")
            cursor.execute("ALTER TABLE notes ADD COLUMN user_id INTEGER REFERENCES users(id) ON DELETE SET NULL")
            
            # Assign existing notes to the first user (usually admin, id=1)
            cursor.execute("SELECT id FROM users ORDER BY id LIMIT 1")
            first_user = cursor.fetchone()
            if first_user:
                print(f"Assigning existing notes to user ID {first_user[0]}")
                cursor.execute("UPDATE notes SET user_id = ?", (first_user[0],))
            
            conn.commit()
            print("Migration successful.")
        else:
            print("user_id column already exists.")

    except Exception as e:
        print(f"Error during migration: {e}")
    finally:
        conn.close()

if __name__ == '__main__':
    migrate()
