from flask import Flask, render_template, request, redirect, url_for, flash, session
import sqlite3
import os
from datetime import datetime, timedelta
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config['SECRET_KEY'] = 'dev-secret-key-change-this'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=1)
DB_PATH = 'notes.db'

login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.init_app(app)

class User(UserMixin):
    def __init__(self, id, username, role):
        self.id = id
        self.username = username
        self.role = role

@login_manager.user_loader
def load_user(user_id):
    conn = get_db_connection()
    user_row = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    conn.close()
    if user_row:
        return User(user_row['id'], user_row['username'], user_row['role'])
    return None

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.execute('PRAGMA foreign_keys = ON')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            role TEXT DEFAULT 'user'
        );
        CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE SET NULL
        );
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE
        );
        CREATE TABLE IF NOT EXISTS note_categories (
            note_id INTEGER,
            category_id INTEGER,
            FOREIGN KEY(note_id) REFERENCES notes(id) ON DELETE CASCADE,
            FOREIGN KEY(category_id) REFERENCES categories(id) ON DELETE CASCADE,
            PRIMARY KEY (note_id, category_id)
        );
    ''')
    # Create default admin if not exists
    admin_exists = conn.execute('SELECT * FROM users WHERE username = ?', ('admin',)).fetchone()
    if not admin_exists:
        hashed_pw = generate_password_hash('admin')
        conn.execute('INSERT INTO users (username, password, role) VALUES (?, ?, ?)', ('admin', hashed_pw, 'admin'))
    
    conn.commit()
    conn.close()

@app.route('/welcome')
def welcome():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    return render_template('welcome.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        conn = get_db_connection()
        user_row = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        conn.close()
        
        if user_row and check_password_hash(user_row['password'], password):
            user = User(user_row['id'], user_row['username'], user_row['role'])
            login_user(user)
            session.permanent = True
            return redirect(url_for('index'))
        flash('Неверное имя пользователя или пароль')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if not username or not password:
            flash('Пожалуйста, заполните все поля')
            return render_template('register.html')
            
        hashed_pw = generate_password_hash(password)
        conn = get_db_connection()
        try:
            conn.execute('INSERT INTO users (username, password) VALUES (?, ?)', (username, hashed_pw))
            conn.commit()
            conn.close()
            flash('Регистрация успешна! Теперь вы можете войти.')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('Пользователь с таким именем уже существует')
            conn.close()
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('welcome'))

@app.route('/')
@login_required
def index():
    conn = get_db_connection()
    if current_user.role == 'admin':
        notes_rows = conn.execute('SELECT * FROM notes ORDER BY created_at DESC').fetchall()
    else:
        notes_rows = conn.execute('SELECT * FROM notes WHERE user_id = ? ORDER BY created_at DESC', (current_user.id,)).fetchall()
    notes = []
    for row in notes_rows:
        note = dict(row)
        categories = conn.execute('''
            SELECT c.name FROM categories c
            JOIN note_categories nc ON c.id = nc.category_id
            WHERE nc.note_id = ?
        ''', (note['id'],)).fetchall()
        note['categories'] = [c['name'] for c in categories]
        notes.append(note)
    
    all_categories = conn.execute('SELECT * FROM categories ORDER BY name').fetchall()
    conn.close()
    return render_template('index.html', notes=notes, all_categories=all_categories)

@app.route('/add', methods=['POST'])
@login_required
def add_note():
    title = request.form.get('title')
    content = request.form.get('content')
    category_ids = request.form.getlist('category_ids')
    new_category_name = request.form.get('new_category')

    if title and content:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('INSERT INTO notes (user_id, title, content) VALUES (?, ?, ?)', (current_user.id, title, content))
        note_id = cursor.lastrowid
        
        for cat_id in category_ids:
            cursor.execute('INSERT INTO note_categories (note_id, category_id) VALUES (?, ?)', (note_id, cat_id))
        
        if new_category_name and new_category_name.strip():
            new_cat_name = new_category_name.strip()
            cursor.execute('INSERT OR IGNORE INTO categories (name) VALUES (?)', (new_cat_name,))
            cursor.execute('SELECT id FROM categories WHERE name = ?', (new_cat_name,))
            cat_row = cursor.fetchone()
            if cat_row:
                cursor.execute('INSERT OR IGNORE INTO note_categories (note_id, category_id) VALUES (?, ?)', (note_id, cat_row[0]))
        
        conn.commit()
        conn.close()
    return redirect(url_for('index'))

@app.route('/admin')
@login_required
def admin():
    if current_user.role != 'admin':
        return redirect(url_for('index'))
    conn = get_db_connection()
    notes_rows = conn.execute('''
        SELECT n.*, u.username as author 
        FROM notes n 
        LEFT JOIN users u ON n.user_id = u.id 
        ORDER BY n.created_at DESC
    ''').fetchall()
    notes = []
    for row in notes_rows:
        note = dict(row)
        categories = conn.execute('''
            SELECT c.name FROM categories c
            JOIN note_categories nc ON c.id = nc.category_id
            WHERE nc.note_id = ?
        ''', (note['id'],)).fetchall()
        note['categories'] = [c['name'] for c in categories]
        notes.append(note)
    conn.close()
    return render_template('admin.html', notes=notes)

@app.route('/delete/<int:note_id>')
@login_required
def delete_note(note_id):
    conn = get_db_connection()
    note = conn.execute('SELECT user_id FROM notes WHERE id = ?', (note_id,)).fetchone()
    if not note:
        conn.close()
        return "Note not found", 404
        
    if current_user.role != 'admin' and note['user_id'] != current_user.id:
        conn.close()
        flash('У вас нет прав для удаления этой заметки')
        return redirect(url_for('index'))

    conn.execute('DELETE FROM notes WHERE id = ?', (note_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('admin' if current_user.role == 'admin' else 'index'))

@app.route('/admin/categories')
@login_required
def manage_categories():
    if current_user.role != 'admin':
        return redirect(url_for('index'))
    conn = get_db_connection()
    categories = conn.execute('SELECT * FROM categories ORDER BY name').fetchall()
    conn.close()
    return render_template('categories.html', categories=categories)

@app.route('/admin/categories/add', methods=['POST'])
@login_required
def add_category():
    if current_user.role != 'admin':
        return redirect(url_for('index'))
    name = request.form.get('name')
    if name:
        conn = get_db_connection()
        conn.execute('INSERT OR IGNORE INTO categories (name) VALUES (?)', (name.strip(),))
        conn.commit()
        conn.close()
    return redirect(url_for('manage_categories'))

@app.route('/admin/categories/delete/<int:cat_id>')
@login_required
def delete_category(cat_id):
    if current_user.role != 'admin':
        return redirect(url_for('index'))
    conn = get_db_connection()
    conn.execute('DELETE FROM categories WHERE id = ?', (cat_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('manage_categories'))

@app.route('/admin/stats')
@login_required
def stats():
    if current_user.role != 'admin':
        return redirect(url_for('index'))
    conn = get_db_connection()
    stat_rows = conn.execute('''
        SELECT c.name, COUNT(nc.note_id) as count
        FROM categories c
        LEFT JOIN note_categories nc ON c.id = nc.category_id
        GROUP BY c.id
        ORDER BY count DESC
    ''').fetchall()
    conn.close()
    return render_template('stats.html', stats=stat_rows)

@app.route('/admin/users')
@login_required
def manage_users():
    if current_user.role != 'admin':
        return redirect(url_for('index'))
    conn = get_db_connection()
    users = conn.execute('SELECT id, username, role FROM users').fetchall()
    conn.close()
    return render_template('users.html', users=users)

@app.route('/admin/users/delete/<int:user_id>')
@login_required
def delete_user(user_id):
    if current_user.role != 'admin' or current_user.id == user_id:
        return redirect(url_for('manage_users'))
    conn = get_db_connection()
    conn.execute('DELETE FROM users WHERE id = ?', (user_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('manage_users'))

@app.route('/edit/<int:note_id>', methods=['GET', 'POST'])
@login_required
def edit_note(note_id):
    conn = get_db_connection()
    note_row = conn.execute('SELECT * FROM notes WHERE id = ?', (note_id,)).fetchone()
    
    if not note_row:
        conn.close()
        return "Note not found", 404
        
    if current_user.role != 'admin' and note_row['user_id'] != current_user.id:
        conn.close()
        flash('У вас нет прав для редактирования этой заметки')
        return redirect(url_for('index'))
    if request.method == 'POST':
        title = request.form.get('title')
        content = request.form.get('content')
        category_ids = request.form.getlist('category_ids')
        new_category_name = request.form.get('new_category')

        if title and content:
            cursor = conn.cursor()
            cursor.execute('UPDATE notes SET title = ?, content = ? WHERE id = ?', (title, content, note_id))
            cursor.execute('DELETE FROM note_categories WHERE note_id = ?', (note_id,))
            for cat_id in category_ids:
                cursor.execute('INSERT INTO note_categories (note_id, category_id) VALUES (?, ?)', (note_id, cat_id))
            
            if new_category_name and new_category_name.strip():
                new_cat_name = new_category_name.strip()
                cursor.execute('INSERT OR IGNORE INTO categories (name) VALUES (?)', (new_cat_name,))
                cursor.execute('SELECT id FROM categories WHERE name = ?', (new_cat_name,))
                cat_row = cursor.fetchone()
                if cat_row:
                    cursor.execute('INSERT OR IGNORE INTO note_categories (note_id, category_id) VALUES (?, ?)', (note_id, cat_row[0]))
            
            conn.commit()
            conn.close()
            return redirect(url_for('admin'))
    
    note_row = conn.execute('SELECT * FROM notes WHERE id = ?', (note_id,)).fetchone()
    if not note_row:
        conn.close()
        return "Note not found", 404
    
    note = dict(note_row)
    selected_categories = conn.execute('SELECT category_id FROM note_categories WHERE note_id = ?', (note_id,)).fetchall()
    note['category_ids'] = [c[0] for c in selected_categories]
    
    all_categories = conn.execute('SELECT * FROM categories ORDER BY name').fetchall()
    conn.close()
    return render_template('edit.html', note=note, all_categories=all_categories)

if __name__ == '__main__':
    init_db()
    app.run(debug=True, port=5000)
