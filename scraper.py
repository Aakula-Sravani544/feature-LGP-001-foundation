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
import random
import asyncio
import aiohttp
from fake_useragent import UserAgent

import database
import google_sheets
import validator

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
        time.sleep(1)
    except: pass

def get_driver():
    kill_chrome()
    tmp_dir = tempfile.mkdtemp()
    try:
        log("Launching Chrome with Fake User-Agent...")
        options = webdriver.ChromeOptions()
        options.page_load_strategy = 'eager'
        options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--disable-software-rasterizer")
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-infobars")
        options.add_argument("--disable-notifications")
        options.add_argument("--single-process")
        options.add_argument("--no-zygote")
        options.add_argument("--renderer-process-limit=1")
        options.add_argument("--aggressive-cache-discard")
        options.add_argument("--memory-pressure-off")
        options.add_argument("--disable-features=VizDisplayCompositor")
        options.add_argument("--disable-features=IsolateOrigins,site-per-process")
        options.add_argument("--force-color-profile=srgb")
        options.add_argument("--metrics-recording-only")
        options.add_argument("--mute-audio")
        
        options.add_argument(f"--disk-cache-dir={tmp_dir}/cache")
        options.add_argument(f"--user-data-dir={tmp_dir}/data")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--blink-settings=imagesEnabled=false")
        options.add_argument('--js-flags=--max-old-space-size=128')
        
        ua = UserAgent(os='windows', browsers=['chrome', 'edge'])
        random_ua = ua.random
        options.add_argument(f"user-agent={random_ua}")
        
        prefs = {
            "profile.managed_default_content_settings.images": 2,
            "profile.managed_default_content_settings.stylesheets": 2,
            "profile.managed_default_content_settings.fonts": 2,
            "profile.default_content_setting_values.notifications": 2
        }
        options.add_experimental_option("prefs", prefs)
        
        render_path = "/opt/render/project/.render/chrome/opt/google/chrome/google-chrome"
        docker_path = "/usr/bin/google-chrome"
        if os.path.exists(render_path):
            options.binary_location = render_path
        elif os.path.exists(docker_path):
            options.binary_location = docker_path
            
        driver = webdriver.Chrome(options=options)
        driver.set_page_load_timeout(20)
        driver.set_script_timeout(20)
        return driver
    except Exception as e:
        log(f"Browser launch failed: {e}")
        log(traceback.format_exc())
        return None

async def fetch_email_from_website(session, website):
    if not website or "google.com" in website:
        return ""
    try:
        async with session.get(website, timeout=5) as response:
            text = await response.text()
            emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text)
            filtered = [e for e in emails if not e.lower().endswith(('.png','.jpg','.jpeg','.gif','.svg','.webp'))]
            return filtered[0] if filtered else ""
    except: return ""

async def extract_emails_async(leads):
    ua = UserAgent()
    headers = {"User-Agent": ua.random}
    connector = aiohttp.TCPConnector(limit=20) # 20 parallel requests
    
    async with aiohttp.ClientSession(headers=headers, connector=connector) as session:
        tasks = []
        for lead in leads:
            tasks.append(fetch_email_from_website(session, lead.get('website', '')))
        
        results = await asyncio.gather(*tasks)
        
        for i, email in enumerate(results):
            if not leads[i].get('email'):
                leads[i]['email'] = email
                
    return leads

def collect_place_urls(driver, query, target=100):
    collected = {}
    stall = 0
    scroll_start = time.time()
    
    log(f"Phase 1: Searching for '{query}'...")
    encoded = urllib.parse.quote_plus(query)
    driver.get(f"https://www.google.com/maps/search/{encoded}")
    time.sleep(random.uniform(3, 5))

    for sel in ["button[aria-label='Accept all']", "button[aria-label='Agree']", "form[action*='consent'] button", ".VfPpkd-LgbsBe[aria-label*='Accept']"]:
        try: driver.find_element(By.CSS_SELECTOR, sel).click(); time.sleep(2); break
        except: continue

    if "consent" in driver.current_url:
        driver.get(f"https://www.google.com/maps/search/{encoded}")
        time.sleep(random.uniform(4, 6))

    try: WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.Nv2PK, div[role='article']")))
    except: driver.refresh(); time.sleep(random.uniform(4, 6))
    
    panel = None
    for sel in ["div[role='feed']", "div.m6QErb.DxyBCb", "div[aria-label*='Results']"]:
        try:
            el = driver.find_element(By.CSS_SELECTOR, sel)
            if el: panel = el; break
        except: continue

    while len(collected) < target and stall < 10 and (time.time() - scroll_start) < 120:
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
        time.sleep(random.uniform(1.5, 3))
        
    log(f"Phase 1: Found {len(collected)} items for '{query}'")
    return collected

