import requests
from bs4 import BeautifulSoup
import time
import random
import re
from datetime import datetime
import urllib.parse

def search_fallback(query):
    """
    Highly resilient fallback using Google, DuckDuckGo and Bing.
    """
    leads = []
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
    }
    
    # Encode query
    q = urllib.parse.quote(query)
    
    # 1. Google (Try first, but usually blocked on Render)
    try:
        resp = requests.get(f"https://www.google.com/search?q={q}", headers=headers, timeout=8)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            # Multiple possible result selectors
            for g in soup.select('div.g, div.tF2Cxc, div.v7W7u, div.jS778'):
                link_el = g.find('a')
                title_el = g.find('h3')
                if link_el and title_el:
                    name = title_el.get_text().strip()
                    website = link_el.get('href', "")
                    if name and website.startswith('http') and "google.com" not in website:
                        leads.append(create_lead(name, website, "Google Search"))
    except: pass

    # 2. DuckDuckGo (Much more bot-friendly)
    if len(leads) < 5:
        try:
            resp = requests.get(f"https://html.duckduckgo.com/html/?q={q}", headers=headers, timeout=8)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "html.parser")
                for res in soup.select('.result__body'):
                    a = res.find('a', class_='result__a')
                    if a:
                        name = a.get_text().strip()
                        url = a.get('href', "")
                        # Handle DDG redirect
                        if "duckduckgo.com/l/?" in url:
                            parsed = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
                            url = parsed.get('uddg', [url])[0]
                        leads.append(create_lead(name, url, "DuckDuckGo"))
        except: pass

    # 3. Bing
    if len(leads) < 5:
        try:
            resp = requests.get(f"https://www.bing.com/search?q={q}", headers=headers, timeout=8)
            soup = BeautifulSoup(resp.text, "html.parser")
            for li in soup.select('li.b_algo'):
                h2 = li.find('h2')
                a = h2.find('a') if h2 else li.find('a')
                if a:
                    name = a.get_text().strip()
                    url = a.get('href', "")
                    leads.append(create_lead(name, url, "Bing Search"))
        except: pass

    return leads

def create_lead(name, website, source):
    name = name.encode("utf-8", errors="ignore").decode("utf-8")
    return {
        "name": name,
        "address": f"Identified via {source}",
        "phone": "Visit Website",
        "email": "Visit Website",
        "website": website,
        "rating": "N/A",
        "reviews": "0",
        "category": "Web Search Result",
        "google_maps_url": website,
        "description": f"Source: {source} Fallback",
        "hours": "N/A",
        "social_media": "",
        "additional_data": f"Engine: {source}",
        "scraped_date": datetime.now().strftime("%Y-%m-%d"),
        "ai_analysis": "N/A",
        "validation_status": "Candidate",
        "validation_notes": f"Scraped via {source} fallback due to Chrome OOM",
        "sub_region": ""
    }
