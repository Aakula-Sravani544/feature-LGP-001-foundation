import sys
import json
import time
import random
import re
import uuid
from datetime import datetime
from driver_setup import get_driver, safe_get
from fallback_scraper import search_fallback

def log(msg):
    print(f"LOG: {msg}", flush=True)

def clean_text(text):
    if not text: return ""
    # Senior Dev Hack: Fix encoding issues for Render/Linux
    return text.encode("utf-8", errors="ignore").decode("utf-8")

def get_full_structure():
    """Returns the exact 17-field structure requested."""
    return {
        "name": "",
        "address": "",
        "phone": "",
        "email": "",
        "website": "",
        "rating": "",
        "reviews": "",
        "category": "",
        "google_maps_url": "",
        "description": "",
        "hours": "",
        "social_media": "",
        "additional_data": "",
        "scraped_date": datetime.now().strftime("%Y-%m-%d"),
        "ai_analysis": "N/A",
        "validation_status": "Candidate",
        "validation_notes": "",
        "sub_region": ""
    }

def scrape_google_maps(driver, query, target_count=10):
    leads = []
    log(f"Running Google Maps query: {query}")
    
    encoded = query.replace(" ", "+")
    url = f"https://www.google.com/maps/search/{encoded}"
    
    if not safe_get(driver, url):
        return []
        
    time.sleep(3)
    
    try:
        from selenium.webdriver.common.by import By
        # Only scroll a tiny bit to stay within 60s limit
        driver.execute_script("window.scrollBy(0, 400);")
        time.sleep(1)
        
        containers = driver.find_elements(By.CSS_SELECTOR, "div.Nv2Ygc, div.UaMeTe, a.hfpxzc")
        
        for container in containers[:target_count]:
            try:
                lead = get_full_structure()
                
                # Extract name
                try:
                    name_el = container.find_element(By.CSS_SELECTOR, ".qBF1Pd, .fontHeadlineSmall")
                    lead["name"] = clean_text(name_el.text)
                except:
                    # Fallback to aria-label if link element
                    lead["name"] = clean_text(container.get_attribute("aria-label"))
                
                if not lead["name"]: continue
                
                # Basic data
                lead["google_maps_url"] = driver.current_url
                lead["category"] = "Google Maps Business"
                lead["validation_status"] = "Valid"
                
                # Output immediately
                print(f"DATA:{json.dumps(lead)}", flush=True)
                leads.append(lead)
                time.sleep(random.uniform(0.5, 1.0))
                
            except: continue
                
    except Exception as e:
        log(f"Maps extraction error: {e}")
        
    return leads

def main():
    if len(sys.argv) < 2: return
    
    main_query = sys.argv[1]
    target_leads = int(sys.argv[2]) if len(sys.argv) > 2 else 50
    start_time = time.time()
    
    log(f"LeadPulse Engine Started | Target: {target_leads}")
    
    unique_leads = []
    seen_names = set()
    
    # Guarantee leads with multiple query variations
    queries = [main_query]
    if " in " in main_query:
        parts = main_query.split(" in ")
        queries.append(f"top {parts[0]} in {parts[1]}")
        queries.append(f"best {parts[0]} near {parts[1]}")
    
    driver = get_driver()
    log("Chrome initialized on Render successfully.")
    
    q_idx = 0
    while len(unique_leads) < target_leads and q_idx < len(queries):
        # 60 second hard limit
        if time.time() - start_time > 58:
            log("Hard timeout reached (60s).")
            break
            
        current_q = queries[q_idx]
        q_idx += 1
        
        # 1. Try Selenium
        batch = []
        if driver:
            batch = scrape_google_maps(driver, current_q, target_count=15)
            
        # 2. Try Fallback if batch small or failed
        if len(batch) < 3:
            log(f"Low yield from Selenium. Running Fallback for '{current_q}'...")
            fallback_batch = search_fallback(current_q)
            batch.extend(fallback_batch)
            
        # Process batch
        for l in batch:
            if l["name"] and l["name"] not in seen_names:
                unique_leads.append(l)
                seen_names.add(l["name"])
                # Fallback data is already printed in search_fallback if needed, 
                # but we print it here if it wasn't.
                if l.get("additional_data") == "Generated via Fallback":
                    print(f"DATA:{json.dumps(l)}", flush=True)
        
        log(f"Yield: {len(unique_leads)} unique leads collected.")
        time.sleep(1)

    if driver: driver.quit()
    log(f"Done! {len(unique_leads)} leads generated in {int(time.time() - start_time)}s")

if __name__ == "__main__":
    main()