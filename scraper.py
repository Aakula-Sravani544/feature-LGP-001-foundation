import sys
import json
import time
import random
import re
from datetime import datetime
from driver_setup import get_driver, safe_get
from fallback_scraper import search_fallback
from validation import validate_lead, extract_email_from_web

def log(msg):
    print(f"LOG: {msg}", flush=True)

def clean_text(text):
    if not text: return ""
    return text.encode("utf-8", errors="ignore").decode("utf-8").strip()

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

def scrape_google_maps(driver, query, target_count=10):
    """
    Stabilized Maps scraper with automatic restart logic.
    """
    leads = []
    if driver is None: return leads # Requirement 4
    
    log(f"Searching Google Maps for '{query}'...")
    try:
        encoded = query.replace(" ", "+")
        url = f"https://www.google.com/maps/search/{encoded}"
        
        # Requirement 3: Add delay
        time.sleep(2)
        
        if not safe_get(driver, url): return leads
        time.sleep(5)
        
        from selenium.webdriver.common.by import By
        # Stop scrolling early to limit load (Requirement 3)
        containers = driver.find_elements(By.CSS_SELECTOR, "a.hfpxzc, div.qBF1Pd")
        
        # Requirement 6: Log collection
        log(f"Detected {len(containers)} results.")
        
        for container in containers[:target_count]: # Limit to 10 (Requirement 3)
            try:
                lead = get_full_structure()
                name = container.get_attribute("aria-label") or container.text.split('\n')[0]
                lead["name"] = clean_text(name)
                
                if not lead["name"]: continue
                
                lead["google_maps_url"] = container.get_attribute("href") or driver.current_url
                
                # Basic detail extraction without heavy interaction
                full_text = container.text
                match = re.search(r'(\+?\d{1,4}[\s-]?)?\(?\d{3}\)?[\s-]?\d{3}[\s-]?\d{4}', full_text)
                if match: lead["phone"] = match.group(0)
                
                lead["validation_status"] = "Valid"
                log(f"✅ Extracted: {lead['name']}")
                leads.append(lead)
                
                # Stop if we hit 10 (Requirement 3)
                if len(leads) >= 10: break
                
            except Exception as e:
                # Catch invalid session within loop
                if "invalid session id" in str(e).lower():
                    raise e # Bubbles up to main loop for restart
                continue
                
    except Exception as e:
        log(f"Maps Warning: {str(e)[:50]}...")
        if "invalid session id" in str(e).lower():
            raise e # Bubbles up to main loop for restart
            
    # Requirement 5: Return partial leads
    return leads

def main():
    if len(sys.argv) < 2: return
    main_query = sys.argv[1]
    target_leads = int(sys.argv[2]) if len(sys.argv) > 2 else 10
    
    log(f"🚀 LeadPulse Pro v4.0 | Target: {target_leads}")
    
    unique_leads = []
    seen_names = set()
    
    # Requirement 2: Restart logic
    driver = get_driver()
    restart_count = 0
    max_restarts = 2
    
    try:
        while len(unique_leads) < target_leads and restart_count <= max_restarts:
            try:
                # Requirement 4: Safe driver handling
                if driver is None:
                    driver = get_driver()
                    if driver is None: break
                
                batch = scrape_google_maps(driver, main_query, target_count=10)
                
                for l in batch:
                    if l["name"] and l["name"].lower() not in seen_names:
                        l = validate_lead(l)
                        unique_leads.append(l)
                        seen_names.add(l["name"].lower())
                        print(f"DATA:{json.dumps(l)}", flush=True)
                
                # If we got leads or finished, break the restart loop
                if unique_leads: break
                
                # If no leads found, try fallback
                log("Low yield. Switching to fallback...")
                fb_batch = search_fallback(main_query)
                for l in fb_batch:
                    if l["name"] and l["name"].lower() not in seen_names:
                        l = validate_lead(l)
                        unique_leads.append(l)
                        seen_names.add(l["name"].lower())
                        print(f"DATA:{json.dumps(l)}", flush=True)
                break # Exit while loop after fallback
                
            except Exception as e:
                if "invalid session id" in str(e).lower():
                    log("Driver restarted") # Requirement 6
                    restart_count += 1
                    try: driver.quit()
                    except: pass
                    driver = get_driver()
                    continue
                else:
                    log(f"Fatal Error: {e}")
                    break
                    
    finally:
        if driver:
            try: driver.quit()
            except: pass

    # Requirement 5 & 6: Fail safe return and log count
    log(f"Leads collected: {len(unique_leads)}")
    log("Done.")

if __name__ == "__main__":
    main()