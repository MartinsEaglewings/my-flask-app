import os
import sqlite3
import psycopg2
from psycopg2.extras import RealDictCursor

def get_db():
    db_url = os.environ.get('DATABASE_URL')
    if db_url:
        if db_url.startswith("postgres://"):
            db_url = db_url.replace("postgres://", "postgresql://", 1)
        conn = psycopg2.connect(db_url, sslmode='require', cursor_factory=RealDictCursor)
        conn.autocommit = True
        return conn, 'postgres'
    else:
        conn = sqlite3.connect('app.db')
        conn.row_factory = sqlite3.Row
        return conn, 'sqlite'

def init_db():
    conn, db_type = get_db()
    cursor = conn.cursor()
    try:
        if db_type == 'postgres':
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    username VARCHAR(150) UNIQUE NOT NULL,
                    password TEXT NOT NULL,
                    balance DOUBLE PRECISION DEFAULT 0.0,
                    is_admin INTEGER DEFAULT 0
                );
            ''')
        else:
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    password TEXT NOT NULL,
                    balance REAL DEFAULT 0.0,
                    is_admin INTEGER DEFAULT 0
                );
            ''')
    except Exception as e:
        print(f"Error creating tables: {e}")
    finally:
        conn.close()

if __name__ == '__main__':
    init_db()
