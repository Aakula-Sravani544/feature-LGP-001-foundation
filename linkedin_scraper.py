"""
Day 10 — LinkedIn Scraper
Collects 25+ LinkedIn profiles using multiple job title queries
Uses Serper API as primary source
Collects 10 fields per profile
Deduplicates against Maps leads by company name
"""
import os, re, json, time, logging, hashlib, requests
from datetime import datetime
from typing import List, Dict

logger = logging.getLogger(__name__)
SERPER_API_KEY = os.environ.get("SERPER_API_KEY", "")
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}


def get_linkedin_structure() -> Dict:
    """Returns LinkedIn lead using same column names as Google Sheets."""
    return {
        "lead_id": "",
        "name": "",           # full_name goes here
        "address": "",        # location goes here
        "phone": "",          # phone if available
        "email": "",          # email_guessed goes here
        "website": "",        # linkedin_url goes here
        "rating": "",
        "reviews": "",
        "category": "LinkedIn Contact",
        "google_maps_url": "",
        "description": "",    # job_title + company_name goes here
        "hours": "",
        "social_media": "",
        "additional_data": "", # company_size + industry goes here
        "scraped_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "ai_analysis": "N/A",
        "validation_status": "Pending",
        "validation_notes": "",
        "sub_region": "",
        # LinkedIn specific extra fields stored in description/additional_data
        "source": "LinkedIn",
        "company_name": "",
        "cross_linked_to": ""
    }


def guess_email(full_name: str, company: str) -> str:
    try:
        parts = full_name.lower().split()
        domain = company.lower().replace(" ", "").replace(",", "") + ".com"
        if len(parts) >= 2:
            return f"{parts[0]}.{parts[-1]}@{domain}"
    except: pass
    return ""


def dedup_against_maps(profiles: List[Dict], maps_leads: List[Dict]) -> List[Dict]:
    maps_cos = {l.get("name","").lower(): l.get("lead_id","") for l in maps_leads}
    seen = set()
    result = []
    for p in profiles:
        lid = p.get("lead_id","")
        if lid in seen: continue
        seen.add(lid)
        
        co = p.get("company_name", "").lower()
            
        for mc, mid in maps_cos.items():
            if co and (co in mc or mc in co):
                p["cross_linked_to"] = mid
                # Also update inside additional_data for completeness
                try:
                    add_data = json.loads(p.get("additional_data", "{}"))
                    add_data["cross_linked_to"] = mid
                    p["additional_data"] = json.dumps(add_data)
                except:
                    pass
                break
        result.append(p)
    return result


def scrape_linkedin(
    keyword: str,
    location: str,
    maps_leads: List[Dict] = None,
    limit: int = 25
) -> List[Dict]:
    all_profiles = []
    seen_ids = set()
    seen_names = set()

    # Use VARIED queries — not just job titles
    # Different query types return different people
    queries = [
        f"site:linkedin.com/in {keyword} {location} CEO OR Founder",
        f"site:linkedin.com/in {keyword} {location} Manager OR Director",
        f"site:linkedin.com/in {keyword} {location} Owner OR Head",
        f"site:linkedin.com/in {keyword} {location} President OR MD",
        f"site:linkedin.com/in {keyword} manager {location}",
        f"site:linkedin.com/in {location} {keyword} executive",
        f"site:linkedin.com/in {location} {keyword} operations",
        f"site:linkedin.com/in {location} {keyword} sales",
    ]

    print(f"LOG:LinkedIn scraper: {keyword} in {location} | Target: {limit}", flush=True)
    print(f"LOG:Running {len(queries)} different queries", flush=True)

    for i, query in enumerate(queries):
        if len(all_profiles) >= limit:
            break

        print(f"LOG:Query {i+1}/{len(queries)}: searching...", flush=True)

        if not SERPER_API_KEY:
            print("LOG:No SERPER_API_KEY!", flush=True)
            break

        try:
            resp = requests.post(
                "https://google.serper.dev/search",
                headers={
                    "X-API-KEY": SERPER_API_KEY,
                    "Content-Type": "application/json"
                },
                json={"q": query, "num": 10, "gl": "in"},
                timeout=10
            )
            results = resp.json().get("organic", [])
            new_this_query = 0

            for r in results:
                if len(all_profiles) >= limit:
                    break
                link = r.get("link", "")
                if "linkedin.com/in" not in link:
                    continue

                p = get_linkedin_structure()
                t = r.get("title", "")
                s = r.get("snippet", "")

                # Parse name and title
                p_full_name = ""
                job_title = ""
                company_name = ""
                
                parts = t.split(" - ")
                if len(parts) >= 2:
                    p_full_name = parts[0].strip()
                    job_title = parts[1].strip()
                    if len(parts) >= 3:
                        company_name = parts[2].strip()
                else:
                    p2 = t.split(" | ")
                    p_full_name = p2[0].strip() if p2 else r.get("title","").strip()
                    job_title = p2[1].strip() if len(p2) > 1 else keyword

                linkedin_url = link
                industry = s[:200]
                company_name = company_name or keyword
                lead_id = hashlib.md5(
                    p_full_name.lower().encode()
                ).hexdigest()

                # Skip duplicates by both ID and name
                if lead_id in seen_ids:
                    continue
                if p_full_name.lower() in seen_names:
                    continue
                seen_ids.add(lead_id)
                seen_names.add(p_full_name.lower())

                email_guessed = guess_email(
                    p_full_name, company_name
                )
                company_size = ""
                size = re.search(
                    r'(\d+[\+]?\d*)\s*(?:employees|connections)', s
                )
                if size:
                    company_size = size.group(1)

                # After parsing name and title, map to Google Sheets columns:
                p["lead_id"] = lead_id
                p["name"] = p_full_name          # full name
                p["email"] = email_guessed       # guessed email
                p["website"] = linkedin_url      # linkedin URL
                p["address"] = location          # city
                p["description"] = f"{job_title} at {company_name}"  # job info
                p["company_name"] = company_name  # Issue 1 fix
                p["cross_linked_to"] = ""         # Issue 3 fix
                p["additional_data"] = json.dumps({
                    "job_title": job_title,
                    "company_name": company_name,
                    "company_size": company_size,
                    "industry": industry,
                    "connection_degree": "2nd",
                    "source": "LinkedIn"
                })
                p["category"] = "LinkedIn Contact"
                p["validation_status"] = "Valid" if p["name"] else "Pending"

                all_profiles.append(p)
                new_this_query += 1
                print(f"LOG:✅ {p['name']} | {job_title}", flush=True)

            print(f"LOG:Query {i+1} added {new_this_query} new profiles. Total: {len(all_profiles)}", flush=True)

        except Exception as e:
            print(f"LOG:Query {i+1} failed: {e}", flush=True)

        time.sleep(0.3)

    # Dedup against Maps leads
    if maps_leads:
        all_profiles = dedup_against_maps(all_profiles, maps_leads)

    print(f"LOG:LinkedIn complete. {len(all_profiles)} unique profiles", flush=True)
    return all_profiles[:limit]
