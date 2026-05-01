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

def scrape_google_maps(driver, query, target_count=5):
    if not driver: return []
    leads = []
    log(f"Searching Google Maps for '{query}'...")
    try:
        encoded = query.replace(" ", "+")
        url = f"https://www.google.com/maps/search/{encoded}"
        if not safe_get(driver, url): return []
        time.sleep(6)
        
        from selenium.webdriver.common.by import By
        # Multi-selector strategy
        selectors = ["a.hfpxzc", "div.qBF1Pd", "div.Nv2Ygc"]
        containers = []
        for s in selectors:
            containers = driver.find_elements(By.CSS_SELECTOR, s)
            if containers: break
            
        for container in containers[:target_count]:
            try:
                lead = get_full_structure()
                name = container.get_attribute("aria-label") or container.text.split('\n')[0]
                lead["name"] = clean_text(name)
                
                # Skip if name empty (Requirement 1)
                if not lead["name"] or len(lead["name"]) < 2: continue
                
                # Enhanced extraction from text
                full_text = container.text
                lead["phone"] = extract_phone(full_text)
                
                # Address extraction
                info = full_text.split('\n')
                if len(info) > 1: lead["address"] = clean_text(info[1])
                
                lead["google_maps_url"] = container.get_attribute("href") or driver.current_url
                
                # Extract website if possible
                if lead["google_maps_url"] and "/place/" in lead["google_maps_url"]:
                    # Deep extraction usually requires clicking, but we skip to stay fast
                    pass
                
                leads.append(lead)
            except: continue
    except Exception as e:
        log(f"Maps Warning: {e}")
    return leads

def extract_phone(text):
    """Requirement 2: Extract phone from text if missing"""
    match = re.search(r'(\+?\d{1,4}[\s-]?)?\(?\d{3}\)?[\s-]?\d{3}[\s-]?\d{4}', text)
    if match:
        return match.group(0)
    return ""

def main():
    if len(sys.argv) < 2: return
    main_query = sys.argv[1]
    target_leads = int(sys.argv[2]) if len(sys.argv) > 2 else 50
    
    log(f"🚀 LeadPulse Pro Backend | Query: {main_query}")
    
    unique_leads = []
    seen_names = set()
    seen_phones = set()
    seen_websites = set()
    
    # Requirement 8: Multiple search queries if yield is low
    base_query = main_query.split(" in ")[0] if " in " in main_query else main_query
    location = main_query.split(" in ")[1] if " in " in main_query else ""
    
    queries = [main_query]
    if location:
        # Rotation: restaurants, hotels, cafes, shops (Requirement 8)
        rotation = ["restaurants", "hotels", "cafes", "shops", "services"]
        for r in rotation:
            if r not in base_query.lower():
                queries.append(f"{r} in {location}")
    
    driver = get_driver()
    q_idx = 0
    
    while len(unique_leads) < target_leads and q_idx < len(queries):
        current_q = queries[q_idx]
        q_idx += 1
        
        batch = []
        if driver:
            batch = scrape_google_maps(driver, current_q, target_count=15)
        
        if not batch:
            log(f"Trying Fallback for {current_q}...")
            batch = search_fallback(current_q)
            
        for l in batch:
            # --- Requirement 1 & 9: Strict Filtering & Deduplication ---
            name = l.get("name", "").strip()
            phone = l.get("phone", "").strip()
            web = l.get("website", "").strip()
            
            if not name: continue
            if name.lower() in seen_names: continue
            if phone and phone in seen_phones: continue
            if web and web in seen_websites: continue
            
            # --- Requirement 2: Email Extraction from Website ---
            if web and not l.get("email"):
                l["email"] = extract_email_from_web(web)
            
            # --- Requirement 1: Skip if no contact info ---
            if not any([phone, web, l.get("email")]):
                continue
            
            # --- Requirement 6: Apply Validation Layer ---
            l = validate_lead(l)
            
            # Final check after normalization (Requirement 1)
            if not any([l["phone"], l["email"], l["website"]]):
                continue
                
            unique_leads.append(l)
            seen_names.add(name.lower())
            if l["phone"]: seen_phones.add(l["phone"])
            if l["website"]: seen_websites.add(l["website"])
            
            # Requirement 10: Debug Log
            print(f"Lead: {l['name']} | {l['validation_status']}")
            print(f"DATA:{json.dumps(l)}", flush=True)
            
            if len(unique_leads) >= target_leads: break
            
        # Stop early if we have enough and it's not the first query (Requirement 8 logic)
        if len(unique_leads) >= 10 and q_idx > 0:
            break

    if driver: driver.quit()
    log(f"Done. Total Unique Leads: {len(unique_leads)}")

if __name__ == "__main__":
    main()