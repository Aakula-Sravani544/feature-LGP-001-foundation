import requests
from bs4 import BeautifulSoup
import time
import random
import re
from datetime import datetime
import urllib.parse

def search_fallback(query):
    """
    Ultimate fallback using multiple engines and longer timeouts for Render.
    """
    leads = []
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    }
    
    q = urllib.parse.quote(query)
    
    # Engine 1: Ask.com (Very bot friendly)
    try:
        url = f"https://www.ask.com/web?q={q}"
        resp = requests.get(url, headers=headers, timeout=15)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            for res in soup.select('.PartialSearchResults-item'):
                title = res.select_one('.PartialSearchResults-item-title')
                link = res.select_one('.PartialSearchResults-item-title a')
                if title and link:
                    name = title.get_text().strip()
                    url = link.get('href', "")
                    if name and url.startswith('http'):
                        leads.append(create_lead(name, url, "", "Ask.com"))
    except: pass

    # Engine 2: Mojeek (Privacy engine, rarely blocks)
    if len(leads) < 5:
        try:
            url = f"https://www.mojeek.com/search?q={q}"
            resp = requests.get(url, headers=headers, timeout=15)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "html.parser")
                for res in soup.select('.result'):
                    a = res.select_one('a.t')
                    s = res.select_one('.s')
                    if a:
                        name = a.get_text().strip()
                        url = a.get('href', "")
                        txt = s.get_text().strip() if s else ""
                        leads.append(create_lead(name, url, txt, "Mojeek"))
        except: pass

    # Engine 3: DuckDuckGo Lite (Try with longer timeout)
    if len(leads) < 3:
        try:
            url = f"https://lite.duckduckgo.com/lite/?q={q}"
            resp = requests.get(url, headers=headers, timeout=20)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "html.parser")
                for table in soup.select('table'):
                    links = table.select('a.result-link')
                    for link_el in links:
                        name = link_el.get_text().strip()
                        website = link_el.get('href', "")
                        if name and website.startswith('http') and "duckduckgo.com" not in website:
                            leads.append(create_lead(name, website, "", "DDG Lite"))
        except: pass

    return leads

def create_lead(name, website, snippet, source):
    name = name.encode("utf-8", errors="ignore").decode("utf-8")
    return {
        "name": name,
        "address": f"Located via {source}",
        "phone": "Check Website",
        "email": "Use Website Contact",
        "website": website,
        "rating": "N/A",
        "reviews": "0",
        "category": "Verified Lead",
        "google_maps_url": website,
        "description": f"Source: {source} Engine",
        "hours": "N/A",
        "social_media": "",
        "additional_data": f"Provider: {source}",
        "scraped_date": datetime.now().strftime("%Y-%m-%d"),
        "ai_analysis": "N/A",
        "validation_status": "Candidate",
        "validation_notes": f"Generated via {source} fallback due to Render timeout",
        "sub_region": ""
    }
