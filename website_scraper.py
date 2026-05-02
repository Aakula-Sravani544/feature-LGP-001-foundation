# Day 5 — Website Scraper: Data Enrichment Engine
# Extracts email, phone, social media, tech stack from business websites
# Uses aiohttp async engine with 20 concurrent connections
# Must extract email/social from 80%+ of reachable websites

import aiohttp
import asyncio
import re
import logging
from bs4 import BeautifulSoup
from typing import Dict, List, Optional
from email_validator import validate_email, EmailNotValidError
import phonenumbers

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 20 concurrent connections as per Day 5 spec
CONCURRENCY_LIMIT = 20
TIMEOUT_SECONDS = 8
MAX_RETRIES = 2

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9"
}

async def scrape_single_website(
    session: aiohttp.ClientSession,
    url: str,
    semaphore: asyncio.Semaphore
) -> Dict:
    """
    Scrape a single website for contact and tech details.
    Implements retry logic with MAX_RETRIES attempts.

    Args:
        session: aiohttp ClientSession
        url: website URL to scrape
        semaphore: limits concurrent connections to 20

    Returns:
        Dict with email, phone, social_media, tech_stack, contact_page_url
    """
    result = {
        "email": "",
        "phone": "",
        "social_media": {},
        "tech_stack": [],
        "contact_page_url": "",
        "meta_description": "",
        "about_content": ""
    }

    async with semaphore:
        for attempt in range(MAX_RETRIES + 1):
            try:
                async with session.get(
                    url,
                    headers=HEADERS,
                    timeout=aiohttp.ClientTimeout(total=TIMEOUT_SECONDS),
                    ssl=False,
                    allow_redirects=True
                ) as response:
                    if response.status >= 400:
                        return result
                    
                    html = await response.text(errors='ignore')
                    soup = BeautifulSoup(html, "html.parser")

                    # 1. Email — mailto links first, then regex
                    for a in soup.find_all("a", href=re.compile(r"^mailto:")):
                        raw = a["href"].replace("mailto:", "").split("?")[0].strip()
                        try:
                            valid = validate_email(raw)
                            result["email"] = valid.normalized
                            break
                        except EmailNotValidError:
                            continue

                    if not result["email"]:
                        email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
                        emails = re.findall(email_pattern, html)
                        for email in emails:
                            try:
                                valid = validate_email(email)
                                # Filter out common false positives
                                if not any(x in email.lower() for x in ['.png','.jpg','.gif','.woff','.svg','.css','.js','bootstrap','jquery']):
                                    result["email"] = valid.normalized
                                    break
                            except:
                                continue

                    # 2. Phone — tel: links first, then regex
                    for a in soup.find_all("a", href=re.compile(r"^tel:")):
                        raw = a["href"].replace("tel:", "").strip()
                        try:
                            parsed = phonenumbers.parse(raw, "IN")
                            if phonenumbers.is_valid_number(parsed):
                                result["phone"] = phonenumbers.format_number(
                                    parsed, phonenumbers.PhoneNumberFormat.E164
                                )
                                break
                        except:
                            continue

                    if not result["phone"]:
                        # Look for common Indian phone patterns
                        phone_matches = re.findall(r'[\+]?[0-9]{10,13}|[0-9]{4,5}[\s\-][0-9]{6,8}', html)
                        for p in phone_matches:
                            try:
                                parsed = phonenumbers.parse(p, "IN")
                                if phonenumbers.is_valid_number(parsed):
                                    result["phone"] = phonenumbers.format_number(
                                        parsed, phonenumbers.PhoneNumberFormat.E164
                                    )
                                    break
                            except:
                                continue

                    # 3. Social media links
                    social_patterns = {
                        "facebook": r'facebook\.com/[^\s\'"<>]+',
                        "instagram": r'instagram\.com/[^\s\'"<>]+',
                        "linkedin": r'linkedin\.com/(?:company|in)/[^\s\'"<>]+',
                        "twitter": r'twitter\.com/[^\s\'"<>]+|x\.com/[^\s\'"<>]+',
                        "youtube": r'youtube\.com/[^\s\'"<>]+'
                    }
                    for platform, pattern in social_patterns.items():
                        match = re.search(pattern, html)
                        if match:
                            result["social_media"][platform] = "https://" + match.group().split('"')[0].split("'")[0]

                    # 4. Meta description
                    meta = soup.find("meta", attrs={"name": "description"})
                    if meta:
                        result["meta_description"] = meta.get("content", "")[:300]

                    # 5. Tech stack detection
                    tech_signals = {
                        "WordPress": ["wp-content", "wp-includes", "wordpress"],
                        "Shopify": ["shopify.com", "cdn.shopify"],
                        "Wix": ["wix.com", "wixstatic"],
                        "Google Analytics": ["google-analytics.com", "gtag(", "UA-", "G-"],
                        "HubSpot": ["hubspot.com", "hs-scripts"],
                        "Zoho": ["zoho.com", "zohopublic"],
                        "React": ["react.min.js", "_react", "__NEXT_DATA__"],
                        "Bootstrap": ["bootstrap.min.css", "bootstrap.min.js"]
                    }
                    for tech, signals in tech_signals.items():
                        if any(s.lower() in html.lower() for s in signals):
                            result["tech_stack"].append(tech)

                    # 6. Contact page URL
                    for a in soup.find_all("a", href=True):
                        href = a.get("href", "").lower()
                        text = a.get_text().lower()
                        if "contact" in href or "contact" in text:
                            contact_url = a["href"]
                            if contact_url.startswith("http"):
                                result["contact_page_url"] = contact_url
                            elif contact_url.startswith("/"):
                                result["contact_page_url"] = url.rstrip("/") + contact_url
                            break

                    # 7. About page content (optional enrichment)
                    for a in soup.find_all("a", href=True):
                        href = a.get("href", "").lower()
                        if "about" in href:
                            about_url = a["href"]
                            if about_url.startswith("/"):
                                about_url = url.rstrip("/") + about_url
                            elif not about_url.startswith("http"):
                                about_url = url.rstrip("/") + "/" + about_url
                                
                            try:
                                async with session.get(
                                    about_url,
                                    headers=HEADERS,
                                    timeout=aiohttp.ClientTimeout(total=5),
                                    ssl=False
                                ) as about_resp:
                                    about_html = await about_resp.text(errors='ignore')
                                    about_soup = BeautifulSoup(about_html, "html.parser")
                                    body = about_soup.find("body")
                                    if body:
                                        result["about_content"] = body.get_text(strip=True)[:500]
                            except:
                                pass
                            break

                    return result

            except asyncio.TimeoutError:
                if attempt == MAX_RETRIES:
                    logger.debug(f"Timeout on {url} after {MAX_RETRIES} retries")
                await asyncio.sleep(1)
            except Exception as e:
                logger.debug(f"Error scraping {url}: {e}")
                if attempt < MAX_RETRIES:
                    await asyncio.sleep(1)

    return result

