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
APIFY_API_TOKEN = os.environ.get("APIFY_API_TOKEN", "")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9"
}

# Sub-regions for major Indian cities
CITY_SUBREGIONS = {
    "hyderabad": ["Banjara Hills", "Jubilee Hills", "Hitech City", "Gachibowli", "Secunderabad", "Kukatpally", "Ameerpet", "Madhapur", "Begumpet", "Kondapur", "Manikonda", "Miyapur", "LB Nagar", "Dilsukhnagar", "Mehdipatnam"],
    "chennai": ["T Nagar", "Anna Nagar", "Adyar", "Velachery", "Nungambakkam", "Mylapore", "Tambaram", "OMR", "Porur", "Chromepet", "Perambur", "Royapettah", "Egmore", "Kodambakkam", "Guindy"],
    "bangalore": ["Koramangala", "Indiranagar", "Whitefield", "Electronic City", "Jayanagar", "HSR Layout", "Marathahalli", "JP Nagar", "Bannerghatta", "BTM Layout", "Rajajinagar", "Malleshwaram", "Hebbal", "Yelahanka", "Sarjapur"],
    "mumbai": ["Andheri", "Bandra", "Powai", "Worli", "Malad", "Goregaon", "Juhu", "Kurla", "Borivali", "Thane", "Dadar", "Chembur", "Vashi", "Kandivali", "Mulund"],
    "delhi": ["Connaught Place", "Lajpat Nagar", "Dwarka", "Rohini", "Karol Bagh", "Saket", "Noida", "Gurgaon", "Janakpuri", "Pitampura", "Vasant Kunj", "Greater Kailash", "Nehru Place", "Preet Vihar", "Faridabad"],
    "vijayawada": ["Benz Circle", "MG Road", "Governorpet", "Labbipet", "Patamata", "Gunadala", "Suryaraopet", "Eluru Road", "Auto Nagar", "Kandrika"],
    "guntur": ["Brodipet", "Arundelpet", "Naaz Centre", "Kothapet", "AT Agraharam", "Old Town", "Amaravathi Road", "Brindavan Gardens", "Vidyanagar", "Nallapadu"],
    "vizag": ["MVP Colony", "Dwaraka Nagar", "Gajuwaka", "Rushikonda", "Seethammadhara", "Maddilapalem", "Akkayyapalem", "Jagadamba", "Siripuram", "NAD Junction"],
    "pune": ["Koregaon Park", "Baner", "Hinjewadi", "Wakad", "Kothrud", "Hadapsar", "Viman Nagar", "Kalyani Nagar", "Aundh", "Magarpatta"],
    "kolkata": ["Park Street", "Salt Lake", "New Town", "Howrah", "Gariahat", "Ballygunge", "Alipore", "Rajarhat", "Dum Dum", "Behala"]
}


def get_subregions(location: str) -> list:
    """Get sub-regions list for a city."""
    loc = location.lower().strip()
    for city, regions in CITY_SUBREGIONS.items():
        if city in loc or loc in city:
            return regions
    return [location]


def search_multi_region(query: str, limit: int = 100) -> list:
    """Search multiple sub-regions to collect 100 unique leads."""
    keyword = query.split(" in ")[0].strip() if " in " in query else query
    location = query.split(" in ")[-1].strip() if " in " in query else "hyderabad"
    subregions = get_subregions(location)

    print(f"LOG:Multi-region mode: {len(subregions)} areas | Target: {limit}", flush=True)

    all_leads = []
    seen_ids = set()
    seen_names = set()

    for region in subregions:
        if len(all_leads) >= limit:
            break

        sub_query = f"{keyword} in {region} {location}"
        print(f"LOG:Searching {region}...", flush=True)

        try:
            resp = requests.post(
                "https://google.serper.dev/maps",
                headers={
                    "X-API-KEY": SERPER_API_KEY,
                    "Content-Type": "application/json"
                },
                json={"q": sub_query, "gl": "in", "hl": "en"},
                timeout=10
            )
            places = resp.json().get("places", [])
            new_count = 0

            for place in places:
                if len(all_leads) >= limit:
                    break
                name = place.get("title", "").strip()
                if not name:
                    continue
                name_lower = name.lower()
                lead_id = hashlib.md5(name_lower.encode()).hexdigest()
                if lead_id in seen_ids or name_lower in seen_names:
                    continue
                seen_ids.add(lead_id)
                seen_names.add(name_lower)

                lead = get_full_structure()
                lead["name"] = name
                lead["address"] = place.get("address", "")
                lead["phone"] = place.get("phoneNumber", "")
                lead["website"] = place.get("website", "")
                lead["rating"] = str(place.get("rating", ""))
                lead["reviews"] = str(place.get("reviews", place.get("reviewsCount", "")))
                lead["category"] = place.get("category", keyword.title())
                lead["google_maps_url"] = place.get("cid", "")
                lead["description"] = place.get("address", "")[:300]
                lead["sub_region"] = region
                lead["lead_id"] = lead_id
                all_leads.append(lead)
                new_count += 1
                print(f"LOG:✅ {name} | ⭐{lead['rating']} | 📞{lead['phone']}", flush=True)

            print(f"LOG:{region} done: {new_count} new | Total: {len(all_leads)}/{limit}", flush=True)

        except Exception as e:
            print(f"LOG:Error in {region}: {e}", flush=True)

        time.sleep(0.5)

    print(f"LOG:Multi-region complete. {len(all_leads)} unique leads found.", flush=True)
    return all_leads[:limit]

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

