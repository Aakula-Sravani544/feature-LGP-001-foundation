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
        log("Cleaning up existing Chrome sessions...")
        if os.name == 'nt':
            os.system('taskkill /f /im chrome.exe /im chromedriver.exe /im google-chrome.exe >nul 2>&1')
        else:
            os.system('pkill -f chrome > /dev/null 2>&1')
            os.system('pkill -f chromedriver > /dev/null 2>&1')
        time.sleep(2)
    except: pass

def get_driver():
    kill_chrome()
    
    # Try Standard Selenium Headless FIRST (Most stable in subprocesses)
    try:
        log("Launching browser... (Headless Standard Selenium)")
        options = webdriver.ChromeOptions()
        options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--start-maximized")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36")
        
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        log("Headless Browser Ready")
        return driver
    except Exception as e:
        log(f"Headless failed: {str(e).splitlines()[0]}")

    # Fallback to UC if Headless fails
    try:
        import undetected_chromedriver as uc
        log("Attempting UC Browser as fallback...")
        options = webdriver.ChromeOptions()
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        driver = uc.Chrome(options=options, use_subprocess=True)
        return driver
    except Exception as e:
        log(f"UC failed: {str(e).splitlines()[0]}")
        
    return None

def parse_address(full_address):
    area, city, state, pincode = "N/A", "N/A", "N/A", "N/A"
    if not full_address or full_address == "N/A": return area, city, state, pincode
    
    try:
        pincode_match = re.search(r'(\d{6})', full_address)
        if pincode_match: pincode = pincode_match.group(1)
        
        parts = [p.strip() for p in full_address.split(',')]
        if len(parts) >= 2:
            city_state = parts[-2].split()
            if len(city_state) >= 2:
                city = city_state[0]
                state = city_state[1]
            else:
                city = parts[-2]
        if len(parts) >= 3:
            area = parts[-3]
    except: pass
    return area, city, state, pincode

def extract_lat_long(url):
    lat, lng = "N/A", "N/A"
    try:
        match = re.search(r'!3d([\d\.\-]+)!4d([\d\.\-]+)', url)
        if match: 
            lat, lng = match.group(1), match.group(2)
        else:
            match = re.search(r'@([\d\.\-]+),([\d\.\-]+)', url)
            if match:
                lat, lng = match.group(1), match.group(2)
    except: pass
    return lat, lng

