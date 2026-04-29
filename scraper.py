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

import database
import google_sheets

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import tempfile

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
    tmp_dir = tempfile.mkdtemp()
    try:
        log("Launching Chrome...")
        options = webdriver.ChromeOptions()
        options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        
        # Memory Flags for 512MB RAM
        options.add_argument("--single-process")
        options.add_argument("--no-zygote")
        options.add_argument("--renderer-process-limit=1")
        options.add_argument("--aggressive-cache-discard")
        options.add_argument("--memory-pressure-off")
        options.add_argument("--js-flags=--max-old-space-size=256 --optimize-for-size --gc-interval=50")
        
        options.add_argument(f"--disk-cache-dir={tmp_dir}/cache")
        options.add_argument(f"--user-data-dir={tmp_dir}/data")
        options.add_argument("--window-size=1280,720")
        options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        
        prefs = {
            "profile.managed_default_content_settings.images": 2,
            "profile.managed_default_content_settings.stylesheets": 2,
            "profile.managed_default_content_settings.fonts": 2,
            "profile.default_content_setting_values.notifications": 2
        }
        options.add_experimental_option("prefs", prefs)
        
        render_path = "/opt/render/project/.render/chrome/opt/google/chrome/google-chrome"
        if os.path.exists(render_path):
            options.binary_location = render_path
            
        driver = webdriver.Chrome(options=options)
        driver.set_page_load_timeout(35)
        driver.set_script_timeout(35)
        return driver
    except Exception as e:
        log(f"Browser launch failed: {e}")
        return None

def extract_email(website):
    if not website or "google.com" in website:
        return ""
    try:
        r = requests.get(website, timeout=4, headers={"User-Agent": "Mozilla/5.0"})
        emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', r.text)
        filtered = [e for e in emails if not e.lower().endswith(('.png','.jpg','.jpeg','.gif','.svg','.webp'))]
        r.close()
        return filtered[0] if filtered else ""
    except: return ""

def collect_place_urls(driver, target=100):
    collected = {}
    stall = 0
    scroll_start = time.time()
    
    panel = None
    for sel in ["div[role='feed']", "div.m6QErb.DxyBCb", "div[aria-label*='Results']"]:
        try:
            el = driver.find_element(By.CSS_SELECTOR, sel)
            if el: panel = el; break
        except: continue

    while len(collected) < target and stall < 15 and (time.time() - scroll_start) < 180:
        cards = driver.find_elements(By.CSS_SELECTOR, "div.Nv2PK, div[role='article']")
        last_count = len(collected)
        
        for card in cards:
            try:
                name = ""
                for sel in ["div.qBF1Pd", ".fontHeadlineSmall", ".NrDZNb", ".lI9IFe"]:
                    try:
                        n = card.find_element(By.CSS_SELECTOR, sel).text.strip()
                        if n: name = n; break
                    except: continue

                if not name or name in collected: continue

                url = ""
                try:
                    anchors = card.find_elements(By.CSS_SELECTOR, "a")
                    for a in anchors:
                        href = a.get_attribute("href") or ""
                        if "maps/place" in href or "/maps/" in href:
                            url = href; break
                except: pass

                if not url: url = f"https://www.google.com/maps/search/{urllib.parse.quote_plus(name)}"

                collected[name] = url
            except: continue
            
        stall = 0 if len(collected) > last_count else stall + 1
        
        try: driver.execute_script("arguments[0].scrollTop += 1200", panel) if panel else driver.execute_script("window.scrollBy(0,1200)")
        except: driver.execute_script("window.scrollBy(0,1200)")
        time.sleep(2)
        log(f"Phase 1: Scrolled to {len(collected)} unique cards...")
        
    return collected

