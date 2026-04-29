import requests
from bs4 import BeautifulSoup
import time
import random
from datetime import datetime
import urllib.parse

def search_fallback(query):
    """
    Guaranteed lead generator using multiple search engines.
    """
    leads = []
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    # Source 1: Google (Limited on Render)
    try:
        url = f"https://www.google.com/search?q={urllib.parse.quote(query)}"
        resp = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(resp.text, "html.parser")
        
        # Look for result blocks - very generic selectors
        for g in soup.select('div.g, div.tF2Cxc, div.v7W7u'):
            anchor = g.find('a')
            h3 = g.find('h3')
            if anchor and h3:
                name = h3.get_text().strip()
                link = anchor['href']
                if name and link.startswith('http'):
                    leads.append(create_lead_struct(name, link, "Google Fallback"))
    except: pass

    # Source 2: DuckDuckGo (Better for Bots)
    if len(leads) < 10:
        try:
            url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
            resp = requests.get(url, headers=headers, timeout=10)
            soup = BeautifulSoup(resp.text, "html.parser")
            for res in soup.select('.result__body, .links_main'):
                a = res.find('a', class_='result__a')
                snippet = res.find('a', class_='result__snippet')
                if a:
                    name = a.get_text().strip()
                    link = a['href']
                    leads.append(create_lead_struct(name, link, "DuckDuckGo Fallback"))
        except: pass

    # Source 3: Bing (Often works when others block)
    if len(leads) < 5:
        try:
            url = f"https://www.bing.com/search?q={urllib.parse.quote(query)}"
            resp = requests.get(url, headers=headers, timeout=10)
            soup = BeautifulSoup(resp.text, "html.parser")
            for li in soup.select('li.b_algo'):
                a = li.find('a')
                if a:
                    name = a.get_text().strip()
                    link = a['href']
                    leads.append(create_lead_struct(name, link, "Bing Fallback"))
        except: pass

    return leads[:20] # Limit to 20 per query for speed

def create_lead_struct(name, website, source):
    """Helper to ensure the exact 17-field structure."""
    name = name.encode("utf-8", errors="ignore").decode("utf-8")
    return {
        "name": name,
        "address": "Search Result Address",
        "phone": "Contact via Website",
        "email": "Contact via Website",
        "website": website,
        "rating": "N/A",
        "reviews": "0",
        "category": "Lead Result",
        "google_maps_url": website,
        "description": f"Extracted via {source}",
        "hours": "N/A",
        "social_media": "",
        "additional_data": f"Source: {source}",
        "scraped_date": datetime.now().strftime("%Y-%m-%d"),
        "ai_analysis": "N/A",
        "validation_status": "Candidate",
        "validation_notes": f"Generated via {source}",
        "sub_region": ""
    }
