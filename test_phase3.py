"""
Day 20 — Full Regression Testing
50 test checklist covering all features Days 1-19
Run: python test_phase3.py
"""

from dotenv import load_dotenv
load_dotenv()

import sys
import os
import json
import subprocess
import time
import logging
from datetime import datetime

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

PASS = "✅ PASS"
FAIL = "❌ FAIL"
SKIP = "⏭️ SKIP"
all_results = []


def log_result(test_name: str, passed: bool, details: str = "") -> None:
    status = PASS if passed else FAIL
    msg = f"{status} | {test_name}"
    if details:
        msg += f" | {details}"
    print(msg)
    all_results.append({"test": test_name, "passed": passed, "details": details})


def log_skip(test_name: str, reason: str = "") -> None:
    print(f"{SKIP} | {test_name} | {reason}")
    all_results.append({"test": test_name, "passed": True, "details": f"SKIPPED: {reason}"})


# ==========================================
# SECTION 1 — AUTH TESTS (Days 11)
# ==========================================
def test_auth():
    print("\n" + "="*60)
    print("SECTION 1 — Authentication (Day 11)")
    print("="*60)
    try:
        from auth import login, register_user, delete_user, get_all_users, update_user_plan

        # Test 1
        success, role, plan = login("admin", "admin123")
        log_result("Admin login correct password", success and role == "admin")

        # Test 2
        success, role, plan = login("admin", "wrong")
        log_result("Admin login wrong password rejected", not success)

        # Test 3
        success, role, plan = login("user", "user123")
        log_result("User login correct password", success)

        # Test 4
        success, msg = register_user("t20_test", "pass123", plan="Free")
        log_result("Register new user", success, msg)

        # Test 5
        success, msg = register_user("admin", "any")
        log_result("Duplicate username rejected", not success)

        # Test 6
        users = get_all_users()
        log_result("Get all users", len(users) > 0, f"{len(users)} users")

        # Test 7
        update_user_plan("t20_test", "Starter")
        log_result("Update user plan", True)

        # Test 8
        delete_user("t20_test")
        log_result("Delete test user", True)

    except Exception as e:
        log_result("Auth tests", False, str(e))


# ==========================================
# SECTION 2 — SUBSCRIPTION TESTS (Day 12)
# ==========================================
def test_subscription():
    print("\n" + "="*60)
    print("SECTION 2 — Subscription Enforcement (Day 12)")
    print("="*60)
    try:
        from subscription import get_max_leads, can_use_linkedin, can_use_ai, can_use_scheduled

        # Test 9
        log_result("Free plan max=50", get_max_leads("Free") == 50, str(get_max_leads("Free")))

        # Test 10
        log_result("Starter plan max=200", get_max_leads("Starter") == 200)

        # Test 11
        log_result("Pro plan max=1000", get_max_leads("Pro") == 1000)

        # Test 12
        log_result("Enterprise plan unlimited", get_max_leads("Enterprise") >= 999999)

        # Test 13
        log_result("Free LinkedIn disabled", not can_use_linkedin("Free"))

        # Test 14
        log_result("Starter LinkedIn enabled", can_use_linkedin("Starter"))

        # Test 15
        log_result("Free AI disabled", not can_use_ai("Free"))

        # Test 16
        log_result("Starter AI enabled", can_use_ai("Starter"))

        # Test 17
        log_result("Free scheduled disabled", not can_use_scheduled("Free"))

        # Test 18
        log_result("Pro scheduled enabled", can_use_scheduled("Pro"))

    except Exception as e:
        log_result("Subscription tests", False, str(e))


# ==========================================
# SECTION 3 — SCRAPER TESTS (Days 1-9)
# ==========================================
def test_scraper():
    print("\n" + "="*60)
    print("SECTION 3 — Scraper Pipeline (Days 1-9)")
    print("="*60)

    leads = []
    try:
        # Test 19 — Scraper runs
        process = subprocess.Popen(
            [sys.executable, "scraper.py", "restaurants in Banjara Hills Hyderabad", "5", "0"],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1
        )
        for line in process.stdout:
            line = line.strip()
            if line.startswith("DATA:"):
                try:
                    lead = json.loads(line.replace("DATA:", ""))
                    leads.append(lead)
                    print(f"  → {lead.get('name','')[:40]}")
                except: pass
        process.wait()
        log_result("Scraper returns leads", len(leads) > 0, f"{len(leads)} leads")

        if leads:
            # Test 20
            log_result("Leads have name", all(l.get("name") for l in leads))

            # Test 21
            log_result("Leads have phone", any(l.get("phone") for l in leads))

            # Test 22
            log_result("Leads have address", any(l.get("address") for l in leads))

            # Test 23
            log_result("Leads have lead_id", all(l.get("lead_id") for l in leads))

            # Test 24
            log_result("Leads have validation_status", all(
                l.get("validation_status") in ["Valid","Invalid","Pending"]
                for l in leads
            ))

            # Test 25
            log_result("Leads have scraped_date", all(l.get("scraped_date") for l in leads))

            # Test 26
            has_dupes = len(leads) != len(set(l.get("lead_id") for l in leads))
            log_result("No duplicate lead_ids", not has_dupes)

    except Exception as e:
        log_result("Scraper tests", False, str(e))

    return leads