def search_with_apify(query: str, limit: int = 50):
    """
    Stable Apify Google Maps scraper integration using synchronous execution
    """

    if not APIFY_API_TOKEN:
        print("LOG: No APIFY_API_TOKEN found", flush=True)
        return []

    try:
        print(f"LOG: Starting synchronous Apify search for {query}", flush=True)

        run_response = requests.post(
            f"https://api.apify.com/v2/acts/compass~crawler-google-places/run-sync-get-dataset-items?token={APIFY_API_TOKEN}",
            json={
                "searchStringsArray": [query],
                "maxCrawledPlacesPerSearch": limit,
                "language": "en",
                "countryCode": "IN"
            },
            timeout=120
        )

        if run_response.status_code != 200:
            print(f"LOG: Apify status: {run_response.status_code}", flush=True)
            print(f"LOG: Apify response: {run_response.text[:1000]}", flush=True)
            return []

        items = run_response.json()
        print(f"LOG: Apify returned {len(items)} places", flush=True)

        leads = []
        seen = set()

        for item in items:
            lead = get_full_structure()

            name = item.get("title", "")
            if not name:
                continue

            lead["name"] = name
            lead["phone"] = item.get("phone", "")
            lead["website"] = item.get("website", "")
            lead["address"] = item.get("address", "")
            lead["category"] = item.get("categoryName", "")
            lead["google_maps_url"] = item.get("url", "")
            lead["rating"] = str(item.get("totalScore", ""))
            lead["reviews"] = str(item.get("reviewsCount", ""))

            lead["lead_id"] = hashlib.md5(
                name.lower().encode()
            ).hexdigest()

            if lead["lead_id"] in seen:
                continue

            seen.add(lead["lead_id"])

            # validation
            lead = validate_lead(lead)

            leads.append(lead)
            print(f"LOG: Added lead {name}", flush=True)

            if len(leads) >= limit:
                break

        print(f"LOG: Final leads count = {len(leads)}", flush=True)
        return leads

    except Exception as e:
        print(f"LOG: Apify error: {e}", flush=True)
        return []

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
    # Set limit cap to 100
    limit = min(int(sys.argv[2]) if len(sys.argv) > 2 else 10, 100)
    use_ai = sys.argv[3] == "1" if len(sys.argv) > 3 else False

    print(f"LOG:🚀 LeadPulse Pro Engine | Target: {limit}", flush=True)
    print(f"LOG:Searching: {query}", flush=True)

    # FIRST try Apify
    leads = search_with_apify(query, limit)

    # If no leads, fallback to Serper
    if not leads:
        print(f"LOG:Apify failed or returned 0 leads. Falling back to Serper Maps...", flush=True)
        leads = search_with_serper(query, limit)

    if not leads:
        print("LOG:No results found.", flush=True)
        return

    print(f"LOG:Processing {len(leads)} leads...", flush=True)

    for i, lead in enumerate(leads):
        print(f"LOG:Processing {i+1}/{len(leads)}: {lead.get('name','')[:30]}", flush=True)

        # Enrich email from website if missing
        if lead.get("website") and not lead.get("email"):
            try:
                resp = requests.get(lead["website"], timeout=2, headers=HEADERS)
                soup = BeautifulSoup(resp.text, "html.parser")
                for a in soup.find_all("a", href=re.compile(r"^mailto:")):
                    email = a["href"].replace("mailto:", "").split("?")[0].strip()
                    try:
                        validate_email(email)
                        lead["email"] = email
                        break
                    except: continue
            except: pass

        # AI scoring
        if use_ai:
            try:
                from ai_engine import analyze_single_lead
                lead = analyze_single_lead(lead)
            except: pass
        else:
            try:
                from ai_engine import rule_based_score
                score = rule_based_score(lead)
                lead["ai_analysis"] = json.dumps(score)
                lead["ai_score"] = score.get("score", 0)
            except: pass

        lead = validate_lead(lead)
        print(f"DATA:{json.dumps(lead)}", flush=True)

    print(f"LOG:✅ Complete. Total: {len(leads)}", flush=True)

if __name__ == "__main__":
    main()