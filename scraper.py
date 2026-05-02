import sys
import json
import time
import random
import re
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional

import requests
from bs4 import BeautifulSoup
from email_validator import validate_email
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

from driver_setup import get_driver, safe_get
from fallback_scraper import search_fallback
from validation import validate_lead

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def extract_email_sync(url: str) -> str:
    """Synchronously scrapes a website for email addresses."""
    if not url or not url.startswith("http"):
        return ""
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, timeout=8, headers=headers)
        soup = BeautifulSoup(resp.text, "html.parser")
        for a in soup.find_all("a", href=re.compile(r"^mailto:")):
            email = a["href"].replace("mailto:", "").split("?")[0].strip()
            try:
                validate_email(email)
                return email
            except:
                continue
        for email in re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', resp.text):
            try:
                validate_email(email)
                return email
            except:
                continue
    except Exception as e:
        logger.debug(f"Email sync extraction failed for {url}: {e}")
    return ""

def get_full_structure() -> Dict[str, Any]:
    """Returns a standardized lead dictionary."""
    return {
        "lead_id": f"lp-{random.randint(100000, 999999)}",
        "name": "", "address": "", "phone": "", "email": "", "website": "",
        "rating": "", "reviews": "", "category": "", "google_maps_url": "",
        "description": "", "hours": "", "social_media": "", "additional_data": "",
        "scraped_date": datetime.now().strftime("%Y-%m-%d"),
        "ai_analysis": "N/A", "validation_status": "Pending",
        "validation_notes": "", "sub_region": ""
    }

def scrape_maps_deep(query: str, target_count: int = 5) -> List[Dict[str, Any]]:
    """Deep scraper that clicks into each listing detail panel."""
    leads = []
    driver = get_driver()
    if not driver:
        return leads

    try:
        encoded = query.replace(" ", "+")
        url = f"https://www.google.com/maps/search/{encoded}"
        if not safe_get(driver, url):
            return leads

        # Wait for search results panel to load
        try:
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "a.hfpxzc"))
            )
        except TimeoutException:
            logger.error("Timeout waiting for search results.")
            return leads

        # Scroll a bit to ensure elements are present
        driver.execute_script("window.scrollBy(0, 500);")
        time.sleep(2)

        cards = driver.find_elements(By.CSS_SELECTOR, "a.hfpxzc")
        logger.info(f"Found {len(cards)} results. Starting deep extraction...")

        for i, card in enumerate(cards[:target_count]):
            try:
                lead = get_full_structure()
                lead["name"] = card.get_attribute("aria-label") or f"Lead {i+1}"
                lead["google_maps_url"] = card.get_attribute("href")

                # Step 1: Click the listing to open detail panel
                logger.info(f"Opening details for: {lead['name']}")
                driver.execute_script("arguments[0].click();", card)
                
                # Step 2: Wait for detail panel and extract (FIX 1)
                try:
                    # Wait for sidebar detail content (FIX 1)
                    WebDriverWait(driver, 12).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "h1.DUwDvf, h1[class*='fontHeadlineLarge']"))
                    )
                    time.sleep(1.5)
                    
                    # Phone (FIX 2)
                    try:
                        phone_el = driver.find_element(By.CSS_SELECTOR, "button[data-item-id^='phone:']")
                        raw = phone_el.get_attribute("data-item-id")
                        lead["phone"] = raw.replace("phone:", "").strip()
                    except NoSuchElementException:
                        try:
                            # Alternative: look for aria-label containing Phone
                            phone_alt = driver.find_element(By.XPATH, "//*[contains(@aria-label, 'Phone')]")
                            lead["phone"] = phone_alt.text
                        except: pass

                    # Website
                    try:
                        web_el = driver.find_element(By.CSS_SELECTOR, "a[data-item-id='authority']")
                        lead["website"] = web_el.get_attribute("href")
                    except NoSuchElementException:
                        try:
                            web_alt = driver.find_element(By.XPATH, "//*[contains(@aria-label, 'Website')]")
                            lead["website"] = web_alt.get_attribute("href")
                        except: pass

                    # Address
                    try:
                        addr_el = driver.find_element(By.CSS_SELECTOR, "button[data-item-id='address']")
                        lead["address"] = addr_el.text
                    except: pass

                    # Rating & Reviews
                    try:
                        rating_el = driver.find_element(By.CSS_SELECTOR, "span[aria-label*='stars']")
                        lead["rating"] = rating_el.get_attribute("aria-label").split()[0]
                        review_el = driver.find_element(By.CSS_SELECTOR, "span[aria-label*='reviews']")
                        lead["reviews"] = re.sub(r'\D', '', review_el.get_attribute("aria-label"))
                    except: pass

                    # Category
                    try:
                        cat_el = driver.find_element(By.CSS_SELECTOR, "button[jsaction*='category']")
                        lead["category"] = cat_el.text
                    except: pass

                except TimeoutException:
                    logger.warning(f"Timeout loading details for {lead['name']}")

                # Step 3: Sync Website Scraper for email (FIX 3)
                if lead.get("website"):
                    lead["email"] = extract_email_sync(lead["website"])

                # Step 4: Validation (Day 4)
                lead = validate_lead(lead)
                
                # Output for real-time Streamlit updates
                print(f"DATA:{json.dumps(lead)}", flush=True)
                leads.append(lead)

                # Step 4: Add back button after each listing click (FIX 4)
                try:
                    back_btn = driver.find_element(By.CSS_SELECTOR, "button[aria-label='Back']")
                    back_btn.click()
                    time.sleep(1.5)
                    cards = driver.find_elements(By.CSS_SELECTOR, "a.hfpxzc")
                except Exception:
                    driver.back()
                    time.sleep(2)

                # Delay between listing clicks (Requirement: random 2-4s)
                time.sleep(random.uniform(2, 4))
                
                if len(leads) >= target_count:
                    break

            except Exception as e:
                logger.error(f"Error processing {lead.get('name', 'Unknown')}: {e}")
                continue

    except Exception as e:
        logger.error(f"Fatal error in Deep Scraper: {e}")
    finally:
        if driver:
            driver.quit()

    return leads

def main():
    if len(sys.argv) < 2: return
    query = sys.argv[1]
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    
    logger.info(f"Starting Deep Generation for: {query} (Target: {limit})")
    
    # Run Deep Scraper
    results = scrape_maps_deep(query, target_count=limit)
    
    # Fallback if primary yields 0
    if not results:
        logger.warning("Deep scraper yielded 0. Switching to Emergency Fallback...")
        fallback = search_fallback(query)
        for l in fallback[:limit]:
            l = validate_lead(l)
            print(f"DATA:{json.dumps(l)}", flush=True)
            results.append(l)

    logger.info(f"Scraping complete. Total: {len(results)} leads.")

if __name__ == "__main__":
    main()