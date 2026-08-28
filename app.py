import os
from flask import Flask, render_template, request, redirect, url_for, session, flash
from db import init_db, get_db

app = Flask(__name__)

# 1. Automatically create PostgreSQL / SQLite tables on startup
init_db()

# 2. Configure Secret Key & 30-day Session Persistence
app.secret_key = os.environ.get('SECRET_KEY', 'martins_dematrix_secure_key_2026')
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['PERMANENT_SESSION_LIFETIME'] = 86400 * 30  # 30 Days

@app.before_request
def make_session_permanent():
    session.permanent = True

# --- App Routes ---

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        conn, db_type = get_db()
        cursor = conn.cursor()
        
        if db_type == 'postgres':
            cursor.execute("SELECT id, username, password FROM users WHERE username = %s AND password = %s", (username, password))
            user = cursor.fetchone()
        else:
            cursor.execute("SELECT id, username, password FROM users WHERE username = ? AND password = ?", (username, password))
            user = cursor.fetchone()
            
        conn.close()

        if user:
            # PostgreSQL returns tuple/dict; SQLite returns Row
            session['user_id'] = user[0] if isinstance(user, (tuple, list)) else user['id']
            session['username'] = user[1] if isinstance(user, (tuple, list)) else user['username']
            return redirect(url_for('dashboard'))
        else:
            flash("Invalid credentials")
            
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('dashboard.html', username=session.get('username'))

@app.route('/tasks')
def tasks():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    conn, db_type = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM tasks")
    
    if db_type == 'postgres':
        columns = [desc[0] for desc in cursor.description]
        tasks_list = [dict(zip(columns, row)) for row in cursor.fetchall()]
    else:
        tasks_list = cursor.fetchall()
        
    conn.close()
    return render_template('tasks.html', tasks=tasks_list)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
