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
        
        # Additional flags from user
        options.add_argument("--aggressive-cache-discard")
        options.add_argument("--max_old_space_size=256")
        
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

def run_scraper(query, target_count=20):
    driver = get_driver()
    if not driver:
        log("FATAL: Browser failed to launch")
        return

    leads = []

    try:
        log("Opening Maps...")
        encoded_query = urllib.parse.quote_plus(query)
        driver.get(f"https://www.google.com/maps/search/{encoded_query}")
        time.sleep(6)

        # Handle consent popup
        for sel in ["button[aria-label='Accept all']", "button[aria-label='Agree']",
                    "form[action*='consent'] button"]:
            try:
                btn = driver.find_element(By.CSS_SELECTOR, sel)
                btn.click()
                time.sleep(2)
                break
            except: continue

        # Wait for first card
        log("Waiting for results...")
        try:
            WebDriverWait(driver, 25).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div.Nv2PK, div[role='article']"))
            )
        except:
            log("Timeout waiting. Refreshing...")
            driver.refresh()
            time.sleep(8)

        # Find scroll panel
        panel = None
        for sel in ["div[role='feed']", "div.m6QErb.DxyBCb", "div[aria-label*='Results']", "div.m6QErb"]:
            try:
                el = driver.find_element(By.CSS_SELECTOR, sel)
                if el:
                    panel = el
                    log(f"Panel: {sel}")
                    break
            except: continue

        # SCROLL to load cards
        log("Scrolling to load cards...")
        seen_names = set()
        stall = 0
        scroll_start = time.time()

        while len(seen_names) < target_count and stall < 8 and (time.time()-scroll_start) < 60:
            cards = driver.find_elements(By.CSS_SELECTOR, "div.Nv2PK, div[role='article']")
            prev = len(seen_names)
            for card in cards:
                try:
                    for sel in ["div.qBF1Pd",".fontHeadlineSmall",".NrDZNb","div[class*='fontBody'] span"]:
                        try:
                            n = card.find_element(By.CSS_SELECTOR, sel).text.strip()
                            if n: seen_names.add(n); break
                        except: continue
                except: continue
            stall = 0 if len(seen_names) > prev else stall+1
            try:
                driver.execute_script("arguments[0].scrollTop += 1200", panel) if panel else driver.execute_script("window.scrollBy(0,1200)")
            except: driver.execute_script("window.scrollBy(0,1200)")
            time.sleep(2)
            log(f"Scrolled: {len(seen_names)} unique cards so far...")

        log(f"Scroll done. {len(seen_names)} cards found. Starting extraction...")

        # EXTRACTION — stay on same page, click and go back
        processed = set()
        extract_start = time.time()
        card_index = 0

        while len(leads) < target_count and (time.time()-extract_start) < 240:
            # Re-fetch cards fresh every iteration (stale element safe)
            try:
                all_cards = driver.find_elements(By.CSS_SELECTOR, "div.Nv2PK, div[role='article']")
            except:
                time.sleep(2)
                continue

            if card_index >= len(all_cards):
                # Scroll a bit more to load next batch
                try:
                    driver.execute_script("arguments[0].scrollTop += 800", panel) if panel else driver.execute_script("window.scrollBy(0,800)")
                    time.sleep(2)
                    all_cards = driver.find_elements(By.CSS_SELECTOR, "div.Nv2PK, div[role='article']")
                except: pass
                if card_index >= len(all_cards):
                    log(f"No more cards at index {card_index}. Done.")
                    break

            card = all_cards[card_index]

            # Get name for dedup check
            card_name = f"card_{card_index}"
            for sel in ["div.qBF1Pd",".fontHeadlineSmall",".NrDZNb"]:
                try:
                    n = card.find_element(By.CSS_SELECTOR, sel).text.strip()
                    if n: card_name = n; break
                except: continue

            if card_name in processed:
                card_index += 1
                continue

            log(f"Extracting {len(leads)+1}/{target_count}: {card_name}")

            try:
                # Scroll into view
                driver.execute_script("arguments[0].scrollIntoView({block:'center'})", card)
                time.sleep(0.8)

                # Click card using JS
                driver.execute_script("arguments[0].click()", card)

                # Wait for detail panel
                detail_loaded = False
                for sel in ["h1.DUwDvf","h1.fontHeadlineLarge","h1[class*='fontHeadline']",
                            "button[data-item-id='address']","[data-item-id*='phone']"]:
                    try:
                        WebDriverWait(driver, 10).until(
                            EC.presence_of_element_located((By.CSS_SELECTOR, sel)))
                        detail_loaded = True
                        break
                    except: continue

                if not detail_loaded:
                    log(f"Detail panel timeout for {card_name}")
                    processed.add(card_name)
                    card_index += 1
                    # Go back
                    try: driver.execute_script("window.history.back()"); time.sleep(3)
                    except: pass
                    continue

                time.sleep(2)

                # Extract all fields
                def get_val(selectors, attr=None):
                    for sel in selectors:
                        try:
                            el = driver.find_element(By.CSS_SELECTOR, sel)
                            val = el.get_attribute(attr) if attr else el.text
                            if val and val.strip(): return val.strip()
                        except: continue
                    return ""

                name = get_val(["h1.DUwDvf","h1.fontHeadlineLarge","h1[class*='fontHeadline']"]) or card_name
                address = get_val(["button[data-item-id='address']","[data-item-id='address'] .Io6YTe"])
                if not address: address = get_val(["button[data-item-id='address']"],"aria-label")
                phone = get_val(["button[data-item-id*='phone']","a[href^='tel:']","button[aria-label*='hone']"])
                if not phone: phone = get_val(["button[data-item-id*='phone']"],"aria-label")
                website = get_val(["a[data-item-id='authority']","a[data-item-id='website']"],"href")
                rating = get_val(["span.ceNzR","div.fontDisplayLarge"])
                reviews = get_val(["span.F7kY9c","button.HH6Xqe","span[aria-label*='review']"])
                if reviews: reviews = reviews.replace("(","").replace(")","").split()[0]
                category = get_val(["button.DkEaL","button.D693id","span.mgr77e"])
                hours = get_val(["div[data-item-id='oh']"],"aria-label")
                description = get_val(["div.PYvS2b","div.fontBodyMedium .Io6YTe"])

                lat, lng = "", ""
                try:
                    m = re.search(r'@([\d\.\-]+),([\d\.\-]+)', driver.current_url)
                    if m: lat,lng = m.group(1),m.group(2)
                except: pass

                maps_url = driver.current_url
                email = ""
                if website and "google.com" not in website:
                    try:
                        r = requests.get(website, timeout=4, headers={"User-Agent":"Mozilla/5.0"})
                        emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', r.text)
                        email = [e for e in emails if not e.lower().endswith(('.png','.jpg','.svg'))][0] if emails else ""
                        r.close()
                    except: pass

                uid = hashlib.md5(f"{name}{phone}{address}".encode()).hexdigest()

                lead = {
                    "lead_id": uid, "business_name": name, "address": address,
                    "phone": phone, "website": website, "email": email,
                    "rating": rating, "review_count": reviews, "category": category,
                    "maps_url": maps_url, "business_hours": hours, "social_media": "",
                    "description": description, "latitude": lat, "longitude": lng,
                    "query": query, "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }

                leads.append(lead)
                processed.add(card_name)
                data_out(lead)
                log(f"✓ Lead {len(leads)}: {name} | {phone or 'no phone'} | {address or 'no address'}")

                # Clear CDP cache every 5 leads to free memory
                if len(leads) % 5 == 0:
                    try: driver.execute_cdp_cmd('Network.clearBrowserCache', {})
                    except: pass

            except Exception as e:
                log(f"Error on {card_name}: {e}")
                processed.add(card_name)

            finally:
                card_index += 1
                # Go back to list — try multiple methods
                back_done = False
                for sel in ["button[aria-label='Back']","button.hYBOP","button[jsaction*='back']"]:
                    try:
                        btn = driver.find_element(By.CSS_SELECTOR, sel)
                        if btn.is_displayed():
                            btn.click()
                            time.sleep(2.5)
                            back_done = True
                            break
                    except: continue
                if not back_done:
                    try: driver.execute_script("window.history.back()"); time.sleep(3)
                    except: pass

        log(f"Extraction done. {len(leads)} leads collected.")

        # SAVE — DB first, then Sheets
        if leads:
            try:
                database.save_to_db(leads)
                log(f"✓ Saved {len(leads)} leads to database")
            except Exception as e:
                log(f"DB error: {e}")

            for attempt in range(3):
                try:
                    success, msg = google_sheets.save_to_google_sheets(leads)
                    if success:
                        log(f"✓ Google Sheets synced: {msg}")
                        break
                    else:
                        log(f"Sheets attempt {attempt+1}: {msg}")
                        time.sleep(4)
                except Exception as e:
                    log(f"Sheets error {attempt+1}: {e}")
                    time.sleep(4)

            try:
                if not os.path.exists("data"): os.makedirs("data")
                pd.DataFrame(leads).to_csv("data/leads.csv", index=False)
                log("✓ CSV backup saved")
            except: pass
        else:
            log("WARNING: 0 leads extracted.")

        log(f"COMPLETE — {len(leads)} leads saved")

    except Exception as e:
        log(f"CRITICAL: {e}")
        log(traceback.format_exc())
    finally:
        try: driver.quit()
        except: pass
        kill_chrome()

if __name__ == "__main__":
    q = sys.argv[1] if len(sys.argv) > 1 else "Hotels Hyderabad"
    run_scraper(q)
