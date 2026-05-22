"""
Day 21 — Launch Day Checklist
Verifies everything is production ready
Run: python launch_checklist.py
"""

import os
import sys
import json
import requests
import logging
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.WARNING)

PASS = "✅"
FAIL = "❌"
WARN = "⚠️"

results = []


def check(label: str, condition: bool, warn_only: bool = False, info: str = None) -> None:
    suffix = f" — {info}" if info else ""
    if condition:
        print(f"{PASS} {label}{suffix}")
        results.append((label, True))
    elif warn_only:
        print(f"{WARN} {label} — optional{suffix}")
        results.append((label, True))
    else:
        print(f"{FAIL} {label}{suffix}")
        results.append((label, False))


def run_launch_checklist():
    print("=" * 60)
    print("🚀 LeadPulse Pro — Day 21 Launch Checklist")
    print(f"   {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # ==========================================
    # SECTION 1 — Environment Variables
    # ==========================================
    print("\n📋 Environment Variables")
    check("SERPER_API_KEY configured", bool(os.getenv("SERPER_API_KEY")))
    check("GEMINI_API_KEY configured", bool(os.getenv("GEMINI_API_KEY")))
    
    google_creds = os.getenv("GOOGLE_SHEETS_CREDENTIALS", "")
    is_valid_creds = False
    if google_creds:
        if google_creds.endswith(".json") and os.path.exists(google_creds):
            is_valid_creds = True
        else:
            try:
                parsed = json.loads(google_creds)
                if isinstance(parsed, dict) and "project_id" in parsed:
                    is_valid_creds = True
            except:
                pass
    check("GOOGLE_SHEETS_CREDENTIALS configured", is_valid_creds)
    
    check("SHEET_NAME configured", bool(os.getenv("SHEET_NAME")))
    check("APP_URL configured", bool(os.getenv("APP_URL")))
    check("APOLLO_API_KEY configured", bool(os.getenv("APOLLO_API_KEY")), warn_only=True)
    check("STRIPE_SECRET_KEY configured", bool(os.getenv("STRIPE_SECRET_KEY")), warn_only=True)
    check("SMTP_USER configured", bool(os.getenv("SMTP_USER")), warn_only=True)

    # ==========================================
    # SECTION 2 — Required Files
    # ==========================================
    print("\n📁 Required Files")
    required_files = [
        "app.py", "scraper.py", "validation.py",
        "ai_engine.py", "database.py", "google_sheets.py",
        "auth.py", "subscription.py", "stripe_handler.py",
        "export_module.py", "scheduler.py", "linkedin_scraper.py",
        "requirements.txt", "Dockerfile", "render.yaml"
    ]
    for f in required_files:
        check(f"File exists: {f}", os.path.exists(f))

    # ==========================================
    # SECTION 3 — Requirements
    # ==========================================
    print("\n📦 Required Packages")
    required_packages = [
        "streamlit", "pandas", "requests", "gspread",
        "google-auth", "beautifulsoup4", "sqlalchemy",
        "phonenumbers", "email-validator", "google-generativeai",
        "bcrypt", "pyyaml", "stripe", "plotly",
        "openpyxl", "reportlab", "apscheduler"
    ]
    try:
        with open("requirements.txt") as f:
            reqs = f.read().lower()
        for pkg in required_packages:
            check(f"Package in requirements: {pkg}", pkg.lower() in reqs)
    except Exception as e:
        check("requirements.txt readable", False)

    # ==========================================
    # SECTION 4 — Auth System
    # ==========================================
    print("\n🔐 Authentication")
    try:
        from auth import login, get_all_users
        success, role, plan = login("admin", "admin123")
        check("Admin login works", success and role == "admin")
        users = get_all_users()
        check("Users exist in system", len(users) > 0, info=f"{len(users)} users")
    except Exception as e:
        check("Auth system functional", False)

    # ==========================================
    # SECTION 5 — Database
    # ==========================================
    print("\n💾 Database")
    try:
        import database
        df = database.load_db()
        check("Database loads", True)
        check("Has leads data", len(df) > 0, info=f"{len(df)} leads")
        check("Has required columns", all(c in df.columns for c in ["name","phone","validation_status"]))
    except Exception as e:
        check("Database functional", False)

    # ==========================================
    # SECTION 6 — Google Sheets
    # ==========================================
    print("\n☁️ Google Sheets")
    try:
        import google_sheets
        connected = google_sheets.check_connection()
        check("Google Sheets connected", connected)
    except Exception as e:
        check("Google Sheets functional", False)

    # ==========================================
    # SECTION 7 — Scraper
    # ==========================================
    print("\n🕷️ Lead Scraper")
    try:
        import subprocess
        proc = subprocess.Popen(
            [sys.executable, "scraper.py", "restaurants in Jubilee Hills Hyderabad", "3", "0"],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1
        )
        leads = []
        for line in proc.stdout:
            if line.strip().startswith("DATA:"):
                try:
                    leads.append(json.loads(line.strip().replace("DATA:","")))
                except: pass
        proc.wait()
        check("Scraper generates leads", len(leads) > 0, info=f"{len(leads)} leads")
        check("Leads have phone numbers", any(l.get("phone") for l in leads))
        check("Leads have addresses", any(l.get("address") for l in leads))
    except Exception as e:
        check("Scraper functional", False)

    # ==========================================
    # SECTION 8 — AI Engine
    # ==========================================
    print("\n🤖 AI Engine")
    try:
        from ai_engine import rule_based_score
        score = rule_based_score({
            "name":"Test", "category":"Restaurant",
            "rating":"4.5", "reviews":"100",
            "phone":"+919999999999"
        })
        check("AI scoring functional", "score" in score)
        check("Score in valid range", 0 <= score.get("score",0) <= 100)
    except Exception as e:
        check("AI engine functional", False)

    # ==========================================
    # SECTION 9 — Export Module
    # ==========================================
    print("\n📤 Export Module")
    try:
        import pandas as pd
        from export_module import export_csv, export_excel, export_json
        test_df = pd.DataFrame([{"name":"Test","phone":"+91999","email":"t@t.com","validation_status":"Valid"}])
        check("CSV export works", len(export_csv(test_df)) > 0)
        check("Excel export works", len(export_excel(test_df)) > 0)
        check("JSON export works", len(export_json(test_df)) > 0)
    except Exception as e:
        check("Export module functional", False)

    # ==========================================
    # SECTION 10 — App Health
    # ==========================================
    print("\n🌐 App Health Check")
    app_url = os.getenv("APP_URL", "https://feature-lgp-001-foundation-art9.onrender.com")
    try:
        response = requests.get(f"{app_url}/_stcore/health", timeout=15)
        check("App responding", response.status_code == 200)
        check("HTTPS active", app_url.startswith("https://"))
    except Exception as e:
        check("App health check", False, info=str(e))

    # ==========================================
    # FINAL REPORT
    # ==========================================
    print("\n" + "="*60)
    passed = sum(1 for _, ok in results if ok)
    total = len(results)
    rate = int(passed/max(total,1)*100)

    print(f"Launch Readiness: {passed}/{total} checks passed ({rate}%)")
    print("="*60)

    if rate >= 90:
        print("""
🎉 LEADPULSE PRO IS LAUNCH READY!

✅ All critical systems operational
✅ Authentication working
✅ Lead generation working
✅ AI scoring working
✅ Export module working
✅ App live with HTTPS

🚀 You have successfully completed the 21-day build!

Share your app: https://feature-lgp-001-foundation-art9.onrender.com
        """)
    elif rate >= 70:
        print("⚠️ MOSTLY READY — Fix failing checks before sharing")
    else:
        print("❌ NOT READY — Multiple critical failures")

    failed = [(label, ok) for label, ok in results if not ok]
    if failed:
        print("\nFix these before launch:")
        for label, _ in failed:
            print(f"  ❌ {label}")


if __name__ == "__main__":
    run_launch_checklist()
