from flask import Flask, render_template, request, jsonify, send_file
from datetime import datetime, timedelta
import sqlite3
import csv
import io

app = Flask(__name__)

def get_db_connection():
    conn = sqlite3.connect('tasks.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task TEXT NOT NULL,
            due_date TEXT,
            created_at TEXT NOT NULL,
            priority TEXT,
            category TEXT,
            completed BOOLEAN NOT NULL,
            completed_at TEXT
        )
    ''')
    conn.close()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/add_task', methods=['POST'])
def add_task():
    task = request.json['task']
    due_date = request.json.get('due_date')
    priority = request.json.get('priority')
    category = request.json.get('category')
    conn = get_db_connection()
    conn.execute('INSERT INTO tasks (task, due_date, priority, category, completed, created_at) VALUES (?, ?, ?, ?, ?, ?)',
                 (task, due_date, priority, category, False, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/get_tasks', methods=['GET'])
def get_tasks():
    order = request.args.get('order', 'asc')
    order_by = 'priority ASC' if order == 'asc' else 'priority DESC'
    conn = get_db_connection()
    active_tasks = conn.execute(f'SELECT id, task, due_date, created_at, priority, category FROM tasks WHERE completed = FALSE ORDER BY {order_by}').fetchall()
    completed_tasks = conn.execute('SELECT id, task, completed_at FROM tasks WHERE completed = TRUE ORDER BY completed_at DESC LIMIT 5').fetchall()
    conn.close()

    return jsonify({
        'active_tasks': [dict(row) for row in active_tasks],
        'completed_tasks': [dict(row) for row in completed_tasks]
    })

@app.route('/complete_task', methods=['POST'])
def complete_task():
    task_id = request.json['id']
    completed_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_db_connection()
    conn.execute('UPDATE tasks SET completed = TRUE, completed_at = ? WHERE id = ?', (completed_at, task_id))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/undo_task', methods=['POST'])
def undo_task():
    task_id = request.json['id']
    conn = get_db_connection()
    conn.execute('UPDATE tasks SET completed = FALSE, completed_at = NULL WHERE id = ?', (task_id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/edit_task', methods=['POST'])
def edit_task():
    task_id = request.json['id']
    task = request.json['task']
    due_date = request.json.get('due_date')
    priority = request.json.get('priority')
    category = request.json.get('category')
    conn = get_db_connection()
    conn.execute('UPDATE tasks SET task = ?, due_date = ?, priority = ?, category = ? WHERE id = ?',
                 (task, due_date, priority, category, task_id))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/delete_task', methods=['POST'])
def delete_task():
    task_id = request.json['id']
    conn = get_db_connection()
    conn.execute('DELETE FROM tasks WHERE id = ?', (task_id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/export_tasks')
def export_tasks():
    try:
        conn = get_db_connection()
        tasks = conn.execute('SELECT * FROM tasks').fetchall()
        conn.close()

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['id', 'task', 'due_date', 'created_at', 'priority', 'category', 'completed', 'completed_at'])
        for task in tasks:
            writer.writerow(task)

        output.seek(0)
        return send_file(
            io.BytesIO(output.getvalue().encode('utf-8')),
            mimetype='text/csv',
            as_attachment=True,
            download_name='tasks.csv'
        )
    except Exception as e:
        app.logger.error(f"Error exporting tasks: {str(e)}")
        return jsonify({'error': 'An error occurred while exporting tasks'}), 500

@app.route('/import_tasks', methods=['POST'])
def import_tasks():
    if 'file' not in request.files:
        return jsonify({'success': False, 'error': 'No file part'})
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'error': 'No selected file'})
    
    if file and file.filename.endswith('.csv'):
        try:
            conn = get_db_connection()
            csv_content = file.stream.read().decode("utf-8")
            csv_reader = csv.reader(csv_content.splitlines())
            next(csv_reader)  # Skip header row
            for row in csv_reader:
                conn.execute('''
                    INSERT OR REPLACE INTO tasks (id, task, due_date, created_at, priority, category, completed, completed_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', row)
            conn.commit()
            conn.close()
            return jsonify({'success': True})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)})
    else:
        return jsonify({'success': False, 'error': 'Invalid file type'})

if __name__ == '__main__':
    init_db()
    app.run(debug=True)