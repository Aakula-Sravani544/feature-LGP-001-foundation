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
    except:
        pass

def get_driver():
    kill_chrome()
    # Each batch gets a fresh /tmp dir so Chrome doesn't choke on stale locks
    import tempfile
    tmp_dir = tempfile.mkdtemp()
    try:
        log("Launching Browser...")
        options = webdriver.ChromeOptions()
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
        options.add_argument("--window-size=1280,720")
        options.add_argument("--blink-settings=imagesEnabled=false")
        options.add_argument(f"--disk-cache-dir={tmp_dir}/cache")
        options.add_argument(f"--user-data-dir={tmp_dir}/data")
        options.add_argument('--js-flags=--max-old-space-size=128')
        options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36")

        prefs = {
            "profile.managed_default_content_settings.images": 2,
            "profile.managed_default_content_settings.stylesheets": 2,
            "profile.managed_default_content_settings.fonts": 2,
            "profile.default_content_setting_values.notifications": 2,
        }
        options.add_experimental_option("prefs", prefs)

        render_path = "/opt/render/project/.render/chrome/opt/google/chrome/google-chrome"
        docker_path = "/usr/bin/google-chrome"
        if os.path.exists(render_path):
            options.binary_location = render_path
        elif os.path.exists(docker_path):
            options.binary_location = docker_path

        driver = webdriver.Chrome(options=options)
        driver.set_page_load_timeout(45)
        driver.set_script_timeout(45)
        return driver
    except Exception as e:
        log(f"Browser launch failed: {e}")
        log(traceback.format_exc())
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
    except:
        return ""


# ─────────────────────────────────────────────
# PHASE 1 — Scroll the list and grab place URLs
# ─────────────────────────────────────────────
def collect_place_urls(driver, panel, target=20):
    """
    Scroll the search-results panel and harvest the direct Maps URL
    from each card's <a> tag.  Never clicks a card — zero DOM disruption.
    Returns  { business_name: url }
    """
    collected = {}
    stall = 0
    last_count = 0
    scroll_start = time.time()

    while len(collected) < target and stall < 20 and (time.time() - scroll_start) < 180:
        cards = driver.find_elements(By.CSS_SELECTOR, "div.Nv2PK, div[role='article']")

        for card in cards:
            try:
                # ── name ──────────────────────────────────────────────
                name = ""
                for sel in ["div.qBF1Pd", ".fontHeadlineSmall", ".NrDZNb",
                            ".lI9IFe", "div[class*='fontBody'] span"]:
                    try:
                        name = card.find_element(By.CSS_SELECTOR, sel).text.strip()
                        if name:
                            break
                    except:
                        continue

                if not name or name in collected:
                    continue

                # ── direct Maps URL from the card's <a> ───────────────
                url = ""
                try:
                    anchors = card.find_elements(By.CSS_SELECTOR, "a")
                    for a in anchors:
                        href = a.get_attribute("href") or ""
                        if "maps/place" in href or ("/maps/" in href and "@" in href):
                            url = href
                            break
                except:
                    pass

                # fallback: build a search URL
                if not url:
                    url = f"https://www.google.com/maps/search/{urllib.parse.quote_plus(name)}"

                collected[name] = url
                log(f"Collected card: {name}")

            except:
                continue

        stall = 0 if len(collected) > last_count else stall + 1
        last_count = len(collected)

        try:
            if panel:
                driver.execute_script("arguments[0].scrollTop += 1200", panel)
            else:
                driver.execute_script("window.scrollBy(0, 1200)")
        except:
            driver.execute_script("window.scrollBy(0, 1200)")
        time.sleep(2.5)

    log(f"Phase 1 complete — {len(collected)} place URLs collected")
    return collected


