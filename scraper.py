import sys
import json
import time
import random
import re
from datetime import datetime
from driver_setup import get_driver, safe_get
from fallback_scraper import search_fallback
from validation import validate_lead

def log(msg):
    print(f"LOG: {msg}", flush=True)

def get_full_structure():
    return {
        "lead_id": f"lp-{random.randint(100000, 999999)}",
        "name": "", "address": "", "phone": "", "email": "", "website": "",
        "rating": "", "reviews": "", "category": "", "google_maps_url": "",
        "description": "", "hours": "", "social_media": "", "additional_data": "",
        "scraped_date": datetime.now().strftime("%Y-%m-%d"),
        "ai_analysis": "N/A", "validation_status": "Pending",
        "validation_notes": "", "sub_region": ""
    }

def main():
    if len(sys.argv) < 2: return
    query = sys.argv[1]
    
    # Requirement 1: Limit to 5 leads
    target_leads = 5
    
    log(f"🚀 LeadPulse Fast Scraper | Query: {query}")
    
    unique_leads = []
    seen_names = set()
    
    driver = get_driver()
    
    # 1. Scraping Phase
    try:
        encoded = query.replace(" ", "+")
        url = f"https://www.google.com/maps/search/{encoded}"
        
        if driver and safe_get(driver, url):
            time.sleep(5)
            from selenium.webdriver.common.by import By
            containers = driver.find_elements(By.CSS_SELECTOR, "a.hfpxzc, div.qBF1Pd")
            
            for container in containers:
                try:
                    lead = get_full_structure()
                    name = container.get_attribute("aria-label") or container.text.split('\n')[0]
                    if not name or name in seen_names: continue
                    
                    lead["name"] = name.strip()
                    
                    # Extract phone from text (Requirement 6 fallback)
                    full_text = container.text
                    match = re.search(r'(\+?\d{1,4}[\s-]?)?\(?\d{3}\)?[\s-]?\d{3}[\s-]?\d{4}', full_text)
                    if match: lead["phone"] = match.group(0)
                    
                    lead["google_maps_url"] = container.get_attribute("href") or driver.current_url
                    
                    # Requirement 3: Explicitly apply validation
                    lead = validate_lead(lead)
                    
                    # Requirement 7: Debug Print
                    print(f"Lead: {lead.get('name')} | Phone: {lead.get('phone')} | Status: {lead.get('validation_status')}")
                    
                    unique_leads.append(lead)
                    seen_names.add(name)
                    print(f"DATA:{json.dumps(lead)}", flush=True)
                    
                    if len(unique_leads) >= target_leads: break
                except: continue
                
    except Exception as e:
        log(f"Maps Error: {e}")
    finally:
        if driver: driver.quit()

    # 2. Fallback if 0 found
    if not unique_leads:
        log("No results in Maps. Trying web fallback...")
        fb_batch = search_fallback(query)
        for lead in fb_batch[:target_leads]:
            if lead.get("name") not in seen_names:
                lead = validate_lead(lead)
                unique_leads.append(lead)
                seen_names.add(lead.get("name"))
                print(f"DATA:{json.dumps(lead)}", flush=True)

    log(f"Done. Collected: {len(unique_leads)}")

if __name__ == "__main__":
    main()