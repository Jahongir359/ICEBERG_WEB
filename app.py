from flask import Flask, render_template, request, redirect, url_for
import sqlite3

app = Flask(__name__)

# Function to create the database and tables
def init_db():
    with sqlite3.connect('database.db') as conn:
        cursor = conn.cursor()
        # Create students table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS students (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL,
                phone TEXT
            )
        ''')
        # Create contacts table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS contacts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL,
                message TEXT NOT NULL
            )
        ''')
        conn.commit()

# Call the function to ensure tables are created before the first request
init_db()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/questions')
def questions():
    return render_template('questions.html')

@app.route('/contacts')
def contacts_list():
    with sqlite3.connect('database.db') as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM contacts')
        contacts = cursor.fetchall()
    return render_template('contacts_list.html', contacts=contacts)

@app.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        message = request.form['message']
        
        with sqlite3.connect('database.db') as conn:
            cursor = conn.cursor()
            cursor.execute('INSERT INTO contacts (name, email, message) VALUES (?, ?, ?)', (name, email, message))
            conn.commit()
        return redirect(url_for('contact'))
    return render_template('contact.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        phone = request.form.get('phone') 
        
        with sqlite3.connect('database.db') as conn:
            cursor = conn.cursor()
            cursor.execute('INSERT INTO students (name, email, phone) VALUES (?, ?, ?)', (name, email, phone))
            conn.commit()
        return redirect(url_for('register'))
    return render_template('register.html')

# Admin pages to view data
@app.route('/admin/students')
def admin_students():
    with sqlite3.connect('database.db') as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM students')
        students = cursor.fetchall()
    return render_template('students.html', students=students)

@app.route('/admin/contacts')
def admin_contacts():
    with sqlite3.connect('database.db') as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM contacts')
        contacts = cursor.fetchall()
    return render_template('contacts_list.html', contacts=contacts)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
