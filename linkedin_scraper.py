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
    return {
        "lead_id": "", "full_name": "", "job_title": "",
        "company_name": "", "location": "", "linkedin_url": "",
        "connection_degree": "2nd", "company_linkedin": "",
        "company_size": "", "industry": "", "email_guessed": "",
        "scraped_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "source": "LinkedIn", "validation_status": "Pending",
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
        co = p.get("company_name","").lower()
        for mc, mid in maps_cos.items():
            if co and (co in mc or mc in co):
                p["cross_linked_to"] = mid
                break
        result.append(p)
    return result


def scrape_linkedin(keyword: str, location: str, maps_leads: List[Dict]=None, limit: int=25) -> List[Dict]:
    all_profiles = []
    seen_ids = set()
    job_titles = ["CEO","Founder","Director","Manager","Owner","Head","General Manager","President","MD","Partner"]

    print(f"LOG:🔍 LinkedIn scraper started: {keyword} in {location}", flush=True)

    for title in job_titles:
        if len(all_profiles) >= limit:
            break
        query = f"site:linkedin.com/in {title} {keyword} {location}"
        print(f"LOG:Searching: {title} {keyword}...", flush=True)

        if not SERPER_API_KEY:
            print("LOG:No SERPER_API_KEY found!", flush=True)
            break

        try:
            resp = requests.post(
                "https://google.serper.dev/search",
                headers={"X-API-KEY": SERPER_API_KEY, "Content-Type": "application/json"},
                json={"q": query, "num": 10, "gl": "in"},
                timeout=10
            )
            results = resp.json().get("organic", [])
            print(f"LOG:{len(results)} results for {title}", flush=True)

            for r in results:
                if len(all_profiles) >= limit: break
                link = r.get("link","")
                if "linkedin.com/in" not in link: continue

                p = get_linkedin_structure()
                t = r.get("title","")
                s = r.get("snippet","")

                parts = t.split(" - ")
                if len(parts) >= 2:
                    p["full_name"] = parts[0].strip()
                    p["job_title"] = parts[1].strip()
                    if len(parts) >= 3:
                        p["company_name"] = parts[2].strip()
                else:
                    p2 = t.split(" | ")
                    p["full_name"] = p2[0].strip() if p2 else r.get("title","").strip()
                    p["job_title"] = p2[1].strip() if len(p2) > 1 else title

                p["linkedin_url"] = link
                p["location"] = location
                p["industry"] = s[:200]
                p["company_name"] = p["company_name"] or keyword
                p["lead_id"] = hashlib.md5(p["full_name"].lower().encode()).hexdigest()

                if p["lead_id"] in seen_ids: continue
                seen_ids.add(p["lead_id"])

                p["email_guessed"] = guess_email(p["full_name"], p["company_name"])
                size = re.search(r'(\d+[\+]?\d*)\s*(?:employees|connections)', s)
                if size: p["company_size"] = size.group(1)
                p["validation_status"] = "Valid" if p["full_name"] else "Pending"

                all_profiles.append(p)
                print(f"LOG:✅ {p['full_name']} | {p['job_title']}", flush=True)

        except Exception as e:
            print(f"LOG:Error for {title}: {e}", flush=True)

        time.sleep(0.3)

    if maps_leads:
        all_profiles = dedup_against_maps(all_profiles, maps_leads)

    print(f"LOG:LinkedIn done. {len(all_profiles)} profiles found", flush=True)
    return all_profiles[:limit]
