import logging
import re
import aiohttp
import asyncio
from bs4 import BeautifulSoup
import requests
import phonenumbers
from email_validator import validate_email, EmailNotValidError
from typing import Dict, Any, Optional

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def normalize_phone(phone: str, region: str = "IN") -> Optional[str]:
    """Normalizes a phone number to E.164 format.

    Args:
        phone: The raw phone number string.
        region: The ISO 3166-1 alpha-2 region code. Defaults to "IN".

    Returns:
        The normalized phone number in E.164 format, or None if invalid.
    """
    if not phone:
        return None
    try:
        parsed = phonenumbers.parse(phone, region)
        if phonenumbers.is_valid_number(parsed):
            return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
    except Exception as e:
        logger.debug(f"Phone normalization failed for {phone}: {e}")
    return None

async def scrape_emails_from_website(url: str) -> Optional[str]:
    """Asynchronously scrapes a website for email addresses.

    Args:
        url: The website URL to scrape.

    Returns:
        The first found email address, or None.
    """
    if not url or not url.startswith("http"):
        return None
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=8)) as response:
                if response.status == 200:
                    html = await response.text()
                    soup = BeautifulSoup(html, "html.parser")
                    
                    # 1. Search mailto links
                    for a in soup.find_all("a", href=re.compile(r"^mailto:")):
                        email = a["href"].replace("mailto:", "").split("?")[0]
                        return email.strip()
                    
                    # 2. Regex search in text
                    emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', html)
                    if emails:
                        return emails[0]
    except Exception as e:
        logger.debug(f"Email scraping failed for {url}: {e}")
    return None

def validate_lead(lead: Dict[str, Any]) -> Dict[str, Any]:
    """Performs Day 4 validation on a lead dictionary.

    Args:
        lead: The lead dictionary containing name, phone, email, website.

    Returns:
        The updated lead dictionary with validation_status and validation_notes.
    """
    notes = []
    
    # 1. Phone Normalization
    raw_phone = lead.get("phone", "")
    normalized_phone = normalize_phone(raw_phone)
    if raw_phone and not normalized_phone:
        notes.append("Invalid phone format")
    lead["phone"] = normalized_phone or ""

    # 2. Email Validation
    raw_email = lead.get("email", "")
    if raw_email:
        try:
            valid = validate_email(raw_email)
            lead["email"] = valid.normalized
        except EmailNotValidError:
            lead["email"] = ""
            notes.append("Email unreachable") # Requirement: Using user's specific note

    # 3. Website Reachability
    website = lead.get("website", "")
    if website and website.startswith("http"):
        try:
            resp = requests.get(website, timeout=5, allow_redirects=True)
            if resp.status_code >= 400:
                notes.append("Website not reachable")
        except Exception:
            notes.append("Website not reachable")
    else:
        lead["website"] = ""

    # 4. Final Status Logic
    has_phone = bool(lead["phone"])
    has_email = bool(lead["email"])
    
    if has_phone or has_email:
        lead["validation_status"] = "Valid"
    elif raw_phone or raw_email:
        lead["validation_status"] = "Invalid"
    else:
        lead["validation_status"] = "Pending"
        notes.append("No contact data found")

    lead["validation_notes"] = ", ".join(notes)
    
    logger.info(f"Lead: {lead.get('name')} | Status: {lead['validation_status']}")
    return lead
