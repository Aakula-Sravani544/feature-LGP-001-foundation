import sqlite3
import pandas as pd
import os

DB_NAME = "data/leadpulse.db"

def init_db():
    if not os.path.exists("data"):
        os.makedirs("data")
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS leads (
            lead_id TEXT PRIMARY KEY,
            business_name TEXT,
            category TEXT,
            rating TEXT,
            reviews TEXT,
            phone TEXT,
            website TEXT,
            full_address TEXT,
            city TEXT,
            state TEXT,
            pincode TEXT,
            latitude TEXT,
            longitude TEXT,
            hours TEXT,
            status TEXT,
            query_used TEXT,
            scraped_at TEXT
        )
    ''')
    conn.commit()
    conn.close()

def save_to_db(leads_data):
    if not leads_data: return
    init_db()
    conn = sqlite3.connect(DB_NAME)
    df = pd.DataFrame(leads_data)
    # Filter out duplicates before inserting
    for idx, row in df.iterrows():
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM leads WHERE lead_id = ?", (row.get('lead_id', ''),))
        if not cursor.fetchone():
            try:
                row_dict = row.to_dict()
                columns = ', '.join(row_dict.keys())
                placeholders = ', '.join(['?'] * len(row_dict))
                query = f"INSERT INTO leads ({columns}) VALUES ({placeholders})"
                cursor.execute(query, tuple(row_dict.values()))
            except Exception as e:
                pass
    conn.commit()
    conn.close()

def load_db():
    init_db()
    conn = sqlite3.connect(DB_NAME)
    df = pd.read_sql_query("SELECT * FROM leads", conn)
    conn.close()
    return df
