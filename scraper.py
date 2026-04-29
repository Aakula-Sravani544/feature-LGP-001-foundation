import time
import sys
import json
import os
import re
import traceback
import hashlib
import urllib.parse
from datetime import datetime
import pandas as pd
import requests

# Database & Sheets
import database
import google_sheets

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

def log(msg):
    print(f"LOG: {msg}", flush=True)

def data_out(obj):
    print(f"DATA: {json.dumps(obj)}", flush=True)

def kill_chrome():
    try:
        if os.name == 'nt':
            os.system('taskkill /f /im chrome.exe /im chromedriver.exe /im google-chrome.exe >nul 2>&1')
        else:
            os.system('pkill -f chrome > /dev/null 2>&1')
        time.sleep(2)
    except: pass

def get_driver():
    kill_chrome()
    try:
        log("Launching Turbo-Optimized Browser...")
        options = webdriver.ChromeOptions()
        options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--disable-software-rasterizer")
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-infobars")
        options.add_argument("--disable-notifications")
        options.add_argument("--remote-debugging-port=9222")
        
        # --- Extreme memory flags requested ---
        options.add_argument("--single-process")
        options.add_argument("--no-zygote")
        options.add_argument("--renderer-process-limit=1")
        options.add_argument("--disable-background-timer-throttling")
        options.add_argument("--disable-backgrounding-occluded-windows")
        options.add_argument("--memory-pressure-off")
        options.add_argument("--js-flags=--max-old-space-size=128 --optimize-for-size --gc-interval=100")
        
        options.add_argument("--window-size=1280,720")
        options.add_argument("--blink-settings=imagesEnabled=false") 
        options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36")
        
        options.add_argument("--disable-features=VizDisplayCompositor")
        options.add_argument("--disable-features=IsolateOrigins,site-per-process")
        options.add_argument("--force-color-profile=srgb")
        options.add_argument("--metrics-recording-only")
        options.add_argument("--mute-audio")
        
        # Offload Memory to Disk
        options.add_argument("--disk-cache-dir=/tmp/chrome-cache")
        options.add_argument("--user-data-dir=/tmp/chrome-data")
        options.add_argument("--disable-dev-shm-usage") # Use /tmp instead of /dev/shm
        
        # Extreme RAM savings: Block images, CSS, fonts, etc.
        prefs = {
            "profile.managed_default_content_settings.images": 2,
            "profile.managed_default_content_settings.stylesheets": 2,
            "profile.managed_default_content_settings.fonts": 2,
            "profile.default_content_setting_values.notifications": 2
        }
        options.add_experimental_option("prefs", prefs)
        
        # Interceptor
        options.set_capability('goog:loggingPrefs', {'performance': 'ALL'})
        
        render_path = "/opt/render/project/.render/chrome/opt/google/chrome/google-chrome"
        docker_path = "/usr/bin/google-chrome"
        
        if os.path.exists(render_path):
            options.binary_location = render_path
        elif os.path.exists(docker_path):
            options.binary_location = docker_path
            
        driver = webdriver.Chrome(options=options)
        
        # CDP Network Interception
        driver.execute_cdp_cmd('Network.enable', {})
        driver.execute_cdp_cmd('Network.setBlockedURLs', {"urls": [
            "*.png", "*.jpg", "*.jpeg", "*.gif", "*.svg", "*.webp", 
            "*.css", "*.woff", "*.woff2", "*.mp4", "*.webm"
        ]})
        
        driver.set_page_load_timeout(120)
        driver.set_script_timeout(120)
        return driver
    except Exception as e:
        log(f"Browser launch failed: {str(e)}")
        import traceback
        log(f"Error Details: {traceback.format_exc()}")
        return None

