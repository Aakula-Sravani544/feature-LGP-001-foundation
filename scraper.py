import sys
import json
import time
import random
import re
import os
import hashlib
import logging
import requests
from datetime import datetime
from bs4 import BeautifulSoup
from email_validator import validate_email
from typing import List, Dict, Any

from validation import validate_lead

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# API Keys from Environment
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", "")
SERPAPI_KEY = os.environ.get("SERPAPI_KEY", "")

def get_full_structure() -> Dict[str, Any]:
    """Returns a standardized lead dictionary with zero-Selenium defaults."""
    return {
        "lead_id": "",
        "name": "", "address": "", "phone": "", "email": "", "website": "",
        "rating": "", "reviews": "", "category": "", "google_maps_url": "N/A",
        "description": "N/A", "hours": "N/A", "social_media": "N/A", "additional_data": "",
        "scraped_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "ai_analysis": "N/A", "validation_status": "Pending",
        "validation_notes": "", "sub_region": ""
    }

def extract_email_sync(url: str) -> str:
    """Lightweight synchronous website email extractor."""
    if not url or not url.startswith("http") or "google.com" in url:
        return ""
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        resp = requests.get(url, timeout=6, headers=headers)
        if resp.status_code != 200:
            return ""
            
        soup = BeautifulSoup(resp.text, "html.parser")
        
        # 1. Check mailto links
        for a in soup.find_all("a", href=re.compile(r"^mailto:")):
            email = a["href"].replace("mailto:", "").split("?")[0].strip()
            try:
                validate_email(email)
                return email
            except: continue
            
        # 2. Regex scan text
        email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        emails = re.findall(email_pattern, resp.text)
        for email in emails:
            try:
                validate_email(email)
                return email
            except: continue
    except:
        pass
    return ""

def generate_lead_id(name: str, address: str) -> str:
    """Generates a unique hash-based lead ID."""
    raw = f"{name}{address}".lower().encode()
    return hashlib.md5(raw).hexdigest()

# --- METHOD 1: GOOGLE PLACES API ---
def search_places_api(query: str, limit: int = 5) -> List[Dict[str, Any]]:
    """Use Google Places API for high-fidelity structured data."""
    logger.info(f"Method 1: Google Places API | Query: {query}")
    leads = []
    
    try:
        search_url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
        params = {"query": query, "key": GOOGLE_API_KEY}
        resp = requests.get(search_url, params=params, timeout=10)
        data = resp.json()
        
        results = data.get("results", [])[:limit]
        for place in results:
            place_id = place.get("place_id")
            
            # Get deep details (phone, website)
            detail_url = "https://maps.googleapis.com/maps/api/place/details/json"
            detail_params = {
                "place_id": place_id,
                "fields": "name,formatted_phone_number,website,formatted_address,rating,user_ratings_total,types",
                "key": GOOGLE_API_KEY
            }
            d_resp = requests.get(detail_url, params=detail_params, timeout=10)
            detail = d_resp.json().get("result", {})
            
            lead = get_full_structure()
            lead["name"] = detail.get("name", place.get("name", ""))
            lead["address"] = detail.get("formatted_address", place.get("formatted_address", ""))
            lead["phone"] = detail.get("formatted_phone_number", "")
            lead["website"] = detail.get("website", "")
            lead["rating"] = str(detail.get("rating", ""))
            lead["reviews"] = str(detail.get("user_ratings_total", ""))
            lead["category"] = ", ".join(detail.get("types", []))
            lead["lead_id"] = generate_lead_id(lead["name"], lead["address"])
            
            if lead["website"]:
                lead["email"] = extract_email_sync(lead["website"])
                
            leads.append(lead)
    except Exception as e:
        logger.error(f"Places API Error: {e}")
        
    return leads

# --- METHOD 2: SERPAPI ---
def search_serpapi(query: str, limit: int = 5) -> List[Dict[str, Any]]:
    """Use SerpAPI to scrape Google Maps via API proxy."""
    logger.info(f"Method 2: SerpAPI | Query: {query}")
    leads = []
    
    try:
        url = "https://serpapi.com/search"
        params = {
            "engine": "google_maps",
            "q": query,
            "api_key": SERPAPI_KEY,
            "num": limit
        }
        resp = requests.get(url, params=params, timeout=15)
        data = resp.json()
        
        for r in data.get("local_results", [])[:limit]:
            lead = get_full_structure()
            lead["name"] = r.get("title", "")
            lead["address"] = r.get("address", "")
            lead["phone"] = r.get("phone", "")
            lead["website"] = r.get("website", "")
            lead["rating"] = str(r.get("rating", ""))
            lead["reviews"] = str(r.get("reviews", ""))
            lead["category"] = r.get("type", "")
            lead["lead_id"] = generate_lead_id(lead["name"], lead["address"])
            
            if lead["website"]:
                lead["email"] = extract_email_sync(lead["website"])
            leads.append(lead)
    except Exception as e:
        logger.error(f"SerpAPI Error: {e}")
        
    return leads

# --- METHOD 3: PURE REQUESTS FALLBACK ---
def search_no_api(query: str, limit: int = 5) -> List[Dict[str, Any]]:
    """Zero-API scraping via requests and BeautifulSoup snippets."""
    logger.info(f"Method 3: Pure Requests Fallback | Query: {query}")
    leads = []
    
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        search_url = f"https://www.google.com/search?q={query.replace(' ', '+')}+phone+email+address"
        resp = requests.get(search_url, headers=headers, timeout=10)
        soup = BeautifulSoup(resp.text, "html.parser")
        
        # Selectors for common business listing blocks
        cards = soup.select("div.VkpGBb, div.rllt__details, div[data-rc]")[:limit]
        for div in cards:
            try:
                lead = get_full_structure()
                name_el = div.select_one("span.OSrXXb, div.dbg0pd, div.OSrXXb")
                lead["name"] = name_el.get_text() if name_el else ""
                
                text_content = div.get_text()
                # Phone extraction from snippet
                phones = re.findall(r'[\+]?[0-9]{1}[\s-][0-9]{4,5}[\s-][0-9]{4,6}', text_content)
                if not phones:
                    phones = re.findall(r'[\+]?[0-9]{10,13}', text_content)
                lead["phone"] = phones[0] if phones else ""
                
                # Email extraction from snippet
                emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text_content)
                lead["email"] = emails[0] if emails else ""
                
                # Try to find website link in the snippet card
                links = div.find_all("a", href=True)
                for a in links:
                    href = a["href"]
                    if "http" in href and "google" not in href:
                        lead["website"] = href
                        break
                
                if lead["name"]:
                    lead["lead_id"] = generate_lead_id(lead["name"], str(random.random()))
                    leads.append(lead)
            except: continue
    except Exception as e:
        logger.error(f"Requests Fallback Error: {e}")
        
    return leads

def main():
    if len(sys.argv) < 2: return
    query = sys.argv[1]
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    
    leads = []
    
    # Priority order
    if GOOGLE_API_KEY:
        leads = search_places_api(query, limit)
    elif SERPAPI_KEY:
        leads = search_serpapi(query, limit)
    else:
        leads = search_no_api(query, limit)
    
    # Final processing and output
    for lead in leads:
        try:
            # Re-validate with the Day 4 logic
            lead = validate_lead(lead)
            print(f"DATA:{json.dumps(lead)}", flush=True)
        except Exception as e:
            logger.error(f"Final lead processing error: {e}")

if __name__ == "__main__":
    main()