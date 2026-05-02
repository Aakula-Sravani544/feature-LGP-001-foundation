import requests
import re
import json
import hashlib
import os
import sys
import logging
from datetime import datetime
from bs4 import BeautifulSoup
from email_validator import validate_email
from typing import Dict, Any

from validation import validate_lead

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def get_full_structure() -> Dict[str, Any]:
    """Returns a standardized lead dictionary with zero-Selenium defaults."""
    return {
        "lead_id": "",
        "name": "", "address": "", "phone": "", "email": "", "website": "",
        "rating": "", "reviews": "", "category": "", "google_maps_url": "",
        "description": "", "hours": "", "social_media": "", "additional_data": "",
        "scraped_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "ai_analysis": "N/A", "validation_status": "Pending",
        "validation_notes": "", "sub_region": ""
    }

def extract_email_sync(url: str) -> str:
    """Synchronously scrapes a website for email addresses."""
    if not url or not url.startswith("http"):
        return ""
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        resp = requests.get(url, timeout=6, headers=headers)
        if resp.status_code != 200:
            return ""
            
        soup = BeautifulSoup(resp.text, "html.parser")
        
        # 1. Search mailto links
        for a in soup.find_all("a", href=re.compile(r"^mailto:")):
            email = a["href"].replace("mailto:", "").split("?")[0].strip()
            try:
                validate_email(email)
                return email
            except:
                continue
        
        # 2. Regex search in page text
        email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        emails = re.findall(email_pattern, resp.text)
        for email in emails:
            try:
                validate_email(email)
                return email
            except:
                continue
    except Exception as e:
        logger.debug(f"Email sync extraction failed for {url}: {e}")
    return ""

def search_google_free(query: str, limit: int = 5) -> list:
    """Scrape Google search for business contacts - no API or Selenium needed."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9"
    }
    leads = []

    # Search: Get business names and snippets
    search_url = f"https://www.google.com/search?q={query.replace(' ', '+')}+contact+phone+email&num=20"
    try:
        resp = requests.get(search_url, headers=headers, timeout=10)
        if resp.status_code != 200:
            logger.error(f"Google search returned status {resp.status_code}")
            return []
            
        soup = BeautifulSoup(resp.text, "html.parser")

        # Extract business cards/blocks from organic results
        for block in soup.select("div.g, div.tF2Cxc, div.MjjYud div.g")[:limit*2]:
            lead = get_full_structure()

            # 1. Name from heading
            title = block.select_one("h3")
            if not title:
                continue
            lead["name"] = title.get_text(strip=True)

            # 2. Website link
            link = block.select_one("a[href^='http']")
            if link:
                url = link.get("href", "")
                if url and "google" not in url:
                    lead["website"] = url

            # 3. Snippet for address/phone
            snippet = block.select_one("div.VwiC3b, span.aCOpRe, div.IsZvec")
            if snippet:
                text = snippet.get_text()
                # Phone extraction
                phones = re.findall(r'[\+]?[0-9]{10,13}|[0-9]{3,5}[\s\-][0-9]{6,8}', text)
                if phones:
                    lead["phone"] = phones[0].strip()
                lead["description"] = text[:200]

            # 4. Generate lead_id using hashlib MD5
            lead["lead_id"] = hashlib.md5(
                (lead["name"] + lead.get("address","")).lower().encode()
            ).hexdigest()

            if lead["name"] and len(lead["name"]) > 3:
                leads.append(lead)

            if len(leads) >= limit:
                break

    except Exception as e:
        logger.error(f"Google search failed: {e}")

    # Step 2: Visit website to find email for each lead
    for lead in leads:
        if lead.get("website") and not lead.get("email"):
            logger.info(f"Scanning website for email: {lead['website']}")
            lead["email"] = extract_email_sync(lead["website"])

    return leads

def main():
    if len(sys.argv) < 2:
        return
    query = sys.argv[1]
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 5

    logger.info(f"🚀 Zero-API Free Scraping: {query} | Target: {limit}")
    leads = search_google_free(query, limit)

    for lead in leads:
        try:
            # Apply Day 4 Validation logic
            lead = validate_lead(lead)
            print(f"DATA:{json.dumps(lead)}", flush=True)
        except Exception as e:
            logger.error(f"Error processing lead: {e}")

    logger.info(f"Done. Total leads: {len(leads)}")

if __name__ == "__main__":
    main()