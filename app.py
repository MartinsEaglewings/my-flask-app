import os
import sys
import traceback
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from db import init_db, get_db

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'martins_dematrix_fresh_key_2026')

# Run DB initialization
try:
    init_db()
except Exception as e:
    print(f"DB Init Failure: {e}", file=sys.stderr)

def fetch_user(username):
    conn, db_type = get_db()
    cursor = conn.cursor()
    try:
        sql = "SELECT * FROM users WHERE LOWER(username) = LOWER(%s)" if db_type == 'postgres' else "SELECT * FROM users WHERE LOWER(username) = LOWER(?)"
        cursor.execute(sql, (username,))
        res = cursor.fetchone()
        return dict(res) if res else None
    except Exception as e:
        print(f"Fetch User Error: {e}", file=sys.stderr)
        return None
    finally:
        conn.close()

def create_user(username, password):
    conn, db_type = get_db()
    cursor = conn.cursor()
    try:
        hashed_pwd = generate_password_hash(password)
        sql = "INSERT INTO users (username, password, balance, is_admin) VALUES (%s, %s, 0.0, 0)" if db_type == 'postgres' else "INSERT INTO users (username, password, balance, is_admin) VALUES (?, ?, 0.0, 0)"
        cursor.execute(sql, (username, hashed_pwd))
        if db_type == 'sqlite':
            conn.commit()
        return True
    except Exception as e:
        print(f"Create User Error: {e}", file=sys.stderr)
        return False
    finally:
        conn.close()

# Routes

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()

        if not username or not password:
            flash("Please enter both a username and password.")
            return render_template('signup.html')

        existing_user = fetch_user(username)
        if existing_user:
            flash("That username is already taken. Try logging in.")
            return render_template('signup.html')

        if create_user(username, password):
            flash("Account created! Please log in now.")
            return redirect(url_for('login'))
        else:
            flash("Database error creating account. Try again.")

    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()

        user = fetch_user(username)
        if user and check_password_hash(user.get('password', ''), password):
            session['user_id'] = user.get('id')
            session['username'] = user.get('username')
            return redirect(url_for('dashboard'))

        flash("Invalid username or password.")

    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('dashboard.html', username=session.get('username'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
