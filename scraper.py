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
    return text.encode("utf-8", errors="ignore").decode("utf-8")

def get_full_structure():
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
    log(f"Phase 1: Searching for '{query}'...")
    
    encoded = query.replace(" ", "+")
    url = f"https://www.google.com/maps/search/{encoded}"
    
    if not safe_get(driver, url):
        return []
        
    time.sleep(4)
    
    try:
        from selenium.webdriver.common.by import By
        # More robust selector for results
        selectors = ["div.Nv2Ygc", "div.UaMeTe", "a.hfpxzc", "div.m67q60-V67S5c", ".fontHeadlineSmall"]
        
        containers = []
        for s in selectors:
            containers = driver.find_elements(By.CSS_SELECTOR, s)
            if containers: break
            
        if not containers:
            # Try one more scroll
            driver.execute_script("window.scrollBy(0, 800);")
            time.sleep(2)
            for s in selectors:
                containers = driver.find_elements(By.CSS_SELECTOR, s)
                if containers: break

        log(f"Detected {len(containers)} potential results. Extracting...")
        
        for container in containers[:target_count]:
            try:
                lead = get_full_structure()
                # Extraction logic
                try:
                    name = container.text.split('\n')[0] if container.text else container.get_attribute("aria-label")
                    if not name:
                        name = container.find_element(By.CSS_SELECTOR, ".qBF1Pd, .fontHeadlineSmall").text
                    lead["name"] = clean_text(name)
                except: continue

                if not lead["name"]: continue
                
                lead["google_maps_url"] = driver.current_url
                lead["validation_status"] = "Valid"
                
                log(f"✅ Found: {lead['name']}")
                print(f"DATA:{json.dumps(lead)}", flush=True)
                leads.append(lead)
                time.sleep(0.5)
                
            except: continue
                
    except Exception as e:
        log(f"Maps Error: {e}")
        
    return leads

def main():
    if len(sys.argv) < 2: return
    
    main_query = sys.argv[1]
    target_leads = int(sys.argv[2]) if len(sys.argv) > 2 else 50
    start_time = time.time()
    
    log(f"🚀 LeadPulse Engine Started | Target: {target_leads}")
    
    unique_leads = []
    seen_names = set()
    
    # Variations to guarantee yield
    queries = [main_query]
    if " in " in main_query:
        b, l = main_query.split(" in ")
        queries += [f"{b} in North {l}", f"{b} in South {l}", f"best {b} in {l}"]
    
    driver = get_driver()
    
    q_idx = 0
    while len(unique_leads) < target_leads and q_idx < len(queries):
        if time.time() - start_time > 58: break
            
        current_q = queries[q_idx]
        q_idx += 1
        
        batch = []
        try:
            if not driver: driver = get_driver()
            if driver:
                batch = scrape_google_maps(driver, current_q, target_count=15)
        except Exception as e:
            log(f"Browser error: {str(e)[:40]}...")
            log("Restarting Chrome to recover memory...")
            try: driver.quit()
            except: pass
            driver = get_driver()
            if driver:
                try: batch = scrape_google_maps(driver, current_q, target_count=5)
                except: pass
            
        if len(batch) < 3:
            log(f"Low yield. Switching to Multi-Source Fallback for '{current_q}'...")
            fb_batch = search_fallback(current_q)
            batch.extend(fb_batch)
            
        for l in batch:
            if l["name"] and l["name"] not in seen_names:
                unique_leads.append(l)
                seen_names.add(l["name"])
                if l.get("additional_data", "").startswith("Source:"):
                    print(f"DATA:{json.dumps(l)}", flush=True)
        
        log(f"Engine Progress: {len(unique_leads)}/{target_leads} leads")
        time.sleep(1)

    if driver: driver.quit()
    log(f"Extraction Finished. Total: {len(unique_leads)} leads in {int(time.time() - start_time)}s")

if __name__ == "__main__":
    main()