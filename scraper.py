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

def search_source_1_ddg(query: str, limit: int) -> list:
    """DuckDuckGo HTML search."""
    leads = []
    try:
        smart = f"{query} contact phone email official website"
        url = f"https://html.duckduckgo.com/html/?q={smart.replace(' ', '+')}"
        resp = requests.get(url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(resp.text, "html.parser")
        results = soup.select("div.result__body")
        logger.info(f"DDG returned {len(results)} results")
        
        skip = ["booking.com","tripadvisor","makemytrip","goibibo",
                "agoda","kayak","expedia","oyo","justdial","sulekha",
                "wikipedia","youtube","facebook","instagram"]
                
        for result in results[:limit*2]:
            title_el = result.select_one("a.result__a")
            if not title_el:
                continue
            name = title_el.get_text(strip=True)
            href = title_el.get("href", "")
            
            if any(s in href.lower() for s in skip):
                continue
                
            lead = get_full_structure()
            lead["name"] = name
            lead["website"] = href if href.startswith("http") else ""
            lead["category"] = query.split()[0].title()
            
            snippet = result.select_one("a.result__snippet")
            if snippet:
                text = snippet.get_text()
                lead["description"] = text[:300]
                phones = re.findall(r'[\+]?[0-9]{10,13}', text)
                if phones:
                    lead["phone"] = phones[0]
                    
            lead["lead_id"] = hashlib.md5(name.lower().encode()).hexdigest()
            if name and len(name) > 3:
                leads.append(lead)
            if len(leads) >= limit:
                break
    except Exception as e:
        logger.error(f"DDG failed: {e}")
    return leads

def search_source_2_bing(query: str, limit: int) -> list:
    """Bing search as fallback."""
    leads = []
    try:
        smart = f"{query} contact phone email"
        url = f"https://www.bing.com/search?q={smart.replace(' ', '+')}&count=20"
        resp = requests.get(url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(resp.text, "html.parser")
        results = soup.select("li.b_algo")
        logger.info(f"Bing returned {len(results)} results")
        
        skip = ["booking.com","tripadvisor","makemytrip","goibibo",
                "agoda","kayak","expedia","oyo","justdial","sulekha",
                "wikipedia","youtube"]
                
        for result in results[:limit*2]:
            title_el = result.select_one("h2 a")
            if not title_el:
                continue
            name = title_el.get_text(strip=True)
            href = title_el.get("href", "")
            
            if any(s in href.lower() for s in skip):
                continue
                
            lead = get_full_structure()
            lead["name"] = name
            lead["website"] = href if href.startswith("http") else ""
            lead["category"] = query.split()[0].title()
            
            snippet = result.select_one("div.b_caption p, p.b_lineclamp2")
            if snippet:
                text = snippet.get_text()
                lead["description"] = text[:300]
                phones = re.findall(r'[\+]?[0-9]{10,13}', text)
                if phones:
                    lead["phone"] = phones[0]
                    
            lead["lead_id"] = hashlib.md5(name.lower().encode()).hexdigest()
            if name and len(name) > 3:
                leads.append(lead)
            if len(leads) >= limit:
                break
    except Exception as e:
        logger.error(f"Bing failed: {e}")
    return leads

def search_source_3_direct(query: str, limit: int) -> list:
    """Direct business directory scraping - sulekha fallback."""
    leads = []
    keyword = query.split(" in ")[0] if " in " in query else query
    location = query.split(" in ")[-1] if " in " in query else "hyderabad"

    try:
        url = f"https://www.sulekha.com/{keyword.replace(' ','-')}/{location.replace(' ','-')}"
        resp = requests.get(url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(resp.text, "html.parser")
        
        for card in soup.select("div.compny-dtls, div.col-xs-12.srp-biz-card")[:limit]:
            lead = get_full_structure()
            name_el = card.select_one("h2, h3, .biz-name")
            if name_el:
                lead["name"] = name_el.get_text(strip=True)
            
            phone_el = card.select_one("[class*='phone'], [class*='mobile']")
            if phone_el:
                lead["phone"] = phone_el.get_text(strip=True)
                
            addr_el = card.select_one("[class*='address'], [class*='addr']")
            if addr_el:
                lead["address"] = addr_el.get_text(strip=True)[:150]
                
            lead["category"] = keyword.title()
            lead["lead_id"] = hashlib.md5(lead["name"].lower().encode()).hexdigest()
            
            if lead["name"]:
                leads.append(lead)
            if len(leads) >= limit:
                break
        logger.info(f"Sulekha returned {len(leads)} results")
    except Exception as e:
        logger.error(f"Sulekha failed: {e}")

    return leads

def search_all_sources(query: str, limit: int = 5) -> list:
    """Try all 3 sources in order until we get results."""
    
    # Source 1: DuckDuckGo
    print(f"LOG:Trying DuckDuckGo search...", flush=True)
    leads = search_source_1_ddg(query, limit)
    if leads:
        print(f"LOG:DuckDuckGo found {len(leads)} results", flush=True)
        return leads

    # Source 2: Bing
    print(f"LOG:DuckDuckGo blocked. Trying Bing...", flush=True)
    leads = search_source_2_bing(query, limit)
    if leads:
        print(f"LOG:Bing found {len(leads)} results", flush=True)
        return leads

    # Source 3: Direct directories
    print(f"LOG:Bing blocked. Trying business directories...", flush=True)
    leads = search_source_3_direct(query, limit)
    if leads:
        print(f"LOG:Directory found {len(leads)} results", flush=True)
        return leads

    print(f"LOG:All sources blocked. No results for '{query}'", flush=True)
    return []

def main():
    # Signal-based timeout
    signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(90)

    if len(sys.argv) < 2:
        return
    query = sys.argv[1]
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 5

    logger.info(f"🚀 Multi-Source Scrape: {query} | Target: {limit}")
    
    leads = search_all_sources(query, limit)

    # If no results found, log a message for the UI
    if not leads:
        print("LOG:No results found. Try a different keyword or location.", flush=True)
        return

    # Enrichment and Validation Loop
    for lead in leads:
        if lead.get("website") and not lead.get("email"):
            try:
                resp = requests.get(lead["website"], timeout=6, headers=HEADERS)
                soup = BeautifulSoup(resp.text, "html.parser")
                # Email from mailto
                for a in soup.find_all("a", href=re.compile(r"^mailto:")):
                    email = a["href"].replace("mailto:", "").split("?")[0].strip()
                    try:
                        validate_email(email)
                        lead["email"] = email
                        break
                    except: continue
                
                # Phone recovery from page
                if not lead.get("phone"):
                    phones = re.findall(r'[\+]?[0-9]{10,13}', resp.text)
                    if phones:
                        lead["phone"] = phones[0]
            except Exception as e:
                logger.debug(f"Website enrichment failed for {lead['name']}: {e}")
        
        # Apply Day 4 Validation and print
        try:
            lead = validate_lead(lead)
            print(f"DATA:{json.dumps(lead)}", flush=True)
        except Exception as e:
            logger.error(f"Lead processing failed: {e}")

    logger.info(f"Done. Successfully provided {len(leads)} leads.")

if __name__ == "__main__":
    main()