def extract_email(website):
    if not website or website == "" or "google.com" in website:
        return ""
    try:
        with requests.Session() as session:
            response = session.get(
                website, 
                timeout=3, 
                headers={"User-Agent": "Mozilla/5.0"}, 
                stream=False
            )
            text = response.text
            response.close() # Immediately close to free socket/memory
            
            emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text)
            filtered = [e for e in emails if not e.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp'))]
            return filtered[0] if filtered else ""
    except:
        return ""

def extract_single_card(driver, card, query):
    try:
        driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", card)
        time.sleep(0.5)
        try: card.click()
        except: driver.execute_script("arguments[0].click()", card)
        time.sleep(4) # Render slow server offset

        def get_val(selectors, attr=None):
            for sel in selectors:
                try:
                    el = driver.find_element(By.CSS_SELECTOR, sel)
                    val = el.get_attribute(attr) if attr else el.text
                    if val and val.strip(): return val.strip()
                except: continue
            return ""

        name = get_val(["h1.DUwDvf", "div.x3AX1-Lf971b-p9v7id-suZ9lb"])
        if not name: return None
        
        address = get_val(["button[data-item-id='address']", "div.Io6YTe.fontBodyMedium.kR997c"])
        phone = get_val(["button[data-item-id*='phone']", "div[data-item-id*='phone'] .Io6YTe"])
        website = get_val(["a[data-item-id='authority']", "div[data-item-id='authority'] .Io6YTe"], "href")
        category = get_val(["button.D693id", "span.mgr77e", "div.fontBodyMedium .sk06S"])
        rating = get_val(["span.ceNzR", "div.fontDisplayLarge"], "aria-label")
        reviews = get_val(["span.F7kY9c", "button.HH6Xqe", "span[aria-label*='reviews']"])
        hours = get_val(["div[data-item-id='oh']", "table.e07dbf"], "aria-label")
        description = get_val(["div.PYvS2b", "div.fontBodyMedium.kR997c .Io6YTe"])
        
        if reviews:
            reviews = reviews.replace("(", "").replace(")", "").split()[0]

        lat, lng = "", ""
        try:
            url = driver.current_url
            match = re.search(r'@([\d\.\-]+),([\d\.\-]+)', url)
            if match: lat, lng = match.group(1), match.group(2)
        except: pass

        uid = hashlib.md5(f"{name}{phone}{address}".encode()).hexdigest()
        
        lead = {
            "lead_id": uid,
            "business_name": name,
            "address": address,
            "phone": phone,
            "website": website,
            "email": extract_email(website),
            "rating": rating,
            "review_count": reviews,
            "category": category,
            "maps_url": driver.current_url,
            "business_hours": hours,
            "social_media": "", 
            "description": description,
            "latitude": lat,
            "longitude": lng,
            "query": query,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        # DOM Pruning
        try:
            driver.execute_script("arguments[0].innerHTML = '';", card)
        except: pass
        
        return lead
    except: return None

def scroll_panel(driver, panel):
    try:
        if panel:
            driver.execute_script("""
                arguments[0].scrollTop += 1500;
            """, panel)
        else:
            driver.execute_script("window.scrollBy(0, 1500)")
    except:
        driver.execute_script("window.scrollBy(0, 1500)")
    time.sleep(3)

def run_scraper(query, target_count=20):
    driver = get_driver()
    if not driver: return

    try:
        wait = WebDriverWait(driver, 30)
        log("Opening Maps...")
        encoded_query = urllib.parse.quote_plus(query)
        driver.get(f"https://www.google.com/maps/search/{encoded_query}")
        
        time.sleep(6)
        consent_selectors = [
            "form[action*='consent'] button",
            "button[aria-label='Accept all']",
            "button[aria-label='Agree']",
            ".VfPpkd-LgbsBe[aria-label*='Accept']"
        ]
        for sel in consent_selectors:
            try:
                btn = driver.find_element(By.CSS_SELECTOR, sel)
                btn.click()
                log("Bypassed Cookie Consent.")
                time.sleep(2)
                break
            except: continue

        if "consent" in driver.current_url:
            driver.get(f"https://www.google.com/maps/search/{encoded_query}")
            time.sleep(6)

        log("Waiting for results to load...")
        try:
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.Nv2PK, div[role='article']")))
        except:
            log("Timeout waiting for cards. Retrying page load...")
            driver.refresh()
            time.sleep(7)

        log("Collecting and extracting result cards...")
        attempts = 0
        MAX_STALL_ATTEMPTS = 8
        scroll_start_time = time.time()
        
        panel = None
        pane_selectors = [
            "div[role='feed']", 
            "div.m6QErb.DxyBCb", 
            "div[aria-label*='Results']",
            "div.m6QErb.klm32b"
        ]
        
        for sel in pane_selectors:
            try:
                elements = driver.find_elements(By.CSS_SELECTOR, sel)
                if elements:
                    panel = elements[0]
                    log(f"Found results pane using: {sel}")
                    break
            except: continue
            
        seen_lead_ids = set()
        leads = []
        total_extracted = 0
            
        while len(leads) < target_count:
            if time.time() - scroll_start_time > 90:
                log(f"Hard timeout reached. Extracting {len(leads)} leads found so far.")
                break
                
            cards = driver.find_elements(By.CSS_SELECTOR, "div.Nv2PK, div[role='article']")
            new_cards_found = 0
            
            for card in cards:
                if len(leads) >= target_count: break
                try:
                    card_name_el = card.find_element(By.CSS_SELECTOR, "div.qBF1Pd, .fontHeadlineSmall")
                    card_name = card_name_el.text.strip() if card_name_el else ""
                    
                    if card_name and card_name not in seen_lead_ids:
                        seen_lead_ids.add(card_name)
                        new_cards_found += 1
                        
                        log(f"Processing lead {len(leads)+1}/{target_count} ({card_name})...")
                        lead = extract_single_card(driver, card, query)
                        if lead:
                            leads.append(lead)
                            data_out(lead)
                            
                        total_extracted += 1
                        if total_extracted > 0 and total_extracted % 10 == 0:
                            try:
                                driver.execute_script("window.gc && window.gc()")
                                driver.execute_cdp_cmd('Network.clearBrowserCache', {})
                            except: pass
                except: continue
            
            if new_cards_found == 0:
                attempts += 1
                
                # --- Map Reset Strategy ---
                if attempts == 4 or attempts == 6:
                    log("Google Maps is stalling. Attempting Map Zoom out...")
                    try:
                        zoom_out_btns = driver.find_elements(By.CSS_SELECTOR, "button[aria-label='Zoom out'], button#widget-zoom-out")
                        if zoom_out_btns:
                            zoom_out_btns[0].click()
                            time.sleep(1)
                    except: pass
                
                if attempts > 3:
                    try:
                        search_area_btns = driver.find_elements(By.XPATH, "//button[contains(., 'Search this area')]")
                        if search_area_btns and search_area_btns[0].is_displayed():
                            log("Clicking 'Search this area' to find more leads...")
                            search_area_btns[0].click()
                            time.sleep(3)
                    except: pass
            else:
                attempts = 0
                
            if attempts >= MAX_STALL_ATTEMPTS:
                log(f"Stalled after {attempts} attempts. Breaking loop.")
                break
                
            scroll_panel(driver, panel)

        log(f"Extraction complete. Processing {len(leads)} leads...")
        database.save_to_db(leads)
        
        log("Connected to Google Sheets...")
        log("Validating existing lead repository...")
        success, msg = google_sheets.save_to_google_sheets(leads)
        if success:
            log(f"Sync Result: {msg}")
            log("Google Sheets sync complete.")
        else:
            log(f"Sheets Sync Warning: {msg}")

        try:
            if not os.path.exists("data"): os.makedirs("data")
            pd.DataFrame(leads).to_csv("data/leads.csv", index=False)
            log("CSV Backup saved.")
        except: pass

        log(f"Completed {len(leads)} leads")

    except Exception as e: log(f"CRITICAL ERROR: {str(e)}")
    finally:
        if driver: 
            try: driver.quit()
            except: pass
        kill_chrome()

if __name__ == "__main__":
    q = sys.argv[1] if len(sys.argv) > 1 else "Hotels Hyderabad"
    run_scraper(q)
