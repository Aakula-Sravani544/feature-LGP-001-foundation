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

SERPER_API_KEY = os.environ.get("SERPER_API_KEY", "")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9"
}

def get_full_structure() -> dict:
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

def extract_email_from_website(url: str) -> str:
    """Synchronously extracts emails from a website."""
    if not url or not url.startswith("http"):
        return ""
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
                if not any(x in email.lower() for x in ['.png','.jpg','.gif','.woff','svg','css','js','example']):
                    return email
            except:
                continue
    except Exception as e:
        logger.debug(f"Email extraction failed for {url}: {e}")
    return ""

def extract_phone_from_website(url: str) -> str:
    """Synchronously extracts phone numbers from a website."""
    if not url or not url.startswith("http"):
        return ""
    try:
        resp = requests.get(url, timeout=6, headers=HEADERS)
        if resp.status_code != 200:
            return ""
            
        phones = re.findall(r'[\+]?[0-9]{10,13}', resp.text)
        for p in phones:
            cleaned = re.sub(r'\D', '', p)
            if len(cleaned) >= 10:
                return p
    except:
        pass
    return ""

def search_with_serper(query: str, limit: int = 5) -> list:
    """Search using Serper.dev API — real Google results."""
    if not SERPER_API_KEY:
        print("LOG:ERROR - SERPER_API_KEY not found in environment!", flush=True)
        return []

    print(f"LOG:Using Serper API with key: {SERPER_API_KEY[:8]}...", flush=True)

    # Domains to exclude (aggregators/directories)
    skip_domains = [
        "booking.com", "tripadvisor", "makemytrip", "goibibo",
        "agoda", "kayak", "expedia", "oyo", "justdial", "sulekha",
        "wikipedia", "youtube", "facebook", "instagram", "twitter",
        "indiamart", "tradeindia", "quora", "reddit", "linkedin"
    ]

    leads = []
    # Run 2 different queries to get more variety and official sites
    queries = [
        f"{query} official website contact phone",
        f"{query} address email phone number"
    ]

    seen_names = set()

    for q in queries:
        if len(leads) >= limit:
            break
        try:
            resp = requests.post(
                "https://google.serper.dev/search",
                headers={
                    "X-API-KEY": SERPER_API_KEY,
                    "Content-Type": "application/json"
                },
                json={
                    "q": q,
                    "num": 10,
                    "gl": "in",
                    "hl": "en"
                },
                timeout=10
            )
            data = resp.json()
            results = data.get("organic", [])
            print(f"LOG:Serper returned {len(results)} results for: {q}", flush=True)

            for r in results:
                if len(leads) >= limit:
                    break

                name = r.get("title", "").strip()
                href = r.get("link", "")
                snippet = r.get("snippet", "")

                # 1. Skip aggregator sites
                if any(s in href.lower() for s in skip_domains):
                    continue

                # 2. Skip duplicate names
                if name in seen_names:
                    continue
                seen_names.add(name)

                lead = get_full_structure()
                lead["name"] = name
                lead["website"] = href
                lead["description"] = snippet[:300]
                lead["category"] = query.split()[0].title()

                # 3. Extract phone from snippet
                phones = re.findall(r'[\+]?[0-9]{10,13}', snippet)
                if phones:
                    lead["phone"] = phones[0]

                # 4. Extract address from snippet
                lead["address"] = snippet[:150]

                # 5. Generate lead_id
                lead["lead_id"] = hashlib.md5(
                    name.lower().encode()
                ).hexdigest()

                if name and len(name) > 3:
                    leads.append(lead)
                    print(f"LOG:Found lead: {name}", flush=True)

        except Exception as e:
            print(f"LOG:Serper error: {e}", flush=True)
            logger.error(f"Serper search failed for query '{q}': {e}")

    return leads

def enrich_leads(leads: list) -> list:
    """Visit each website to extract email and phone."""
    for i, lead in enumerate(leads):
        if lead.get("website"):
            print(f"LOG:Enriching {i+1}/{len(leads)}: {lead['name'][:30]}", flush=True)
            # Recovery: Email
            if not lead.get("email"):
                lead["email"] = extract_email_from_website(lead["website"])
            # Recovery: Phone
            if not lead.get("phone"):
                lead["phone"] = extract_phone_from_website(lead["website"])
            time.sleep(0.3)
    return leads

def main():
    if len(sys.argv) < 2:
        print("LOG:No query provided", flush=True)
        return

    query = sys.argv[1]
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 5

    print(f"LOG:🚀 LeadPulse Pro Engine | Target: {limit}", flush=True)
    print(f"LOG:Searching for: {query}", flush=True)

    # Step 1: Search with Serper
    leads = search_with_serper(query, limit)

    if not leads:
        print("LOG:No results found. Check SERPER_API_KEY in Render environment.", flush=True)
        return

    # Step 2: Enrich with website data
    print(f"LOG:Enriching {len(leads)} leads with website data...", flush=True)
    leads = enrich_leads(leads)

    # Step 3: Validate and output
    print(f"LOG:Validating leads...", flush=True)
    for lead in leads:
        try:
            # Apply Day 4 Validation
            lead = validate_lead(lead)
            print(f"DATA:{json.dumps(lead)}", flush=True)
        except Exception as e:
            logger.error(f"Validation failed for lead: {e}")

    print(f"LOG:Complete. Total leads: {len(leads)}", flush=True)

if __name__ == "__main__":
    main()