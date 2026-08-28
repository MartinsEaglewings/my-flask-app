import sqlite3
import werkzeug.security
import uuid
from datetime import datetime, timedelta
from database import get_db

FAILED_ATTEMPTS = {}
LOCKOUT_TIME = timedelta(minutes=5)

def is_rate_limited(ip):
    now = datetime.now()
    if ip in FAILED_ATTEMPTS:
        attempts, lock_until = FAILED_ATTEMPTS[ip]
        if lock_until and now < lock_until:
            return True
        if lock_until and now >= lock_until:
            FAILED_ATTEMPTS[ip] = (0, None)
    return False

def record_failed_attempt(ip):
    now = datetime.now()
    attempts, _ = FAILED_ATTEMPTS.get(ip, (0, None))
    attempts += 1
    if attempts >= 5:
        FAILED_ATTEMPTS[ip] = (attempts, now + LOCKOUT_TIME)
    else:
        FAILED_ATTEMPTS[ip] = (attempts, None)

def register_user(username, email, password):
    db = get_db()
    pw_hash = werkzeug.security.generate_password_hash(password)
    try:
        db.execute(
            'INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)',
            (username, email, pw_hash)
        )
        db.commit()
        return True, None
    except sqlite3.IntegrityError as e:
        err_msg = str(e)
        if 'username' in err_msg:
            return False, "Username is already taken."
        elif 'email' in err_msg:
            return False, "Email is already registered."
        return False, "Account creation failed."

def authenticate_user(username, password):
    db = get_db()
    user = db.execute(
        'SELECT * FROM users WHERE username = ? OR email = ?', (username, username)
    ).fetchone()

    if not user:
        return None, "Invalid username or password."

    user_dict = dict(user)
    
    if user_dict.get('is_suspended', 0):
        return None, "Account is suspended."

    if werkzeug.security.check_password_hash(user_dict['password_hash'], password):
        return user_dict, None

    return None, "Invalid username or password."

def create_session(user_id):
    db = get_db()
    session_id = str(uuid.uuid4())
    expires_at = datetime.now() + timedelta(days=7)
    
    # Execute insert and IMMEDIATELY commit to release write-lock
    cursor = db.cursor()
    cursor.execute(
        'INSERT INTO sessions (id, user_id, expires_at) VALUES (?, ?, ?)',
        (session_id, user_id, expires_at.strftime('%Y-%m-%d %H:%M:%S'))
    )
    db.commit()
    return session_id
