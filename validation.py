import re
import requests
import phonenumbers
from email_validator import validate_email, EmailNotValidError

def validate_lead(lead):
    """
    Day 4 Refined: Strict validation for LeadPulse Pro.
    """
    notes = []
    status = "Pending"
    
    # 1. Phone Normalisation (+91...)
    phone = lead.get("phone", "").strip()
    if phone and phone != "Check Website" and phone != "Visit Website":
        try:
            # Clean non-digits for parsing check
            clean_phone = re.sub(r'[^\d+]', '', phone)
            if not clean_phone.startswith('+'):
                if len(clean_phone) == 10:
                    clean_phone = "+91" + clean_phone
                elif clean_phone.startswith('0') and len(clean_phone) == 11:
                    clean_phone = "+91" + clean_phone[1:]
            
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

    # 2. Email Validation
    email = lead.get("email", "").strip()
    if email and "@" in email and "." in email:
        try:
            valid = validate_email(email)
            lead["email"] = valid.normalized
        except EmailNotValidError:
            lead["email"] = ""
            notes.append("Invalid email")
    else:
        lead["email"] = ""

    # 3. Website Reachability
    website = lead.get("website", "").strip()
    if website and website.startswith("http"):
        try:
            # Ping website (5s timeout)
            resp = requests.head(website, timeout=5, allow_redirects=True)
            if resp.status_code >= 400:
                notes.append("Website not reachable")
        except:
            notes.append("Website not reachable")
    else:
        lead["website"] = ""

    # 4. Final Status Logic
    has_phone = bool(lead["phone"])
    has_email = bool(lead["email"])
    has_web = bool(lead["website"])
    
    # Valid if ANY contact info is valid and no critical fails
    if has_phone or has_email or has_web:
        status = "Valid"
    elif not has_phone and not has_email and not has_web:
        if notes:
            status = "Invalid"
        else:
            status = "Pending"
            
    lead["validation_status"] = status
    lead["validation_notes"] = ", ".join(notes)
    
    # Debug Log
    print(f"Lead: {lead.get('name')} | Status: {status}")
    
    return lead

def extract_email_from_web(url):
    """
    Advanced extraction from website HTML
    """
    if not url or not url.startswith("http"): return ""
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, headers=headers, timeout=5)
        emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', resp.text)
        if emails:
            # Filter out common false positives
            filtered = [e for e in emails if not e.endswith(('.png', '.jpg', '.jpeg', '.gif'))]
            return filtered[0] if filtered else ""
    except:
        pass
    return ""
