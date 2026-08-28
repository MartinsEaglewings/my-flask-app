from flask import Flask, render_template, render_template_string, request, redirect, url_for, make_response, jsonify, session
from database import get_db, init_db
from datetime import datetime, timedelta
import random
import auth
import models

app = Flask(__name__)
app.secret_key = 'martins-app-secret-key'

init_db()

ADMIN_KEY = "martins_pass_2026"

ADMIN_LOGIN_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link rel="stylesheet" href="/static/css/style.css">
    <title>System Access</title>
</head>
<body>
    <div class="container" style="max-width:350px; margin-top:50px; padding: 20px;">
        <h3>Admin Access</h3>
        {% if error %}
            <p style="color: #ef4444;">{{ error }}</p>
        {% endif %}
        <form method="POST" action="/admin/login">
            <label style="display:block; margin-bottom:6px;">Secret Key</label>
            <input type="password" name="admin_key" placeholder="Enter key" required style="width:100%; padding:8px; margin-bottom:12px;">
            <button type="submit" style="width:100%; padding:8px;">Authenticate</button>
        </form>
    </div>
</body>
</html>
"""

ADMIN_DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link rel="stylesheet" href="/static/css/style.css">
    <title>Admin Dashboard</title>
</head>
<body>
    <div class="container" style="padding:15px;">
        <h2>Admin Overview</h2>
        
        <h3>Registered Users & Balances</h3>
        <div style="overflow-x:auto;">
            <table style="width:100%; border-collapse:collapse; text-align:left; background:#1e293b; color:#fff; font-size:0.85rem;">
                <thead>
                    <tr style="border-bottom:1px solid #334155;">
                        <th style="padding:8px;">User</th>
                        <th style="padding:8px;">Earned</th>
                        <th style="padding:8px;">Withdrawn</th>
                        <th style="padding:8px;">Available</th>
                    </tr>
                </thead>
                <tbody>
                    {% for u in users %}
                    <tr style="border-bottom:1px solid #334155;">
                        <td style="padding:8px;">{{ u.username }}<br><small style="color:#94a3b8">{{ u.email }}</small></td>
                        <td style="padding:8px; color:#22c55e;">${{ u.total_earnings }}</td>
                        <td style="padding:8px; color:#ef4444;">${{ u.total_withdrawn }}</td>
                        <td style="padding:8px; font-weight:bold;">${{ u.available_balance }}</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>

        <h3 style="margin-top:25px;">All Withdrawal Requests</h3>
        {% for w in withdrawals %}
        <div class="card" style="margin-bottom:8px; font-size:0.85rem; padding: 10px; background: #1e293b; border-radius: 6px;">
            <strong>{{ w.username }}</strong> requested <strong>${{ w.formatted_amount }}</strong><br>
            <small>Method: {{ w.payment_method }} | Account: {{ w.account_details }}</small><br>
            <small style="color:#94a3b8">Date: {{ w.created_at }}</small>
        </div>
        {% else %}
        <p>No withdrawals logged yet.</p>
        {% endfor %}
        
        <br>
        <a href="/logout" style="color:#ef4444; display: inline-block; margin-top: 15px;">Exit Admin</a>
    </div>
</body>
</html>
"""

def safe_float(val):
    try:
        return float(val or 0.0)
    except (ValueError, TypeError):
        return 0.0

def get_current_user():
    token = request.cookies.get('session_id')
    if not token:
        return None
    db = get_db()
    user_session = db.execute(
        'SELECT u.* FROM sessions s JOIN users u ON s.user_id = u.id WHERE s.id = ? AND s.expires_at > CURRENT_TIMESTAMP',
        (token,)
    ).fetchone()
    return user_session

