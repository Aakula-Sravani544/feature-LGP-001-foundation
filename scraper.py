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

def open_business_direct(driver, business_name, partial_address=""):
    """Open business detail page via direct search URL instead of clicking cards."""
    query = f"{business_name} {partial_address}".strip()
    encoded = urllib.parse.quote_plus(query)
    url = f"https://www.google.com/maps/search/{encoded}"
    driver.get(url)
    time.sleep(4)
    
    # Wait for either a single result detail page OR a list
    try:
        # If single result, detail panel loads directly
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, 
                "h1.DUwDvf, h1.fontHeadlineLarge, button[data-item-id='address']"))
        )
        return True
    except:
        # Multiple results shown — click the first one
        try:
            first_card = WebDriverWait(driver, 8).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "div.Nv2PK, div[role='article']"))
            )
            driver.execute_script("arguments[0].click()", first_card)
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 
                    "h1.DUwDvf, h1.fontHeadlineLarge"))
            )
            return True
        except:
            return False

def collect_cards_from_list(driver, panel, target=20):
    """Collect all visible card data without clicking anything."""
    seen_names = set()
    card_data = []
    scroll_start = time.time()
    stall_count = 0
    last_count = 0

    while len(card_data) < target and stall_count < 8 and (time.time() - scroll_start) < 90:
        cards = driver.find_elements(By.CSS_SELECTOR, "div.Nv2PK, div[role='article']")
        
        for card in cards:
            try:
                # Extract name from card
                name = ""
                for sel in ["div.qBF1Pd", ".fontHeadlineSmall", ".NrDZNb", 
                            "div[class*='fontBody'] span", ".lI9IFe"]:
                    try:
                        name = card.find_element(By.CSS_SELECTOR, sel).text.strip()
                        if name: break
                    except: continue
                
                if not name or name in seen_names: continue
                seen_names.add(name)

                # Extract rating from card
                rating = ""
                for sel in ["span.MW4etd", "span[aria-hidden='true']"]:
                    try:
                        rating = card.find_element(By.CSS_SELECTOR, sel).text.strip()
                        if rating: break
                    except: continue

                # Extract review count from card
                reviews = ""
                for sel in ["span.UY7F9", "span[aria-label*='review']"]:
                    try:
                        reviews = card.find_element(By.CSS_SELECTOR, sel).text.strip()
                        reviews = reviews.replace("(","").replace(")","").strip()
                        if reviews: break
                    except: continue

                # Extract category/type from card
                category = ""
                for sel in ["div.W4Efsd span.W4Efsd span", ".W4Efsd:first-child > span"]:
                    try:
                        texts = card.find_elements(By.CSS_SELECTOR, sel)
                        for t in texts:
                            val = t.text.strip()
                            if val and "·" not in val and len(val) > 2:
                                category = val
                                break
                        if category: break
                    except: continue

                # Extract partial address from card
                address_partial = ""
                for sel in [".W4Efsd .W4Efsd", "div.W4Efsd:last-child span"]:
                    try:
                        spans = card.find_elements(By.CSS_SELECTOR, sel)
                        for s in spans:
                            val = s.text.strip()
                            if val and ("·" in val or any(c.isdigit() for c in val)):
                                address_partial = val.replace("·","").strip()
                                break
                        if address_partial: break
                    except: continue

                card_data.append({
                    "name": name,
                    "rating": rating,
                    "reviews": reviews,
                    "category": category,
                    "address_partial": address_partial
                })
                log(f"Collected card: {name}")

            except: continue

        if len(card_data) == last_count:
            stall_count += 1
        else:
            stall_count = 0
        last_count = len(card_data)

        # Scroll down
        try:
            driver.execute_script("arguments[0].scrollTop += 1200", panel)
        except:
            driver.execute_script("window.scrollBy(0, 1200)")
        time.sleep(2.5)

    log(f"Phase 1 complete: {len(card_data)} cards collected")
    return card_data

