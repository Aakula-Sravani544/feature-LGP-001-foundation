import requests
import re
import json
import hashlib
import os
import sys
import logging
import time
from datetime import datetime
from bs4 import BeautifulSoup
from email_validator import validate_email
from typing import Dict, Any

from validation import validate_lead

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

def get_full_structure() -> Dict[str, Any]:
    """Returns a standardized lead dictionary."""
    return {
        "lead_id": "", "name": "", "address": "", "phone": "",
        "email": "", "website": "", "rating": "", "reviews": "",
        "category": "", "google_maps_url": "", "description": "",
        "hours": "", "social_media": "", "additional_data": "",
        "scraped_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "ai_analysis": "N/A", "validation_status": "Pending",
        "validation_notes": "", "sub_region": ""
    }

def extract_email_sync(url: str) -> str:
    """Synchronously extracts emails from a website."""
    try:
        resp = requests.get(url, timeout=6, headers=HEADERS)
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
                # Filter out garbage
                if not any(x in email.lower() for x in ['.png','.jpg','.gif','.woff','css','js']):
                    return email
            except:
                continue
    except Exception as e:
        logger.debug(f"Email extraction failed for {url}: {e}")
    return ""

def search_duckduckgo(query: str, limit: int = 5) -> list:
    """Search DuckDuckGo HTML — more reliable for cloud server IPs."""
    leads = []
    try:
        # Use DuckDuckGo HTML version which is very lightweight and less prone to blocks
        url = f"https://html.duckduckgo.com/html/?q={query.replace(' ', '+')}"
        resp = requests.get(url, headers=HEADERS, timeout=12)
        if resp.status_code != 200:
            logger.error(f"DuckDuckGo returned status {resp.status_code}")
            return []
            
        soup = BeautifulSoup(resp.text, "html.parser")
        results = soup.select("div.result__body")
        logger.info(f"DuckDuckGo returned {len(results)} raw results")

        for result in results[:limit*3]:
            lead = get_full_structure()

            # 1. Name
            title_el = result.select_one("a.result__a")
            if not title_el:
                continue
            lead["name"] = title_el.get_text(strip=True)

            # 2. Website
            href = title_el.get("href", "")
            if href and href.startswith("http") and "duckduckgo" not in href:
                lead["website"] = href

            # 3. Snippet — extract phone and address
            snippet_el = result.select_one("a.result__snippet")
            if snippet_el:
                text = snippet_el.get_text()
                lead["description"] = text[:300]
                # Improved phone regex
                phones = re.findall(r'[\+]?[0-9]{10,13}|[0-9]{4,5}[\s\-][0-9]{6,8}', text)
                if phones:
                    lead["phone"] = phones[0].strip()

            # 4. Lead ID
            lead["lead_id"] = hashlib.md5(
                lead["name"].lower().encode()
            ).hexdigest()

            if lead["name"] and len(lead["name"]) > 3:
                leads.append(lead)

            if len(leads) >= limit:
                break

    except Exception as e:
        logger.error(f"DuckDuckGo search error: {e}")

    # Deep Scan: Visit each website to find email + phone
    for lead in leads:
        if lead.get("website"):
            logger.info(f"Deep scanning: {lead['website']}")
            # Recover Email
            if not lead.get("email"):
                lead["email"] = extract_email_sync(lead["website"])
            
            # Recover Phone if missing from snippet
            if not lead.get("phone"):
                try:
                    resp = requests.get(lead["website"], timeout=6, headers=HEADERS)
                    phones = re.findall(r'[\+]?[0-9]{10,13}', resp.text)
                    if phones:
                        lead["phone"] = phones[0]
                except:
                    pass
        time.sleep(0.5)

    return leads

def main():
    if len(sys.argv) < 2:
        return
    query = sys.argv[1]
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 5

    logger.info(f"🚀 DuckDuckGo Smart Scrape: {query} | Target: {limit}")
    leads = search_duckduckgo(query, limit)

    for lead in leads:
        try:
            # Apply Day 4 Validation
            lead = validate_lead(lead)
            print(f"DATA:{json.dumps(lead)}", flush=True)
        except Exception as e:
            logger.error(f"Lead processing failed: {e}")

    logger.info(f"Done. Successfully provided {len(leads)} leads.")

if __name__ == "__main__":
    main()