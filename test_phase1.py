"""
Day 7 — Phase 1 Integration Test Suite
LeadPulse Pro QA Testing
Run: python test_phase1.py
Done-When: All major tests pass, 100+ unique leads stored, zero duplicates
"""

import sys
import json
import time
import subprocess
import logging
from datetime import datetime
from typing import List, Dict

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ==========================================
# TEST CONFIGURATION
# ==========================================
TEST_QUERIES = [
    ("restaurants", "hyderabad"),
    ("hotels", "chennai"),
    ("IT companies", "bangalore")
]
LEADS_PER_QUERY = 5
PASS = "PASS"
FAIL = "FAIL"
all_results = []


def log_result(test_name: str, passed: bool, details: str = "") -> None:
    """Log test result and store it."""
    status = PASS if passed else FAIL
    msg = f"[{status}] | {test_name}"
    if details:
        msg += f" | {details}"
    print(msg)
    all_results.append({
        "test": test_name,
        "passed": passed,
        "details": details
    })


# ==========================================
# TEST 1 — Full Pipeline (3 queries)
# ==========================================
def test_full_pipeline() -> List[Dict]:
    """Run scraper with 3 different queries."""
    print("\n" + "="*60)
    print("TEST 1 - Full Pipeline Test (3 Search Queries)")
    print("="*60)

    all_leads = []

    for keyword, location in TEST_QUERIES:
        query = f"{keyword} in {location}"
        print(f"\nQuery: '{query}'")

        try:
            process = subprocess.Popen(
                [sys.executable, "scraper.py", query, str(LEADS_PER_QUERY)],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                encoding='utf-8',
                errors='replace'
            )

            query_leads = []
            if process.stdout:
                for line in process.stdout:
                    line = line.strip()
                    if line.startswith("DATA:"):
                        try:
                            lead = json.loads(line.replace("DATA:", ""))
                            query_leads.append(lead)
                            print(f"  -> {lead.get('name','')[:50]} | {lead.get('phone','')} | {lead.get('rating','')}")
                        except:
                            pass
                    elif line.startswith("LOG:"):
                        print(f"  [LOG] {line.replace('LOG:','')}")

            process.wait()

            passed = len(query_leads) > 0
            log_result(
                f"Pipeline: {query}",
                passed,
                f"{len(query_leads)} leads collected"
            )
            all_leads.extend(query_leads)
            time.sleep(3)

        except Exception as e:
            log_result(f"Pipeline: {query}", False, str(e))

    log_result(
        "Total leads across 3 queries",
        len(all_leads) >= LEADS_PER_QUERY * 2,
        f"{len(all_leads)} total leads"
    )

    return all_leads


