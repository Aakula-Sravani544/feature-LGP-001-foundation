import requests
from bs4 import BeautifulSoup
import time
import random
from datetime import datetime

def search_fallback(query):
    """
    Lightweight fallback using requests + BeautifulSoup to guarantee leads.
    """
    leads = []
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
    }
    
    url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code != 200:
            return []
            
        soup = BeautifulSoup(response.text, "html.parser")
        
        # Look for search result blocks
        # Google's HTML structure changes, so we look for common patterns
        search_results = soup.select('div.g')
        
        for result in search_results:
            try:
                name_el = result.select_one('h3')
                link_el = result.select_one('a')
                snippet_el = result.select_one('div.VwiC3b')
                
                if name_el and link_el:
                    name = name_el.get_text()
                    website = link_el['href']
                    snippet = snippet_el.get_text() if snippet_el else ""
                    
                    # Clean and encode
                    name = name.encode("utf-8", errors="ignore").decode("utf-8")
                    website = website.encode("utf-8", errors="ignore").decode("utf-8")
                    snippet = snippet.encode("utf-8", errors="ignore").decode("utf-8")
                    
                    lead = {
                        "name": name,
                        "address": snippet[:100] if snippet else "",
                        "phone": "",
                        "email": "",
                        "website": website,
                        "rating": "N/A",
                        "reviews": "0",
                        "category": "Search Result",
                        "google_maps_url": website,
                        "description": snippet,
                        "hours": "",
                        "social_media": "",
                        "additional_data": "Generated via Fallback",
                        "scraped_date": datetime.now().strftime("%Y-%m-%d"),
                        "ai_analysis": "N/A",
                        "validation_status": "Candidate",
                        "validation_notes": "Source: Google Search Fallback",
                        "sub_region": ""
                    }
                    leads.append(lead)
            except:
                continue
                
    except Exception as e:
        print(f"Fallback error: {e}")
        
    return leads
