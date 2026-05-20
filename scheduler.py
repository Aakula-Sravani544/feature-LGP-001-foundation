"""
Day 18 — APScheduler Integration
Automated scraping jobs for Pro/Enterprise users
Background thread execution
Results auto-saved to Google Sheets
Email notification on completion
"""

import os
import sys
import json
import logging
import subprocess
import threading
from datetime import datetime
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

# Job storage — in memory
scheduled_jobs = {}
job_history = []


# ==========================================
# JOB EXECUTION
# ==========================================
def run_scraping_job(
    job_id: str,
    keyword: str,
    location: str,
    max_leads: int = 50,
    use_ai: bool = False
) -> None:
    """Execute scraping job in background thread with correct path resolution."""
    import time
    query = f"{keyword} in {location}"
    logger.info(f"Job {job_id} starting: {query}")

    # Register/update status to running immediately so it shows up in UI
    found = False
    for job in job_history:
        if job["job_id"] == job_id:
            job["status"] = "running"
            job["started_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            found = True
            break
    if not found:
        job_history.append({
            "job_id": job_id,
            "query": query,
            "status": "running",
            "started_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "leads_collected": 0,
            "completed_at": ""
        })

    leads = []

    try:
        # Resolve correct path to scraper.py
        current_dir = os.path.dirname(os.path.abspath(__file__))
        scraper_path = os.path.join(current_dir, "scraper.py")

        # Fallback paths if not found
        if not os.path.exists(scraper_path):
            fallback_paths = [
                "/app/scraper.py",
                os.path.join(os.getcwd(), "scraper.py"),
                "scraper.py"
            ]
            for path in fallback_paths:
                if os.path.exists(path):
                    scraper_path = path
                    break

        logger.info(f"Job {job_id}: using scraper at {scraper_path}")
        print(f"LOG:Scheduler job {job_id} starting: {query}", flush=True)

        ai_flag = "1" if use_ai else "0"

        # Setup environment with UTF-8 encoding to prevent UnicodeEncodeError in subprocess pipes
        sub_env = os.environ.copy()
        sub_env["PYTHONIOENCODING"] = "utf-8"

        process = subprocess.Popen(
            [sys.executable, scraper_path, query, str(max_leads), ai_flag],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            bufsize=1,
            cwd=current_dir,
            env=sub_env
        )

        # Read output with timeout
        start_time = time.time()
        max_runtime = 300  # 5 minutes max

        for line in process.stdout:
            line = line.strip()

            # Check timeout
            if time.time() - start_time > max_runtime:
                logger.warning(f"Job {job_id}: timeout reached")
                process.kill()
                break

            if line.startswith("DATA:"):
                try:
                    lead = json.loads(line.replace("DATA:", "").strip())
                    if lead.get("name"):
                        leads.append(lead)
                        logger.info(f"Job {job_id}: collected {lead.get('name','')[:30]}")
                except Exception as e:
                    logger.debug(f"Parse error: {e}")

            elif line.startswith("LOG:"):
                logger.info(f"Job {job_id}: {line.replace('LOG:','').strip()}")

        process.wait()
        logger.info(f"Job {job_id}: scraper finished. Leads: {len(leads)}")

        # Save to database
        if leads:
            try:
                import database
                database.save_to_db(leads)
                logger.info(f"Job {job_id}: saved {len(leads)} to database")
            except Exception as e:
                logger.error(f"Job {job_id}: database error: {e}")

            # Save to Google Sheets
            try:
                import google_sheets
                success, msg = google_sheets.save_to_google_sheets(leads)
                logger.info(f"Job {job_id}: sheets sync: {msg}")
            except Exception as e:
                logger.error(f"Job {job_id}: sheets error: {e}")

            # Email notification
            try:
                send_job_notification(job_id, query, len(leads))
            except Exception as e:
                logger.debug(f"Job {job_id}: email error: {e}")

    except Exception as e:
        logger.error(f"Job {job_id} error: {e}")

    finally:
        # ALWAYS update job history when done — success or failure
        final_status = "completed" if len(leads) > 0 else "failed"
        final_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        updated = False
        for job in job_history:
            if job["job_id"] == job_id:
                job["status"] = final_status
                job["leads_collected"] = len(leads)
                job["completed_at"] = final_time
                updated = True
                break

        if not updated:
            job_history.append({
                "job_id": job_id,
                "query": query,
                "status": final_status,
                "started_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "leads_collected": len(leads),
                "completed_at": final_time
            })

        logger.info(f"Job {job_id} {final_status}: {len(leads)} leads")


def send_job_notification(job_id: str, query: str, leads_count: int) -> None:
    """Send email notification when job completes."""
    try:
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart

        smtp_user = os.environ.get("SMTP_USER", "")
        smtp_pass = os.environ.get("SMTP_PASS", "")
        notify_email = os.environ.get("NOTIFY_EMAIL", smtp_user)

        if not smtp_user or not smtp_pass:
            logger.debug("SMTP not configured — skipping notification")
            return

        msg = MIMEMultipart()
        msg["Subject"] = f"✅ LeadPulse Job Done — {leads_count} leads"
        msg["From"] = smtp_user
        msg["To"] = notify_email

        body = MIMEText(f"""
LeadPulse Pro — Scheduled Job Complete

Job ID     : {job_id}
Query      : {query}
Leads      : {leads_count}
Completed  : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Login to view your new leads:
{os.environ.get('APP_URL', 'https://leadpulse-pro.onrender.com')}
        """)
        msg.attach(body)

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)
            logger.info(f"Email sent to {notify_email}")

    except Exception as e:
        logger.debug(f"Email failed: {e}")