def extract_from_urls(driver, place_urls, query):
    leads = []
    
    for idx, (name, url) in enumerate(place_urls.items()):
        log(f"Extracting {idx+1}/{len(place_urls)}: {name}")
        try:
            for load_attempt in range(2):
                try:
                    driver.get(url)
                    time.sleep(3)
                    break
                except Exception as te:
                    if load_attempt == 0:
                        log(f"Timeout on {name}, retrying...")
                        driver.execute_script("window.stop();")
                        time.sleep(2)
                    else: raise te

            if "/search/" in driver.current_url or "search?" in driver.current_url:
                try:
                    first = WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.CSS_SELECTOR, "div.Nv2PK, div[role='article'] a")))
                    driver.execute_script("arguments[0].click()", first)
                    time.sleep(3)
                except: pass

            # Wait for detail panel
            loaded = False
            for sel in ["h1.DUwDvf", "h1.fontHeadlineLarge", "button[data-item-id='address']"]:
                try:
                    WebDriverWait(driver, 8).until(EC.presence_of_element_located((By.CSS_SELECTOR, sel)))
                    loaded = True; break
                except: continue

            if not loaded: log(f"Detail panel did not fully load for {name}, extracting partial...")

            def get_val(selectors, attr=None):
                for sel in selectors:
                    try:
                        el = driver.find_element(By.CSS_SELECTOR, sel)
                        val = el.get_attribute(attr) if attr else el.text
                        if val and val.strip(): return val.strip()
                    except: continue
                return ""

            biz_name = get_val(["h1.DUwDvf", "h1.fontHeadlineLarge"]) or name
            address = get_val(["button[data-item-id='address']", ".rogA2c .Io6YTe"]) or get_val(["button[data-item-id='address']"], "aria-label")
            phone = get_val(["button[data-item-id*='phone']", "button[aria-label*='hone']"]) or get_val(["button[data-item-id*='phone']"], "aria-label")
            if phone and phone.lower().startswith("phone:"): phone = phone[6:].strip()
            website = get_val(["a[data-item-id='authority']", "a[data-item-id='website']"], "href")
            rating = get_val(["span.ceNzR", "div.fontDisplayLarge"]) or get_val(["span.ceNzR"], "aria-label")
            reviews = get_val(["span.F7kY9c", "button.HH6Xqe", "span[aria-label*='review']"])
            if reviews: reviews = reviews.replace("(","").replace(")","").split()[0]
            category = get_val(["button.DkEaL", "button.D693id", "span.mgr77e", "div.skqShb"])
            hours = get_val(["div[data-item-id='oh']"], "aria-label")

            lat, lng = "", ""
            try:
                m = re.search(r'@([\d.\-]+),([\d.\-]+)', driver.current_url)
                if m: lat, lng = m.group(1), m.group(2)
            except: pass

            email = extract_email(website)
            uid = hashlib.md5(f"{biz_name}{phone}{address}".encode()).hexdigest()

            lead = {
                "lead_id": uid, "business_name": biz_name, "address": address,
                "phone": phone, "website": website, "email": email,
                "rating": rating, "review_count": reviews, "category": category,
                "maps_url": driver.current_url, "business_hours": hours, "social_media": "",
                "description": "", "latitude": lat, "longitude": lng,
                "query": query, "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }

            leads.append(lead)
            data_out(lead)
            log(f"✓ Lead {len(leads)}: {biz_name} | {phone or 'no phone'}")

            # RAM cleanup after every lead
            try: driver.execute_cdp_cmd('Network.clearBrowserCache', {})
            except: pass
            
            # Deep RAM flush every 10 leads
            if len(leads) % 10 == 0:
                driver.get("about:blank")
                time.sleep(2)

        except Exception as e:
            log(f"Skipping {name} due to error: {e}")
            continue

    return leads

def run_scraper(query, target_count=100):
    log("=== LeadPulse Pro — Starting extraction ===")
    
    driver = get_driver()
    if not driver:
        log("FATAL: Browser failed to launch")
        return

    place_urls = {}
    leads = []

    try:
        log("Opening Maps...")
        encoded = urllib.parse.quote_plus(query)
        driver.get(f"https://www.google.com/maps/search/{encoded}")
        time.sleep(6)

        for sel in ["button[aria-label='Accept all']", "button[aria-label='Agree']", "form[action*='consent'] button", ".VfPpkd-LgbsBe[aria-label*='Accept']"]:
            try: driver.find_element(By.CSS_SELECTOR, sel).click(); time.sleep(2); break
            except: continue

        if "consent" in driver.current_url:
            driver.get(f"https://www.google.com/maps/search/{encoded}")
            time.sleep(6)

        try: WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.Nv2PK, div[role='article']")))
        except: driver.refresh(); time.sleep(6)

        log("Phase 1: Collecting place URLs from card list...")
        place_urls = collect_place_urls(driver, target=target_count)
        
        if place_urls:
            log(f"Phase 2: Extracting details for {len(place_urls)} businesses...")
            leads = extract_from_urls(driver, place_urls, query)
        else:
            log("No URLs collected. Exiting.")

    except Exception as e:
        log(f"Critical error: {e}")
        log(traceback.format_exc())
    finally:
        try: driver.quit()
        except: pass
        kill_chrome()

    if not leads: return

    try:
        database.save_to_db(leads)
        log(f"✓ Saved {len(leads)} leads to local database")
    except Exception as e: log(f"DB error: {e}")

    for attempt in range(3):
        try:
            success, msg = google_sheets.save_to_google_sheets(leads)
            if success:
                log(f"✓ Google Sheets synced: {msg}")
                break
            else:
                log(f"Sheets attempt {attempt+1} failed: {msg}")
                time.sleep(4)
        except Exception as e:
            log(f"Sheets error attempt {attempt+1}: {e}")
            time.sleep(4)

    try:
        if not os.path.exists("data"): os.makedirs("data")
        pd.DataFrame(leads).to_csv("data/leads.csv", index=False)
        log("✓ CSV backup saved")
    except: pass

    log(f"=== COMPLETE — {len(leads)} leads extracted and saved ===")

if __name__ == "__main__":
    q = sys.argv[1] if len(sys.argv) > 1 else "Hotels Hyderabad"
    run_scraper(q)