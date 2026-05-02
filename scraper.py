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
from typing import Dict, Any, List

from validation import validate_lead
from website_scraper import run_website_enrichment

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

def build_smart_queries(query: str) -> list:
    """Build queries that return actual business contact pages instead of aggregators."""
    base = query.strip()
    return [
        f"{base} official website phone number email contact",
        f"{base} contact us phone email address site:.in",
        f'"{base}" phone "+91" email contact',
    ]

def search_duckduckgo(query: str, limit: int = 5) -> list:
    """Smart DuckDuckGo search that filters out aggregators and finds official sites."""
    leads = []
    seen_names = set()
    queries = build_smart_queries(query)

    for smart_query in queries:
        if len(leads) >= limit:
            break
        try:
            logger.info(f"Trying smart query: {smart_query}")
            url = f"https://html.duckduckgo.com/html/?q={smart_query.replace(' ', '+')}"
            resp = requests.get(url, headers=HEADERS, timeout=12)
            if resp.status_code != 200:
                continue
                
            soup = BeautifulSoup(resp.text, "html.parser")
            results = soup.select("div.result__body")

            for result in results:
                if len(leads) >= limit:
                    break

                title_el = result.select_one("a.result__a")
                if not title_el:
                    continue

                name = title_el.get_text(strip=True)

                # 1. Skip aggregator/directory domains
                skip_domains = [
                    "booking.com", "tripadvisor", "makemytrip", "goibibo",
                    "agoda", "kayak", "expedia", "holidify", "oyo",
                    "hotels.com", "yatra", "cleartrip", "trivago", "justdial",
                    "indiamart", "yellowpages", "facebook.com", "instagram.com"
                ]
                href = title_el.get("href", "")
                if any(skip in href.lower() for skip in skip_domains):
                    continue
                
                # 2. Skip listicle titles
                if any(skip in name.lower() for skip in ["best hotels", "top 10", "list of", "10 best"]):
                    continue

                if name in seen_names:
                    continue
                seen_names.add(name)

                lead = get_full_structure()
                lead["name"] = name
                lead["website"] = href if href.startswith("http") else ""
                lead["category"] = query.split()[0].title()

                # Extract info from snippet
                snippet_el = result.select_one("a.result__snippet")
                if snippet_el:
                    text = snippet_el.get_text()
                    lead["description"] = text[:300]
                    # Phone extraction
                    phones = re.findall(r'[\+]?[0-9]{10,13}', text)
                    if phones:
                        lead["phone"] = phones[0]
                    # Attempt address extraction from snippet
                    addr_match = re.search(r'[A-Z][a-z]+(?:\s[A-Z][a-z]+)*,\s*[A-Za-z]+', text)
                    if addr_match:
                        lead["address"] = addr_match.group()

                lead["lead_id"] = hashlib.md5(name.lower().encode()).hexdigest()

                if lead["name"] and len(lead["name"]) > 3:
                    leads.append(lead)

        except Exception as e:
            logger.error(f"Search error for query '{smart_query}': {e}")
            time.sleep(2)

    return leads[:limit]

def main():
    if len(sys.argv) < 2:
        return
    query = sys.argv[1]
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 5

    logger.info(f"🚀 Smart Scrape: {query} | Target: {limit}")
    leads = search_duckduckgo(query, limit)

    # Day 5 — Website Enrichment
    if leads:
        logger.info("Running Day 5 website enrichment...")
        leads = run_website_enrichment(leads)

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