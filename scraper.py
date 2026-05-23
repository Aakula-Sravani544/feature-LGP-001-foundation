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
try:
    from ai_engine import enrich_leads_with_ai
except Exception as e:
    logger = logging.getLogger(__name__)
    logger.error(f"Failed to import ai_engine: {e}")
    # Dummy fallback
    def enrich_leads_with_ai(leads): return leads

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
    try:
        from zoneinfo import ZoneInfo
        now_ist = datetime.now(ZoneInfo("Asia/Kolkata"))
    except ImportError:
        from datetime import timedelta
        now_ist = datetime.utcnow() + timedelta(hours=5, minutes=30)
        
    return {
        "lead_id": "", "name": "", "address": "", "phone": "",
        "email": "", "website": "", "rating": "", "reviews": "",
        "category": "", "google_maps_url": "", "description": "",
        "hours": "", "social_media": "", "additional_data": "",
        "scraped_date": now_ist.strftime("%Y-%m-%d %H:%M:%S"),
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

def search_with_serper(query: str, limit: int = 10) -> list:
    """Search using exact query — sub-region already included."""
    if not SERPER_API_KEY:
        print("LOG:No SERPER_API_KEY found!", flush=True)
        return []

    print(f"LOG:Serper Maps search: {query}", flush=True)
    leads = []
    seen_names = set()

    try:
        resp = requests.post(
            "https://google.serper.dev/maps",
            headers={
                "X-API-KEY": SERPER_API_KEY,
                "Content-Type": "application/json"
            },
            json={"q": query, "gl": "in", "hl": "en"},
            timeout=10
        )
        data = resp.json()
        places = data.get("places", [])
        print(f"LOG:Serper returned {len(places)} places for: {query}", flush=True)

        for place in places:
            # 1. NAME
            name = place.get("title") or place.get("name") or ""
            name = name.strip()
            if not name or name.lower() in seen_names:
                continue
            seen_names.add(name.lower())

            lead = get_full_structure()
            lead["name"] = name
            
            # 2. ADDRESS
            lead["address"] = place.get("address") or place.get("fullAddress") or ""
            
            # 3. PHONE
            lead["phone"] = place.get("phoneNumber") or place.get("phone") or ""
            
            # 4. WEBSITE
            lead["website"] = place.get("website") or place.get("site") or place.get("link") or ""
            
            # 5. RATING
            lead["rating"] = str(place.get("rating", ""))
            
            # 6. REVIEWS
            reviews = (
                place.get("reviews")
                or place.get("reviewsCount")
                or place.get("review_count")
                or place.get("userRatingCount")
                or 0
            )
            lead["reviews"] = str(reviews)
            
            # 7. CATEGORY
            lead["category"] = place.get("category") or place.get("type") or place.get("businessType") or query.split()[0].title()
            
            # 8. GOOGLE MAPS
            lead["google_maps_url"] = place.get("google_maps_url") or place.get("cid") or place.get("maps_link") or ""
            
            # 9. DESCRIPTION
            desc = place.get("description") or place.get("snippet") or lead["address"]
            lead["description"] = desc[:300] if desc else ""
            
            # 10. HOURS
            lead["hours"] = str(place.get("hours") or place.get("openingHours") or "")
            
            lead["sub_region"] = query
            lead["lead_id"] = hashlib.md5(name.lower().encode()).hexdigest()
            leads.append(lead)
            print(f"LOG:✅ {name} | ⭐{lead['rating']} | 📞{lead['phone']}", flush=True)

            if len(leads) >= limit:
                break

    except Exception as e:
        print(f"LOG:Serper error: {e}", flush=True)

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

def enrich_single_fast(lead: dict) -> dict:
    """Safe, fast website enrichment with strict limits."""
    for k in ["email", "social_media", "additional_data", "hours"]:
        if not lead.get(k):
            lead[k] = ""
            
    if not lead.get("website") or not str(lead["website"]).startswith("http"):
        return lead
        
    needs_enrich = not lead["email"] or not lead["social_media"] or not lead["additional_data"]
    if not needs_enrich:
        return lead
        
    try:
        resp = requests.get(
            lead["website"],
            timeout=1,
            headers=HEADERS,
            stream=True,
            allow_redirects=False
        )
        
        html = ""
        for chunk in resp.iter_content(chunk_size=2048):
            html += chunk.decode('utf-8', errors='ignore')
            if len(html) > 15360:  # 15KB limit
                break
        resp.close()
        
        if html:
            # 1. Email Extraction
            if not lead["email"]:
                mailto_match = re.search(r'href=[\'"]mailto:([^\'"?]+)', html, re.IGNORECASE)
                if mailto_match:
                    try:
                        email = mailto_match.group(1).strip()
                        validate_email(email)
                        lead["email"] = email
                    except: pass
                    
                if not lead["email"]:
                    emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', html)
                    for e in emails:
                        e_lower = e.lower()
                        if not any(x in e_lower for x in ['png', 'jpg', 'jpeg', 'css', 'js', 'example', 'noreply', 'no-reply']):
                            try:
                                validate_email(e)
                                lead["email"] = e
                                break
                            except: pass
                            
            # 2. Social Media Extraction
            if not lead["social_media"]:
                social = {}
                patterns = {
                    "facebook": r'facebook\.com/[^\s\'"<>\)]{3,50}',
                    "instagram": r'instagram\.com/[^\s\'"<>\)]{3,50}',
                    "linkedin": r'linkedin\.com/(?:company|in)/[^\s\'"<>\)]{3,50}',
                    "twitter": r'(?:twitter|x)\.com/[^\s\'"<>\)]{3,50}',
                    "youtube": r'youtube\.com/[^\s\'"<>\)]{3,50}'
                }
                for platform, pattern in patterns.items():
                    matches = re.findall(pattern, html, re.IGNORECASE)
                    if matches:
                        clean = matches[0].rstrip('/"\'').strip()
                        if len(clean) > 10:
                            social[platform] = "https://" + clean
                if social:
                    lead["social_media"] = json.dumps(social)
                    
            # 3. Additional Data Extraction
            if not lead["additional_data"]:
                add_data = {}
                tech = []
                html_lower = html.lower()
                if "wp-content" in html_lower or "wp-includes" in html_lower: tech.append("WordPress")
                if "shopify" in html_lower: tech.append("Shopify")
                if "wix.com" in html_lower: tech.append("Wix")
                if "gtag" in html_lower or "google-analytics" in html_lower: tech.append("Google Analytics")
                if tech: add_data["tech_stack"] = tech
                    
                title_match = re.search(r'<title[^>]*>([^<]+)</title>', html, re.IGNORECASE)
                if title_match: add_data["page_title"] = title_match.group(1).strip()
                    
                meta_match = re.search(r'<meta[^>]*name=[\'"]description[\'"][^>]*content=[\'"]([^\'"]+)[\'"]', html, re.IGNORECASE)
                if not meta_match:
                    meta_match = re.search(r'<meta[^>]*content=[\'"]([^\'"]+)[\'"][^>]*name=[\'"]description[\'"]', html, re.IGNORECASE)
                if meta_match: add_data["meta_description"] = meta_match.group(1).strip()
                    
                if add_data:
                    data_str = json.dumps(add_data)
                    if len(data_str) > 500: data_str = data_str[:497] + "..."
                    lead["additional_data"] = data_str
                    
        del html
    except Exception:
        pass
        
    return lead

def process_single_lead(lead, use_ai=False, deep_enrich=False):
    """Lightweight Fast Mode lead enrichment with Optional Deep Enrichment."""
    
    # Missing data safety default to empty string
    if not lead.get("email"):
        lead["email"] = ""
    if not lead.get("website"):
        lead["website"] = ""
    if not lead.get("social_media"):
        lead["social_media"] = ""
    if not lead.get("additional_data"):
        lead["additional_data"] = ""
    if not lead.get("hours"):
        lead["hours"] = ""
        
    # Optional Deep Enrichment Mode
    if deep_enrich and lead["website"] and str(lead["website"]).startswith("http"):
        needs_enrich = not lead["email"] or not lead["social_media"] or not lead["hours"] or not lead["additional_data"]
        if needs_enrich:
            print(f"LOG:[SYS] Deep Enrichment enabled for missing fields", flush=True)
            try:
                # 2 seconds timeout, only read 20KB HTML, requests only
                resp = requests.get(lead["website"], timeout=2, headers=HEADERS, stream=True)
                html = ""
                for chunk in resp.iter_content(chunk_size=2048):
                    html += chunk.decode('utf-8', errors='ignore')
                    if len(html) > 20480:  # Stop at 20KB
                        break
                resp.close()
                
                if html:
                    # Email Extraction
                    if not lead["email"]:
                        mailto_match = re.search(r'href=[\'"]mailto:([^\'"?]+)', html, re.IGNORECASE)
                        if mailto_match:
                            try:
                                validate_email(mailto_match.group(1))
                                lead["email"] = mailto_match.group(1).strip()
                                print("LOG:[SYS] Email found from website", flush=True)
                            except: pass
                            
                        if not lead["email"]:
                            emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', html)
                            for e in emails:
                                if not any(x in e.lower() for x in ['png','jpg','gif','svg','css','js','example']):
                                    try:
                                        validate_email(e)
                                        lead["email"] = e
                                        print("LOG:[SYS] Email found from website", flush=True)
                                        break
                                    except: pass
                                    
                    # Social Media Extraction
                    if not lead["social_media"]:
                        social = {}
                        patterns = {
                            "facebook": r'facebook\.com/[^\s\'"<>\)]{3,50}',
                            "instagram": r'instagram\.com/[^\s\'"<>\)]{3,50}',
                            "linkedin": r'linkedin\.com/(?:company|in)/[^\s\'"<>\)]{3,50}',
                            "twitter": r'(?:twitter|x)\.com/[^\s\'"<>\)]{3,50}',
                            "youtube": r'youtube\.com/[^\s\'"<>\)]{3,50}'
                        }
                        for platform, pattern in patterns.items():
                            matches = re.findall(pattern, html, re.IGNORECASE)
                            if matches:
                                clean = matches[0].rstrip('/"\'').strip()
                                if len(clean) > 10:
                                    social[platform] = "https://" + clean
                        if social:
                            lead["social_media"] = json.dumps(social)
                            
                    # Additional Data (Tech Stack / description)
                    if not lead["additional_data"]:
                        tech = []
                        if any(s in html for s in ["wp-content", "wp-includes"]): tech.append("WordPress")
                        if any(s in html for s in ["shopify.com", "cdn.shopify"]): tech.append("Shopify")
                        if any(s in html for s in ["gtag(", "google-analytics"]): tech.append("Google Analytics")
                        if tech:
                            lead["additional_data"] = json.dumps(tech)
                            
                # Release memory
                del html
            except Exception as e:
                print("LOG:[SYS] Website unavailable, continuing", flush=True)
    else:
        print("LOG:[SYS] Fast Mode: using Serper data", flush=True)

    # ONLY rule-based AI scoring to avoid Gemini memory spikes
    try:
        from ai_engine import rule_based_score
        score = rule_based_score(lead)
        lead["ai_analysis"] = json.dumps(score)
        lead["ai_score"] = score.get("score", 0)
    except Exception:
        pass

    try:
        lead = validate_lead(lead)
    except Exception:
        lead["validation_status"] = "Pending"

    return lead


def normalize_str(val):
    if not val:
        return ""
    return "".join(c for c in str(val).lower() if c.isalnum())

def get_lead_keys(lead):
    name = lead.get("name") or lead.get("business_name")
    name_norm = normalize_str(name)
    if not name_norm:
        return []
    keys = []
    phone = lead.get("phone")
    phone_norm = normalize_str(phone)
    if phone_norm:
        keys.append(f"np_{name_norm}_{phone_norm}")
    maps_url = lead.get("google_maps_url") or lead.get("maps_url")
    maps_url_norm = normalize_str(maps_url)
    if maps_url_norm:
        keys.append(f"nm_{name_norm}_{maps_url_norm}")
    address = lead.get("address")
    address_norm = normalize_str(address)
    if address_norm:
        keys.append(f"na_{name_norm}_{address_norm}")
    return keys

def is_db_duplicate_lead(lead1, lead2):
    name1 = normalize_str(lead1.get("name") or lead1.get("business_name"))
    name2 = normalize_str(lead2.get("name") or lead2.get("business_name"))
    if not name1 or name1 != name2:
        return False
    phone1 = normalize_str(lead1.get("phone"))
    phone2 = normalize_str(lead2.get("phone"))
    if phone1 and phone2 and phone1 == phone2:
        return True
    url1 = normalize_str(lead1.get("google_maps_url") or lead1.get("maps_url"))
    url2 = normalize_str(lead2.get("google_maps_url") or lead2.get("maps_url"))
    if url1 and url2 and url1 == url2:
        return True
    return False


def main():
    if len(sys.argv) < 2:
        return
    query = sys.argv[1]
    limit = min(int(sys.argv[2]) if len(sys.argv) > 2 else 10, 100)
    use_ai = sys.argv[3] == "1" if len(sys.argv) > 3 else False
    deep_enrich = sys.argv[4] == "1" if len(sys.argv) > 4 else False

    print(f"LOG:🚀 LeadPulse Fast Mode | Target: {limit}", flush=True)
    print(f"LOG:Query: {query}", flush=True)

    # Search
    leads = search_with_serper(query, limit)

    if not leads:
        print(f"LOG:No results for: {query}", flush=True)
        return

    print(f"LOG:Found {len(leads)} leads. Processing...", flush=True)

    for i, lead in enumerate(leads):
        print(f"LOG:Processing {i+1}/{len(leads)}: {lead.get('name','')[:30]}", flush=True)
        try:
            # 1. Fast Enrichment
            lead = enrich_single_fast(lead)
            
            # 2. Rule-based score
            try:
                from ai_engine import rule_based_score
                score = rule_based_score(lead)
                lead["ai_analysis"] = json.dumps(score)
                lead["ai_score"] = score.get("score", 0)
            except Exception:
                pass
                
            # 3. Validate
            try:
                lead = validate_lead(lead)
            except Exception:
                lead["validation_status"] = "Pending"
                
            print(f"DATA:{json.dumps(lead)}", flush=True)
        except Exception as e:
            logger.debug(f"Lead failed: {e}")
            lead["validation_status"] = "Pending"
            print(f"DATA:{json.dumps(lead)}", flush=True)
        finally:
            del lead

    print(f"LOG:✅ Done: {len(leads)} leads from {query}", flush=True)


if __name__ == "__main__":
    main()