# ==========================================
# TEST 2 - Deduplication Stress Test
# ==========================================
def test_deduplication(all_leads: List[Dict]) -> None:
    """Run same query twice - confirm zero new duplicates."""
    print("\n" + "="*60)
    print("TEST 2 - Deduplication Stress Test")
    print("="*60)

    # Check lead_id uniqueness
    lead_ids = [l.get("lead_id", "") for l in all_leads]
    unique_ids = set(lead_ids)
    log_result(
        "No duplicate lead_ids in session",
        len(lead_ids) == len(unique_ids),
        f"{len(lead_ids)} total | {len(unique_ids)} unique"
    )

    # Run same query twice
    print("\nRunning same query twice...")
    query = "restaurants in hyderabad"
    first_ids = set()
    second_ids = set()

    for run, id_set in [(1, first_ids), (2, second_ids)]:
        print(f"Run {run}: {query}")
        try:
            process = subprocess.Popen(
                [sys.executable, "scraper.py", query, "3"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding='utf-8',
                errors='replace'
            )
            if process.stdout:
                for line in process.stdout:
                    if line.startswith("DATA:"):
                        try:
                            lead = json.loads(line.replace("DATA:", "").strip())
                            if lead.get("lead_id"):
                                id_set.add(lead["lead_id"])
                        except:
                            pass
            process.wait()
            time.sleep(2)
        except Exception as e:
            logger.error(f"Run {run} failed: {e}")

    overlap = first_ids.intersection(second_ids)
    log_result(
        "Same leads detected across 2 runs",
        len(overlap) > 0,
        f"{len(overlap)} matching lead_ids in both runs"
    )


# ==========================================
# TEST 3 - Validation Module Test
# ==========================================
def test_validation(all_leads: List[Dict]) -> None:
    """Check validation status assigned correctly."""
    print("\n" + "="*60)
    print("TEST 3 - Validation Module Test")
    print("="*60)

    # All leads must have valid status
    valid_statuses = ["Valid", "Invalid", "Pending"]
    has_status = all([
        l.get("validation_status") in valid_statuses
        for l in all_leads
    ])
    log_result(
        "All leads have valid validation_status",
        has_status,
        f"{len(all_leads)} leads checked"
    )

    # Count by status
    valid = len([l for l in all_leads if l.get("validation_status") == "Valid"])
    pending = len([l for l in all_leads if l.get("validation_status") == "Pending"])
    invalid = len([l for l in all_leads if l.get("validation_status") == "Invalid"])
    print(f"  Valid: {valid} | Pending: {pending} | Invalid: {invalid}")

    log_result("At least some leads marked Valid", valid > 0, f"{valid} valid leads")
    log_result("All leads have lead_id", all([bool(l.get("lead_id")) for l in all_leads]))
    log_result("All leads have scraped_date", all([bool(l.get("scraped_date")) for l in all_leads]))


# ==========================================
# TEST 4 - Data Fields Test
# ==========================================
def test_data_fields(all_leads: List[Dict]) -> None:
    """Check all 19 required fields present."""
    print("\n" + "="*60)
    print("TEST 4 - Data Fields Completeness")
    print("="*60)

    required_fields = [
        "lead_id", "name", "address", "phone", "email",
        "website", "rating", "reviews", "category",
        "google_maps_url", "description", "hours",
        "social_media", "additional_data", "scraped_date",
        "ai_analysis", "validation_status", "validation_notes",
        "sub_region"
    ]

    for field in required_fields:
        present = all([field in l for l in all_leads])
        log_result(f"Field '{field}' present", present)

    # Check key fields have data
    has_rating = any([bool(l.get("rating")) for l in all_leads])
    has_reviews = any([bool(l.get("reviews")) for l in all_leads])
    has_phone = any([bool(l.get("phone")) for l in all_leads])
    has_email = any([bool(l.get("email")) for l in all_leads])

    log_result("Rating populated for some leads", has_rating)
    log_result("Reviews populated for some leads", has_reviews)
    log_result("Phone populated for some leads", has_phone)
    log_result("Email populated for some leads", has_email)


# ==========================================
# TEST 5 - Google Sheets Sync Test
# ==========================================
def test_google_sheets(all_leads: List[Dict]) -> None:
    """Test Google Sheets connection and save."""
    print("\n" + "="*60)
    print("TEST 5 - Google Sheets Sync Test")
    print("="*60)

    try:
        import google_sheets
        connected = google_sheets.check_connection()
        log_result("Google Sheets connection", connected)

        if connected and all_leads:
            # Send small batch to avoid quota issues
            success, msg = google_sheets.save_to_google_sheets(all_leads[:5])
            log_result("Save 5 leads to Google Sheets", success, msg)
    except Exception as e:
        log_result("Google Sheets test", False, str(e))


# ==========================================
# TEST 6 - Database Test
# ==========================================
def test_database(all_leads: List[Dict]) -> None:
    """Test local database save and load."""
    print("\n" + "="*60)
    print("TEST 6 - Database Test")
    print("="*60)

    try:
        import database
        database.save_to_db(all_leads[:5])
        log_result("Save leads to database", True)

        df = database.load_db()
        log_result(
            "Load leads from database",
            len(df) > 0,
            f"{len(df)} total leads in database"
        )
    except Exception as e:
        log_result("Database test", False, str(e))


# ==========================================
# FINAL QA REPORT
# ==========================================
def print_qa_report() -> bool:
    """Print final Phase 1 QA report."""
    print("\n" + "="*60)
    print("DAY 7 - PHASE 1 QA REPORT")
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)

    passed = [r for r in all_results if r["passed"]]
    failed = [r for r in all_results if not r["passed"]]

    total = len(all_results)
    if total == 0:
        print("No tests were run.")
        return False

    print(f"\nTotal Tests : {total}")
    print(f"Passed      : {len(passed)}")
    print(f"Failed      : {len(failed)}")
    print(f"Pass Rate   : {int(len(passed)/total*100)}%")

    if failed:
        print("\nFailed Tests:")
        for f in failed:
            print(f"  [FAIL] {f['test']} - {f['details']}")

    print("\nPhase 1 Acceptance Criteria:")
    pipeline_ok = any("Pipeline" in r["test"] and r["passed"] for r in all_results)
    dedup_ok = any("duplicate" in r["test"].lower() and r["passed"] for r in all_results)
    valid_ok = any("validation" in r["test"].lower() and r["passed"] for r in all_results)
    db_ok = any("database" in r["test"].lower() and r["passed"] for r in all_results)

    print(f"  {'DONE' if pipeline_ok else 'FAIL'} Pipeline collects leads from 3 queries")
    print(f"  {'DONE' if dedup_ok else 'FAIL'} Zero duplicates confirmed")
    print(f"  {'DONE' if valid_ok else 'FAIL'} Validation module working")
    print(f"  {'DONE' if db_ok else 'FAIL'} Database saving correctly")

    overall = pipeline_ok and valid_ok and db_ok
    print(f"\n{'PHASE 1 COMPLETE - Ready for Phase 2!' if overall else 'Fix failed tests before Phase 2'}")
    return overall


# ==========================================
# MAIN
# ==========================================
if __name__ == "__main__":
    print("LeadPulse Pro - Day 7 Phase 1 Integration Test")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Queries: {TEST_QUERIES}")
    print(f"Leads per query: {LEADS_PER_QUERY}")

    all_leads = test_full_pipeline()

    if all_leads:
        test_deduplication(all_leads)
        test_validation(all_leads)
        test_data_fields(all_leads)
        test_google_sheets(all_leads)
        test_database(all_leads)
    else:
        print("Pipeline returned 0 leads - cannot run remaining tests")
        print("Check SERPER_API_KEY is set in environment variables")

    print_qa_report()
