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
    """Visit each website with strict 5 second total timeout per lead."""
    for i, lead in enumerate(leads):
        if not lead.get("website"):
            lead["social_media"] = ""
            lead["additional_data"] = ""
            continue

        print(f"LOG:Enriching {i+1}/{len(leads)}: {lead['name'][:30]}", flush=True)

        try:
            # Single website request — reuse for email, phone, social, tech
            resp = requests.get(
                lead["website"],
                timeout=3,
                headers=HEADERS,
                allow_redirects=True
            )
            html = resp.text
            soup = BeautifulSoup(html, "html.parser")

            # Email
            if not lead.get("email"):
                for a in soup.find_all("a", href=re.compile(r"^mailto:")):
                    email = a["href"].replace("mailto:", "").split("?")[0].strip()
                    try:
                        validate_email(email)
                        lead["email"] = email
                        break
                    except: continue
                if not lead.get("email"):
                    for email in re.findall(
                        r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', html
                    ):
                        try:
                            validate_email(email)
                            if not any(x in email.lower() for x in
                                ['png','jpg','gif','svg','css','js','example']):
                                lead["email"] = email
                                break
                        except: continue

            # Phone
            if not lead.get("phone"):
                for a in soup.find_all("a", href=re.compile(r"^tel:")):
                    lead["phone"] = a["href"].replace("tel:", "").strip()
                    break
                if not lead.get("phone"):
                    phones = re.findall(r'[\+]?[0-9]{10,13}', html)
                    if phones:
                        lead["phone"] = phones[0]

            # Social media
            social = {}
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
            lead["social_media"] = json.dumps(social) if social else ""

            # Tech stack
            tech = []
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
                if any(s in html for s in signals):
                    tech.append(tech_name)
            lead["additional_data"] = json.dumps(tech) if tech else ""

        except Exception as e:
            logger.debug(f"Enrichment failed for {lead.get('name')}: {e}")
            lead["social_media"] = ""
            lead["additional_data"] = ""

        time.sleep(0.1)

    return leads

def main():
    if len(sys.argv) < 2:
        return
    query = sys.argv[1]
    limit = min(int(sys.argv[2]) if len(sys.argv) > 2 else 5, 20)
    use_ai = sys.argv[3] == "1" if len(sys.argv) > 3 else False

    print(f"LOG:🚀 LeadPulse Pro Engine | Target: {limit}", flush=True)
    print(f"LOG:Searching: {query}", flush=True)

    # Step 1: Get leads from Serper immediately
    leads = search_with_serper(query, limit)

    if not leads:
        print("LOG:No results found.", flush=True)
        return

    print(f"LOG:Found {len(leads)} leads. Starting enrichment...", flush=True)

    # Step 2: Enrich and OUTPUT each lead immediately
    # Do NOT wait for all leads — print as soon as each one is ready
    for i, lead in enumerate(leads):
        print(f"LOG:Processing {i+1}/{len(leads)}: {lead.get('name','')[:30]}", flush=True)

        # Enrich this single lead with website data
        if lead.get("website"):
            try:
                resp = requests.get(
                    lead["website"],
                    timeout=2,
                    headers=HEADERS,
                    allow_redirects=True
                )
                html = resp.text
                soup = BeautifulSoup(html, "html.parser")

                # Email
                if not lead.get("email"):
                    for a in soup.find_all("a", href=re.compile(r"^mailto:")):
                        email = a["href"].replace("mailto:", "").split("?")[0].strip()
                        try:
                            validate_email(email)
                            lead["email"] = email
                            break
                        except: continue

                # Phone
                if not lead.get("phone"):
                    phones = re.findall(r'[\+]?[0-9]{10,13}', html)
                    if phones:
                        lead["phone"] = phones[0]

                # Social media
                social = {}
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
                lead["social_media"] = json.dumps(social) if social else ""

                # Tech stack
                tech = []
                tech_signals = {
                    "WordPress": ["wp-content", "wp-includes"],
                    "Shopify": ["shopify.com", "cdn.shopify"],
                    "Google Analytics": ["gtag(", "google-analytics"],
                    "Bootstrap": ["bootstrap.min.css"],
                    "React": ["__NEXT_DATA__", "react.min.js"]
                }
                for tech_name, signals in tech_signals.items():
                    if any(s in html for s in signals):
                        tech.append(tech_name)
                lead["additional_data"] = json.dumps(tech) if tech else ""

            except Exception as e:
                logger.debug(f"Website enrichment skipped for {lead.get('name')}: {e}")
                lead["social_media"] = ""
                lead["additional_data"] = ""
        else:
            lead["social_media"] = ""
            lead["additional_data"] = ""

        # AI scoring and Day 9 Enrichment
        try:
            from ai_engine import analyze_single_lead
            lead = analyze_single_lead(lead, use_ai=use_ai)
        except Exception as e:
            logger.debug(f"Analysis failed: {e}")

        # Validate
        lead = validate_lead(lead)

        # OUTPUT IMMEDIATELY — do not wait for other leads
        print(f"DATA:{json.dumps(lead)}", flush=True)

    print(f"LOG:Complete. Total: {len(leads)}", flush=True)

if __name__ == "__main__":
    main()