import os
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from db import init_db, get_db

app = Flask(__name__)

# Automatically verify database tables on startup
init_db()

# Secret Key and Session Persistence Configuration
app.secret_key = os.environ.get('SECRET_KEY', 'martins_dematrix_secure_key_2026')
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['PERMANENT_SESSION_LIFETIME'] = 86400 * 30  # 30 Days persistence

@app.before_request
def make_session_permanent():
    session.permanent = True

# --- Application Routes ---

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
            if db_type == 'postgres':
                cursor.execute(
                    "INSERT INTO users (username, password, balance, is_admin) VALUES (%s, %s, 0.0, 0)",
                    (username, hashed_password)
                )
            else:
                cursor.execute(
                    "INSERT INTO users (username, password, balance, is_admin) VALUES (?, ?, 0.0, 0)",
                    (username, hashed_password)
                )
            conn.commit()
            conn.close()
            flash("Account created successfully! Please log in.")
            return redirect(url_for('login'))
        except Exception as e:
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
        
        if db_type == 'postgres':
            cursor.execute("SELECT id, username, password FROM users WHERE username = %s", (username,))
            user = cursor.fetchone()
        else:
            cursor.execute("SELECT id, username, password FROM users WHERE username = ?", (username,))
            user = cursor.fetchone()
            
        conn.close()

        if user:
            user_id = user[0] if isinstance(user, (tuple, list)) else user['id']
            stored_pwd = user[2] if isinstance(user, (tuple, list)) else user['password']
            
            # Check hashed password or plain text fallback
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
