import gspread
from google.oauth2.service_account import Credentials
import os
import json
import ast
from datetime import datetime
from validation import validate_lead

# Global variable to store the last error for diagnostics
LAST_ERROR = None

def get_credentials():
    """
    Enhanced credential loader for Render.
    Handles environment variable GOOGLE_SHEETS_CREDENTIALS.
    Supports both standard JSON and single-quoted dictionaries.
    """
    global LAST_ERROR
    scopes = [
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/drive'
    ]
    
    # 1. Try Environment Variable
    env_creds = os.environ.get('GOOGLE_SHEETS_CREDENTIALS', '').strip()
    
    # Render Troubleshooting: Remove surrounding quotes if they exist
    if env_creds.startswith(("'", '"')) and env_creds.endswith(("'", '"')):
        env_creds = env_creds[1:-1]
        
    if env_creds:
        try:
            str_len = len(env_creds)
            try:
                creds_dict = json.loads(env_creds, strict=False)
            except Exception as json_e:
                try:
                    creds_dict = ast.literal_eval(env_creds)
                except Exception as ast_e:
                    LAST_ERROR = f"Format Error (Len: {str_len}): JSON fail ({str(json_e)}), AST fail ({str(ast_e)}). Start: {env_creds[:10]}... End: {env_creds[-10:]}"
                    return None
            print(f"DEBUG: Successfully parsed GOOGLE_SHEETS_CREDENTIALS (Len: {str_len})")
            return Credentials.from_service_account_info(creds_dict, scopes=scopes)
        except Exception as e:
            LAST_ERROR = f"Credential Load Error: {str(e)}"
            print(f"DEBUG: {LAST_ERROR}")
            
    # 2. Local Fallback
    if os.path.exists("creds.json"):
        try:
            print("DEBUG: Using local creds.json")
            return Credentials.from_service_account_file('creds.json', scopes=scopes)
        except Exception as e:
            LAST_ERROR = f"File Error: {str(e)}"
            print(f"DEBUG: {LAST_ERROR}")
    elif not env_creds:
        LAST_ERROR = "Environment variable GOOGLE_SHEETS_CREDENTIALS is empty or missing."
        
    return None

def save_to_google_sheets(leads_data):
    """
    Appends data to Google Sheets with deduplication.
    """
    global LAST_ERROR
    if not leads_data:
        return False, "No data provided"
        
    try:
        credentials = get_credentials()
        if not credentials:
            return False, f"Auth Failed: {LAST_ERROR or 'Check credentials'}"
            
        gc = gspread.authorize(credentials)
        sheet_name = os.environ.get('SHEET_NAME', 'LeadPulse_Data')
        
        try:
            sh = gc.open(sheet_name)
        except gspread.exceptions.SpreadsheetNotFound:
            sh = gc.create(sheet_name)
            
        worksheet = sh.sheet1
        all_values = worksheet.get_all_values()
        existing_ids = set()
        
        headers = [
            "lead_id", "business_name", "address", "phone", "email", "website",
            "rating", "reviews", "category", "maps_url", "scraped_date",
            "validation_status", "validation_notes"
        ]
        
        if not all_values:
            worksheet.append_row(headers)
        else:
            for row in all_values[1:]:
                if row: existing_ids.add(str(row[0]).strip())
        
        # Batch collect rows
        rows_to_append = []
        for lead in leads_data:
            def clean(key):
                val = lead.get(key, "")
                if val is None or str(val).strip().lower() in ["", "none", "n/a", "nan", "undefined"]:
                    return ""
                return str(val).strip()

            l_id = clean("lead_id")
            if not l_id or l_id in existing_ids:
                continue
                
            # Apply Validation before syncing to cloud (Requirement 4)
            lead = validate_lead(lead)

            row_data = [
                l_id, 
                clean("business_name") or clean("name"), 
                clean("address"), 
                clean("phone"),
                clean("email"),
                clean("website"), 
                clean("rating"), 
                clean("reviews") or clean("review_count"),
                clean("category"), 
                clean("maps_url") or clean("google_maps_url"), 
                clean("scraped_date") or clean("timestamp"),
                clean("validation_status") or "Pending", 
                clean("validation_notes")
            ]
            rows_to_append.append(row_data)
            existing_ids.add(l_id)
            
        # Write batch of rows (max 100 at a time or however many we have)
        if rows_to_append:
            worksheet.append_rows(rows_to_append)
            print(f"DEBUG: Appended {len(rows_to_append)} rows")
            return True, f"Successfully synced {len(rows_to_append)} new leads."
            
        return True, "All leads already synced."
        
    except Exception as e:
        LAST_ERROR = str(e)
        return False, f"Sync Error: {str(e)}"

def check_connection():
    """Simplified check for UI badge"""
    global LAST_ERROR
    try:
        credentials = get_credentials()
        if not credentials: return False
        gspread.authorize(credentials)
        return True
    except Exception as e:
        LAST_ERROR = f"Handshake Error: {str(e)}"
        return False

def get_last_error():
    """Exposes error message to UI for diagnostics"""
    global LAST_ERROR
    return LAST_ERROR

def clear_sheet_data():
    """Resets the cloud sheet"""
    try:
        credentials = get_credentials()
        if not credentials: return False, "Auth failed"
        gc = gspread.authorize(credentials)
        sheet_name = os.environ.get('SHEET_NAME', 'LeadPulse_Data')
        sh = gc.open(sheet_name)
        worksheet = sh.sheet1
        headers = [
            "lead_id", "business_name", "address", "phone", "email", "website",
            "rating", "reviews", "category", "maps_url", "scraped_date",
            "validation_status", "validation_notes"
        ]
        worksheet.clear()
        worksheet.append_row(headers)
        return True, "Cloud Sheet Reset Success"
    except Exception as e:
        return False, str(e)

def load_from_google_sheets():
    """Reads all rows from the Google Sheet and returns them as a list of dictionaries"""
    try:
        credentials = get_credentials()
        if not credentials: return None
        
        gc = gspread.authorize(credentials)
        sheet_name = os.environ.get('SHEET_NAME', 'LeadPulse_Data')
        sh = gc.open(sheet_name)
        worksheet = sh.sheet1
        
        # get_all_records automatically uses the first row as dictionary keys
        records = worksheet.get_all_records()
        return records
    except Exception as e:
        global LAST_ERROR
        LAST_ERROR = f"Load Error: {str(e)}"
        return None