# ==========================================
# SCHEDULER SETUP
# ==========================================
def start_scheduler() -> Optional[object]:
    """Initialize APScheduler with background thread."""
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.cron import CronTrigger

        scheduler = BackgroundScheduler()
        scheduler.start()
        logger.info("APScheduler started")
        return scheduler

    except ImportError:
        logger.warning("APScheduler not installed")
        return None
    except Exception as e:
        logger.error(f"Scheduler start error: {e}")
        return None


def add_scheduled_job(
    scheduler,
    job_id: str,
    keyword: str,
    location: str,
    schedule_type: str,
    schedule_time: str,
    max_leads: int = 50,
    use_ai: bool = False
) -> tuple:
    """
    Add a new scheduled scraping job.
    schedule_type: daily, weekly, hourly
    schedule_time: HH:MM for daily, day:HH:MM for weekly
    """
    try:
        from apscheduler.triggers.cron import CronTrigger

        if schedule_type == "hourly":
            trigger = CronTrigger(minute=0)
        elif schedule_type == "daily":
            hour, minute = schedule_time.split(":")
            trigger = CronTrigger(hour=int(hour), minute=int(minute))
        elif schedule_type == "weekly":
            parts = schedule_time.split(":")
            day = parts[0]
            hour = parts[1]
            minute = parts[2] if len(parts) > 2 else "0"
            trigger = CronTrigger(
                day_of_week=day,
                hour=int(hour),
                minute=int(minute)
            )
        else:
            trigger = CronTrigger(hour=9, minute=0)

        scheduler.add_job(
            func=run_scraping_job,
            trigger=trigger,
            args=[job_id, keyword, location, max_leads, use_ai],
            id=job_id,
            name=f"{keyword} in {location}",
            replace_existing=True
        )

        scheduled_jobs[job_id] = {
            "job_id": job_id,
            "keyword": keyword,
            "location": location,
            "schedule_type": schedule_type,
            "schedule_time": schedule_time,
            "max_leads": max_leads,
            "use_ai": use_ai,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "status": "active"
        }

        logger.info(f"Job {job_id} scheduled: {keyword} in {location}")
        return True, f"Job scheduled successfully"

    except Exception as e:
        logger.error(f"Schedule job error: {e}")
        return False, str(e)


def remove_scheduled_job(scheduler, job_id: str) -> tuple:
    """Remove a scheduled job."""
    try:
        if scheduler:
            scheduler.remove_job(job_id)
        if job_id in scheduled_jobs:
            del scheduled_jobs[job_id]
        return True, f"Job {job_id} removed"
    except Exception as e:
        return False, str(e)


def run_job_now(job_id: str, keyword: str, location: str, max_leads: int = 50) -> None:
    """Run a job immediately in background thread."""
    thread = threading.Thread(
        target=run_scraping_job,
        args=[job_id, keyword, location, max_leads, False],
        daemon=True
    )
    thread.start()
    logger.info(f"Job {job_id} started in background thread")


