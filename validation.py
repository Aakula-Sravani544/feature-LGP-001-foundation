import phonenumbers
from email_validator import validate_email, EmailNotValidError
import requests
import re

def validate_lead(lead):
    """
    Day 4: Validation Layer
    Applies phone normalization, email validation, and URL reachability checks.
    """
    notes = []
    has_valid_phone = False
    has_valid_email = False
    has_valid_url = False
    
    # 1. Phone Normalization (E.164)
    phone = lead.get("phone", "")
    if phone and phone != "Check Website":
        try:
            parsed_phone = phonenumbers.parse(phone, "IN")
            if phonenumbers.is_valid_number(parsed_phone):
                lead["phone"] = phonenumbers.format_number(parsed_phone, phonenumbers.PhoneNumberFormat.E164)
                has_valid_phone = True
            else:
                notes.append("Invalid phone")
                lead["phone"] = ""
        except:
            notes.append("Phone format error")
            lead["phone"] = ""
    
    # 2. Email Validation
    email = lead.get("email", "")
    if email and email != "Use Website Contact":
        try:
            valid = validate_email(email)
            lead["email"] = valid.email
            has_valid_email = True
        except EmailNotValidError:
            notes.append("Invalid email")
            lead["email"] = ""
        except:
            notes.append("Email validation error")
            lead["email"] = ""
            
    # 3. URL Reachability Check
    url = lead.get("website", "")
    if url and url.startswith(("http://", "https://")):
        try:
            response = requests.get(url, timeout=5, allow_redirects=True)
            if 200 <= response.status_code < 400:
                has_valid_url = True
            else:
                notes.append(f"Website unreachable ({response.status_code})")
        except:
            notes.append("Website timeout/error")
    elif url:
        notes.append("Invalid URL format")
        
    # 4. Validation Status Field
    if has_valid_phone or has_valid_email or has_valid_url:
        lead["validation_status"] = "Valid"
    elif not lead.get("phone") and not lead.get("email") and not lead.get("website"):
        lead["validation_status"] = "Pending"
    else:
        lead["validation_status"] = "Invalid"
        
    # 5. Validation Notes Field
    lead["validation_notes"] = ", ".join(notes) if notes else "All checks passed"
    
    return lead