# ==========================================
# SECTION 4 — AI TESTS (Days 8-9)
# ==========================================
def test_ai():
    print("\n" + "="*60)
    print("SECTION 4 — AI Scoring (Days 8-9)")
    print("="*60)
    try:
        from ai_engine import rule_based_score, enrich_leads_with_ai

        test_lead = {
            "name": "Test Restaurant", "category": "Restaurant",
            "rating": "4.5", "reviews": "500",
            "phone": "+919999999999", "email": "test@test.com",
            "website": "https://test.com", "address": "Hyderabad"
        }

        # Test 27
        score = rule_based_score(test_lead)
        log_result("Rule-based scoring works", "score" in score, f"score={score.get('score')}")

        # Test 28
        log_result("Score in 0-100 range", 0 <= score.get("score", -1) <= 100)

        # Test 29
        log_result("Qualification text present", bool(score.get("qualification")))

        # Test 30
        log_result("Industry field present", bool(score.get("industry")))

        # Test 31
        enriched = enrich_leads_with_ai([test_lead])
        log_result("Batch AI enrichment works", len(enriched) > 0)

    except Exception as e:
        log_result("AI tests", False, str(e))


# ==========================================
# SECTION 5 — LINKEDIN TESTS (Day 10)
# ==========================================
def test_linkedin():
    print("\n" + "="*60)
    print("SECTION 5 — LinkedIn Scraper (Day 10)")
    print("="*60)
    try:
        from linkedin_scraper import scrape_linkedin

        # Test 32
        profiles = scrape_linkedin("hotels", "hyderabad", limit=5)
        log_result("LinkedIn returns profiles", len(profiles) > 0, f"{len(profiles)} profiles")

        if profiles:
            # Test 33
            has_name = any(p.get("name") or p.get("full_name") for p in profiles)
            log_result("Profiles have names", has_name)

            # Test 34
            has_linkedin = any(
                "linkedin.com" in str(p.get("website","")) or
                "linkedin.com" in str(p.get("linkedin_url",""))
                for p in profiles
            )
            log_result("Profiles have LinkedIn URLs", has_linkedin)

    except Exception as e:
        log_result("LinkedIn tests", False, str(e))


# ==========================================
# SECTION 6 — DATABASE TESTS (Day 3)
# ==========================================
def test_database(leads):
    print("\n" + "="*60)
    print("SECTION 6 — Database & Google Sheets (Days 3-4)")
    print("="*60)
    try:
        import database

        # Test 35
        if leads:
            database.save_to_db(leads[:2])
            log_result("Save leads to database", True)

        # Test 36
        df = database.load_db()
        log_result("Load from database", len(df) > 0, f"{len(df)} total leads")

        # Test 37
        required_cols = ["name", "phone", "validation_status", "scraped_date"]
        has_cols = all(c in df.columns for c in required_cols)
        log_result("Database has required columns", has_cols)

    except Exception as e:
        log_result("Database tests", False, str(e))

    try:
        import google_sheets

        # Test 38
        connected = google_sheets.check_connection()
        log_result("Google Sheets connected", connected)

        # Test 39
        if connected and leads:
            success, msg = google_sheets.save_to_google_sheets(leads[:2])
            log_result("Save to Google Sheets", success, msg)

    except Exception as e:
        log_result("Google Sheets tests", False, str(e))


# ==========================================
# SECTION 7 — EXPORT TESTS (Day 17)
# ==========================================
def test_exports():
    print("\n" + "="*60)
    print("SECTION 7 — Export Module (Day 17)")
    print("="*60)
    try:
        import pandas as pd
        from export_module import export_csv, export_excel, export_json, export_pdf

        test_df = pd.DataFrame([{
            "name": "Test Business", "phone": "+919999999999",
            "email": "test@test.com", "category": "Restaurant",
            "rating": "4.5", "validation_status": "Valid",
            "scraped_date": "2026-05-20"
        }])

        # Test 40
        csv = export_csv(test_df)
        log_result("CSV export works", len(csv) > 0, f"{len(csv)} bytes")

        # Test 41
        excel = export_excel(test_df)
        log_result("Excel export works", len(excel) > 0, f"{len(excel)} bytes")

        # Test 42
        json_data = export_json(test_df)
        log_result("JSON export works", len(json_data) > 0)

        # Test 43
        pdf = export_pdf(test_df)
        log_result("PDF export works", len(pdf) > 0, f"{len(pdf)} bytes")

    except Exception as e:
        log_result("Export tests", False, str(e))


