import phonenumbers
from email_validator import validate_email, EmailNotValidError

def validate_lead(lead):
    notes = []
    status = "Pending"
    
    # Phone Validation
    phone = lead.get('phone', '')
    if phone:
        try:
            if not phone.startswith('+'):
                parsed_phone = phonenumbers.parse(phone, "IN") # Fallback to IN if missing country code
            else:
                parsed_phone = phonenumbers.parse(phone, None)
                
            if phonenumbers.is_valid_number(parsed_phone):
                lead['phone'] = phonenumbers.format_number(parsed_phone, phonenumbers.PhoneNumberFormat.E164)
                status = "Valid"
            else:
                notes.append("Invalid phone number format")
                status = "Warning"
        except phonenumbers.NumberParseException:
            notes.append("Unparseable phone number")
            status = "Warning"
    else:
        notes.append("Missing phone number")
        status = "Warning"

    # Email Validation
    email = lead.get('email', '')
    if email:
        try:
            valid = validate_email(email)
            lead['email'] = valid.normalized
            if status != "Warning": status = "Valid"
        except EmailNotValidError as e:
            notes.append(f"Invalid email: {str(e)}")
            status = "Warning"
    else:
        notes.append("Missing email")
        if status != "Invalid":
            status = "Warning"

    # Website check
    if not lead.get('website', ''):
        notes.append("Missing website")

    if not phone and not email:
        status = "Invalid"
        notes.append("No contact information available")

    lead['validation_status'] = status
    lead['validation_notes'] = "; ".join(notes)
    return lead
