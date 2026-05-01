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
    
    log(f"🚀 LeadPulse Deep Scraper | Query: {query}")
    
    unique_leads = []
    seen_names = set()
    
    driver = get_driver()
    
    try:
        encoded = query.replace(" ", "+")
        url = f"https://www.google.com/maps/search/{encoded}"
        
        if driver and safe_get(driver, url):
            time.sleep(6)
            from selenium.webdriver.common.by import By
            
            # Find lead cards
            cards = driver.find_elements(By.CSS_SELECTOR, "a.hfpxzc")
            if not cards:
                cards = driver.find_elements(By.CSS_SELECTOR, "div.qBF1Pd")
            
            log(f"Found {len(cards)} candidates. Extracting deep details...")
            
            for i, card in enumerate(cards[:10]): # Check first 10
                try:
                    # 1. Basic Extract
                    lead = get_full_structure()
                    name = card.get_attribute("aria-label") or card.text.split('\n')[0]
                    if not name or name in seen_names: continue
                    lead["name"] = name.strip()
                    
                    # 2. CLICK to open sidebar (Guarantee details)
                    try:
                        driver.execute_script("arguments[0].click();", card)
                        time.sleep(2.5) # Wait for sidebar
                        
                        # Extract from sidebar
                        sidebar_text = driver.find_element(By.CSS_SELECTOR, "div.m67q60").text
                        
                        # Phone
                        phone_match = re.search(r'(\+?\d{1,4}[\s-]?)?\(?\d{3}\)?[\s-]?\d{3}[\s-]?\d{4}', sidebar_text)
                        if phone_match: lead["phone"] = phone_match.group(0)
                        
                        # Website
                        try:
                            web_el = driver.find_element(By.CSS_SELECTOR, "a[data-item-id='authority']")
                            lead["website"] = web_el.get_attribute("href")
                        except: pass
                        
                        # Address
                        try:
                            addr_el = driver.find_element(By.CSS_SELECTOR, "button[data-item-id='address']")
                            lead["address"] = addr_el.text
                        except: pass
                        
                    except Exception as e:
                        log(f"Sidebar error for {name}: {str(e)[:30]}")
                    
                    lead["google_maps_url"] = driver.current_url
                    lead = validate_lead(lead)
                    
                    if lead["validation_status"] != "Pending":
                        unique_leads.append(lead)
                        seen_names.add(name)
                        print(f"DATA:{json.dumps(lead)}", flush=True)
                        log(f"✅ Extracted: {name}")
                    
                    if len(unique_leads) >= target_leads: break
                    
                except: continue
                
    except Exception as e:
        log(f"Maps Error: {e}")
    finally:
        if driver: driver.quit()

    # Final Fallback if still under 5
    if len(unique_leads) < target_leads:
        log("Yield low. Running Emergency Web Fallback...")
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