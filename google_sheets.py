import gspread
from google.oauth2.service_account import Credentials
import os
import json
from datetime import datetime

def get_credentials():
    """
    Production-safe credential loader for local and Render environments.
    Reads from GOOGLE_SHEETS_CREDENTIALS environment variable as a JSON string.
    """
    scopes = [
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/drive'
    ]
    
    # 1. Primary: Try GOOGLE_SHEETS_CREDENTIALS (Full JSON string content)
    env_creds = os.environ.get('GOOGLE_SHEETS_CREDENTIALS', '').strip()
    
    # Render sometimes wraps values in extra quotes, we strip them to be safe
    if env_creds.startswith(("'", '"')) and env_creds.endswith(("'", '"')):
        env_creds = env_creds[1:-1]
        
    if env_creds:
        try:
            creds_dict = json.loads(env_creds)
            print("LOG: Using ENV credentials")
            return Credentials.from_service_account_info(creds_dict, scopes=scopes)
        except Exception as e:
            # Print exact error for debugging in Render logs
            print(f"LOG: CRITICAL Error parsing GOOGLE_SHEETS_CREDENTIALS: {str(e)}")
            
    # 2. Fallback: Local creds.json (Local dev only)
    if os.path.exists("creds.json"):
        try:
            print("LOG: Using local creds.json fallback")
            return Credentials.from_service_account_file('creds.json', scopes=scopes)
        except Exception as e:
            print(f"LOG: Error reading local creds.json: {str(e)}")
        
    return None

def save_to_google_sheets(leads_data):
    """
    Main function to sync leads to Google Sheets. 
    Appends fresh leads only, preserving existing data.
    """
    if not leads_data:
        return False, "No data to upload"
        
    try:
        credentials = get_credentials()
        if not credentials:
            error_msg = "OFFLINE: No valid Google Credentials found in Environment"
            print(f"LOG: {error_msg}")
            return False, error_msg
            
        gc = gspread.authorize(credentials)
        sheet_name = os.environ.get('SHEET_NAME', 'LeadPulse_Data')
        
        try:
            print(f"LOG: Connecting to Google Sheets: {sheet_name}")
            sh = gc.open(sheet_name)
        except gspread.exceptions.SpreadsheetNotFound:
            print(f"LOG: Creating new sheet: {sheet_name}")
            sh = gc.create(sheet_name)
            
        worksheet = sh.sheet1
        
        # 1. Fetch existing lead_ids for deduplication
        all_values = worksheet.get_all_values()
        existing_ids = set()
        
        headers = [
            "lead_id", "business_name", "address", "phone", "website", "email",
            "rating", "review_count", "category", "maps_url", "business_hours",
            "social_media", "description", "latitude", "longitude", "query", "timestamp"
        ]
        
        if not all_values:
            worksheet.append_row(headers)
        else:
            # lead_id is in the first column
            for row in all_values[1:]:
                if row and len(row) > 0:
                    existing_ids.add(str(row[0]).strip())
        
        # 2. Prepare clean rows (No N/A, No None)
        rows_to_append = []
        for lead in leads_data:
            def clean(key):
                val = lead.get(key, "")
                if val is None or str(val).strip() == "" or str(val).lower() in ["n/a", "none", "nan", "undefined"]:
                    return ""
                return str(val).strip()

            l_id = clean("lead_id")
            if not l_id or l_id in existing_ids:
                continue
                
            row_data = [
                l_id,
                clean("business_name"),
                clean("address"),
                clean("phone"),
                clean("website"),
                clean("email"),
                clean("rating"),
                clean("review_count"),
                clean("category"),
                clean("maps_url"),
                clean("business_hours"),
                clean("social_media"),
                clean("description"),
                clean("latitude"),
                clean("longitude"),
                clean("query"),
                clean("timestamp")
            ]
            rows_to_append.append(row_data)
            existing_ids.add(l_id)
            
        if rows_to_append:
            print(f"LOG: Writing {len(rows_to_append)} rows to Google Sheets...")
            worksheet.append_rows(rows_to_append)
            print("LOG: Write successful")
            return True, f"Success: Appended {len(rows_to_append)} fresh leads"
            
        return True, "Sync Complete: All leads already present in sheet"
        
    except Exception as e:
        error_msg = f"Sync Failed: {str(e)}"
        print(f"LOG: {error_msg}")
        return False, error_msg

def check_connection():
    """Helper to verify connection status for Dashboard badge"""
    try:
        credentials = get_credentials()
        if not credentials:
            return False
        gspread.authorize(credentials)
        return True
    except:
        return False

def clear_sheet_data():
    """Administrative reset function"""
    try:
        credentials = get_credentials()
        if not credentials:
            return False, "OFFLINE"
            
        gc = gspread.authorize(credentials)
        sheet_name = os.environ.get('SHEET_NAME', 'LeadPulse_Data')
        sh = gc.open(sheet_name)
        worksheet = sh.sheet1
        
        headers = [
            "lead_id", "business_name", "address", "phone", "website", "email",
            "rating", "review_count", "category", "maps_url", "business_hours",
            "social_media", "description", "latitude", "longitude", "query", "timestamp"
        ]
        worksheet.clear()
        worksheet.append_row(headers)
        return True, "Sheet cleared successfully"
    except Exception as e:
        return False, str(e)
