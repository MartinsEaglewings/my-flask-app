from database import get_db

def record_transaction(db, user_id, amount, tx_type, status='completed', description=''):
    db.execute('''
        INSERT INTO transactions (user_id, amount, tx_type, status, description)
        VALUES (?, ?, ?, ?, ?)
    ''', (user_id, amount, tx_type, status, description))

def calculate_user_balances(user_id):
    db = get_db()
    
    # Calculate Total Earnings
    earnings_row = db.execute('''
        SELECT COALESCE(SUM(amount), 0.0) as total 
        FROM transactions 
        WHERE user_id = ? AND amount > 0 AND (status = 'completed' OR status IS NULL)
    ''', (user_id,)).fetchone()
    
    # Calculate Spin Earnings
    spin_row = db.execute('''
        SELECT COALESCE(SUM(amount), 0.0) as total 
        FROM transactions 
        WHERE user_id = ? AND tx_type = 'daily_spin' AND amount > 0
    ''', (user_id,)).fetchone()

    # Calculate Task Earnings
    task_row = db.execute('''
        SELECT COALESCE(SUM(amount), 0.0) as total 
        FROM transactions 
        WHERE user_id = ? AND tx_type = 'task' AND amount > 0
    ''', (user_id,)).fetchone()

    # Calculate Total Withdrawn
    withdrawn_row = db.execute('''
        SELECT COALESCE(SUM(ABS(amount)), 0.0) as total 
        FROM transactions 
        WHERE user_id = ? AND (tx_type = 'withdrawal' OR amount < 0)
    ''', (user_id,)).fetchone()

    total_earnings = float(earnings_row['total']) if earnings_row else 0.0
    spin_earnings = float(spin_row['total']) if spin_row else 0.0
    task_earnings = float(task_row['total']) if task_row else 0.0
    total_withdrawn = float(withdrawn_row['total']) if withdrawn_row else 0.0
    
    available_balance = max(0.0, total_earnings - total_withdrawn)

    return {
        'total_earnings': total_earnings,
        'spin_earnings': spin_earnings,
        'task_earnings': task_earnings,
        'total_withdrawn': total_withdrawn,
        'available_balance': available_balance
    }