# ─────────────────────────────────────────────
# PHASE 2 — Visit each URL in batches of 5
# Each batch gets a FRESH browser → max ~150 MB RAM at any moment
# ─────────────────────────────────────────────
def extract_from_urls(place_urls, query):
    leads = []
    items = list(place_urls.items())
    BATCH = 3  # 3 per batch = safer on Render 512MB

    for batch_start in range(0, len(items), BATCH):
        batch = items[batch_start: batch_start + BATCH]
        log(f"=== Batch {batch_start//BATCH + 1}: leads {batch_start+1}–{batch_start+len(batch)} ===")

        driver = get_driver()
        if not driver:
            log("Browser failed for this batch — skipping")
            continue

        try:
            for name, url in batch:
                log(f"Opening: {name}")
                try:
                    # Try loading URL, retry once on timeout
                    for load_attempt in range(2):
                        try:
                            driver.get(url)
                            time.sleep(5)
                            break
                        except Exception as te:
                            if load_attempt == 0:
                                log(f"Load timeout for {name}, retrying...")
                                time.sleep(3)
                            else:
                                log(f"Failed to load {name} after retry, skipping")
                                raise

                    # If we landed on a search-results page, click the first card
                    if "/search/" in driver.current_url or "search?" in driver.current_url:
                        try:
                            first = WebDriverWait(driver, 10).until(
                                EC.element_to_be_clickable(
                                    (By.CSS_SELECTOR, "div.Nv2PK, div[role='article']")))
                            driver.execute_script("arguments[0].click()", first)
                            time.sleep(4)
                        except:
                            log(f"Could not open first result for {name}")

                    # Wait for the detail panel
                    detail_loaded = False
                    for sel in ["h1.DUwDvf", "h1.fontHeadlineLarge",
                                "h1[class*='fontHeadline']",
                                "button[data-item-id='address']",
                                "[data-item-id*='phone']"]:
                        try:
                            WebDriverWait(driver, 12).until(
                                EC.presence_of_element_located((By.CSS_SELECTOR, sel)))
                            detail_loaded = True
                            break
                        except:
                            continue

                    if not detail_loaded:
                        log(f"Detail panel did not load for {name} — saving partial data")

                    time.sleep(2)

                    # ── field extractor ────────────────────────────────
                    def get_val(selectors, attr=None):
                        for sel in selectors:
                            try:
                                el = driver.find_element(By.CSS_SELECTOR, sel)
                                val = el.get_attribute(attr) if attr else el.text
                                if val and val.strip():
                                    return val.strip()
                            except:
                                continue
                        return ""

                    biz_name = get_val([
                        "h1.DUwDvf", "h1.fontHeadlineLarge",
                        "h1[class*='fontHeadline']"
                    ]) or name

                    address = get_val([
                        "button[data-item-id='address']",
                        "[data-item-id='address'] .Io6YTe",
                        ".rogA2c .Io6YTe"
                    ])
                    if not address:
                        address = get_val(["button[data-item-id='address']"], "aria-label")

                    phone = get_val([
                        "button[data-item-id*='phone']",
                        "a[href^='tel:']",
                        "button[aria-label*='hone']"
                    ])
                    if not phone:
                        phone = get_val(["button[data-item-id*='phone']"], "aria-label")
                    if phone and phone.lower().startswith("phone:"):
                        phone = phone[6:].strip()

                    website = get_val([
                        "a[data-item-id='authority']",
                        "a[data-item-id='website']"
                    ], "href")

                    rating = get_val(["span.ceNzR", "div.fontDisplayLarge"])
                    if not rating:
                        rating = get_val(["span.ceNzR"], "aria-label")

                    reviews = get_val(["span.F7kY9c", "button.HH6Xqe",
                                       "span[aria-label*='review']"])
                    if reviews:
                        reviews = reviews.replace("(","").replace(")","").split()[0]

                    category = get_val([
                        "button.DkEaL", "button.D693id",
                        "span.mgr77e", "div.skqShb"
                    ])

                    hours = get_val(["div[data-item-id='oh']", "table.y0skZc"], "aria-label")
                    description = get_val(["div.PYvS2b", "div.fontBodyMedium .Io6YTe",
                                           "div.iP2t7d"])

                    lat, lng = "", ""
                    try:
                        m = re.search(r'@([\d.\-]+),([\d.\-]+)', driver.current_url)
                        if m:
                            lat, lng = m.group(1), m.group(2)
                    except:
                        pass

                    email = extract_email(website)

                    uid = hashlib.md5(f"{biz_name}{phone}{address}".encode()).hexdigest()

                    lead = {
                        "lead_id":       uid,
                        "business_name": biz_name,
                        "address":       address,
                        "phone":         phone,
                        "website":       website,
                        "email":         email,
                        "rating":        rating,
                        "review_count":  reviews,
                        "category":      category,
                        "maps_url":      driver.current_url,
                        "business_hours":hours,
                        "social_media":  "",
                        "description":   description,
                        "latitude":      lat,
                        "longitude":     lng,
                        "query":         query,
                        "timestamp":     datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    }

                    leads.append(lead)
                    data_out(lead)
                    log(f"✓ Lead {len(leads)}: {biz_name} | {phone or 'no phone'} | {address or 'no addr'}")

                    # Free browser cache every lead
                    try:
                        driver.execute_cdp_cmd('Network.clearBrowserCache', {})
                    except:
                        pass

                except Exception as e:
                    log(f"Error on {name}: {e}")
                    continue

        finally:
            try:
                driver.quit()
            except:
                pass
            kill_chrome()
            log(f"Batch done — total leads so far: {len(leads)}")
            time.sleep(3)   # let OS reclaim RAM before next batch

    return leads