# ==========================================
# SCHEDULER UI
# ==========================================
def render_scheduler_ui(plan: str) -> None:
    """
    Render scheduler UI — only for Pro and Enterprise users.
    """
    import streamlit as st
    from subscription import can_use_scheduled, get_upgrade_message

    st.markdown("### ⏰ Automated Scraping")

    # Plan gate
    if not can_use_scheduled(plan):
        st.warning(f"🔒 {get_upgrade_message(plan, 'scheduled_scraping')}")
        st.info("Upgrade to **Pro** or **Enterprise** to unlock scheduled scraping.")
        return

    st.success(f"✅ Scheduled scraping enabled on your {plan} plan")

    # Create new scheduled job
    st.markdown("#### ➕ Create New Scheduled Job")
    col1, col2, col3 = st.columns(3)
    with col1:
        sched_keyword = st.text_input("Keyword", placeholder="e.g. restaurants", key="sched_keyword")
        sched_location = st.text_input("Location", placeholder="e.g. Hyderabad", key="sched_location")
    with col2:
        sched_type = st.selectbox(
            "Schedule",
            ["daily", "weekly", "hourly"],
            key="sched_type"
        )
        sched_time = st.text_input(
            "Time (HH:MM)",
            value="09:00",
            help="Daily: HH:MM | Weekly: mon:09:00",
            key="sched_time"
        )
    with col3:
        sched_leads = st.slider("Max Leads", 10, 100, 50, key="sched_leads")
        sched_ai = st.toggle("Enable AI", key="sched_ai")

    col4, col5 = st.columns(2)
    with col4:
        if st.button("📅 Schedule Job", use_container_width=True, key="create_sched"):
            if sched_keyword and sched_location:
                import uuid
                job_id = f"job_{uuid.uuid4().hex[:8]}"
                scheduler = st.session_state.get("scheduler")
                if scheduler:
                    success, msg = add_scheduled_job(
                        scheduler, job_id,
                        sched_keyword, sched_location,
                        sched_type, sched_time,
                        sched_leads, sched_ai
                    )
                    if success:
                        st.success(f"✅ {msg} — ID: {job_id}")
                    else:
                        st.error(msg)
                else:
                    st.warning("Scheduler not running. Restart the app.")
            else:
                st.warning("Enter keyword and location")

    with col5:
        if st.button("▶️ Run Job Now (Test)", use_container_width=True, key="run_now"):
            if sched_keyword and sched_location:
                import uuid
                job_id = f"manual_{uuid.uuid4().hex[:8]}"
                run_job_now(job_id, sched_keyword, sched_location, sched_leads)
                st.success(f"✅ Job started in background! ID: {job_id}")
                st.info("Check Job History below for results in 1-2 minutes.")
            else:
                st.warning("Enter keyword and location")

    st.markdown("---")

    # Active scheduled jobs
    st.markdown("#### 📋 Active Scheduled Jobs")
    if scheduled_jobs:
        import pandas as pd
        jobs_df = pd.DataFrame(list(scheduled_jobs.values()))
        st.dataframe(jobs_df, hide_index=True, use_container_width=True)

        # Remove job
        remove_job_id = st.text_input("Job ID to remove", key="remove_job_id")
        if st.button("🗑️ Remove Job", key="remove_job"):
            if remove_job_id:
                scheduler = st.session_state.get("scheduler")
                success, msg = remove_scheduled_job(scheduler, remove_job_id)
                if success:
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)
    else:
        st.info("No scheduled jobs yet. Create one above.")

    st.markdown("---")

    st.markdown("#### 📜 Job History")

    col_r1, col_r2 = st.columns(2)
    with col_r1:
        if st.button("🔄 Refresh Status", use_container_width=True, key="refresh_jobs"):
            st.rerun()
    with col_r2:
        if st.button("🗑️ Clear History", use_container_width=True, key="clear_jobs"):
            job_history.clear()
            st.rerun()

    if job_history:
        import pandas as pd
        history_df = pd.DataFrame(job_history)
        display_cols = [
            "job_id", "query", "status",
            "started_at", "leads_collected", "completed_at"
        ]
        available = [c for c in display_cols if c in history_df.columns]
        st.dataframe(
            history_df[available],
            hide_index=True,
            use_container_width=True
        )

        # Summary metrics
        completed = len([j for j in job_history if j.get("status") == "completed"])
        running = len([j for j in job_history if j.get("status") == "running"])
        failed = len([j for j in job_history if j.get("status") == "failed"])
        total_leads = sum(j.get("leads_collected", 0) for j in job_history)

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Completed", completed)
        m2.metric("Running", running)
        m3.metric("Failed", failed)
        m4.metric("Total Leads Collected", total_leads)
    else:
        st.info("No jobs run yet. Click 'Run Job Now' above.")

    st.markdown("---")

    # Email status
    st.markdown("#### 📧 Email Notifications")
    smtp_configured = bool(os.environ.get("SMTP_USER")) and bool(os.environ.get("SMTP_PASS"))
    if smtp_configured:
        smtp_user = os.environ.get("SMTP_USER", "")
        notify = os.environ.get("NOTIFY_EMAIL", smtp_user)
        st.success(f"✅ Email notifications active — sending to {notify}")
    else:
        st.warning("⚠️ Email notifications not configured")
        st.markdown("Add these to Render environment variables:")
        st.code("""
    SMTP_USER=your.email@gmail.com
    SMTP_PASS=your_app_password
    NOTIFY_EMAIL=notify@email.com
        """)
