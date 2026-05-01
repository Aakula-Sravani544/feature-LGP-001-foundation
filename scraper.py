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
    target_leads = 5
    
    log(f"🚀 LeadPulse Smart Scraper | Query: {query}")
    
    unique_leads = []
    seen_names = set()
    
    driver = get_driver()
    
    # 1. Main Search Phase
    try:
        encoded = query.replace(" ", "+")
        url = f"https://www.google.com/maps/search/{encoded}"
        
        if driver and safe_get(driver, url):
            time.sleep(6)
            from selenium.webdriver.common.by import By
            
            containers = driver.find_elements(By.CSS_SELECTOR, "a.hfpxzc, div.qBF1Pd")
            log(f"Analyzing {len(containers)} potential leads...")
            
            for container in containers:
                try:
                    lead = get_full_structure()
                    name = container.get_attribute("aria-label") or container.text.split('\n')[0]
                    if not name or name in seen_names: continue
                    
                    lead["name"] = name.strip()
                    
                    # Extract info from text
                    full_text = container.text
                    phone_match = re.search(r'(\+?\d{1,4}[\s-]?)?\(?\d{3}\)?[\s-]?\d{3}[\s-]?\d{4}', full_text)
                    if phone_match: lead["phone"] = phone_match.group(0)
                    
                    lead["google_maps_url"] = container.get_attribute("href") or driver.current_url
                    
                    # Apply Validation
                    lead = validate_lead(lead)
                    
                    # --- IMPROVEMENT: If Pending, try Fallback Search for this specific lead ---
                    if lead["validation_status"] == "Pending":
                        log(f"Searching for details for: {name}...")
                        fb_leads = search_fallback(f"{name} {query.split(' in ')[-1]}")
                        if fb_leads:
                            match = fb_leads[0]
                            lead["phone"] = match.get("phone") or lead["phone"]
                            lead["website"] = match.get("website") or lead["website"]
                            lead = validate_lead(lead)
                    
                    # If still Pending, we might have to skip or keep searching
                    if lead["validation_status"] != "Pending":
                        unique_leads.append(lead)
                        seen_names.add(name)
                        print(f"DATA:{json.dumps(lead)}", flush=True)
                        log(f"✅ Found Lead with Details: {name}")
                    else:
                        # Don't skip permanently, just log it
                        log(f"⚠️ Could not find details for {name}, trying next...")
                    
                    if len(unique_leads) >= target_leads: break
                except: continue
                
    except Exception as e:
        log(f"Maps Error: {e}")
    finally:
        if driver: driver.quit()

    # 2. Final Fallback (if still under target)
    if len(unique_leads) < target_leads:
        log(f"Still need {target_leads - len(unique_leads)} more leads. Running Global Fallback...")
        fb_batch = search_fallback(query)
        for lead in fb_batch:
            if lead.get("name") not in seen_names:
                lead = validate_lead(lead)
                if lead["validation_status"] != "Pending":
                    unique_leads.append(lead)
                    seen_names.add(lead.get("name"))
                    print(f"DATA:{json.dumps(lead)}", flush=True)
                    if len(unique_leads) >= target_leads: break

    log(f"Done. Collected {len(unique_leads)} Verified Leads.")

if __name__ == "__main__":
    main()