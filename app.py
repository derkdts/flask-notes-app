from flask import Flask, render_template, request, redirect, url_for
import sqlite3
import os
from datetime import datetime

app = Flask(__name__)
DB_PATH = 'notes.db'

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.execute('PRAGMA foreign_keys = ON')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
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
    conn.commit()
    conn.close()

@app.route('/')
def index():
    conn = get_db_connection()
    notes_rows = conn.execute('SELECT * FROM notes ORDER BY created_at DESC').fetchall()
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
def add_note():
    title = request.form.get('title')
    content = request.form.get('content')
    category_ids = request.form.getlist('category_ids')
    new_category_name = request.form.get('new_category')

    if title and content:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('INSERT INTO notes (title, content) VALUES (?, ?)', (title, content))
        note_id = cursor.lastrowid
        
        # Add existing categories
        for cat_id in category_ids:
            cursor.execute('INSERT INTO note_categories (note_id, category_id) VALUES (?, ?)', (note_id, cat_id))
        
        # Add new category if provided
        if new_category_name and new_category_name.strip():
            new_cat_name = new_category_name.strip()
            # Try to find or create
            cursor.execute('INSERT OR IGNORE INTO categories (name) VALUES (?)', (new_cat_name,))
            cursor.execute('SELECT id FROM categories WHERE name = ?', (new_cat_name,))
            cat_row = cursor.fetchone()
            if cat_row:
                cursor.execute('INSERT OR IGNORE INTO note_categories (note_id, category_id) VALUES (?, ?)', (note_id, cat_row[0]))
        
        conn.commit()
        conn.close()
    return redirect(url_for('index'))

@app.route('/admin')
def admin():
    conn = get_db_connection()
    notes_rows = conn.execute('SELECT * FROM notes ORDER BY created_at DESC').fetchall()
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
def delete_note(note_id):
    conn = get_db_connection()
    conn.execute('DELETE FROM notes WHERE id = ?', (note_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('admin'))

@app.route('/admin/categories')
def manage_categories():
    conn = get_db_connection()
    categories = conn.execute('SELECT * FROM categories ORDER BY name').fetchall()
    conn.close()
    return render_template('categories.html', categories=categories)

@app.route('/admin/categories/add', methods=['POST'])
def add_category():
    name = request.form.get('name')
    if name:
        conn = get_db_connection()
        conn.execute('INSERT OR IGNORE INTO categories (name) VALUES (?)', (name.strip(),))
        conn.commit()
        conn.close()
    return redirect(url_for('manage_categories'))

@app.route('/admin/categories/delete/<int:cat_id>')
def delete_category(cat_id):
    conn = get_db_connection()
    conn.execute('DELETE FROM categories WHERE id = ?', (cat_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('manage_categories'))

@app.route('/edit/<int:note_id>', methods=['GET', 'POST'])
def edit_note(note_id):
    conn = get_db_connection()
    if request.method == 'POST':
        title = request.form.get('title')
        content = request.form.get('content')
        category_ids = request.form.getlist('category_ids')
        new_category_name = request.form.get('new_category')

        if title and content:
            cursor = conn.cursor()
            cursor.execute('UPDATE notes SET title = ?, content = ? WHERE id = ?', (title, content, note_id))
            
            # Update categories: delete old ones, add new ones
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
