import os
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from db import init_db, get_db

app = Flask(__name__)

# Initialize DB tables automatically on startup
init_db()

# Session Settings
app.secret_key = os.environ.get('SECRET_KEY', 'martins_dematrix_secure_key_2026')
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['PERMANENT_SESSION_LIFETIME'] = 86400 * 30

@app.before_request
def make_session_permanent():
    session.permanent = True

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
        username = request.form.get('username')
        password = request.form.get('password')
        
        if not username or not password:
            flash("Username and password are required.")
            return render_template('signup.html')

        hashed_password = generate_password_hash(password)
        conn, db_type = get_db()
        cursor = conn.cursor()
        
        try:
            placeholder = "%s" if db_type == 'postgres' else "?"
            cursor.execute(
                f"INSERT INTO users (username, password, balance, is_admin) VALUES ({placeholder}, {placeholder}, 0.0, 0)",
                (username, hashed_password)
            )
            conn.commit()
            conn.close()
            flash("Account created successfully! Please log in.")
            return redirect(url_for('login'))
        except Exception:
            conn.close()
            flash("Username already exists or an error occurred.")
            
    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        conn, db_type = get_db()
        cursor = conn.cursor()
        
        placeholder = "%s" if db_type == 'postgres' else "?"
        cursor.execute(f"SELECT * FROM users WHERE username = {placeholder}", (username,))
        user = cursor.fetchone()
        conn.close()

        if user:
            # Handle dictionary access safely for both Postgres & SQLite
            user_id = user['id']
            stored_pwd = user['password']
            
            if check_password_hash(stored_pwd, password) or stored_pwd == password:
                session['user_id'] = user_id
                session['username'] = username
                return redirect(url_for('dashboard'))
            
        flash("Invalid username or password.")
            
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    conn, db_type = get_db()
    cursor = conn.cursor()
    placeholder = "%s" if db_type == 'postgres' else "?"
    cursor.execute(f"SELECT * FROM users WHERE id = {placeholder}", (session['user_id'],))
    user = cursor.fetchone()
    conn.close()
    
    return render_template('dashboard.html', user=user, username=session.get('username'))

@app.route('/tasks')
def tasks():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    conn, db_type = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM tasks")
    tasks_list = cursor.fetchall()
    conn.close()
    
    return render_template('tasks.html', tasks=tasks_list)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
