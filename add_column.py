
import sqlite3

def add_phone_column():
    try:
        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        
        # Add the 'phone' column to the 'contacts' table
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
