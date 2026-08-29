import os
import sqlite3
import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor

pg_pool = None

def get_db():
    global pg_pool
    db_url = os.environ.get('DATABASE_URL')
    if db_url:
        if db_url.startswith("postgres://"):
            db_url = db_url.replace("postgres://", "postgresql://", 1)
        if pg_pool is None:
            # High-performance connection pool (1-10 connections)
            pg_pool = psycopg2.pool.SimpleConnectionPool(1, 10, db_url, sslmode='require')
        conn = pg_pool.getconn()
        return conn, 'postgres'
    else:
        conn = sqlite3.connect('app.db')
        conn.row_factory = sqlite3.Row
        return conn, 'sqlite'

def release_db(conn, db_type):
    global pg_pool
    if db_type == 'postgres' and pg_pool:
        pg_pool.putconn(conn)
    else:
        conn.close()

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
                CREATE INDEX IF NOT EXISTS idx_users_username ON users(LOWER(username));
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS tasks (
                    id SERIAL PRIMARY KEY,
                    title VARCHAR(150) NOT NULL,
                    description TEXT,
                    reward_amount DOUBLE PRECISION DEFAULT 0.0
                );
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS transactions (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER REFERENCES users(id),
                    amount DOUBLE PRECISION,
                    tx_type VARCHAR(50),
                    status VARCHAR(50),
                    description TEXT
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
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    description TEXT,
                    reward_amount REAL DEFAULT 0.0
                );
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    amount REAL,
                    tx_type TEXT,
                    status TEXT,
                    description TEXT
                );
            ''')
        conn.commit()
    except Exception as e:
        print(f"Error initializing database: {e}")
        if conn:
            conn.rollback()
    finally:
        release_db(conn, db_type)

if __name__ == '__main__':
    init_db()
