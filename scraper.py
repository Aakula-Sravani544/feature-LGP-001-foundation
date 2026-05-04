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
from ai_engine import enrich_leads_with_ai

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

def extract_social_media(url: str) -> dict:
    """Lightweight social media extractor — no aiohttp, no concurrent connections."""
    social = {}
    if not url or not url.startswith("http"):
        return social
    try:
        resp = requests.get(url, timeout=5, headers=HEADERS)
        html = resp.text
        patterns = {
            "facebook": r'facebook\.com/[^\s\'"<>\)]{3,50}',
            "instagram": r'instagram\.com/[^\s\'"<>\)]{3,50}',
            "linkedin": r'linkedin\.com/(?:company|in)/[^\s\'"<>\)]{3,50}',
            "twitter": r'(?:twitter|x)\.com/[^\s\'"<>\)]{3,50}',
            "youtube": r'youtube\.com/[^\s\'"<>\)]{3,50}'
        }
        for platform, pattern in patterns.items():
            matches = re.findall(pattern, html)
            for match in matches:
                clean = match.rstrip('/"\'').strip()
                if len(clean) > 10:
                    social[platform] = "https://" + clean
                    break
    except Exception as e:
        logger.debug(f"Social extraction failed for {url}: {e}")
    return social

def search_with_serper(query: str, limit: int = 5) -> list:
    """Search using Serper Maps API — returns rating, reviews, phone directly from Google Maps."""
    if not SERPER_API_KEY:
        print("LOG:ERROR - SERPER_API_KEY not found!", flush=True)
        return []

    print(f"LOG:Using Serper Maps API...", flush=True)
    leads = []
    seen_names = set()

    try:
        resp = requests.post(
            "https://google.serper.dev/maps",
            headers={
                "X-API-KEY": SERPER_API_KEY,
                "Content-Type": "application/json"
            },
            json={
                "q": query,
                "gl": "in",
                "hl": "en"
            },
            timeout=10
        )
        data = resp.json()
        places = data.get("places", [])
        print(f"LOG:Serper Maps returned {len(places)} places", flush=True)

        for place in places[:limit*2]:
            name = place.get("title", "").strip()
            if not name or name in seen_names:
                continue
            seen_names.add(name)

            lead = get_full_structure()
            lead["name"] = name
            lead["address"] = place.get("address", "")
            lead["phone"] = place.get("phoneNumber", "")
            lead["website"] = place.get("website", "")
            lead["rating"] = str(place.get("rating", ""))
            lead["reviews"] = str(place.get("reviews", place.get("reviewsCount", place.get("ratingCount", ""))))
            lead["category"] = place.get("category", query.split()[0].title())
            lead["google_maps_url"] = place.get("cid", "")
            lead["description"] = place.get("address", "")[:300]
            lead["lead_id"] = hashlib.md5(
                name.lower().encode()
            ).hexdigest()

            if name and len(name) > 3:
                leads.append(lead)
                print(f"LOG:Found: {name} | Rating:{lead['rating']} | Phone:{lead['phone']}", flush=True)

            if len(leads) >= limit:
                break

    except Exception as e:
        print(f"LOG:Serper Maps error: {e}", flush=True)
        logger.error(f"Serper Maps failed: {e}")

    # If maps returns 0, fallback to web search
    if not leads:
        print(f"LOG:Maps returned 0. Trying web search fallback...", flush=True)
        try:
            resp = requests.post(
                "https://google.serper.dev/search",
                headers={
                    "X-API-KEY": SERPER_API_KEY,
                    "Content-Type": "application/json"
                },
                json={
                    "q": f"{query} contact phone email",
                    "num": 10,
                    "gl": "in"
                },
                timeout=10
            )
            data = resp.json()
            for r in data.get("organic", [])[:limit]:
                name = r.get("title", "").strip()
                if not name or name in seen_names:
                    continue
                seen_names.add(name)
                lead = get_full_structure()
                lead["name"] = name
                lead["website"] = r.get("link", "")
                lead["description"] = r.get("snippet", "")[:300]
                lead["category"] = query.split()[0].title()
                lead["lead_id"] = hashlib.md5(name.lower().encode()).hexdigest()
                leads.append(lead)
                print(f"LOG:Fallback found: {name}", flush=True)
        except Exception as e:
            print(f"LOG:Web fallback error: {e}", flush=True)

    return leads

