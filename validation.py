import logging
import re
import aiohttp
import asyncio
import requests
from bs4 import BeautifulSoup
import phonenumbers
from email_validator import validate_email, EmailNotValidError
from typing import Dict, Any, Optional

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def extract_email_from_website(url: str) -> str:
    """Asynchronously scrapes a website for email addresses.

    Args:
        url: The website URL to scrape.

    Returns:
        The first valid email address found, or an empty string.
    """
    if not url or not url.startswith("http"):
        return ""
    
    try:
        timeout = aiohttp.ClientTimeout(total=8)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url) as response:
                if response.status == 200:
                    html = await response.text()
                    soup = BeautifulSoup(html, "html.parser")
                    
                    # 1. Search mailto: links
                    for a in soup.find_all("a", href=re.compile(r"^mailto:")):
                        email = a["href"].replace("mailto:", "").split("?")[0].strip()
                        try:
                            validate_email(email)
                            return email
                        except:
                            continue
                    
                    # 2. Regex search in page text
                    email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
                    emails = re.findall(email_pattern, html)
                    for email in emails:
                        try:
                            validate_email(email)
                            return email
                        except:
                            continue
    except Exception as e:
        logger.debug(f"Email extraction failed for {url}: {e}")
        
    return ""

def validate_lead(lead: Dict[str, Any]) -> Dict[str, Any]:
    """Day 4 Validation Layer: Strict contact verification.

    Args:
        lead: Dictionary containing 'phone', 'email', 'website'.

    Returns:
        Updated dictionary with 'validation_status' and 'validation_notes'.
    """
    notes = []
    
    # 1. Phone Validation (E.164)
    raw_phone = lead.get("phone", "").strip()
    if raw_phone:
        try:
            # Clean and parse
            parsed = phonenumbers.parse(raw_phone, "IN")
            if phonenumbers.is_valid_number(parsed):
                lead["phone"] = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
            else:
                lead["phone"] = ""
                notes.append("Invalid phone format")
        except Exception:
            lead["phone"] = ""
            notes.append("Invalid phone format")
    else:
        lead["phone"] = ""

    # 2. Email Validation
    raw_email = lead.get("email", "").strip()
    if raw_email:
        try:
            valid = validate_email(raw_email)
            lead["email"] = valid.normalized
        except EmailNotValidError:
            lead["email"] = ""
            notes.append("Email invalid or unreachable")

    # 3. Website Check
    website = lead.get("website", "").strip()
    if website and website.startswith("http"):
        try:
            resp = requests.head(website, timeout=5)
            if resp.status_code >= 400:
                notes.append("Website returned error status")
        except Exception:
            notes.append("Website unreachable")

    # 4. Status Logic
    has_phone = bool(lead.get("phone"))
    has_email = bool(lead.get("email"))
    
    # "Valid" -> phone OR email is present and passed validation
    if has_phone or has_email:
        lead["validation_status"] = "Valid"
    else:
        lead["validation_status"] = "Pending"
        notes.append("Contact details not available from source")

    lead["validation_notes"] = ", ".join(notes)
    return lead