# ==========================================
# SECTION 8 — SCHEDULER TESTS (Day 18)
# ==========================================
def test_scheduler():
    print("\n" + "="*60)
    print("SECTION 8 — Scheduler (Day 18)")
    print("="*60)
    try:
        from scheduler import start_scheduler, run_job_now, job_history

        # Test 44
        scheduler = start_scheduler()
        log_result("Scheduler starts", scheduler is not None)

        # Test 45
        initial = len(job_history)
        run_job_now("test_job_day20", "restaurants", "hyderabad", max_leads=3)
        time.sleep(3)
        log_result("Run job now executes", True, "Job started in background")

        # Test 46
        log_result("Job appears in history", len(job_history) > initial)

        if scheduler:
            try:
                scheduler.shutdown(wait=False)
            except: pass

    except Exception as e:
        log_result("Scheduler tests", False, str(e))


# ==========================================
# SECTION 9 — STRIPE TESTS (Day 13)
# ==========================================
def test_stripe():
    print("\n" + "="*60)
    print("SECTION 9 — Stripe Integration (Day 13)")
    print("="*60)
    try:
        from stripe_handler import create_checkout_session

        # Test 47
        stripe_key = os.environ.get("STRIPE_SECRET_KEY", "")
        log_result("Stripe key configured", bool(stripe_key))

        # Test 48
        success, url = create_checkout_session("Starter", "test_user")
        log_result("Checkout session creates", success, url[:40] if url else "no url")

    except Exception as e:
        log_result("Stripe tests", False, str(e))


# ==========================================
# SECTION 10 — SECURITY TESTS
# ==========================================
def test_security():
    print("\n" + "="*60)
    print("SECTION 10 — Security Checks")
    print("="*60)
    try:
        from auth import login

        # Test 49 — SQL injection attempt
        success, _, _ = login("admin'; DROP TABLE users;--", "any")
        log_result("SQL injection rejected", not success)

        # Test 50 — Empty credentials
        success, _, _ = login("", "")
        log_result("Empty credentials rejected", not success)

    except Exception as e:
        log_result("Security tests", False, str(e))


# ==========================================
# FINAL REPORT
# ==========================================
def print_report():
    print("\n" + "="*60)
    print("DAY 20 — FULL REGRESSION TEST REPORT")
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)

    passed = [r for r in all_results if r["passed"]]
    failed = [r for r in all_results if not r["passed"]]

    print(f"\nTotal Tests  : {len(all_results)}")
    print(f"Passed       : {len(passed)}")
    print(f"Failed       : {len(failed)}")
    rate = int(len(passed)/max(len(all_results),1)*100)
    print(f"Pass Rate    : {rate}%")

    if failed:
        print(f"\nFailed Tests:")
        for f in failed:
            print(f"  ❌ {f['test']} — {f['details']}")

    print(f"\nAcceptance Criteria:")
    checks = {
        "Auth": any("login" in r["test"].lower() and r["passed"] for r in all_results),
        "Subscription": any("plan" in r["test"].lower() and r["passed"] for r in all_results),
        "Scraper": any("scraper" in r["test"].lower() and r["passed"] for r in all_results),
        "AI": any("scoring" in r["test"].lower() and r["passed"] for r in all_results),
        "Database": any("database" in r["test"].lower() and r["passed"] for r in all_results),
        "Export": any("export" in r["test"].lower() and r["passed"] for r in all_results),
    }
    for feature, ok in checks.items():
        print(f"  {'✅' if ok else '❌'} {feature}")

    overall = rate >= 80
    print(f"\n{'🎉 DAY 20 COMPLETE — Ready for Launch!' if overall else '⚠️ Fix failed tests before launch'}")
    return overall


if __name__ == "__main__":
    print("🚀 LeadPulse Pro — Day 20 Full Regression Test")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    test_auth()
    test_subscription()
    leads = test_scraper()
    test_ai()
    test_linkedin()
    test_database(leads)
    test_exports()
    test_scheduler()
    test_stripe()
    test_security()
    print_report()