def enrich_leads(leads: list) -> list:
    """Visit each website to extract email, phone, social media and tech stack."""
    for i, lead in enumerate(leads):
        if lead.get("website"):
            print(f"LOG:Enriching {i+1}/{len(leads)}: {lead['name'][:30]}", flush=True)
            # Email
            if not lead.get("email"):
                lead["email"] = extract_email_from_website(lead["website"])
            # Phone
            if not lead.get("phone"):
                lead["phone"] = extract_phone_from_website(lead["website"])
            # Social media — lightweight, no aiohttp
            social = extract_social_media(lead["website"])
            if social:
                lead["social_media"] = json.dumps(social)
            else:
                lead["social_media"] = ""
            
            # Tech stack detection (CHANGE 2)
            try:
                tech = []
                resp_text = requests.get(
                    lead["website"], timeout=5, headers=HEADERS
                ).text
                tech_signals = {
                    "WordPress": ["wp-content", "wp-includes"],
                    "Shopify": ["shopify.com", "cdn.shopify"],
                    "Google Analytics": ["gtag(", "google-analytics"],
                    "Bootstrap": ["bootstrap.min.css"],
                    "React": ["__NEXT_DATA__", "react.min.js"],
                    "Wix": ["wix.com", "wixstatic"],
                    "HubSpot": ["hubspot.com", "hs-scripts"]
                }
                for tech_name, signals in tech_signals.items():
                    if any(s in resp_text for s in signals):
                        tech.append(tech_name)
                if tech:
                    lead["additional_data"] = json.dumps(tech)
                else:
                    lead["additional_data"] = ""
            except Exception:
                lead["additional_data"] = ""
                
            time.sleep(0.3)
        else:
            lead["social_media"] = ""
            lead["additional_data"] = ""
    return leads

def main():
    if len(sys.argv) < 2:
        return
    query = sys.argv[1]
    limit = min(int(sys.argv[2]) if len(sys.argv) > 2 else 5, 10)
    use_ai = sys.argv[3] == "1" if len(sys.argv) > 3 else False

    print(f"LOG:🚀 LeadPulse Pro Engine | Target: {limit}", flush=True)
    print(f"LOG:AI Scoring: {'ON' if use_ai else 'OFF'}", flush=True)

    # Search
    leads = search_with_serper(query, limit)

    if not leads:
        print("LOG:No results found.", flush=True)
        return

    # Enrich
    print(f"LOG:Enriching {len(leads)} leads...", flush=True)
    leads = enrich_leads(leads)

    # AI Analysis
    if use_ai:
        print(f"LOG:Running AI analysis...", flush=True)
        try:
            from ai_engine import enrich_leads_with_ai
            leads = enrich_leads_with_ai(leads)
            print(f"LOG:AI analysis complete", flush=True)
        except Exception as e:
            print(f"LOG:AI failed: {e} — using rule-based", flush=True)
            from ai_engine import enrich_leads_with_ai
            leads = enrich_leads_with_ai(leads)
    else:
        print(f"LOG:Using rule-based scoring", flush=True)
        try:
            from ai_engine import enrich_leads_with_ai
            leads = enrich_leads_with_ai(leads)
        except Exception as e:
            print(f"LOG:Rule-based scoring failed: {e}", flush=True)

    # Validate and output
    for lead in leads:
        try:
            lead = validate_lead(lead)
            print(f"DATA:{json.dumps(lead)}", flush=True)
        except Exception as e:
            logger.error(f"Validation failed for lead: {e}")

    print(f"LOG:Complete. Total: {len(leads)}", flush=True)

if __name__ == "__main__":
    main()