# ─────────────────────────────────────────────
# MAIN ENTRY POINT
# ─────────────────────────────────────────────
def run_scraper(query, target_count=100):
    log("=== LeadPulse Pro — Starting extraction ===")
    place_urls = {}

    # ── Phase 1: scroll the list, collect URLs (one browser, then quit) ──
    driver = get_driver()
    if not driver:
        log("FATAL: Browser failed to launch")
        return

    try:
        log("Opening Maps...")
        encoded = urllib.parse.quote_plus(query)
        driver.get(f"https://www.google.com/maps/search/{encoded}")
        time.sleep(6)

        # Dismiss consent popup
        for sel in ["button[aria-label='Accept all']", "button[aria-label='Agree']",
                    "form[action*='consent'] button",
                    ".VfPpkd-LgbsBe[aria-label*='Accept']"]:
            try:
                driver.find_element(By.CSS_SELECTOR, sel).click()
                time.sleep(2)
                break
            except:
                continue

        # Retry if still on consent page
        if "consent" in driver.current_url:
            driver.get(f"https://www.google.com/maps/search/{encoded}")
            time.sleep(6)

        log("Waiting for results...")
        try:
            WebDriverWait(driver, 25).until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, "div.Nv2PK, div[role='article']")))
        except:
            log("Timeout — refreshing...")
            driver.refresh()
            time.sleep(8)

        # Find scroll panel
        panel = None
        for sel in ["div[role='feed']", "div.m6QErb.DxyBCb",
                    "div[aria-label*='Results']", "div.m6QErb"]:
            try:
                el = driver.find_element(By.CSS_SELECTOR, sel)
                if el:
                    panel = el
                    log(f"Panel found: {sel}")
                    break
            except:
                continue

        log("Phase 1: Collecting place URLs from card list...")
        place_urls = collect_place_urls(driver, panel, target=target_count)


    except Exception as e:
        log(f"Phase 1 error: {e}")
        log(traceback.format_exc())
    finally:
        try:
            driver.quit()
        except:
            pass
        kill_chrome()
        time.sleep(3)

    if not place_urls:
        log("No URLs collected — nothing to extract. Exiting.")
        return

    # ── Phase 2: visit each URL in batches of 5 ──────────────────────────
    log(f"Phase 2: Extracting details for {len(place_urls)} businesses (batches of 5)...")
    leads = extract_from_urls(place_urls, query)

    # ── Save results ──────────────────────────────────────────────────────
    if not leads:
        log("WARNING: 0 leads extracted.")
        return

    # Local DB first (always safe)
    try:
        database.save_to_db(leads)
        log(f"✓ Saved {len(leads)} leads to local database")
    except Exception as e:
        log(f"DB error: {e}")

    # Google Sheets with 3 retries
    sheets_ok = False
    for attempt in range(3):
        try:
            success, msg = google_sheets.save_to_google_sheets(leads)
            if success:
                log(f"✓ Google Sheets synced: {msg}")
                sheets_ok = True
                break
            else:
                log(f"Sheets attempt {attempt+1} failed: {msg}")
                time.sleep(4)
        except Exception as e:
            log(f"Sheets error attempt {attempt+1}: {e}")
            time.sleep(4)

    if not sheets_ok:
        log("Google Sheets sync failed — leads are safe in local DB and CSV")

    # CSV backup
    try:
        if not os.path.exists("data"):
            os.makedirs("data")
        pd.DataFrame(leads).to_csv("data/leads.csv", index=False)
        log("✓ CSV backup saved to data/leads.csv")
    except:
        pass

    log(f"=== COMPLETE — {len(leads)} leads extracted and saved ===")


if __name__ == "__main__":
    q = sys.argv[1] if len(sys.argv) > 1 else "Hotels Hyderabad"
    run_scraper(q)