@app.route('/')
def home():
    user = get_current_user()
    if user:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()
        
        if not username or not email or not password:
            return render_template('signup.html', error="All fields are required.")
            
        success, err = auth.register_user(username, email, password)
        if success:
            return redirect(url_for('login'))
        return render_template('signup.html', error=err)
    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        ip = request.remote_addr or '127.0.0.1'
        if auth.is_rate_limited(ip):
            return render_template('login.html', error="Too many failed attempts. Wait 5 minutes.")
        
        user, err = auth.authenticate_user(request.form.get('username'), request.form.get('password'))
        if user:
            token = auth.create_session(user['id'])
            resp = make_response(redirect(url_for('dashboard')))
            resp.set_cookie('session_id', token, httponly=True, path='/')
            return resp
        auth.record_failed_attempt(ip)
        return render_template('login.html', error=err)
    return render_template('login.html')

@app.route('/logout')
def logout():
    token = request.cookies.get('session_id')
    if token:
        db = get_db()
        db.execute('DELETE FROM sessions WHERE id = ?', (token,))
        db.commit()
    session.pop('is_admin', None)
    resp = make_response(redirect(url_for('login')))
    resp.set_cookie('session_id', '', expires=0, path='/')
    return resp

# Secret Admin Routes
@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    error = None
    if request.method == 'POST':
        key = request.form.get('admin_key', '').strip()
        if key == ADMIN_KEY:
            session['is_admin'] = True
            return redirect(url_for('admin_dashboard'))
        else:
            error = "Invalid Security Key"
    return render_template_string(ADMIN_LOGIN_HTML, error=error)

@app.route('/admin')
def admin_dashboard():
    if not session.get('is_admin'):
        return redirect(url_for('admin_login'))
    
    db = get_db()
    users = db.execute('SELECT id, username, email FROM users').fetchall()
    
    users_data = []
    for u in users:
        bal = models.calculate_user_balances(u['id'])
        users_data.append({
            'id': u['id'],
            'username': u['username'],
            'email': u['email'],
            'total_earnings': f"{safe_float(bal.get('total_earnings')):.2f}",
            'total_withdrawn': f"{safe_float(bal.get('total_withdrawn')):.2f}",
            'available_balance': f"{safe_float(bal.get('available_balance')):.2f}"
        })

    raw_withdrawals = db.execute('''
        SELECT w.*, u.username 
        FROM withdrawals w 
        JOIN users u ON w.user_id = u.id 
        ORDER BY w.created_at DESC
    ''').fetchall()

    withdrawals_data = []
    for w in raw_withdrawals:
        w_dict = dict(w)
        w_dict['formatted_amount'] = f"{safe_float(w_dict.get('amount')):.2f}"
        withdrawals_data.append(w_dict)

    return render_template_string(ADMIN_DASHBOARD_HTML, users=users_data, withdrawals=withdrawals_data)

@app.route('/dashboard')
def dashboard():
    user = get_current_user()
    if not user:
        return redirect(url_for('login'))
    
    db = get_db()
    balances = models.calculate_user_balances(user['id'])
    
    last_spin = db.execute(
        'SELECT spun_at FROM daily_spins WHERE user_id = ? ORDER BY spun_at DESC LIMIT 1', (user['id'],)
    ).fetchone()
    
    can_spin = True
    if last_spin:
        try:
            last_time = datetime.strptime(last_spin['spun_at'], '%Y-%m-%d %H:%M:%S')
            if datetime.now() - last_time < timedelta(hours=24):
                can_spin = False
        except Exception:
            can_spin = True

    transactions = db.execute(
        'SELECT * FROM transactions WHERE user_id = ? ORDER BY timestamp DESC LIMIT 10', (user['id'],)
    ).fetchall()
    
    return render_template('dashboard.html', user=user, balances=balances, transactions=transactions or [], can_spin=can_spin)

