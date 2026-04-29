import requests
from bs4 import BeautifulSoup
import time
import random
from datetime import datetime

def search_fallback(query):
    """
    Enhanced lightweight fallback with robust selectors.
    """
    leads = []
    # Rotate common user agents
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
    ]
    
    headers = {"User-Agent": random.choice(user_agents)}
    url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code != 200:
            # Try DuckDuckGo if Google blocks
            url = f"https://html.duckduckgo.com/html/?q={query.replace(' ', '+')}"
            response = requests.get(url, headers=headers, timeout=10)
            
        soup = BeautifulSoup(response.text, "html.parser")
        
        # Robust selection for multiple search engines
        # Google: div.g, DuckDuckGo: div.result
        results = soup.select('div.g, div.tF2Cxc, div.result, .result__body')
        
        for result in results[:10]:
            try:
                # Try multiple common title/link selectors
                title_el = result.select_one('h3, .result__title, a.result__a')
                link_el = result.select_one('a')
                snippet_el = result.select_one('div.VwiC3b, .result__snippet, .st')
                
                if title_el and link_el:
                    name = title_el.get_text().strip()
                    website = link_el.get('href', "")
                    # Clean DuckDuckGo redirect links if necessary
                    if "duckduckgo.com/l/?" in website:
                        import urllib.parse
                        parsed = urllib.parse.parse_qs(urllib.parse.urlparse(website).query)
                        website = parsed.get('uddg', [""])[0]
                    
                    snippet = snippet_el.get_text().strip() if snippet_el else ""
                    
                    # Senior Dev: Fix encoding and structure
                    name = name.encode("utf-8", errors="ignore").decode("utf-8")
                    website = website.encode("utf-8", errors="ignore").decode("utf-8")
                    
                    lead = {
                        "name": name,
                        "address": snippet[:100],
                        "phone": "",
                        "email": "",
                        "website": website,
                        "rating": "N/A",
                        "reviews": "0",
                        "category": "Organic Search",
                        "google_maps_url": website,
                        "description": snippet,
                        "hours": "",
                        "social_media": "",
                        "additional_data": "Generated via Fallback",
                        "scraped_date": datetime.now().strftime("%Y-%m-%d"),
                        "ai_analysis": "N/A",
                        "validation_status": "Candidate",
                        "validation_notes": "Source: Search Fallback",
                        "sub_region": ""
                    }
                    leads.append(lead)
            except:
                continue
                
    except Exception as e:
        print(f"Fallback Error: {e}")
        
    return leads
