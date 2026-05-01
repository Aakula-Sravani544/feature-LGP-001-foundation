import re
import requests
import phonenumbers
from email_validator import validate_email, EmailNotValidError

def validate_lead(lead):
    """
    Day 4 Validation Layer: Strict validation of existing lead data.
    """
    notes = []
    
    # 1. Phone validation & normalization
    phone = str(lead.get("phone", "")).strip()
    if phone and phone.lower() not in ["none", "n/a", "check website", "visit website"]:
        try:
            # Clean non-digits for normalization
            clean_phone = re.sub(r'[^\d+]', '', phone)
            if not clean_phone.startswith('+') and len(clean_phone) == 10:
                clean_phone = "+91" + clean_phone
            
            parsed = phonenumbers.parse(clean_phone, "IN")
            if phonenumbers.is_valid_number(parsed):
                lead["phone"] = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
            else:
                lead["phone"] = ""
                notes.append("Invalid phone")
        except:
            lead["phone"] = ""
            notes.append("Invalid phone")
    else:
        lead["phone"] = ""

    # 2. Email validation
    email = str(lead.get("email", "")).strip()
    if email and email.lower() not in ["none", "n/a", "use website contact"]:
        try:
            valid = validate_email(email)
            lead["email"] = valid.normalized
        except EmailNotValidError:
            lead["email"] = ""
            notes.append("Invalid email")
    else:
        lead["email"] = ""

    # 3. Website validation
    website = str(lead.get("website", "")).strip()
    if website and website.startswith("http"):
        try:
            # Quick check (Requirement: timeout 5s)
            resp = requests.head(website, timeout=5, allow_redirects=True)
            if resp.status_code >= 400:
                notes.append("Website not reachable")
        except:
            notes.append("Website not reachable")
    else:
        lead["website"] = ""

    # 4. Validation logic (Requirement 4)
    has_phone = bool(lead.get("phone"))
    has_email = bool(lead.get("email"))
    has_web = bool(lead.get("website"))
    
    if has_phone or has_email or has_web:
        status = "Valid"
    else:
        status = "Pending"
            
    lead["validation_status"] = status
    lead["validation_notes"] = ", ".join(notes)
    
    return lead
