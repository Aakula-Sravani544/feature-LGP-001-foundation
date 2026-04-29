import sqlite3
import psycopg2
from psycopg2.extras import DictCursor
import pandas as pd
import os
from datetime import datetime
from sqlalchemy import create_engine

DB_NAME = "data/leadpulse.db"
DATABASE_URL = os.environ.get("DATABASE_URL")
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
USE_POSTGRES = DATABASE_URL is not None

def get_connection():
    if USE_POSTGRES:
        return psycopg2.connect(DATABASE_URL)
    else:
        if not os.path.exists("data"):
            os.makedirs("data")
        return sqlite3.connect(DB_NAME)

def get_engine():
    if USE_POSTGRES:
        return create_engine(DATABASE_URL)
    return None

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    
    # 19-Field Leads table
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
            timestamp TEXT,
            validation_status TEXT,
            validation_notes TEXT,
            sub_region TEXT,
            ai_analysis TEXT,
            additional_data TEXT
        )
    ''')
    
    # Try to add new columns to existing SQLite table gracefully
    if not USE_POSTGRES:
        try: cursor.execute("ALTER TABLE leads ADD COLUMN validation_status TEXT")
        except: pass
        try: cursor.execute("ALTER TABLE leads ADD COLUMN validation_notes TEXT")
        except: pass
        try: cursor.execute("ALTER TABLE leads ADD COLUMN sub_region TEXT")
        except: pass
        try: cursor.execute("ALTER TABLE leads ADD COLUMN ai_analysis TEXT")
        except: pass
        try: cursor.execute("ALTER TABLE leads ADD COLUMN additional_data TEXT")
        except: pass
    else:
        try:
            cursor.execute("ALTER TABLE leads ADD COLUMN IF NOT EXISTS validation_status TEXT")
            cursor.execute("ALTER TABLE leads ADD COLUMN IF NOT EXISTS validation_notes TEXT")
            cursor.execute("ALTER TABLE leads ADD COLUMN IF NOT EXISTS sub_region TEXT")
            cursor.execute("ALTER TABLE leads ADD COLUMN IF NOT EXISTS ai_analysis TEXT")
            cursor.execute("ALTER TABLE leads ADD COLUMN IF NOT EXISTS additional_data TEXT")
        except: pass
    
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
    if USE_POSTGRES:
        engine = get_engine()
        df = pd.read_sql_query("SELECT * FROM session_logs ORDER BY timestamp DESC", engine)
    else:
        conn = get_connection()
        df = pd.read_sql_query("SELECT * FROM session_logs ORDER BY timestamp DESC", conn)
        conn.close()
    return df

def save_to_db(leads_data):
    if not leads_data: return
    init_db()
    conn = get_connection()
    cursor = conn.cursor()
    
    # Mapping for new scraper fields to DB columns
    MAPPING = {
        "name": "business_name",
        "google_maps_url": "maps_url",
        "reviews": "review_count",
        "hours": "business_hours",
        "scraped_date": "timestamp"
    }
    
    for row_dict in leads_data:
        # 1. Map fields
        final_dict = {}
        for k, v in row_dict.items():
            db_key = MAPPING.get(k, k)
            final_dict[db_key] = v
            
        # 2. Ensure lead_id exists
        if "lead_id" not in final_dict or not final_dict["lead_id"]:
            import uuid
            final_dict["lead_id"] = str(uuid.uuid4())[:8]
            
        # 3. Clean for DB schema (keep only existing columns)
        # We'll just filter keys that we know are in the table
        valid_cols = ["lead_id", "business_name", "address", "phone", "website", "email", 
                     "rating", "review_count", "category", "maps_url", "business_hours", 
                     "social_media", "description", "latitude", "longitude", "query", 
                     "timestamp", "validation_status", "validation_notes", "sub_region", 
                     "ai_analysis", "additional_data"]
        
        db_row = {k: v for k, v in final_dict.items() if k in valid_cols}
        columns = ', '.join(db_row.keys())
        
        if USE_POSTGRES:
            placeholders = ', '.join(['%s'] * len(db_row))
            query = f"INSERT INTO leads ({columns}) VALUES ({placeholders}) ON CONFLICT (lead_id) DO NOTHING"
            try:
                cursor.execute(query, tuple(db_row.values()))
            except Exception as e:
                print(f"DB Insert Error: {e}")
        else:
            placeholders = ', '.join(['?'] * len(db_row))
            cursor.execute("SELECT 1 FROM leads WHERE lead_id = ?", (db_row.get('lead_id', ''),))
            if not cursor.fetchone():
                query = f"INSERT INTO leads ({columns}) VALUES ({placeholders})"
                try:
                    cursor.execute(query, tuple(db_row.values()))
                except: pass
                
    conn.commit()
    conn.close()

def load_db():
    init_db()
    if USE_POSTGRES:
        engine = get_engine()
        df = pd.read_sql_query("SELECT * FROM leads", engine)
    else:
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
