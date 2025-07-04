from flask import Flask, render_template, request, redirect, url_for, session, flash
import requests
import sqlite3
import os

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Telegram Bot configuration
# The token you provided is used here.
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '7983397749:AAFbfSoSoZp8Ic7rHMoSJLiaQeBeBSiIBlc')
# IMPORTANT: You need to get your Chat ID and add it below.
# 1. Open Telegram and search for the bot named "userinfobot".
# 2. Start a chat with "userinfobot" and it will immediately reply with your user details, including your "Id".
# 3. Replace 'YOUR_CHAT_ID' with that ID.
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID', '5783171867') # <-- REPLACE

ADMIN_PASSWORD = "iceberg12345"

def send_telegram_notification(message_text):
    """Sends a message to the configured Telegram chat."""
    if TELEGRAM_CHAT_ID == 'YOUR_CHAT_ID' or not TELEGRAM_BOT_TOKEN:
        app.logger.warning("Telegram notifications are not configured. Missing Bot Token or Chat ID.")
        return

    api_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    
    try:
        response = requests.post(api_url, json={'chat_id': TELEGRAM_CHAT_ID, 'text': message_text, 'parse_mode': 'Markdown'})
        response.raise_for_status()
        app.logger.info("Telegram notification sent successfully.")
    except requests.exceptions.RequestException as e:
        app.logger.error(f"Failed to send Telegram notification: {e}")

def init_db():
    with sqlite3.connect('database.db') as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS students (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_name TEXT NOT NULL,
                student_phone TEXT NOT NULL,
                dob TEXT NOT NULL,
                course TEXT NOT NULL
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS contacts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                phone TEXT,
                message TEXT NOT NULL,
                email TEXT
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
    
    with sqlite3.connect('database.db') as conn:
        conn.row_factory = sqlite3.Row # Allows accessing columns by name
        cursor = conn.cursor()
        
        # Get stats
        cursor.execute('SELECT COUNT(*) FROM students')
        total_students = cursor.fetchone()[0]
        cursor.execute('SELECT COUNT(*) FROM contacts')
        total_contacts = cursor.fetchone()[0]
        
        # Get recent students
        cursor.execute('SELECT * FROM students ORDER BY id DESC LIMIT 5')
        recent_students = cursor.fetchall()

        # Get recent contacts
        cursor.execute('SELECT * FROM contacts ORDER BY id DESC LIMIT 5')
        recent_contacts = cursor.fetchall()

    stats = {
        'total_students': total_students,
        'total_contacts': total_contacts
    }
    return render_template('admin_dashboard.html', stats=stats, recent_students=recent_students, recent_contacts=recent_contacts)

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
        message_body = request.form['message']
        
        with sqlite3.connect('database.db') as conn:
            cursor = conn.cursor()
            cursor.execute('INSERT INTO contacts (name, phone, message) VALUES (?, ?, ?)', (name, phone, message_body))
            conn.commit()

        # Send Telegram notification
        telegram_message = f"""
*Yangi Xabar!* 🚀

*Ism:* {name}
*Telefon:* `{phone}`

*Xabar:*
{message_body}
"""
        send_telegram_notification(telegram_message)

        flash('Xabaringiz uchun rahmat! Tez orada siz bilan bog\'lanamiz.', 'success')
        return redirect(url_for('contact'))
    return render_template('contact.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        student_name = request.form['student_name']
        student_phone = request.form['student_phone']
        dob = request.form['dob']
        course = request.form['course']
        
        with sqlite3.connect('database.db') as conn:
            cursor = conn.cursor()
            cursor.execute('''INSERT INTO students (student_name, student_phone, dob, course) 
                               VALUES (?, ?, ?, ?)''', 
                           (student_name, student_phone, dob, course))
            conn.commit()

        # Send Telegram notification for new registration
        telegram_message = f"""
*Kursga Yangi Yozilish!* 🎓

*O'quvchi:* {student_name}
*Telefon:* `{student_phone}`
*Kurs:* {course}
*Tug'ilgan sana:* {dob}
        """
        send_telegram_notification(telegram_message)

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

@app.route('/admin/delete_student/<int:student_id>', methods=['POST'])
def delete_student(student_id):
    if not session.get('logged_in'):
        return redirect(url_for('admin_login'))
    with sqlite3.connect('database.db') as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM students WHERE id = ?', (student_id,))
        conn.commit()
    flash('O\'quvchi muvaffaqiyatli o\'chirildi.', 'success')
    return redirect(url_for('students'))

@app.route('/admin/delete_contact/<int:contact_id>', methods=['POST'])
def delete_contact(contact_id):
    if not session.get('logged_in'):
        return redirect(url_for('admin_login'))
    with sqlite3.connect('database.db') as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM contacts WHERE id = ?', (contact_id,))
        conn.commit()
    flash('Xabar muvaffaqiyatli o\'chirildi.', 'success')
    return redirect(url_for('contacts_list'))

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8080)