def extract_full_details(driver, card_data, query):
    """For each card, open its detail page directly and extract all fields."""
    leads = []
    extract_start = time.time()

    for idx, card in enumerate(card_data):
        if time.time() - extract_start > 300:
            log("Extract timeout reached")
            break

        name = card["name"]
        log(f"Extracting details {idx+1}/{len(card_data)}: {name}")

        try:
            success = open_business_direct(driver, name, card.get("address_partial",""))
            if not success:
                log(f"Could not open detail page for {name}, saving partial data")

            def get_val(selectors, attr=None):
                for sel in selectors:
                    try:
                        el = driver.find_element(By.CSS_SELECTOR, sel)
                        val = el.get_attribute(attr) if attr else el.text
                        if val and val.strip(): return val.strip()
                    except: continue
                return ""

            # Full address
            address = get_val([
                "button[data-item-id='address']",
                "button[aria-label*='ddress']",
                "[data-item-id='address'] .Io6YTe"
            ])
            if not address:
                address = get_val(["button[data-item-id='address']"], "aria-label")
            if not address:
                address = card.get("address_partial", "")

            # Phone
            phone = get_val([
                "button[data-item-id*='phone']",
                "button[aria-label*='hone']",
                "a[href^='tel:']"
            ])
            if not phone:
                phone = get_val(["button[data-item-id*='phone']"], "aria-label")

            # Website
            website = get_val(["a[data-item-id='authority']", "a[data-item-id='website']"], "href")

            # Rating — use card data as fallback
            rating = get_val(["span.ceNzR", "div.fontDisplayLarge"]) or card.get("rating","")

            # Reviews — use card data as fallback
            reviews = get_val(["span.F7kY9c", "button.HH6Xqe"]) or card.get("reviews","")
            if reviews:
                reviews = reviews.replace("(","").replace(")","").split()[0]

            # Category — use card data as fallback
            category = get_val(["button.DkEaL","button.D693id","span.mgr77e"]) or card.get("category","")

            # Hours
            hours = get_val(["div[data-item-id='oh']"], "aria-label")

            # Description
            description = get_val(["div.PYvS2b", "div.fontBodyMedium .Io6YTe"])

            # Lat/Lng
            lat, lng = "", ""
            try:
                match = re.search(r'@([\d\.\-]+),([\d\.\-]+)', driver.current_url)
                if match: lat, lng = match.group(1), match.group(2)
            except: pass

            # Maps URL
            maps_url = driver.current_url

            # Email from website
            email = ""
            if website and "google.com" not in website:
                email = extract_email(website)

            import hashlib
            uid = hashlib.md5(f"{name}{phone}{address}".encode()).hexdigest()

            lead = {
                "lead_id": uid,
                "business_name": name,
                "address": address,
                "phone": phone,
                "website": website,
                "email": email,
                "rating": rating,
                "review_count": reviews,
                "category": category,
                "maps_url": maps_url,
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
            log(f"✓ Lead {len(leads)} saved: {name} | {phone} | {address}")
            
            # Periodically force GC
            if len(leads) > 0 and len(leads) % 10 == 0:
                try:
                    driver.execute_script("window.gc && window.gc()")
                    driver.execute_cdp_cmd('Network.clearBrowserCache', {})
                except: pass

        except Exception as e:
            log(f"Error extracting {name}: {e}")
            continue

    return leads

def save_leads(leads, query):
    if not leads:
        log("No leads to save.")
        return

    # Save to local DB first (always works)
    try:
        database.save_to_db(leads)
        log(f"✓ Saved {len(leads)} leads to local database")
    except Exception as e:
        log(f"DB save error: {e}")

    # Save to Google Sheets with retry
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

    # CSV backup
    try:
        if not os.path.exists("data"): os.makedirs("data")
        pd.DataFrame(leads).to_csv("data/leads.csv", index=False)
        log("✓ CSV backup saved")
    except: pass

    log(f"COMPLETE — {len(leads)} leads extracted and saved")

def run_scraper(query, target_count=20):
    driver = get_driver()
    if not driver:
        log("FATAL: Browser failed to launch")
        return

    try:
        # Load Google Maps
        log("Opening Maps...")
        encoded_query = urllib.parse.quote_plus(query)
        driver.get(f"https://www.google.com/maps/search/{encoded_query}")
        time.sleep(5)

        # Handle consent popup
        for sel in ["button[aria-label='Accept all']", "form[action*='consent'] button"]:
            try:
                driver.find_element(By.CSS_SELECTOR, sel).click()
                time.sleep(2)
                break
            except: continue

        # Wait for results
        log("Waiting for results to load...")
        try:
            WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div.Nv2PK, div[role='article']"))
            )
        except:
            log("Results did not load. Retrying...")
            driver.refresh()
            time.sleep(7)

        # Find scroll panel
        panel = None
        for sel in ["div[role='feed']", "div.m6QErb.DxyBCb", "div[aria-label*='Results']"]:
            try:
                el = driver.find_element(By.CSS_SELECTOR, sel)
                if el:
                    panel = el
                    log(f"Panel found: {sel}")
                    break
            except: continue

        # PHASE 1: Collect card names from list
        log("Phase 1: Collecting card names...")
        card_data = collect_cards_from_list(driver, panel, target=target_count)

        if not card_data:
            log("No cards collected. Exiting.")
            return

        # PHASE 2: Extract full details for each card
        log(f"Phase 2: Extracting details for {len(card_data)} businesses...")
        leads = extract_full_details(driver, card_data, query)

        # PHASE 3: Save everything
        save_leads(leads, query)

    except Exception as e:
        log(f"CRITICAL ERROR: {e}")
        import traceback
        log(traceback.format_exc())
    finally:
        try:
            driver.quit()
        except: pass
        kill_chrome()

if __name__ == "__main__":
    q = sys.argv[1] if len(sys.argv) > 1 else "Hotels Hyderabad"
    run_scraper(q)