async def enrich_leads_batch(leads: List[Dict]) -> List[Dict]:
    """
    Enrich a batch of leads with website data.
    Runs 20 concurrent connections as per Day 5 spec.

    Args:
        leads: list of lead dicts with 'website' field

    Returns:
        Enriched leads with email, phone, social_media, tech_stack filled in
    """
    semaphore = asyncio.Semaphore(CONCURRENCY_LIMIT)
    connector = aiohttp.TCPConnector(limit=CONCURRENCY_LIMIT, ssl=False)

    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = []
        for lead in leads:
            url = lead.get("website", "")
            if url and url.startswith("http") and "google.com" not in url:
                tasks.append(scrape_single_website(session, url, semaphore))
            else:
                # Return empty result for invalid URLs
                async def empty_res(): return {}
                tasks.append(empty_res())

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for lead, result in zip(leads, results):
            if isinstance(result, dict) and result:
                # Fill missing data only
                if result.get("email") and not lead.get("email"):
                    lead["email"] = result["email"]
                if result.get("phone") and not lead.get("phone"):
                    lead["phone"] = result["phone"]
                if result.get("social_media"):
                    lead["social_media"] = str(result["social_media"])
                if result.get("tech_stack"):
                    lead["additional_data"] = str(result["tech_stack"])
                if result.get("meta_description") and not lead.get("description"):
                    lead["description"] = result["meta_description"]
                if result.get("contact_page_url"):
                    lead["contact_page_url"] = result.get("contact_page_url", "")
                if result.get("about_content"):
                    lead["about_info"] = result["about_content"]

    return leads

def run_website_enrichment(leads: List[Dict]) -> List[Dict]:
    """
    Synchronous wrapper to call async enrichment from scraper.py or app.py

    Args:
        leads: list of lead dicts

    Returns:
        Enriched leads list
    """
    if not leads:
        return []
        
    try:
        # Create a new event loop for the current thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(enrich_leads_batch(leads))
        finally:
            loop.close()
    except Exception as e:
        logger.error(f"Website enrichment failed: {e}")
        return leads