def extract_from_urls(driver, place_urls, base_query, sub_region):
    leads = []
    
    for idx, (name, url) in enumerate(place_urls.items()):
        log(f"Extracting {idx+1}/{len(place_urls)}: {name}")
        try:
            try:
                driver.get(url)
            except Exception as te:
                log(f"Partial timeout on {name}, forcing extraction...")
                try: driver.execute_script("window.stop();")
                except: pass

            if "/search/" in driver.current_url or "search?" in driver.current_url:
                try:
                    first = WebDriverWait(driver, 3).until(EC.element_to_be_clickable((By.CSS_SELECTOR, "div.Nv2PK, div[role='article'] a")))
                    driver.execute_script("arguments[0].click()", first)
                except: pass

            loaded = False
            for sel in ["h1.DUwDvf", "h1.fontHeadlineLarge", "button[data-item-id='address']"]:
                try:
                    WebDriverWait(driver, 3).until(EC.presence_of_element_located((By.CSS_SELECTOR, sel)))
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
            description = get_val(["div.PYvS2b", "div.fontBodyMedium .Io6YTe", "div.iP2t7d"])

            socials = []
            try:
                links = driver.find_elements(By.CSS_SELECTOR, "a")
                for l in links:
                    href = l.get_attribute("href") or ""
                    if any(s in href for s in ["facebook.com", "instagram.com", "linkedin.com", "twitter.com", "x.com"]) and "share" not in href:
                        if href not in socials: socials.append(href)
            except: pass
            social_media = ", ".join(socials)

            lat, lng = "", ""
            try:
                m = re.search(r'@([\d.\-]+),([\d.\-]+)', driver.current_url)
                if m: lat, lng = m.group(1), m.group(2)
            except: pass

            uid = hashlib.md5(f"{biz_name}{phone}{address}".encode()).hexdigest()

            # Ensure all 19 fields exist as per requirements
            lead = {
                "lead_id": uid, "business_name": biz_name, "address": address,
                "phone": phone, "website": website, "email": "",
                "rating": rating, "review_count": reviews, "category": category,
                "maps_url": driver.current_url, "business_hours": hours, "social_media": social_media,
                "description": description, "latitude": lat, "longitude": lng,
                "query": base_query, "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "ai_analysis": "", "validation_status": "", "validation_notes": "", "sub_region": sub_region,
                "additional_data": ""
            }

            # Fill missing with empty string
            for k in lead:
                if lead[k] is None: lead[k] = ""

            leads.append(lead)

            # Deep RAM flush every 10 leads
            if len(leads) % 10 == 0:
                driver.get("about:blank")
                time.sleep(1)

        except Exception as e:
            log(f"Skipping {name} due to error: {e}")
            continue

    return leads

def generate_subregions(query):
    """
    If the user asks for 'Dentists in Hyderabad', we split it into subregions
    to guarantee we can bypass the 100-result limit per search query.
    """
    areas = ["North", "South", "East", "West", "Central", "Downtown", "Suburbs"]
    if " in " in query.lower():
        base, loc = re.split(r'\s+in\s+', query, flags=re.IGNORECASE, maxsplit=1)
        return [f"{base} in {area} {loc}" for area in areas] + [query]
    else:
        return [f"{query} {area}" for area in areas] + [query]

def run_scraper(base_query, target_count=100):
    log("=== LeadPulse Pro — Starting Guarantee Extraction ===")
    
    driver = get_driver()
    if not driver:
        log("FATAL: Browser failed to launch")
        return

    all_leads = {}
    subregions = generate_subregions(base_query)
    
    try:
        for sub_query in subregions:
            if len(all_leads) >= target_count:
                break
                
            log(f"--- Running Sub-Query: {sub_query} ---")
            place_urls = collect_place_urls(driver, sub_query, target=target_count - len(all_leads))
            
            if place_urls:
                batch_leads = extract_from_urls(driver, place_urls, base_query, sub_query)
                for lead in batch_leads:
                    if lead["lead_id"] not in all_leads:
                        all_leads[lead["lead_id"]] = lead
            
            log(f"Total Unique Leads so far: {len(all_leads)}/{target_count}")
            
    except Exception as e:
        log(f"Critical error during extraction: {e}")
        log(traceback.format_exc())
    finally:
        try: driver.quit()
        except: pass
        kill_chrome()

    if not all_leads: 
        log("No leads extracted.")
        return

    leads_list = list(all_leads.values())[:target_count]
    
    log("Phase 3: Async Email Extraction & Validation...")
    # Run Async Email Extractor
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    leads_list = asyncio.run(extract_emails_async(leads_list))
    
    for i in range(len(leads_list)):
        leads_list[i] = validator.validate_lead(leads_list[i])
        data_out(leads_list[i])

    try:
        database.save_to_db(leads_list)
        log(f"✓ Saved {len(leads_list)} leads to local database")
    except Exception as e: log(f"DB error: {e}")

    for attempt in range(3):
        try:
            success, msg = google_sheets.save_to_google_sheets(leads_list)
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
        pd.DataFrame(leads_list).to_csv("data/leads.csv", index=False)
        log("✓ CSV backup saved")
    except: pass

    log(f"=== COMPLETE — {len(leads_list)} leads extracted and saved ===")

if __name__ == "__main__":
    q = sys.argv[1] if len(sys.argv) > 1 else "Hotels Hyderabad"
    t_count = int(sys.argv[2]) if len(sys.argv) > 2 else 100
    run_scraper(q, target_count=t_count)