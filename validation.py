import re
import requests
import phonenumbers
from email_validator import validate_email, EmailNotValidError

def validate_lead(lead):
    """
    Day 4 Refined: Corrected validation logic for fast results.
    """
    notes = []
    
    # 1. Phone Normalisation
    phone = lead.get("phone", "").strip()
    if phone:
        try:
            clean_phone = re.sub(r'[^\d+]', '', phone)
            if not clean_phone.startswith('+') and len(clean_phone) == 10:
                clean_phone = "+91" + clean_phone
            parsed = phonenumbers.parse(clean_phone, "IN")
            if phonenumbers.is_valid_number(parsed):
                lead["phone"] = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
            else:
                notes.append("Invalid phone")
        except:
            notes.append("Invalid phone")

    # 2. Email Validation
    email = lead.get("email", "").strip()
    if email:
        try:
            valid = validate_email(email)
            lead["email"] = valid.normalized
        except:
            notes.append("Invalid email")

    # 3. Final Status Logic (Requirement 4 & 5)
    has_phone = bool(lead.get("phone"))
    has_email = bool(lead.get("email"))
    has_web = bool(lead.get("website"))
    
    # Valid if at least one exists (Requirement 5)
    if has_phone or has_email or has_web:
        status = "Valid"
    else:
        status = "Pending"
            
    lead["validation_status"] = status
    lead["validation_notes"] = ", ".join(notes)
    
    return lead

def extract_email_from_web(url):
    if not url or not url.startswith("http"): return ""
    try:
        resp = requests.get(url, timeout=5)
        emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', resp.text)
        return emails[0] if emails else ""
    except:
        return ""
