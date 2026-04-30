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

def clean_text(text):
    if not text: return ""
    return text.encode("utf-8", errors="ignore").decode("utf-8")

def get_full_structure():
    return {
        "name": "", "address": "", "phone": "", "email": "", "website": "",
        "rating": "", "reviews": "", "category": "", "google_maps_url": "",
        "description": "", "hours": "", "social_media": "", "additional_data": "",
        "scraped_date": datetime.now().strftime("%Y-%m-%d"),
        "ai_analysis": "N/A", "validation_status": "Candidate",
        "validation_notes": "", "sub_region": ""
    }

def scrape_google_maps(driver, query, target_count=10):
    leads = []
    log(f"Phase 1: Searching for '{query}'...")
    
    encoded = query.replace(" ", "+")
    url = f"https://www.google.com/maps/search/{encoded}"
    
    if not safe_get(driver, url): return []
    time.sleep(5)
    
    try:
        from selenium.webdriver.common.by import By
        # Ensure results have loaded
        containers = driver.find_elements(By.CSS_SELECTOR, "div.Nv2Ygc, div.UaMeTe, a.hfpxzc")
        
        if not containers:
            driver.execute_script("window.scrollBy(0, 1000);")
            time.sleep(2)
            containers = driver.find_elements(By.CSS_SELECTOR, "div.Nv2Ygc, div.UaMeTe, a.hfpxzc")

        log(f"Detected {len(containers)} results. Pulling details...")
        
        for container in containers[:target_count]:
            try:
                lead = get_full_structure()
                # Use splitlines for more accurate field isolation
                info = container.text.split('\n')
                if not info: continue
                
                lead["name"] = clean_text(info[0])
                
                # Search for specific data in the info block
                for line in info:
                    # Phone number regex
                    if re.search(r'\d{3,}[\s-]\d{3,}', line):
                        lead["phone"] = clean_text(line)
                    # Rating/Review check
                    elif "(" in line and ")" in line and any(c.isdigit() for c in line):
                        lead["reviews"] = clean_text(line)
                
                # Address usually 2nd or 3rd line
                if len(info) > 1:
                    lead["address"] = clean_text(info[1])
                
                lead["google_maps_url"] = driver.current_url
                lead["validation_status"] = "Valid"
                
                log(f"✅ Extracted: {lead['name']}")
                
                # Apply Day 4 Validation
                lead = validate_lead(lead)
                
                print(f"DATA:{json.dumps(lead)}", flush=True)
                leads.append(lead)
                time.sleep(0.3)
                
            except: continue
                
    except Exception as e:
        log(f"Maps Error: {e}")
        
    return leads

def main():
    if len(sys.argv) < 2: return
    main_query = sys.argv[1]
    target_leads = int(sys.argv[2]) if len(sys.argv) > 2 else 50
    start_time = time.time()
    
    log(f"🚀 Engine Started | Target: {target_leads}")
    
    unique_leads = []
    seen_names = set()
    
    queries = [main_query]
    if " in " in main_query:
        b, l = main_query.split(" in ")
        queries += [f"best {b} in {l}", f"top {b} near {l}"]
    
    driver = get_driver()
    
    q_idx = 0
    while len(unique_leads) < target_leads and q_idx < len(queries):
        if time.time() - start_time > 58: break
        current_q = queries[q_idx]
        q_idx += 1
        
        batch = []
        try:
            if not driver: driver = get_driver()
            if driver: batch = scrape_google_maps(driver, current_q, target_count=15)
        except:
            log("OOM Recovery: Restarting Chrome...")
            try: driver.quit()
            except: pass
            driver = get_driver()
            if driver:
                try: batch = scrape_google_maps(driver, current_q, target_count=5)
                except: pass
            
        if len(batch) < 3:
            log(f"Low yield. Using Fallback Engine for '{current_q}'...")
            fb_batch = search_fallback(current_q)
            batch.extend(fb_batch)
            
        for l in batch:
            if l["name"] and l["name"] not in seen_names:
                unique_leads.append(l)
                seen_names.add(l["name"])
                # Fallback data is printed here if not already printed
                if l.get("additional_data") == "Generated via Fallback":
                    # Apply Day 4 Validation
                    l = validate_lead(l)
                    print(f"DATA:{json.dumps(l)}", flush=True)
                else:
                    # If it came from scrape_google_maps it's already validated there,
                    # but we can validate again to be 100% sure for requirement 8
                    l = validate_lead(l)
        
        log(f"Status: {len(unique_leads)}/{target_leads} leads")
        time.sleep(1)

    if driver: driver.quit()
    log(f"Done. Total: {len(unique_leads)} leads.")

if __name__ == "__main__":
    main()