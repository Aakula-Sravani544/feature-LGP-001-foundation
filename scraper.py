import sys
import json
import time
import random
import re
import asyncio
import logging
from datetime import datetime
from typing import List, Dict, Any

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from driver_setup import get_driver, safe_get
from fallback_scraper import search_fallback
from validation import validate_lead, scrape_emails_from_website

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def get_full_structure() -> Dict[str, Any]:
    """Returns a fresh lead dictionary with default fields."""
    return {
        "lead_id": f"lp-{random.randint(100000, 999999)}",
        "name": "", "address": "", "phone": "", "email": "", "website": "",
        "rating": "", "reviews": "", "category": "", "google_maps_url": "",
        "description": "", "hours": "", "social_media": "", "additional_data": "",
        "scraped_date": datetime.now().strftime("%Y-%m-%d"),
        "ai_analysis": "N/A", "validation_status": "Pending",
        "validation_notes": "", "sub_region": ""
    }

async def process_lead_details(lead: Dict[str, Any]) -> Dict[str, Any]:
    """Enriches lead with email if website is found.

    Args:
        lead: The lead dictionary.

    Returns:
        The enriched lead dictionary.
    """
    if lead.get("website"):
        logger.info(f"Scanning website for emails: {lead['website']}")
        email = await scrape_emails_from_website(lead["website"])
        if email:
            lead["email"] = email
            logger.info(f"Found email: {email}")
    return lead

def scrape_maps(query: str, target_count: int = 5) -> List[Dict[str, Any]]:
    """Scrapes Google Maps by clicking into detail pages.

    Args:
        query: Search query string.
        target_count: Number of leads to collect.

    Returns:
        A list of validated lead dictionaries.
    """
    leads = []
    driver = get_driver()
    if not driver:
        return leads

    try:
        encoded = query.replace(" ", "+")
        url = f"https://www.google.com/maps/search/{encoded}"
        if not safe_get(driver, url):
            return leads

        # Wait for results
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "a.hfpxzc"))
        )

        cards = driver.find_elements(By.CSS_SELECTOR, "a.hfpxzc")
        logger.info(f"Found {len(cards)} listings. Processing detail pages...")

        for i, card in enumerate(cards[:target_count]):
            try:
                lead = get_full_structure()
                name = card.get_attribute("aria-label")
                lead["name"] = name if name else f"Business {i+1}"
                lead["google_maps_url"] = card.get_attribute("href")

                # --- STEP: CLICK INTO DETAIL PAGE ---
                try:
                    driver.execute_script("arguments[0].click();", card)
                    # Use a slightly longer wait for detail panel to load
                    time.sleep(3)
                    
                    # 1. Extract Phone from detail page
                    # Selector for phone: data-item-id="phone:..."
                    try:
                        phone_el = driver.find_element(By.CSS_SELECTOR, "button[data-item-id*='phone:']")
                        lead["phone"] = phone_el.get_attribute("data-item-id").split("phone:tel:")[1]
                    except:
                        # Fallback to general text search in sidebar
                        sidebar = driver.find_element(By.CSS_SELECTOR, "div.m67q60")
                        phone_match = re.search(r'\+?\d{1,4}[\s-]?)?\(?\d{3}\)?[\s-]?\d{3}[\s-]?\d{4}', sidebar.text)
                        if phone_match:
                            lead["phone"] = phone_match.group(0)

                    # 2. Extract Website
                    try:
                        web_el = driver.find_element(By.CSS_SELECTOR, "a[data-item-id='authority']")
                        lead["website"] = web_el.get_attribute("href")
                    except:
                        pass
                except Exception as click_e:
                    logger.warning(f"Failed to click/scrape detail page for {lead['name']}: {click_e}")

                # --- STEP: ASYNC EMAIL SCRAPING ---
                if lead["website"]:
                    lead = asyncio.run(process_lead_details(lead))

                # --- STEP: VALIDATION ---
                lead = validate_lead(lead)
                
                # Output immediately for Streamlit streaming
                print(f"DATA:{json.dumps(lead)}", flush=True)
                leads.append(lead)

                if len(leads) >= target_count:
                    break

            except Exception as e:
                logger.error(f"Error processing card {i}: {e}")
                continue

    except Exception as e:
        logger.error(f"Scraper encountered a critical error: {e}")
    finally:
        if driver:
            driver.quit()
    
    return leads

def main():
    if len(sys.argv) < 2:
        return
    
    query = sys.argv[1]
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    
    logger.info(f"Engine starting for query: {query} (Limit: {limit})")
    
    # Run primary scraper
    results = scrape_maps(query, target_count=limit)
    
    # Fallback if primary yielded zero (e.g. Chrome block)
    if not results:
        logger.warning("Primary scraper yielded zero results. Switching to fallback...")
        fallback_results = search_fallback(query)
        for lead in fallback_results[:limit]:
            lead = validate_lead(lead)
            print(f"DATA:{json.dumps(lead)}", flush=True)
            results.append(lead)
            
    logger.info(f"Task complete. Total leads collected: {len(results)}")

if __name__ == "__main__":
    main()