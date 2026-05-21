import requests
from bs4 import BeautifulSoup
import time
import random
import re
from datetime import datetime
import urllib.parse

def search_fallback(query):
    """
    Robust fallback to get REAL business data without being blocked.
    Uses Google Lite and DuckDuckGo Lite.
    """
    leads = []
    headers = {
        "User-Agent": "Mozilla/5.0 (Linux; Android 10; SM-G960F) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.6167.164 Mobile Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Referer": "https://www.google.com/"
    }
    
    q = urllib.parse.quote(query)
    
    # Source 1: Google GBV=1
    try:
        url = f"https://www.google.com/search?q={q}&gbv=1&tbs=qdr:y"
        resp = requests.get(url, headers=headers, timeout=12)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            for g in soup.select('div.ZIN69d, div.kCrYT'):
                link = g.find('a')
                title = g.find('h3')
                snippet = g.find('div.BNeawe')
                
                if link and title:
                    name = title.get_text().strip()
                    website = link.get('href', "")
                    if "/url?q=" in website:
                        website = website.split("/url?q=")[1].split("&")[0]
                        website = urllib.parse.unquote(website)
                    
                    if name and website.startswith('http') and "google.com" not in website:
                        leads.append(create_lead(name, website, snippet.get_text() if snippet else "", "Google Global"))
    except Exception as e:
        print(f"DEBUG: Google Global Failed: {e}")

    # Source 2: DuckDuckGo Lite
    if len(leads) < 5:
        try:
            url = f"https://lite.duckduckgo.com/lite/?q={q}"
            resp = requests.get(url, headers=headers, timeout=12)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "html.parser")
                for table in soup.select('table'):
                    links = table.select('a.result-link')
                    snippets = table.select('td.result-snippet')
                    for l_el, s_el in zip(links, snippets):
                        name = l_el.get_text().strip()
                        url = l_el.get('href', "")
                        txt = s_el.get_text().strip() if s_el else ""
                        if name and url.startswith('http') and "duckduckgo.com" not in url:
                            leads.append(create_lead(name, url, txt, "DDG Lite"))
        except: pass

    return leads

def create_lead(name, website, snippet, source):
    # Sanitize
    name = name.encode("utf-8", errors="ignore").decode("utf-8").strip()
    snippet = snippet.encode("utf-8", errors="ignore").decode("utf-8").strip()
    
    # Phone extraction from snippet (Requirement 2)
    phone = ""
    phone_match = re.search(r'(\+?\d{1,4}[\s-]?)?\(?\d{3}\)?[\s-]?\d{3}[\s-]?\d{4}', snippet)
    if phone_match: phone = phone_match.group(0)
    
    address = "Multiple Locations"
    if "," in snippet and any(c.isdigit() for c in snippet):
        parts = snippet.split(",")
        if len(parts) > 1:
            address = f"{parts[-2].strip()}, {parts[-1].strip()}"[:100]

    try:
        from zoneinfo import ZoneInfo
        now_ist = datetime.now(ZoneInfo("Asia/Kolkata"))
    except ImportError:
        from datetime import timedelta
        now_ist = datetime.utcnow() + timedelta(hours=5, minutes=30)

    return {
        "name": name,
        "address": address,
        "phone": phone,
        "email": "", # Will be extracted from website in main scraper
        "website": website,
        "rating": "N/A",
        "reviews": "0",
        "category": "Verified Result",
        "google_maps_url": website,
        "description": snippet[:200],
        "hours": "N/A",
        "social_media": "",
        "additional_data": f"Engine: {source}",
        "scraped_date": now_ist.strftime("%Y-%m-%d %H:%M:%S"),
        "ai_analysis": "N/A",
        "validation_status": "Pending",
        "validation_notes": "",
        "sub_region": ""
    }