@app.route('/spin', methods=['POST'])
def spin_wheel():
    user = get_current_user()
    if not user:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401

    db = get_db()
    last_spin = db.execute(
        'SELECT spun_at FROM daily_spins WHERE user_id = ? ORDER BY spun_at DESC LIMIT 1', (user['id'],)
    ).fetchone()

    if last_spin:
        try:
            last_time = datetime.strptime(last_spin['spun_at'], '%Y-%m-%d %H:%M:%S')
            if datetime.now() - last_time < timedelta(hours=24):
                return jsonify({'success': False, 'message': 'Daily spin already claimed today!'}), 400
        except Exception:
            pass

    wheels_options = [3, 5, 0, 20, 0.5, 0, 50]
    selected_reward = random.choice(wheels_options)
    reward_index = wheels_options.index(selected_reward)

    db.execute('INSERT INTO daily_spins (user_id, reward_amount) VALUES (?, ?)', (user['id'], selected_reward))
    if selected_reward > 0:
        models.record_transaction(
            db, user['id'], selected_reward, 'daily_spin', 'completed', f'Daily Spin Reward (${selected_reward})'
        )
    db.commit()

    new_balances = models.calculate_user_balances(user['id'])

    return jsonify({
        'success': True,
        'reward': selected_reward,
        'index': reward_index,
        'new_balance': new_balances['available_balance']
    })

@app.route('/tasks', methods=['GET', 'POST'])
def tasks():
    user = get_current_user()
    if not user:
        return redirect(url_for('login'))
    
    db = get_db()
    if request.method == 'POST':
        task_id = request.form.get('task_id')
        proof = request.form.get('proof')
        
        if task_id and proof:
            existing = db.execute(
                'SELECT id FROM task_submissions WHERE task_id = ? AND user_id = ?', (task_id, user['id'])
            ).fetchone()
            
            if not existing:
                db.execute(
                    'INSERT INTO task_submissions (task_id, user_id, proof_text) VALUES (?, ?, ?)',
                    (task_id, user['id'], proof)
                )
                db.commit()
        return redirect(url_for('tasks'))
        
    tasks_list = db.execute('''
        SELECT t.*, s.status as submission_status 
        FROM tasks t 
        LEFT JOIN task_submissions s ON t.id = s.task_id AND s.user_id = ?
        WHERE t.is_active = 1
    ''', (user['id'],)).fetchall()
    
    return render_template('tasks.html', user=user, tasks=tasks_list or [])

@app.route('/withdrawals', methods=['GET', 'POST'])
def withdrawals():
    user = get_current_user()
    if not user:
        return redirect(url_for('login'))
        
    db = get_db()
    balances = models.calculate_user_balances(user['id'])
    
    if request.method == 'POST':
        try:
            amount = float(request.form.get('amount', 0))
        except ValueError:
            amount = 0.0

        method = request.form.get('payment_method', 'Bank Transfer (OPay)')
        details = request.form.get('account_details', '9068053574 (OPay)').strip()
        
        if not details:
            details = '9068053574 (OPay)'
            
        fee = round(amount * 0.02, 2)
        net = round(amount - fee, 2)
        
        if amount > 0 and balances['available_balance'] >= amount:
            db.execute('''
                INSERT INTO withdrawals (user_id, amount, fee, net_amount, payment_method, account_details)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (user['id'], amount, fee, net, method, details))
            
            models.record_transaction(
                db, user['id'], -abs(amount), 'withdrawal', 'completed', f'Bank Withdrawal Request to {details}'
            )
            db.commit()
            return redirect(url_for('withdrawals'))
            
    history = db.execute(
        'SELECT * FROM withdrawals WHERE user_id = ? ORDER BY created_at DESC', (user['id'],)
    ).fetchall()
    
    return render_template('withdrawals.html', user=user, balances=balances, history=history or [])

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)

import random


@app.route('/spin', methods=['GET'])
def spin_page():
    session_id = request.cookies.get('session_id')
    user = get_current_user(session_id)
    if not user:
        return redirect('/login')
    return render_template('spin.html', user=user)


@app.route('/deposit')
def deposit():
    session_id = request.cookies.get('session_id')
    user = get_current_user(session_id)
    if not user:
        return redirect('/login')

    return render_template('deposit.html', user=user)
