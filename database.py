import sqlite3
import psycopg2
from psycopg2.extras import DictCursor
import pandas as pd
import os
from datetime import datetime

DB_NAME = "data/leadpulse.db"
DATABASE_URL = os.environ.get("DATABASE_URL")
USE_POSTGRES = DATABASE_URL is not None

def get_connection():
    if USE_POSTGRES:
        return psycopg2.connect(DATABASE_URL)
    else:
        if not os.path.exists("data"):
            os.makedirs("data")
        return sqlite3.connect(DB_NAME)

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    
    # 17-Field Leads table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS leads (
            lead_id TEXT PRIMARY KEY,
            business_name TEXT,
            address TEXT,
            phone TEXT,
            website TEXT,
            email TEXT,
            rating TEXT,
            review_count TEXT,
            category TEXT,
            maps_url TEXT,
            business_hours TEXT,
            social_media TEXT,
            description TEXT,
            latitude TEXT,
            longitude TEXT,
            query TEXT,
            timestamp TEXT
        )
    ''')
    
    # Users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password TEXT,
            role TEXT
        )
    ''')
    
    # Logs table - Postgres vs SQLite AUTOINCREMENT
    if USE_POSTGRES:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS session_logs (
                id SERIAL PRIMARY KEY,
                username TEXT,
                action TEXT,
                timestamp TEXT
            )
        ''')
    else:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS session_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT,
                action TEXT,
                timestamp TEXT
            )
        ''')
    
    # Default users
    cursor.execute("SELECT 1 FROM users WHERE username='admin'")
    if not cursor.fetchone():
        cursor.execute("INSERT INTO users (username, password, role) VALUES ('admin', 'admin123', 'admin')")
        cursor.execute("INSERT INTO users (username, password, role) VALUES ('user', 'user123', 'user')")
        
    conn.commit()
    conn.close()

def log_action(username, action):
    init_db()
    conn = get_connection()
    cursor = conn.cursor()
    if USE_POSTGRES:
        cursor.execute("INSERT INTO session_logs (username, action, timestamp) VALUES (%s, %s, %s)", 
                       (username, action, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    else:
        cursor.execute("INSERT INTO session_logs (username, action, timestamp) VALUES (?, ?, ?)", 
                       (username, action, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()

def get_logs():
    init_db()
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM session_logs ORDER BY timestamp DESC", conn)
    conn.close()
    return df

def save_to_db(leads_data):
    if not leads_data: return
    init_db()
    conn = get_connection()
    cursor = conn.cursor()
    df = pd.DataFrame(leads_data)
    
    for idx, row in df.iterrows():
        row_dict = row.to_dict()
        columns = ', '.join(row_dict.keys())
        
        if USE_POSTGRES:
            placeholders = ', '.join(['%s'] * len(row_dict))
            query = f"INSERT INTO leads ({columns}) VALUES ({placeholders}) ON CONFLICT (lead_id) DO NOTHING"
            try:
                cursor.execute(query, tuple(row_dict.values()))
            except Exception as e:
                print(f"DB Insert Error: {e}")
        else:
            placeholders = ', '.join(['?'] * len(row_dict))
            # SQLite deduplication
            cursor.execute("SELECT 1 FROM leads WHERE lead_id = ?", (row.get('lead_id', ''),))
            if not cursor.fetchone():
                query = f"INSERT INTO leads ({columns}) VALUES ({placeholders})"
                try:
                    cursor.execute(query, tuple(row_dict.values()))
                except: pass
                
    conn.commit()
    conn.close()

def load_db():
    init_db()
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM leads", conn)
    conn.close()
    return df

def verify_user(username, password):
    init_db()
    conn = get_connection()
    cursor = conn.cursor()
    if USE_POSTGRES:
        cursor.execute("SELECT role FROM users WHERE username=%s AND password=%s", (username, password))
    else:
        cursor.execute("SELECT role FROM users WHERE username=? AND password=?", (username, password))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None

def clear_all_leads():
    init_db()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM leads")
    conn.commit()
    conn.close()
