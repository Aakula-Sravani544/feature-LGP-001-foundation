import gspread
from google.oauth2.service_account import Credentials
import os
from datetime import datetime

def upload_to_sheets(leads_data):
    if not leads_data:
        return False, "No data to upload"
        
    if not os.path.exists("creds.json"):
        return False, "creds.json missing"
        
    try:
        scopes = [
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive'
        ]
        credentials = Credentials.from_service_account_file('creds.json', scopes=scopes)
        gc = gspread.authorize(credentials)
        
        sheet_name = "LeadPulse_Data"
        try:
            sh = gc.open(sheet_name)
        except gspread.exceptions.SpreadsheetNotFound:
            sh = gc.create(sheet_name)
            
        worksheet = sh.sheet1
        
        # 1. Full Reset for Professional Sync
        worksheet.clear()
        
        # 2. 17-Field Professional Headers
        headers = [
            "lead_id", "business_name", "address", "phone", "website", "email",
            "rating", "review_count", "category", "maps_url", "business_hours",
            "social_media", "description", "latitude", "longitude", "query", "timestamp"
        ]
        worksheet.append_row(headers)
        
        # 3. Clean and Batch Prepare Data
        rows_to_upload = []
        for lead in leads_data:
            def clean(key):
                val = lead.get(key, "")
                if val is None or str(val).lower() == "n/a" or str(val).lower() == "none":
                    return ""
                return str(val).strip()

            row = [
                clean("lead_id"),
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
            rows_to_upload.append(row)
            
        if rows_to_upload:
            worksheet.append_rows(rows_to_upload)
            return True, f"Uploaded {len(rows_to_upload)} leads"
            
        return True, "No data to sync"
        
    except Exception as e:
        return False, str(e)

def check_connection():
    if not os.path.exists("creds.json"):
        return False
    try:
        scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
        credentials = Credentials.from_service_account_file('creds.json', scopes=scopes)
        gspread.authorize(credentials)
        return True
    except:
        return False

def clear_sheet_data():
    if not os.path.exists("creds.json"):
        return False, "creds.json missing"
    try:
        scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
        credentials = Credentials.from_service_account_file('creds.json', scopes=scopes)
        gc = gspread.authorize(credentials)
        
        sh = gc.open("LeadPulse_Data")
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