def run_scraper(query, target_count=100):
    driver = get_driver()
    if not driver: return

    try:
        wait = WebDriverWait(driver, 20)
        log("Opening Maps...")
        
        encoded_query = urllib.parse.quote_plus(query)
        search_url = f"https://www.google.com/maps/search/{encoded_query}"
        driver.get(search_url)
        time.sleep(5)
        
        log("Searching...")

        # Wait for results panel
        panel = None
        for sel in ["div[role='feed']", "div.m6QErb.DxyBCb", "div[aria-label*='Results']"]:
            try:
                panel = driver.find_element(By.CSS_SELECTOR, sel)
                if panel: break
            except: continue
            
        if not panel:
            log("No results panel. Will use body scroll fallback.")
            try:
                panel = driver.find_element(By.TAG_NAME, "body")
            except: pass

        # Scroll logic
        last_count = 0
        no_new_count = 0
        start_time = time.time()
        
        if panel:
            # Max 10 mins
            while time.time() - start_time < 600:
                cards = driver.find_elements(By.CSS_SELECTOR, "div.Nv2PK, div[role='article'], a.hfpxzc")
                log(f"Loaded {len(cards)} cards...")
                
                if len(cards) >= target_count + 10: break
                
                if len(cards) == last_count:
                    no_new_count += 1
                    if no_new_count >= 10: 
                        log("No new cards after 10 tries.")
                        break
                    # Nudge scroll
                    driver.execute_script("arguments[0].scrollTop -= 200", panel)
                    time.sleep(1)
                else:
                    no_new_count = 0
                    
                last_count = len(cards)
                driver.execute_script("arguments[0].scrollTop = arguments[0].scrollHeight", panel)
                time.sleep(2.5)

        # Extraction logic
        final_cards = driver.find_elements(By.CSS_SELECTOR, "div.Nv2PK, div[role='article']")
        
        extracted_leads = []
        processed_keys = set()
        leads_extracted = 0
        
        for i in range(len(final_cards)):
            if leads_extracted >= target_count: break
            if time.time() - start_time > 600: break
            
            try:
                current_cards = driver.find_elements(By.CSS_SELECTOR, "div.Nv2PK, div[role='article']")
                if i >= len(current_cards): break
                card = current_cards[i]
                
                driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", card)
                time.sleep(0.5)
                try: card.click()
                except: driver.execute_script("arguments[0].click();", card)
                time.sleep(3.5)

                name = "N/A"
                try: name = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "h1.DUwDvf"))).text
                except: continue
                
                if not name or name == "N/A": continue
                
                address = "N/A"
                try: address = driver.find_element(By.CSS_SELECTOR, "button[data-item-id='address']").text
                except: pass
                
                phone = "N/A"
                try: phone = driver.find_element(By.CSS_SELECTOR, "button[data-item-id*='phone']").text
                except: pass
                
                # Duplicate check before heavier extraction
                unique_str = f"{name}_{phone}_{address}".lower()
                if unique_str in processed_keys: continue
                processed_keys.add(unique_str)
                
                lead_id = hashlib.md5(unique_str.encode()).hexdigest()
                
                category = "N/A"
                try: category = driver.find_element(By.CSS_SELECTOR, "button.D693id").text
                except: pass
                
                rating = "N/A"
                try: rating = driver.find_element(By.CSS_SELECTOR, "span.ceNzR").get_attribute("aria-label")
                except: pass
                
                reviews = "N/A"
                try: reviews = driver.find_element(By.CSS_SELECTOR, "span.F7kY9c").text
                except: pass
                
                area, city, state, pincode = parse_address(address)
                
                website = "N/A"
                try: website = driver.find_element(By.CSS_SELECTOR, "a[data-item-id='authority']").get_attribute("href")
                except: pass
                
                hours = "N/A"
                try: hours = driver.find_element(By.CSS_SELECTOR, "div[data-item-id='oh']").get_attribute("aria-label")
                except: pass
                
                current_url = driver.current_url
                lat, lng = extract_lat_long(current_url)
                status = "Active"
                
                lead_data = {
                    "lead_id": lead_id,
                    "business_name": name,
                    "category": category,
                    "rating": rating,
                    "reviews": reviews,
                    "phone": phone,
                    "website": website,
                    "full_address": address,
                    "city": city,
                    "state": state,
                    "pincode": pincode,
                    "latitude": lat,
                    "longitude": lng,
                    "hours": hours,
                    "status": status,
                    "query_used": query,
                    "scraped_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
                
                extracted_leads.append(lead_data)
                data_out(lead_data)
                leads_extracted += 1
                
            except Exception as e: 
                continue

        log(f"Extracted {leads_extracted} leads...")

        # Save to SQLite
        try:
            database.save_to_db(extracted_leads)
            log("Saved to DB...")
        except Exception as e:
            log(f"DB Error: {str(e)}")

        # Save to Google Sheets
        try:
            success, msg = google_sheets.upload_to_sheets(extracted_leads)
            if success:
                log("Uploaded to Google Sheets...")
            else:
                log(f"Sheets Upload Failed: {msg}")
        except Exception as e:
            log(f"Sheets Error: {str(e)}")

        # Save to CSV
        try:
            if not os.path.exists("data"): os.makedirs("data")
            csv_path = "data/leads.csv"
            df = pd.DataFrame(extracted_leads)
            if os.path.exists(csv_path):
                old_df = pd.read_csv(csv_path)
                combined = pd.concat([old_df, df]).drop_duplicates(subset=["lead_id"], keep='first')
                combined.to_csv(csv_path, index=False)
            else:
                df.to_csv(csv_path, index=False)
            log("Saved to CSV...")
        except Exception as e:
            log(f"CSV Error: {str(e)}")

        log("Completed Successfully")

    except Exception as e:
        log(f"CRITICAL ERROR: {str(e)}")
        log(traceback.format_exc())
    finally:
        if driver: driver.quit()

if __name__ == "__main__":
    q = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "Dentists Hyderabad"
    run_scraper(q)
