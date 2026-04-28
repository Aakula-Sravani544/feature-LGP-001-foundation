import gspread
from google.oauth2.service_account import Credentials
import os

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
        
        existing_records = worksheet.get_all_records()
        existing_ids = set([str(row.get('lead_id', '')) for row in existing_records])
        
        new_rows = []
        headers = [
            "lead_id", "business_name", "category", "rating", "reviews", "phone", 
            "website", "full_address", "city", "state", "pincode", "latitude", 
            "longitude", "hours", "status", "query_used", "scraped_at"
        ]
        
        if not existing_records:
            worksheet.append_row(headers)
            
        for lead in leads_data:
            if str(lead.get('lead_id', '')) not in existing_ids:
                row = [str(lead.get(h, 'N/A')) for h in headers]
                new_rows.append(row)
                existing_ids.add(str(lead.get('lead_id', '')))
                
        if new_rows:
            worksheet.append_rows(new_rows)
            return True, f"Uploaded {len(new_rows)} rows"
        return True, "No new rows to upload"
        
    except Exception as e:
        return False, str(e)
