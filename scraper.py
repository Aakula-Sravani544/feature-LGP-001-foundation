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

def go_back_to_list(driver):
    """Navigate back to the search results list."""
    try:
        back_btns = driver.find_elements(By.CSS_SELECTOR, 
            "button[aria-label='Back'], button.hYBOP, button[jsaction*='back']")
        if back_btns:
            back_btns[0].click()
            time.sleep(2)
            return True
    except: pass
    try:
        driver.execute_script("window.history.back()")
        time.sleep(2)
        return True
    except: pass
    return False

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

        log("Phase 1: Scrolling to collect card names...")
        attempts = 0
        MAX_STALL_ATTEMPTS = 8
        SCROLL_TIMEOUT = 90
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
            
        all_card_names = []
            
        while len(all_card_names) < target_count:
            if time.time() - scroll_start_time > SCROLL_TIMEOUT:
                log(f"Hard scroll timeout reached. Found {len(all_card_names)} cards.")
                break
                
            cards = driver.find_elements(By.CSS_SELECTOR, "div.Nv2PK, div[role='article']")
            new_names = 0
            
            for card in cards:
                try:
                    n = card.find_element(By.CSS_SELECTOR, "div.qBF1Pd, .fontHeadlineSmall, .NrDZNb, div[class*='fontBody']").text.strip()
                    if n and n not in all_card_names:
                        all_card_names.append(n)
                        new_names += 1
                        if len(all_card_names) >= target_count: break
                except: pass
                
            log(f"Scrolled: found {len(all_card_names)}/{target_count} unique cards so far...")
            
            if new_names == 0:
                attempts += 1
                if attempts == 4 or attempts == 6:
                    log("Google Maps stalling. Zooming out...")
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
                log(f"Stalled after {attempts} attempts. Moving to extraction.")
                break
                
            scroll_panel(driver, panel)

        log(f"Snapshot taken: {len(all_card_names)} card names ready for extraction")

        log("Phase 2: Extracting leads...")
        seen = set()
        leads = []
        EXTRACT_TIMEOUT = 300
        extract_start = time.time()

        for idx, card_name in enumerate(all_card_names):
            if time.time() - extract_start > EXTRACT_TIMEOUT:
                log("Extraction timeout reached. Stopping.")
                break
                
            if card_name in seen: continue
            seen.add(card_name)
            log(f"Extracting lead {idx+1}/{len(all_card_names)}: {card_name}")
            
            go_back_to_list(driver)
            
            try:
                if "'" in card_name:
                    xpath_expr = f"//div[contains(@class,'Nv2PK')]//div[text()=\"{card_name}\"] | //div[@role='article']//div[text()=\"{card_name}\"]"
                else:
                    xpath_expr = f"//div[contains(@class,'Nv2PK')]//div[text()='{card_name}'] | //div[@role='article']//div[text()='{card_name}']"
                
                clickable = driver.find_element(By.XPATH, xpath_expr)
                driver.execute_script("arguments[0].scrollIntoView({block:'center'})", clickable)
                time.sleep(0.5)
                driver.execute_script("arguments[0].closest('.Nv2PK, [role=article]').click()", clickable)
            except Exception as e:
                log(f"Could not click card '{card_name}': {e}")
                continue
            
            # Wait for detail panel
            try:
                WebDriverWait(driver, 15).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "h1.DUwDvf, h1.fontHeadlineLarge, h1[class*='fontHeadline']"))
                )
            except:
                log(f"Detail panel did not load for '{card_name}', skipping")
                continue

            def get_val(selectors, attr=None):
                for sel in selectors:
                    try:
                        el = driver.find_element(By.CSS_SELECTOR, sel)
                        val = el.get_attribute(attr) if attr else el.text
                        if val and val.strip(): return val.strip()
                    except: continue
                return ""

            name = get_val([
                "h1.DUwDvf",
                "h1.fontHeadlineLarge",
                "h1[class*='fontHeadline']",
                "div.x3AX1-LfntMc-header-title-title",
                "span.fontHeadlineLarge",
                ".DUwDvf"
            ])
            
            if not name:
                log(f"No name found for card {idx+1}, skipping")
                continue
                
            address = get_val([
                "button[data-item-id='address']",
                "button[aria-label*='Address']",
                "div[data-item-id='address']",
                ".rogA2c .Io6YTe",
                "button[data-tooltip='Copy address']"
            ], "aria-label")
            if not address:
                address = get_val([
                    "button[data-item-id='address']",
                    "div[data-item-id='address'] .Io6YTe"
                ])
                
            phone = get_val([
                "button[data-item-id*='phone']",
                "button[aria-label*='phone']",
                "button[aria-label*='Phone']",
                "a[href^='tel:']",
                "span[aria-label*='+91']"
            ], "aria-label")
            if not phone:
                phone = get_val(["button[data-item-id*='phone']", "a[href^='tel:']"])

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
            
            leads.append(lead)
            data_out(lead)
            
            # Periodically force GC
            if idx > 0 and idx % 10 == 0:
                try:
                    driver.execute_script("window.gc && window.gc()")
                    driver.execute_cdp_cmd('Network.clearBrowserCache', {})
                except: pass

        log(f"Extraction complete. Found {len(leads)} valid leads.")
        database.save_to_db(leads)
        
        log("Connected to Google Sheets...")
        success, msg = google_sheets.save_to_google_sheets(leads)
        if success:
            log(f"Sync Result: {msg}")
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
