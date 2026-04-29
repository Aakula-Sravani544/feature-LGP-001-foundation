import requests
from bs4 import BeautifulSoup
import time
import random
import re
from datetime import datetime
import urllib.parse

def search_fallback(query):
    """
    Improved fallback with Regex detail extraction.
    """
    leads = []
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    # Sources to check
    engines = [
        f"https://www.google.com/search?q={urllib.parse.quote(query)}",
        f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
    ]
    
    for url in engines:
        try:
            resp = requests.get(url, headers=headers, timeout=10)
            soup = BeautifulSoup(resp.text, "html.parser")
            
            # Select results
            results = soup.select('div.g, .result__body')
            for res in results:
                title_el = res.select_one('h3, .result__title')
                link_el = res.select_one('a')
                snippet_el = res.select_one('.VwiC3b, .result__snippet')
                
                if title_el and link_el:
                    name = title_el.get_text().strip()
                    website = link_el.get('href', "")
                    snippet = snippet_el.get_text().strip() if snippet_el else ""
                    
                    # --- Advanced Detail Extraction ---
                    # 1. Try to find Phone Numbers in snippet
                    phone_match = re.search(r'(\+?\d{1,4}[\s-]?)?\(?\d{3}\)?[\s-]?\d{3}[\s-]?\d{4}', snippet)
                    phone = phone_match.group(0) if phone_match else "Check Website"
                    
                    # 2. Try to find Address-like patterns
                    address = "Multiple Locations"
                    if " in " in query:
                        loc = query.split(" in ")[-1]
                        address = f"{loc} Area"
                    
                    # Clean DuckDuckGo links
                    if "duckduckgo.com/l/?" in website:
                        parsed = urllib.parse.parse_qs(urllib.parse.urlparse(website).query)
                        website = parsed.get('uddg', [website])[0]
                    
                    lead = {
                        "name": name.encode("utf-8", errors="ignore").decode("utf-8"),
                        "address": address,
                        "phone": phone,
                        "email": "Use Website Contact",
                        "website": website,
                        "rating": "N/A",
                        "reviews": "0",
                        "category": "Lead Result",
                        "google_maps_url": website,
                        "description": snippet.encode("utf-8", errors="ignore").decode("utf-8"),
                        "hours": "N/A",
                        "social_media": "",
                        "additional_data": "Generated via Fallback",
                        "scraped_date": datetime.now().strftime("%Y-%m-%d"),
                        "ai_analysis": "N/A",
                        "validation_status": "Candidate",
                        "validation_notes": "Extracted from search snippet",
                        "sub_region": ""
                    }
                    leads.append(lead)
        except: continue
        
    return leads[:20]
