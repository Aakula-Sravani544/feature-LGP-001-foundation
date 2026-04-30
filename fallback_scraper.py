import requests
from bs4 import BeautifulSoup
import time
import random
import re
from datetime import datetime
import urllib.parse

def search_fallback(query):
    """
    Highly resilient fallback using DuckDuckGo Lite and Bing.
    These are less likely to block Render IPs than Google.
    """
    leads = []
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1"
    }
    
    q = urllib.parse.quote(query)
    
    # Source 1: DuckDuckGo Lite (Extremely bot-friendly, no JS)
    try:
        url = f"https://lite.duckduckgo.com/lite/?q={q}"
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            # DDG Lite uses a table structure
            for table in soup.select('table'):
                links = table.select('a.result-link')
                snippets = table.select('td.result-snippet')
                
                for link_el, snippet_el in zip(links, snippets):
                    name = link_el.get_text().strip()
                    website = link_el.get('href', "")
                    snippet = snippet_el.get_text().strip()
                    
                    if name and website.startswith('http') and "duckduckgo.com" not in website:
                        leads.append(create_lead(name, website, snippet, "DuckDuckGo Lite"))
    except Exception as e:
        print(f"DEBUG: DDG Lite Failed: {e}")

    # Source 2: Bing (Standard)
    if len(leads) < 5:
        try:
            url = f"https://www.bing.com/search?q={q}"
            resp = requests.get(url, headers=headers, timeout=10)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "html.parser")
                for li in soup.select('li.b_algo'):
                    a = li.find('a')
                    snippet = li.find('p')
                    if a:
                        name = a.get_text().strip()
                        url = a.get('href', "")
                        txt = snippet.get_text().strip() if snippet else ""
                        if name and url.startswith('http'):
                            leads.append(create_lead(name, url, txt, "Bing"))
        except: pass

    # Source 3: Google (Last resort, often blocks)
    if len(leads) < 3:
        try:
            url = f"https://www.google.com/search?q={q}"
            resp = requests.get(url, headers=headers, timeout=10)
            soup = BeautifulSoup(resp.text, "html.parser")
            for g in soup.select('div.g, div.tF2Cxc'):
                a = g.find('a')
                h3 = g.find('h3')
                if a and h3:
                    name = h3.get_text().strip()
                    url = a.get('href', "")
                    if name and url.startswith('http'):
                        leads.append(create_lead(name, url, "", "Google"))
        except: pass

    return leads

def create_lead(name, website, snippet, source):
    # Senior Dev: Fix encoding and structure
    name = name.encode("utf-8", errors="ignore").decode("utf-8")
    snippet = snippet.encode("utf-8", errors="ignore").decode("utf-8")
    
    # Try to find phone in snippet
    phone = "Check Website"
    phone_match = re.search(r'(\+?\d{1,4}[\s-]?)?\(?\d{3}\)?[\s-]?\d{3}[\s-]?\d{4}', snippet)
    if phone_match: phone = phone_match.group(0)

    return {
        "name": name,
        "address": "Multiple Locations" if len(snippet) < 5 else snippet[:100],
        "phone": phone,
        "email": "Contact via Website",
        "website": website,
        "rating": "N/A",
        "reviews": "0",
        "category": "Lead Result",
        "google_maps_url": website,
        "description": snippet[:200],
        "hours": "N/A",
        "social_media": "",
        "additional_data": f"Source: {source}",
        "scraped_date": datetime.now().strftime("%Y-%m-%d"),
        "ai_analysis": "N/A",
        "validation_status": "Candidate",
        "validation_notes": f"Generated via {source} fallback",
        "sub_region": ""
    }
