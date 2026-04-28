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
        # Extreme RAM Optimization for Render
        options.add_argument('--js-flags="--max-old-space-size=256"')
        options.add_argument("--window-size=1280,720")
        options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36")
        
        render_path = "/opt/render/project/.render/chrome/opt/google/chrome/google-chrome"
        docker_path = "/usr/bin/google-chrome"
        
        if os.path.exists(render_path):
            options.binary_location = render_path
        elif os.path.exists(docker_path):
            options.binary_location = docker_path
            
        driver = webdriver.Chrome(options=options)
        driver.set_page_load_timeout(30)
        return driver
    except Exception as e:
        log(f"Browser launch failed: {str(e)}")
        return None

def extract_email(website):
    if not website or website == "" or "google.com" in website:
        return ""
    try:
        response = requests.get(website, timeout=5, headers={"User-Agent": "Mozilla/5.0"})
        emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', response.text)
        filtered = [e for e in emails if not e.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp'))]
        return filtered[0] if filtered else ""
    except:
        return ""

def run_scraper(query, target_count=100):
    driver = get_driver()
    if not driver: return

    try:
        wait = WebDriverWait(driver, 15)
        log("Opening Maps...")
        encoded_query = urllib.parse.quote_plus(query)
        driver.get(f"https://www.google.com/maps/search/{encoded_query}")
        
        # --- NEW: Handle Cookie Consent / "Accept All" ---
        time.sleep(3)
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

        # Ensure we are on the search page after potential redirect
        if "consent" in driver.current_url:
            log("Still on consent page, retrying search...")
            driver.get(f"https://www.google.com/maps/search/{encoded_query}")
            time.sleep(5)

        log("Waiting for results to load...")
        try:
            # Wait until at least one card is present
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.Nv2PK, div[role='article']")))
        except:
            log("Timeout waiting for cards. Retrying page load...")
            driver.refresh()
            time.sleep(7)

        log("Collecting result cards...")
        last_count = 0
        attempts = 0
        
        panel = None
        # Robust list of selectors for the results pane
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
            
        while attempts < 35: # Even more attempts for 100+ leads
            cards = driver.find_elements(By.CSS_SELECTOR, "div.Nv2PK, div[role='article']")
            log(f"Found {len(cards)} leads so far...")
            
            if len(cards) >= target_count: 
                log(f"Target reached ({len(cards)}/{target_count}). Moving to extraction.")
                break
            
            if len(cards) == last_count:
                attempts += 1
                # Method 1: JS Scroll
                driver.execute_script("arguments[0].scrollTop = arguments[0].scrollHeight", panel if panel else driver.execute_script("return document.body"))
                time.sleep(1)
                # Method 2: Keyboard Nudge (very reliable)
                try:
                    if panel:
                        panel.send_keys(Keys.PAGE_DOWN)
                        panel.send_keys(Keys.END)
                except: pass
                time.sleep(2)
            else:
                attempts = 0
                
            last_count = len(cards)
            driver.execute_script("arguments[0].scrollTop = arguments[0].scrollHeight", panel if panel else driver.execute_script("return document.body"))
            time.sleep(2)

        final_cards = driver.find_elements(By.CSS_SELECTOR, "div.Nv2PK, div[role='article']")
        log(f"Final collection: {len(final_cards)} cards. Extracting details...")
        
        leads = []
        for i in range(len(final_cards)):
            if len(leads) >= target_count: break
            try:
                log(f"Processing lead {i+1} of {len(final_cards)}...")
                current_cards = driver.find_elements(By.CSS_SELECTOR, "div.Nv2PK, div[role='article']")
                if i >= len(current_cards): break
                card = current_cards[i]
                
                driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", card)
                time.sleep(0.5)
                try: card.click()
                except: driver.execute_script("arguments[0].click()", card)
                time.sleep(2.5) # Turbo speed: reduced from 4s

                def get_val(selectors, attr=None):
                    for sel in selectors:
                        try:
                            el = driver.find_element(By.CSS_SELECTOR, sel)
                            val = el.get_attribute(attr) if attr else el.text
                            if val and val.strip(): return val.strip()
                        except: continue
                    return ""

                name = get_val(["h1.DUwDvf", "div.x3AX1-Lf971b-p9v7id-suZ9lb"])
                if not name: continue
                
                address = get_val(["button[data-item-id='address']", "div.Io6YTe.fontBodyMedium.kR997c"])
                phone = get_val(["button[data-item-id*='phone']", "div[data-item-id*='phone'] .Io6YTe"])
                website = get_val(["a[data-item-id='authority']", "div[data-item-id='authority'] .Io6YTe"], "href")
                category = get_val(["button.D693id", "span.mgr77e", "div.fontBodyMedium .sk06S"])
                rating = get_val(["span.ceNzR", "div.fontDisplayLarge"], "aria-label")
                reviews = get_val(["span.F7kY9c", "button.HH6Xqe", "span[aria-label*='reviews']"])
                hours = get_val(["div[data-item-id='oh']", "table.e07dbf"], "aria-label")
                description = get_val(["div.PYvS2b", "div.fontBodyMedium.kR997c .Io6YTe"])
                
                # Clean reviews string
                if reviews:
                    reviews = reviews.replace("(", "").replace(")", "").split()[0]

                # Lat/Long
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
                
            except Exception as e: continue

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
        if driver: driver.quit()

if __name__ == "__main__":
    q = sys.argv[1] if len(sys.argv) > 1 else "Hotels Hyderabad"
    run_scraper(q)
