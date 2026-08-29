import os
import sys
import traceback
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from psycopg2.extras import RealDictCursor
from db import init_db, get_db, release_db

app = Flask(__name__)

# Fast Startup Init
try:
    init_db()
except Exception as e:
    print(f"DB Init Exception: {e}", file=sys.stderr)

app.secret_key = os.environ.get('SECRET_KEY', 'martins_dematrix_fast_key_2026')
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['PERMANENT_SESSION_LIFETIME'] = 86400 * 30

@app.before_request
def make_session_permanent():
    session.permanent = True

def execute_query(sql, params=(), fetch_one=False, fetch_all=False, commit=False):
    conn, db_type = get_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor) if db_type == 'postgres' else conn.cursor()
    result = None
    try:
        if db_type == 'postgres':
            sql = sql.replace('?', '%s')
        
        cursor.execute(sql, params)
        
        if commit:
            conn.commit()
        if fetch_one:
            res = cursor.fetchone()
            result = dict(res) if res else None
        elif fetch_all:
            res = cursor.fetchall()
            result = [dict(r) for r in res] if res else []
    except Exception as e:
        if conn and commit:
            conn.rollback()
        print(f"Database Query Error: {e}", file=sys.stderr)
        raise e
    finally:
        release_db(conn, db_type)
    return result

@app.route('/health')
def health():
    try:
        conn, db_type = get_db()
        release_db(conn, db_type)
        return jsonify({"status": "healthy", "database": db_type})
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/signup', methods=['GET', 'POST'])
@app.route('/register', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        
        if not username or not password:
            flash("Username and password are required.")
            return render_template('signup.html')

        hashed_password = generate_password_hash(password)
        
        try:
            execute_query(
                "INSERT INTO users (username, password, balance, is_admin) VALUES (?, ?, 0.0, 0)",
                (username, hashed_password),
                commit=True
            )
            flash("Account created successfully! Please log in.")
            return redirect(url_for('login'))
        except Exception as e:
            print(f"Signup Error: {traceback.format_exc()}", file=sys.stderr)
            flash("Username already exists or database connection failed.")
            
    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        
        user = execute_query(
            "SELECT * FROM users WHERE LOWER(username) = LOWER(?)",
            (username,),
            fetch_one=True
        )

        if user:
            stored_pwd = str(user.get('password', ''))
            if check_password_hash(stored_pwd, password):
                session['user_id'] = user.get('id')
                session['username'] = user.get('username')
                return redirect(url_for('dashboard'))
            
        flash("Invalid username or password.")
            
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    user = execute_query(
        "SELECT * FROM users WHERE id = ?",
        (session['user_id'],),
        fetch_one=True
    )
    
    if not user:
        session.clear()
        return redirect(url_for('login'))
        
    user_data = {
        'id': user.get('id'),
        'username': user.get('username', session.get('username')),
        'balance': float(user.get('balance', 0.0) or 0.0),
        'is_admin': user.get('is_admin', 0)
    }
    
    return render_template('dashboard.html', user=user_data, username=user_data['username'])

@app.route('/tasks')
def tasks():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    tasks_list = execute_query("SELECT * FROM tasks", fetch_all=True)
    return render_template('tasks.html', tasks=tasks_list)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
