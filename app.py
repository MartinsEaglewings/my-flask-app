import os
import sys
import traceback
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from db import init_db, get_db

app = Flask(__name__)

# Run DB Initialization safely
try:
    init_db()
except Exception as e:
    print(f"DB Init Exception: {e}", file=sys.stderr)

app.secret_key = os.environ.get('SECRET_KEY', 'martins_dematrix_secure_key_2026')
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['PERMANENT_SESSION_LIFETIME'] = 86400 * 30

@app.before_request
def make_session_permanent():
    session.permanent = True

def get_table_name(base_name):
    _, db_type = get_db()
    return f"app2_{base_name}" if db_type == 'postgres' else base_name

def query_one(sql, params=()):
    conn, db_type = get_db()
    cursor = conn.cursor()
    try:
        if db_type == 'postgres':
            sql = sql.replace('?', '%s')
        cursor.execute(sql, params)
        res = cursor.fetchone()
        return dict(res) if res else None
    except Exception as e:
        print(f"Database Query One Error: {e}", file=sys.stderr)
        return None
    finally:
        conn.close()

def query_all(sql, params=()):
    conn, db_type = get_db()
    cursor = conn.cursor()
    try:
        if db_type == 'postgres':
            sql = sql.replace('?', '%s')
        cursor.execute(sql, params)
        res = cursor.fetchall()
        return [dict(r) for r in res] if res else []
    except Exception as e:
        print(f"Database Query All Error: {e}", file=sys.stderr)
        return []
    finally:
        conn.close()

def execute_db(sql, params=()):
    conn, db_type = get_db()
    cursor = conn.cursor()
    try:
        if db_type == 'postgres':
            sql = sql.replace('?', '%s')
        cursor.execute(sql, params)
        conn.commit()
    except Exception as e:
        if conn:
            conn.rollback()
        print(f"Database Execute Error: {e}", file=sys.stderr)
        raise e
    finally:
        conn.close()

# --- Emergency Diagnostics Route ---
@app.route('/debug-db')
def debug_db():
    try:
        conn, db_type = get_db()
        cursor = conn.cursor()
        table = get_table_name('users')
        if db_type == 'postgres':
            cursor.execute(f"SELECT column_name, data_type FROM information_schema.columns WHERE table_name = '{table}';")
        else:
            cursor.execute(f"PRAGMA table_info({table});")
        cols = cursor.fetchall()
        conn.close()
        return jsonify({"status": "success", "db_type": db_type, "columns": [dict(c) if isinstance(c, dict) else c for c in cols]})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e), "traceback": traceback.format_exc()})

# --- Routes ---

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
        table = get_table_name('users')
        
        try:
            execute_db(
                f"INSERT INTO {table} (username, password, balance, is_admin) VALUES (?, ?, 0.0, 0)",
                (username, hashed_password)
            )
            flash("Account created successfully! Please log in.")
            return redirect(url_for('login'))
        except Exception as e:
            print(f"Signup Exception Trace: {traceback.format_exc()}", file=sys.stderr)
            flash("Username already exists or a database error occurred.")
            
    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        
        table = get_table_name('users')
        user = query_one(f"SELECT * FROM {table} WHERE LOWER(username) = LOWER(?)", (username,))

        if user:
            stored_pwd = str(user.get('password', ''))
            is_valid = False
            
            try:
                if stored_pwd and check_password_hash(stored_pwd, password):
                    is_valid = True
            except Exception:
                pass
                
            if not is_valid and stored_pwd == password:
                is_valid = True

            if is_valid:
                session['user_id'] = user.get('id')
                session['username'] = user.get('username')
                return redirect(url_for('dashboard'))
            
        flash("Invalid username or password.")
            
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    table = get_table_name('users')
    user = query_one(f"SELECT * FROM {table} WHERE id = ?", (session['user_id'],))
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
        
    table = get_table_name('tasks')
    tasks_list = query_all(f"SELECT * FROM {table}")
    return render_template('tasks.html', tasks=tasks_list)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
