
import sqlite3

def add_phone_column():
    conn = None
    try:
        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()

        cursor.execute('PRAGMA table_info(contacts)')
        existing_columns = {row[1] for row in cursor.fetchall()}
        if 'phone' in existing_columns:
            print("The 'phone' column already exists in the 'contacts' table.")
            return

        cursor.execute('ALTER TABLE contacts ADD COLUMN phone TEXT')

        conn.commit()
        print("Successfully added the 'phone' column to the 'contacts' table.")

    except sqlite3.Error as e:
        print(f"An error occurred: {e}")

    finally:
        if conn:
            conn.close()

if __name__ == '__main__':
    add_phone_column()
