import requests
import re
import json
import hashlib
import os
import sys
import logging
import time
import signal
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

def timeout_handler(signum, frame):
    """Handler for the 90s global timeout."""
    logger.error("Scraper timed out after 90 seconds")
    sys.exit(1)

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

def search_duckduckgo(query: str, limit: int = 5) -> list:
    """Smart DuckDuckGo search that filters out aggregators and finds official sites."""
    leads = []
    seen_names = set()
    
    # Build a smarter query based on user input
    location = query.split(" in ")[-1] if " in " in query else ""
    keyword = query.split(" in ")[0] if " in " in query else query
    smart_query = f"{keyword} {location} contact phone email official website"
    
    try:
        logger.info(f"Searching DuckDuckGo with: {smart_query}")
        url = f"https://html.duckduckgo.com/html/?q={smart_query.replace(' ', '+')}"
        
        # Connection error handling
        try:
            resp = requests.get(url, headers=HEADERS, timeout=8)
            resp.raise_for_status()
        except requests.exceptions.Timeout:
            logger.error("DuckDuckGo timeout")
            return leads
        except requests.exceptions.ConnectionError:
            logger.error("DuckDuckGo connection error")
            return leads
        except Exception as e:
            logger.error(f"Search failed: {e}")
            return leads
            
        soup = BeautifulSoup(resp.text, "html.parser")
        results = soup.select("div.result__body")

        for result in results:
            if len(leads) >= limit:
                break

            title_el = result.select_one("a.result__a")
            if not title_el:
                continue

            name = title_el.get_text(strip=True)

            # Skip aggregator/directory domains
            skip_domains = [
                "booking.com", "tripadvisor", "makemytrip", "goibibo",
                "agoda", "kayak", "expedia", "holidify", "oyo",
                "hotels.com", "yatra", "cleartrip", "trivago", "justdial",
                "indiamart", "yellowpages", "facebook.com", "instagram.com"
            ]
            href = title_el.get("href", "")
            if any(skip in href.lower() for skip in skip_domains):
                continue
            
            if any(skip in name.lower() for skip in ["best hotels", "top 10", "list of", "10 best"]):
                continue

            if name in seen_names:
                continue
            seen_names.add(name)

            lead = get_full_structure()
            lead["name"] = name
            lead["website"] = href if href.startswith("http") else ""
            lead["category"] = keyword.title()

            snippet_el = result.select_one("a.result__snippet")
            if snippet_el:
                text = snippet_el.get_text()
                lead["description"] = text[:300]
                phones = re.findall(r'[\+]?[0-9]{10,13}', text)
                if phones:
                    lead["phone"] = phones[0]
                addr_match = re.search(r'[A-Z][a-z]+(?:\s[A-Z][a-z]+)*,\s*[A-Za-z]+', text)
                if addr_match:
                    lead["address"] = addr_match.group()

            lead["lead_id"] = hashlib.md5(name.lower().encode()).hexdigest()

            # Immediate print for UI feedback
            if lead["name"]:
                lead = validate_lead(lead)
                print(f"DATA:{json.dumps(lead)}", flush=True)
                leads.append(lead)

    except Exception as e:
        logger.error(f"Search error: {e}")

    return leads[:limit]

def main():
    # Signal-based timeout
    signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(90)

    if len(sys.argv) < 2:
        return
    query = sys.argv[1]
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 5

    logger.info(f"🚀 Smart Scrape: {query} | Target: {limit}")
    
    leads = search_duckduckgo(query, limit)

    # If no results found, log a message for the UI
    if not leads:
        print("LOG:No results found. Try a different keyword or location.", flush=True)

    # Day 5 — Website Enrichment (Parallel Batch)
    if leads:
        logger.info("Running Day 5 website enrichment...")
        leads = run_website_enrichment(leads)

    # Final output with enriched data
    for lead in leads:
        try:
            lead = validate_lead(lead)
            print(f"DATA:{json.dumps(lead)}", flush=True)
        except Exception as e:
            logger.error(f"Lead processing failed: {e}")

    logger.info(f"Done. Successfully provided {len(leads)} leads.")

if __name__ == "__main__":
    main()