from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
import os

app = Flask(__name__)
app.secret_key = os.urandom(24)

ADMIN_PASSWORD = "iceberg_admin_2025"

def init_db():
    with sqlite3.connect('database.db') as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS students (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_name TEXT NOT NULL,
                student_phone TEXT NOT NULL,
                parent_name TEXT NOT NULL,
                parent_phone TEXT NOT NULL,
                course TEXT NOT NULL
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS contacts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                phone TEXT NOT NULL,
                message TEXT NOT NULL
            )
        ''')
        conn.commit()

init_db()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/our_programs')
def our_programs():
    return render_template('our_programs.html')

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    error = None
    if request.method == 'POST':
        password = request.form['password']
        if password == ADMIN_PASSWORD:
            session['logged_in'] = True
            flash('Muvaffaqiyatli kirdingiz!', 'success')
            return redirect(url_for('admin_dashboard'))
        else:
            error = 'Parol noto\'g\'ri. Iltimos, qayta urinib ko\'ring.'
    return render_template('admin_login.html', error=error)

@app.route('/admin/logout')
def logout():
    session.pop('logged_in', None)
    flash('Siz tizimdan chiqdingiz.', 'info')
    return redirect(url_for('index'))

@app.route('/admin/dashboard')
def admin_dashboard():
    if not session.get('logged_in'):
        return redirect(url_for('admin_login'))
    return redirect(url_for('students'))

@app.route('/contacts_list')
def contacts_list():
    if not session.get('logged_in'):
        return redirect(url_for('admin_login'))
    with sqlite3.connect('database.db') as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM contacts')
        contacts = cursor.fetchall()
    return render_template('contacts_list.html', contacts=contacts)

@app.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        name = request.form['name']
        phone = request.form['phone']
        message = request.form['message']
        
        with sqlite3.connect('database.db') as conn:
            cursor = conn.cursor()
            cursor.execute('INSERT INTO contacts (name, phone, message) VALUES (?, ?, ?)', (name, phone, message))
            conn.commit()
        flash('Xabaringiz uchun rahmat! Tez orada siz bilan bog\'lanamiz.', 'success')
        return redirect(url_for('contact'))
    return render_template('contact.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        student_name = request.form['student_name']
        student_phone = request.form['student_phone']
        parent_name = request.form['parent_name']
        parent_phone = request.form['parent_phone']
        course = request.form['course']
        
        with sqlite3.connect('database.db') as conn:
            cursor = conn.cursor()
            cursor.execute('''INSERT INTO students (student_name, student_phone, parent_name, parent_phone, course) 
                               VALUES (?, ?, ?, ?, ?)''', 
                           (student_name, student_phone, parent_name, parent_phone, course))
            conn.commit()
        flash('Siz muvaffaqiyatli ro\'yxatdan o\'tdingiz!', 'success')
        return redirect(url_for('register'))
    return render_template('register.html')

@app.route('/students')
def students():
    if not session.get('logged_in'):
        return redirect(url_for('admin_login'))
    with sqlite3.connect('database.db') as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM students')
        students = cursor.fetchall()
    return render_template('students.html', students=students)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
