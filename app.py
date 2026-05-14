import streamlit as st
import pandas as pd
import os
import subprocess
import sys
import json
import time
from datetime import datetime
from dotenv import load_dotenv
import re

# Load environment variables
load_dotenv()

import database
import google_sheets
# Import new auth module
from auth import (
    init_session, render_login_page, render_logout_button,
    check_session_expiry, get_user_info, get_all_users,
    register_user, delete_user, update_user_plan, update_password
)
from stripe_handler import (
    render_billing_tab,
    render_admin_billing,
    check_payment_success
)
from export_module import render_export_ui

# Initialize session
init_session()

# Check for payment success from Stripe redirect
check_payment_success()

# Check session expiry
if st.session_state.authenticated and check_session_expiry():
    st.warning("Session expired. Please login again.")
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()

# Show login if not authenticated
if not st.session_state.authenticated:
    render_login_page()
    st.stop()

# ==========================================
# STARTUP SYNC
# ==========================================
if 'startup_sync_done' not in st.session_state:
    st.session_state.startup_sync_done = True
    # Pull leads from Google Sheets -> save to local DB on startup
    try:
        leads_from_sheets = google_sheets.load_from_google_sheets()
        if leads_from_sheets:
            database.save_to_db(leads_from_sheets)
    except: pass

# ==========================================
# PAGE CONFIGURATION
# ==========================================
st.set_page_config(
    page_title="LeadPulse Pro | Modern Lead Engine",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==========================================
# MODERN SAAS UI CSS
# ==========================================
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
    
    :root {
        --primary: #2563EB;
        --secondary: #0F172A;
        --sidebar-bg: #0F172A;
        --bg: #F8FAFC;
        --card: #FFFFFF;
        --text-primary: #0F172A;
        --text-secondary: #64748B;
        --success: #22C55E;
    }

    html, body, [class*="css"] { 
        font-family: 'Inter', sans-serif; 
        background-color: var(--bg);
    }
    
    .stApp { background-color: var(--bg); }

    /* Centered Headings */
    .main-title {
        text-align: center;
        font-weight: 800;
        font-size: 2.2rem;
        color: var(--secondary);
        margin-bottom: 0.5rem;
    }
    .sub-title {
        text-align: center;
        color: var(--text-secondary);
        margin-bottom: 2rem;
        font-size: 1rem;
    }

    /* Metric Card Styling */
    .metric-card { 
        background: var(--card); 
        padding: 24px; 
        border-radius: 12px; 
        border: 1px solid #E2E8F0; 
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05); 
        text-align: center;
        transition: all 0.3s ease;
    }
    .metric-card:hover {
        transform: translateY(-3px);
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
    }
    .metric-label { 
        color: var(--text-secondary); 
        font-size: 0.7rem; 
        font-weight: 700; 
        text-transform: uppercase; 
        letter-spacing: 0.08em;
        margin-bottom: 8px; 
    }
    .metric-value { 
        color: var(--text-primary); 
        font-size: 1.6rem; 
        font-weight: 800; 
    }

    /* Sidebar Styling */
    [data-testid="stSidebar"] {
        background-color: var(--sidebar-bg);
        color: white;
    }
    [data-testid="stSidebar"] * { color: white !important; }
    
    .sidebar-logo {
        padding: 2rem 1rem 1rem 1rem;
        text-align: left;
        font-size: 1.5rem;
        font-weight: 800;
        color: white !important;
        display: flex;
        align-items: center;
        gap: 12px;
    }
    .sidebar-logo span { color: var(--primary); }
    
    .user-info {
        padding: 0 1rem 1.5rem 1rem;
        font-size: 0.8rem;
        color: #94A3B8 !important;
    }
    .user-info strong { color: white !important; font-weight: 600; }
    
    .sidebar-divider {
        border-top: 1px solid rgba(255,255,255,0.1);
        margin: 0.5rem 1rem 1.5rem 1rem;
    }

    /* Active Menu Highlight */
    .nav-item-active {
        background: rgba(37, 99, 235, 0.15);
        border-left: 4px solid var(--primary);
        padding: 10px 15px;
        margin: 5px 0;
        border-radius: 0 8px 8px 0;
        font-weight: 600;
    }

    /* Modern Buttons */
    div.stButton > button:first-child { 
        background: linear-gradient(135deg, #2563EB 0%, #1D4ED8 100%) !important;
        color: white !important; 
        border: none !important; 
        border-radius: 10px !important; 
        padding: 12px 24px !important; 
        font-weight: 600 !important; 
        width: 100%; 
        transition: all 0.2s ease;
    }
    div.stButton > button:hover { 
        transform: scale(1.02);
        box-shadow: 0 5px 15px rgba(37, 99, 235, 0.3);
    }
    
    /* Logout Button Specific (if different) */
    .logout-btn button {
        background: rgba(255,255,255,0.05) !important;
        border: 1px solid rgba(255,255,255,0.1) !important;
    }

    /* Log Box */
    .log-box { 
        background-color: #0F172A; 
        color: #10B981; 
        padding: 20px; 
        border-radius: 12px; 
        font-family: 'Monaco', 'Consolas', monospace; 
        font-size: 0.8rem; 
        height: 300px; 
        overflow-y: auto;
        border: 1px solid #1E293B;
    }

    /* Badge */
    .badge { padding: 4px 10px; border-radius: 99px; font-size: 0.7rem; font-weight: 700; }
    .badge-success { background: #DCFCE7; color: #166534; }
    .badge-idle { background: #F1F5F9; color: #475569; }
    </style>
    """, unsafe_allow_html=True)

# Session state initialized via auth.init_session()

# ==========================================
# SHARED UTILITIES
# ==========================================
# Shared logout replaced by auth.render_logout_button()

def get_stats():
    try:
        df = database.load_db()
        total = len(df)
        today = 0
        quality = 0
        if total > 0:
            date_col = 'timestamp' if 'timestamp' in df.columns else 'scraped_at'
            today_str = datetime.now().strftime("%Y-%m-%d")
            today = len(df[df[date_col].str.contains(today_str, na=False)])
            valid = len(df[(df['phone'] != '') & (df['phone'].notna())])
            quality = int((valid / total) * 100)
        return total, today, quality
    except: return 0, 0, 0

# ==========================================
# LOGIN PAGE
# ==========================================
# Old login page removed for Day 11 streamlit-authenticator

# ==========================================
# GENERATION COMPONENT (SHARED)
# ==========================================
def get_sub_regions_ai(keyword: str, region: str, city: str) -> list:
    """
    Use Gemini AI to generate detailed sub-regions for a given area.
    Falls back to hardcoded sub-regions and city-wide hubs if needed.
    """
    # Hardcoded Fallbacks
    specific_area_fallback = {
        "kphb": ["KPHB Phase 1", "KPHB Phase 2", "KPHB Phase 3", "KPHB Phase 4", "KPHB Phase 5", "KPHB Phase 6", "KPHB Main Road", "Kukatpally Main Road", "JNTU Road KPHB", "KPHB Colony"],
        "banjara hills": ["Banjara Hills Road 1", "Banjara Hills Road 2", "Banjara Hills Road 3", "Banjara Hills Road 10", "Banjara Hills Road 12", "Banjara Hills Road 13", "Banjara Hills Road 14"],
        "jubilee hills": ["Jubilee Hills Road 36", "Jubilee Hills Road 45", "Jubilee Hills Check Post", "Jubilee Hills Main Road"],
        "hitech city": ["Hitech City Main Road", "Madhapur Hitech City", "Cyber Towers Hitech City", "Hitech City Phase 1", "Hitech City Phase 2"],
        "gachibowli": ["Gachibowli Main Road", "Gachibowli Stadium Road", "Financial District Gachibowli", "ISB Road Gachibowli"],
        "kukatpally": ["Kukatpally Main Road", "KPHB Kukatpally", "Moosapet Kukatpally", "Bhavani Nagar Kukatpally"],
        "ameerpet": ["Ameerpet Main Road", "SR Nagar Ameerpet", "Punjagutta Ameerpet", "Erramanzil Ameerpet"],
        "secunderabad": ["Secunderabad Main Road", "SD Road Secunderabad", "MG Road Secunderabad", "Paradise Secunderabad"],
        "begumpet": ["Begumpet Main Road", "Begumpet Colony", "Somajiguda Begumpet", "Raj Bhavan Road Begumpet"],
        "t nagar": ["T Nagar Main Road", "Usman Road T Nagar", "Venkatnarayana Road T Nagar", "GN Chetty Road T Nagar"],
        "anna nagar": ["Anna Nagar Main Road", "Anna Nagar 2nd Avenue", "Anna Nagar Tower", "Anna Nagar West"],
        "koramangala": ["Koramangala 1st Block", "Koramangala 4th Block", "Koramangala 5th Block", "Koramangala 6th Block", "Koramangala 7th Block"],
        "indiranagar": ["Indiranagar 100 Feet Road", "Indiranagar 12th Main", "Indiranagar CMH Road", "Indiranagar Double Road"],
    }

    city_hubs_fallback = {
        "hyderabad": ["Madhapur", "Banjara Hills", "Jubilee Hills", "Hitech City", "Gachibowli", "Secunderabad", "Kukatpally", "Ameerpet", "Begumpet", "Kondapur", "Manikonda", "Miyapur", "LB Nagar", "Dilsukhnagar", "Mehdipatnam"],
        "chennai": ["T Nagar", "Anna Nagar", "Adyar", "Velachery", "Nungambakkam", "Mylapore", "Tambaram", "OMR", "Porur", "Chromepet"],
        "bangalore": ["Koramangala", "Indiranagar", "Whitefield", "Electronic City", "Jayanagar", "HSR Layout", "Marathahalli", "JP Nagar", "Bannerghatta", "BTM Layout"],
        "vijayawada": ["Benz Circle", "MG Road", "Governorpet", "Labbipet", "Patamata", "Gunadala", "Suryaraopet", "Eluru Road", "Auto Nagar", "Kandrika"],
        "guntur": ["Brodipet", "Arundelpet", "Kothapet", "AT Agraharam", "Old Town", "Amaravathi Road", "Vidyanagar", "Nallapadu", "Naaz Centre", "Brindavan Gardens"],
    }

    specific_regions = []
    
    # 1. Try Gemini AI for specific sub-regions
    gemini_key = os.environ.get("GEMINI_API_KEY", "")
    if gemini_key:
        try:
            import google.generativeai as genai
            genai.configure(api_key=gemini_key)
            model = genai.GenerativeModel("gemini-1.5-flash")
            prompt = f"""You are a local area expert for {city}, India.
For the area "{region}" in {city}, list all specific sub-areas, phases, road numbers, sectors, and localities where {keyword} businesses might be found.
Be very specific — include road numbers, phase numbers, colony names, sector numbers.
Return ONLY a JSON array of strings. No other text. No markdown."""
            response = model.generate_content(prompt)
            raw = response.text.strip().replace("```json","").replace("```","").strip()
            import json
            sub_regions = json.loads(raw)
            if isinstance(sub_regions, list) and len(sub_regions) > 0:
                specific_regions = sub_regions[:15]
        except Exception as e:
            st.session_state.logs += f"[SYS] AI sub-region failed: {e}\n"

    # 2. If AI failed, try hardcoded area fallback
    if not specific_regions:
        region_lower = region.lower()
        for key, regions in specific_area_fallback.items():
            if key in region_lower:
                specific_regions = regions
                break

    # 3. Get City Hubs Fallback
    city_hubs = []
    city_lower = city.lower()
    for key, regions in city_hubs_fallback.items():
        if key in city_lower:
            city_hubs = regions
            break

    # 4. Combine Everything
    # Rules: Specific first, then City Hubs, No Duplicates
    combined = []
    seen = set()
    
    for r in specific_regions:
        if r.lower() not in seen:
            combined.append(r)
            seen.add(r.lower())
            
    for r in city_hubs:
        if r.lower() not in seen:
            combined.append(r)
            seen.add(r.lower())
            
    if not combined:
        return [region or city]
        
    return combined[:25] # Return top 25 areas to ensure we hit 100 leads

def generation_ui(label_suffix=""):
    # Import subscription module
    from subscription import (
        get_max_leads, can_use_linkedin, can_use_ai,
        get_upgrade_message, render_upgrade_banner, get_plan
    )

    # Get current user plan
    current_plan = st.session_state.get("plan", "Free")
    max_allowed = get_max_leads(current_plan)

    st.markdown(f"### 🔍 Start New Extraction {label_suffix}")

    with st.container():
        # Row 1 — Category and Business Type
        c1, c2, c3 = st.columns([2, 2, 1])
        with c1:
            category = st.selectbox(
                "Business Category",
                [
                    "Restaurants", "Hotels", "Hospitals", "Clinics",
                    "IT Companies", "Schools", "Colleges", "Banks",
                    "Gyms", "Salons", "Bakeries", "Cafes",
                    "Pharmacies", "Real Estate", "Law Firms",
                    "Chartered Accountants", "Architects", "Dentists",
                    "Coaching Centers", "Garments", "Electronics",
                    "Auto Dealers", "Logistics", "Custom..."
                ],
                key=f"cat_{label_suffix}"
            )
        with c2:
            custom_keyword = st.text_input(
                "Custom Keyword (optional)",
                placeholder="e.g. Biryani shops, Car wash",
                key=f"custom_{label_suffix}"
            )
        with c3:
            source = st.selectbox("Source", ["Google Maps", "LinkedIn"], key=f"src_{label_suffix}")

        # Row 2 — City and Region
        c3, c4 = st.columns(2)
        with c3:
            city = st.text_input(
                "City",
                placeholder="e.g. Hyderabad",
                key=f"city_{label_suffix}"
            )
        with c4:
            region = st.text_input(
                "Region / Area",
                placeholder="e.g. KPHB, Banjara Hills",
                key=f"region_{label_suffix}"
            )

        # Row 3 — Max leads, AI toggle, Source
        c5, c6, c7 = st.columns([2, 1, 1])
        with c5:
            max_leads = st.slider(
                f"Max Leads / Session (Plan limit: {max_allowed})",
                min_value=10,
                max_value=min(max_allowed, 1000), # Cap slider at 1000 for UI, or use max_allowed
                value=min(50, max_allowed),
                step=10,
                key=f"max_{label_suffix}"
            )
        with c6:
            st.markdown("<br>", unsafe_allow_html=True)
            ai_allowed = can_use_ai(current_plan)
            use_ai = st.toggle(
                "🤖 Enable AI Scoring",
                value=False,
                disabled=not ai_allowed,
                help=get_upgrade_message(current_plan, "ai_scoring") if not ai_allowed else "Enable AI lead scoring",
                key=f"ai_{label_suffix}"
            )
            if not ai_allowed:
                st.caption(f"🔒 AI Scoring requires Starter plan. You are on {current_plan}.")
        with c7:
            st.markdown("<br>", unsafe_allow_html=True)
            btn_generate = st.button(
                "🚀 Generate Leads",
                disabled=st.session_state.is_scraping,
                key=f"btn_{label_suffix}",
                use_container_width=True
            )

    if btn_generate:
        # Enforce lead cap
        if max_leads > max_allowed:
            st.error(f"Your {current_plan} plan allows max {max_allowed} leads per session.")
            render_upgrade_banner(current_plan)
            return

        # When LinkedIn is selected but not allowed
        if source == "LinkedIn" and not can_use_linkedin(current_plan):
            st.error(get_upgrade_message(current_plan, "linkedin"))
            render_upgrade_banner(current_plan)
            st.stop()

        # Build keyword
        keyword = custom_keyword.strip() if custom_keyword.strip() else category

        if not city:
            st.warning("Please enter a city name.")
            return

        # Build base query
        if region.strip():
            base_query = f"{keyword} in {region} {city}"
        else:
            base_query = f"{keyword} in {city}"

        st.session_state.is_scraping = True
        st.session_state.session_leads = []
        st.session_state.logs = ""

        progress_bar = st.progress(0)
        status_text = st.empty()
        log_placeholder = st.empty()
        metrics_placeholder = st.empty()
        table_placeholder = st.empty()

        with metrics_placeholder.container():
            m1, m2, m3 = st.columns(3)
            m1_metric = m1.empty()
            m2_metric = m2.empty()
            m3_metric = m3.empty()

        # Step 1 — Generate sub-regions using AI
        if source == "LinkedIn":
            status_text.text("🔍 Searching LinkedIn profiles...")
            try:
                from linkedin_scraper import scrape_linkedin
                
                # Fetch existing maps leads for cross-linking
                try:
                    df_master = database.load_db()
                    maps_leads = df_master.to_dict('records') if not df_master.empty else []
                except:
                    maps_leads = []
                    
                profiles = scrape_linkedin(keyword, city if not region else f"{region} {city}", maps_leads=maps_leads, limit=max_leads)
                
                for i, profile in enumerate(profiles):
                    # Apply AI Scoring here so UI updates per lead
                    if use_ai:
                        try:
                            from ai_engine import analyze_single_lead
                            profile = analyze_single_lead(profile)
                        except Exception as e:
                            print(f"LOG:AI Enrichment Error: {e}", flush=True)
                            
                    st.session_state.session_leads.append(profile)
                    progress_bar.progress((i+1)/max(len(profiles),1))
                    status_text.text(f"LinkedIn: {i+1}/{len(profiles)} profiles collected & scored...")
                    m1_metric.metric("Total Scraped", i+1)
                    m2_metric.metric("Valid Leads", i+1)
                    m3_metric.metric("Duplicates Skipped", 0)
                    with table_placeholder.container():
                        df_view = pd.DataFrame(st.session_state.session_leads)
                        cols = [c for c in ["name","description","website","validation_status"] if c in df_view.columns]
                        st.dataframe(df_view[cols] if cols else df_view, hide_index=True)
                
                database.save_to_db(st.session_state.session_leads)
                success, msg = google_sheets.save_to_google_sheets(st.session_state.session_leads)
                if success:
                    st.success(f"✅ {len(profiles)} LinkedIn profiles saved!")
                else:
                    st.warning(f"Saved locally. Sheets: {msg}")
            except Exception as e:
                st.error(f"LinkedIn error: {e}")
            
            st.session_state.is_scraping = False
            time.sleep(1)
            st.rerun()
            return

        # Step 1 — Generate sub-regions using AI (for Google Maps)
        status_text.text(f"🤖 AI analyzing sub-regions for {region or city}...")
        st.session_state.logs += f"[SYS] Generating sub-regions for {region or city}...\n"
        log_placeholder.markdown(
            f'<div class="log-box">{st.session_state.logs}</div>',
            unsafe_allow_html=True
        )

        sub_regions = get_sub_regions_ai(keyword, region or city, city)

        st.session_state.logs += f"[SYS] Found {len(sub_regions)} sub-regions\n"
        for sr in sub_regions:
            st.session_state.logs += f"[SYS]  → {sr}\n"
        log_placeholder.markdown(
            f'<div class="log-box">{st.session_state.logs[-3000:]}</div>',
            unsafe_allow_html=True
        )

        # Step 2 — Scrape each sub-region
        collected_count = 0
        duplicates_skipped = 0
        target_total = max_leads

        for sub_region in sub_regions:
            if collected_count >= target_total:
                break

            query = f"{keyword} in {sub_region} {city}"
            status_text.text(f"🔄 Scraping: {query} ({collected_count}/{target_total})")
            st.session_state.logs += f"[SYS] Scraping: {query}\n"
            log_placeholder.markdown(
                f'<div class="log-box">{st.session_state.logs[-3000:]}</div>',
                unsafe_allow_html=True
            )

            ai_flag = "1" if use_ai else "0"
            batch_target = min(10, target_total - collected_count)

            process = subprocess.Popen(
                [sys.executable, "scraper.py", query, str(batch_target), ai_flag],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True
            )

            for line in process.stdout:
                line = line.strip()
                if line.startswith("DATA:"):
                    try:
                        data = json.loads(line.replace("DATA:", "").strip())
                        # Check duplicate by name
                        existing_names = [l.get("name","").lower() for l in st.session_state.session_leads]
                        if data.get("name","").lower() not in existing_names:
                            st.session_state.session_leads.append(data)
                            database.save_to_db([data])
                            collected_count = len(st.session_state.session_leads)
                        else:
                            duplicates_skipped += 1

                        valid_count = len([x for x in st.session_state.session_leads if x.get("validation_status") == "Valid"])
                        m1_metric.metric("Total Scraped", collected_count)
                        m2_metric.metric("Valid Leads", valid_count)
                        m3_metric.metric("Duplicates Skipped", duplicates_skipped)
                        progress_bar.progress(min(collected_count / target_total, 1.0))

                        with table_placeholder.container():
                            df_view = pd.DataFrame(st.session_state.session_leads).iloc[::-1]
                            cols = [c for c in ["name", "phone", "email", "sub_region", "validation_status"] if c in df_view.columns]
                            st.dataframe(df_view[cols] if cols else df_view, hide_index=True)
                    except: pass

                elif line.startswith("LOG:"):
                    msg = line.replace("LOG:", "").strip()
                    st.session_state.logs += f"[SYS] {msg}\n"
                    log_placeholder.markdown(
                        f'<div class="log-box">{st.session_state.logs[-3000:]}</div>',
                        unsafe_allow_html=True
                    )

            process.wait()

            if collected_count >= target_total:
                break

        # Step 3 — Save to Google Sheets
        status_text.text("✅ Extraction Complete! Syncing to Cloud...")
        success, msg = google_sheets.save_to_google_sheets(st.session_state.session_leads)
        if success:
            st.success(f"✅ {collected_count} leads collected from {len(sub_regions)} sub-regions!")

        st.session_state.is_scraping = False
        import time
        time.sleep(2)
        st.rerun()

# ==========================================
# USER DASHBOARD
# ==========================================
def show_user_analytics(username: str) -> None:
    """
    Day 15 — User Dashboard Analytics
    5 charts using plotly:
    1. Leads this month counter
    2. Valid/Invalid donut chart
    3. Top categories bar chart
    4. Leads by sub-region chart
    5. Session history table
    """
    try:
        import plotly.express as px
        import plotly.graph_objects as go
        import pandas as pd
        from datetime import datetime, timedelta

        # Load user leads from database
        df = database.load_db()

        if df.empty:
            st.info("No leads data yet. Generate leads to see analytics.")
            return

        # ==========================================
        # METRIC 1 — Leads This Month Counter
        # ==========================================
        st.markdown("### 📊 Your Analytics Dashboard")

        today = datetime.now()
        current_month = today.strftime("%Y-%m")
        last_month = (today - timedelta(days=30)).strftime("%Y-%m")

        date_col = "scraped_date" if "scraped_date" in df.columns else "timestamp"
        if date_col in df.columns:
            df[date_col] = df[date_col].astype(str)
            this_month_leads = df[df[date_col].str.startswith(current_month)]
            last_month_leads = df[df[date_col].str.startswith(last_month)]
            this_count = len(this_month_leads)
            last_month_leads_list = last_month_leads.to_dict('records')
            last_count = len(last_month_leads_list)
            delta = this_count - last_count
        else:
            this_count = len(df)
            delta = 0

        # Metric cards row
        m1, m2, m3, m4 = st.columns(4)
        with m1:
            st.metric(
                "Leads This Month",
                this_count,
                delta=f"{delta:+d} vs last month"
            )
        with m2:
            valid = len(df[df.get("validation_status", pd.Series(dtype='object')) == "Valid"]) if "validation_status" in df.columns else 0
            st.metric("Valid Leads", valid)
        with m3:
            total = len(df)
            quality = int((valid / total * 100)) if total > 0 else 0
            st.metric("Data Quality", f"{quality}%")
        with m4:
            categories = df["category"].nunique() if "category" in df.columns else 0
            st.metric("Categories", categories)

        st.markdown("---")

        # ==========================================
        # CHART 1 — Valid/Invalid Donut Chart
        # ==========================================
        col1, col2 = st.columns(2)

        with col1:
            st.markdown("**Validation Status Distribution**")
            if "validation_status" in df.columns:
                status_counts = df["validation_status"].value_counts().reset_index()
                status_counts.columns = ["Status", "Count"]
                colors = {
                    "Valid": "#22C55E",
                    "Invalid": "#EF4444",
                    "Pending": "#F59E0B"
                }
                color_list = [colors.get(s, "#94A3B8") for s in status_counts["Status"]]
                fig1 = go.Figure(data=[go.Pie(
                    labels=status_counts["Status"],
                    values=status_counts["Count"],
                    hole=0.5,
                    marker_colors=color_list
                )])
                fig1.update_layout(
                    height=300,
                    margin=dict(t=20, b=20, l=20, r=20),
                    showlegend=True,
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)"
                )
                st.plotly_chart(fig1, use_container_width=True)
            else:
                st.info("No validation data available")

        # ==========================================
        # CHART 2 — Top Categories Bar Chart
        # ==========================================
        with col2:
            st.markdown("**Top 10 Business Categories**")
            if "category" in df.columns:
                cat_counts = df["category"].value_counts().head(10).reset_index()
                cat_counts.columns = ["Category", "Count"]
                fig2 = px.bar(
                    cat_counts,
                    x="Count",
                    y="Category",
                    orientation="h",
                    color="Count",
                    color_continuous_scale="Blues",
                    height=300
                )
                fig2.update_layout(
                    margin=dict(t=20, b=20, l=20, r=20),
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    showlegend=False,
                    coloraxis_showscale=False
                )
                fig2.update_xaxes(showgrid=False)
                fig2.update_yaxes(showgrid=False)
                st.plotly_chart(fig2, use_container_width=True)
            else:
                st.info("No category data available")

        st.markdown("---")

        # ==========================================
        # CHART 3 — Leads by Sub-Region Chart
        # ==========================================
        col3, col4 = st.columns(2)

        with col3:
            st.markdown("**Leads by Sub-Region**")
            if "sub_region" in df.columns:
                region_counts = df[df["sub_region"].notna() & (df["sub_region"] != "")]
                if not region_counts.empty:
                    region_counts = region_counts["sub_region"].value_counts().head(10).reset_index()
                    region_counts.columns = ["Sub-Region", "Count"]
                    fig3 = px.bar(
                        region_counts,
                        x="Sub-Region",
                        y="Count",
                        color="Count",
                        color_continuous_scale="Greens",
                        height=300
                    )
                    fig3.update_layout(
                        margin=dict(t=20, b=20, l=20, r=20),
                        paper_bgcolor="rgba(0,0,0,0)",
                        plot_bgcolor="rgba(0,0,0,0)",
                        xaxis_tickangle=-45,
                        coloraxis_showscale=False
                    )
                    fig3.update_xaxes(showgrid=False)
                    fig3.update_yaxes(showgrid=False)
                    st.plotly_chart(fig3, use_container_width=True)
                else:
                    st.info("No sub-region data available")
            else:
                st.info("No sub-region data available")

        # ==========================================
        # CHART 4 — Leads Over Time Line Chart
        # ==========================================
        with col4:
            st.markdown("**Leads Collected Over Time**")
            if date_col in df.columns:
                try:
                    df["date_only"] = pd.to_datetime(
                        df[date_col].str[:10],
                        errors="coerce"
                    )
                    daily = df.groupby("date_only").size().reset_index(name="Count")
                    daily = daily.sort_values("date_only")
                    fig4 = px.line(
                        daily,
                        x="date_only",
                        y="Count",
                        markers=True,
                        height=300,
                        color_discrete_sequence=["#2563EB"]
                    )
                    fig4.update_layout(
                        margin=dict(t=20, b=20, l=20, r=20),
                        paper_bgcolor="rgba(0,0,0,0)",
                        plot_bgcolor="rgba(0,0,0,0)",
                        xaxis_title="Date",
                        yaxis_title="Leads"
                    )
                    fig4.update_xaxes(showgrid=False)
                    fig4.update_yaxes(showgrid=False)
                    st.plotly_chart(fig4, use_container_width=True)
                except Exception as e:
                    st.info(f"Timeline chart unavailable: {e}")
            else:
                st.info("No date data available")

        st.markdown("---")

        # ==========================================
        # CHART 5 — Session History Table
        # ==========================================
        st.markdown("**📋 Session History**")
        if date_col in df.columns:
            try:
                df["date_only"] = pd.to_datetime(
                    df[date_col].str[:10],
                    errors="coerce"
                )
                session_history = df.groupby("date_only").agg(
                    leads_collected=("lead_id", "count"),
                    valid_leads=("validation_status", lambda x: (x == "Valid").sum()),
                    categories=("category", lambda x: ", ".join([str(i) for i in x.dropna().unique()[:3]]))
                ).reset_index()
                session_history = session_history.sort_values(
                    "date_only", ascending=False
                ).head(10)
                session_history.columns = [
                    "Date", "Leads Collected",
                    "Valid Leads", "Categories"
                ]
                st.dataframe(
                    session_history,
                    hide_index=True,
                    use_container_width=True
                )
            except Exception as e:
                st.info(f"Session history unavailable: {e}")
        else:
            st.info("No session history available")

    except ImportError:
        st.error("Plotly not installed. Add 'plotly' to requirements.txt")
    except Exception as e:
        st.error(f"Analytics error: {e}")

def show_user_dashboard():
    st.markdown('<h1 class="main-title">User Workspace</h1>', unsafe_allow_html=True)

    # Metric cards at top
    total_db, today_db, quality_pct = get_stats()
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(f'<div class="metric-card"><div class="metric-label">Session Leads</div><div class="metric-value">{len(st.session_state.session_leads)}</div></div>', unsafe_allow_html=True)
    with c2:
        st.markdown(f'<div class="metric-card"><div class="metric-label">Data Accuracy</div><div class="metric-value">{quality_pct}%</div></div>', unsafe_allow_html=True)
    with c3:
        status_text = "ACTIVE" if st.session_state.is_scraping else "IDLE"
        st.markdown(f'<div class="metric-card"><div class="metric-label">Engine Status</div><div class="metric-value">{status_text}</div></div>', unsafe_allow_html=True)
    with c4:
        gs_connected = google_sheets.check_connection()
        gs_text = "Connected" if gs_connected else "Offline"
        st.markdown(f'<div class="metric-card"><div class="metric-label">Cloud Sync</div><div class="metric-value">{gs_text}</div></div>', unsafe_allow_html=True)

    st.markdown("<br><hr><br>", unsafe_allow_html=True)

    # Tabs
    tabs = st.tabs(["🚀 Generate", "⚡ My Leads", "📊 Analytics", "💳 Billing"])

    with tabs[0]:
        generation_ui()

    with tabs[1]:
        if st.session_state.session_leads:
            st.markdown("### ⚡ My Leads Table")
            df = pd.DataFrame(st.session_state.session_leads)
            status_filter = st.multiselect(
                "Filter by Status",
                options=df["validation_status"].unique() if "validation_status" in df.columns else []
            )
            if status_filter and "validation_status" in df.columns:
                df = df[df["validation_status"].isin(status_filter)]
            user_cols = ["name", "address", "phone", "email", "rating", "reviews", "category", "validation_status"]
            st.dataframe(df_leads[[c for c in user_cols if c in df_leads.columns]], hide_index=True)
            st.markdown("---")
            # Export UI
            render_export_ui(df_leads, "Export My Leads")
        else:
            st.info("💡 Generate leads first to see your leads table.")

    with tabs[2]:
        show_user_analytics(st.session_state.get("username", ""))

    with tabs[3]:
        render_billing_tab()

# ==========================================
# ADMIN DASHBOARD
# ==========================================
def show_admin_dashboard():
    st.markdown('<h1 class="main-title">Admin Dashboard</h1>', unsafe_allow_html=True)
    st.markdown('<p class="sub-title">Full system access, user management, and master database control</p>', unsafe_allow_html=True)

    # ==========================================
    # PLATFORM OVERVIEW PANEL
    # ==========================================
    from auth import get_all_users
    from subscription import get_plan

    all_users = get_all_users()
    df_master = database.load_db()
    total_leads = len(df_master)
    valid_leads = len(df_master[df_master["validation_status"] == "Valid"]) if "validation_status" in df_master.columns else 0
    quality_pct = int((valid_leads / total_leads * 100)) if total_leads > 0 else 0

    # Calculate MRR
    plan_revenue = {"Free": 0, "Starter": 29, "Pro": 79, "Enterprise": 500}
    mrr = sum(plan_revenue.get(u.get("plan", "Free"), 0) for u in all_users)

    # Top row metrics
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        st.markdown(f'<div class="metric-card"><div class="metric-label">Total Leads</div><div class="metric-value">{total_leads}</div></div>', unsafe_allow_html=True)
    with c2:
        st.markdown(f'<div class="metric-card"><div class="metric-label">Active Users</div><div class="metric-value">{len(all_users)}</div></div>', unsafe_allow_html=True)
    with c3:
        st.markdown(f'<div class="metric-card"><div class="metric-label">Global Quality</div><div class="metric-value">{quality_pct}%</div></div>', unsafe_allow_html=True)
    with c4:
        st.markdown(f'<div class="metric-card"><div class="metric-label">MRR</div><div class="metric-value">${mrr}</div></div>', unsafe_allow_html=True)
    with c5:
        paid_users = sum(1 for u in all_users if u.get("plan", "Free") != "Free")
        st.markdown(f'<div class="metric-card"><div class="metric-label">Paid Users</div><div class="metric-value">{paid_users}</div></div>', unsafe_allow_html=True)

    st.markdown("<br><hr><br>", unsafe_allow_html=True)

    # ==========================================
    # TABS
    # ==========================================
    tabs = st.tabs([
        "🚀 Generate",
        "🗄️ Master Database",
        "👥 User Management",
        "📜 Activity Logs",
        "📊 Analytics",
        "💰 Revenue",
        "🛠️ System Settings"
    ])

    # ==========================================
    # TAB 1 — Generate
    # ==========================================
    with tabs[0]:
        generation_ui("(Admin)")
        if not st.session_state.is_scraping and st.session_state.session_leads:
            st.markdown("### ⚡ Session Preview")
            st.dataframe(pd.DataFrame(st.session_state.session_leads), hide_index=True)

    # ==========================================
    # TAB 2 — Master Database
    # ==========================================
    with tabs[1]:
        st.markdown("### 🗄️ Master Lead Repository")
        if not df_master.empty:
            # Analytics charts
            import plotly.express as px
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("**Top Categories**")
                if "category" in df_master.columns:
                    cat_counts = df_master["category"].value_counts().head(8).reset_index()
                    cat_counts.columns = ["Category", "Count"]
                    fig = px.bar(cat_counts, x="Category", y="Count", color="Count", color_continuous_scale="Blues", height=280)
                    fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", margin=dict(t=10,b=10,l=10,r=10), coloraxis_showscale=False)
                    fig.update_xaxes(showgrid=False, tickangle=-45)
                    fig.update_yaxes(showgrid=False)
                    st.plotly_chart(fig, use_container_width=True)
            with col2:
                st.markdown("**Validation Distribution**")
                if "validation_status" in df_master.columns:
                    val_counts = df_master["validation_status"].value_counts().reset_index()
                    val_counts.columns = ["Status", "Count"]
                    colors = {"Valid": "#22C55E", "Invalid": "#EF4444", "Pending": "#F59E0B"}
                    color_list = [colors.get(s, "#94A3B8") for s in val_counts["Status"]]
                    import plotly.graph_objects as go
                    fig2 = go.Figure(data=[go.Pie(labels=val_counts["Status"], values=val_counts["Count"], hole=0.5, marker_colors=color_list)])
                    fig2.update_layout(paper_bgcolor="rgba(0,0,0,0)", height=280, margin=dict(t=10,b=10,l=10,r=10))
                    st.plotly_chart(fig2, use_container_width=True)

            st.markdown("---")
            # Filter options
            col3, col4, col5 = st.columns(3)
            with col3:
                status_filter = st.multiselect("Filter by Status", df_master["validation_status"].unique() if "validation_status" in df_master.columns else [])
            with col4:
                cat_filter = st.multiselect("Filter by Category", df_master["category"].unique() if "category" in df_master.columns else [])
            with col5:
                search_term = st.text_input("Search by name", placeholder="Type to search...")

            filtered_df = df_master.copy()
            if status_filter:
                filtered_df = filtered_df[filtered_df["validation_status"].isin(status_filter)]
            if cat_filter:
                filtered_df = filtered_df[filtered_df["category"].isin(cat_filter)]
            if search_term:
                filtered_df = filtered_df[filtered_df["name"].str.contains(search_term, case=False, na=False)]

            st.markdown(f"**Showing {len(filtered_df)} of {len(df_master)} leads**")
            st.dataframe(filtered_df, hide_index=True, use_container_width=True)

            # Export UI
            st.markdown("---")
            render_export_ui(filtered_df, "Export Master Database")
        else:
            st.info("No leads in database yet.")

    # ==========================================
    # TAB 3 — User Management (CRUD)
    # ==========================================
    with tabs[2]:
        st.markdown("### 👥 User Management")

        # Users table
        if all_users:
            df_users = pd.DataFrame(all_users)
            st.dataframe(df_users, hide_index=True, use_container_width=True)
        else:
            st.info("No users found")

        st.markdown("---")

        # CRUD operations
        crud_col1, crud_col2 = st.columns(2)

        with crud_col1:
            with st.expander("➕ Create New User"):
                from auth import register_user
                u_name = st.text_input("Username", key="crud_u_name")
                u_pass = st.text_input("Password", type="password", key="crud_u_pass")
                u_role = st.selectbox("Role", ["user", "admin"], key="crud_u_role")
                u_plan = st.selectbox("Plan", ["Free", "Starter", "Pro", "Enterprise"], key="crud_u_plan")
                u_email = st.text_input("Email", key="crud_u_email")
                if st.button("Create User", key="crud_create"):
                    success, msg = register_user(u_name, u_pass, u_role, u_plan, u_name, u_email)
                    st.success(msg) if success else st.error(msg)
                    if success:
                        st.rerun()

            with st.expander("✏️ Edit User Plan"):
                from auth import update_user_plan
                edit_username = st.text_input("Username to edit", key="crud_edit_name")
                new_plan = st.selectbox("New Plan", ["Free", "Starter", "Pro", "Enterprise"], key="crud_edit_plan")
                if st.button("Update Plan", key="crud_update"):
                    if update_user_plan(edit_username, new_plan):
                        st.success(f"Plan updated for {edit_username}")
                        st.rerun()
                    else:
                        st.error("User not found")

        with crud_col2:
            with st.expander("🔑 Reset Password"):
                from auth import update_password
                reset_user = st.text_input("Username", key="crud_reset_name")
                reset_pass = st.text_input("New Password", type="password", key="crud_reset_pass")
                if st.button("Reset Password", key="crud_reset"):
                    if update_password(reset_user, reset_pass):
                        st.success(f"Password reset for {reset_user}")
                    else:
                        st.error("User not found")

            with st.expander("🚫 Suspend / Delete User"):
                from auth import delete_user
                del_user = st.text_input("Username to delete", key="crud_del_name")
                st.warning("⚠️ This action is permanent")
                if st.button("Delete User", key="crud_delete", type="primary"):
                    if delete_user(del_user):
                        st.success(f"User {del_user} deleted")
                        st.rerun()
                    else:
                        st.error("Cannot delete user or user not found")

    # ==========================================
    # TAB 4 — Activity Logs
    # ==========================================
    with tabs[3]:
        st.markdown("### 📜 System Activity Logs")
        try:
            logs_df = database.get_logs()
            if not logs_df.empty:
                st.dataframe(logs_df, hide_index=True, use_container_width=True)
            else:
                st.info("No activity logs yet")
        except Exception as e:
            st.info(f"Logs unavailable: {e}")

    # ==========================================
    # TAB 5 — Analytics
    # ==========================================
    with tabs[4]:
        st.markdown("### 📊 Platform Analytics")
        if not df_master.empty:
            import plotly.express as px

            col1, col2 = st.columns(2)

            with col1:
                st.markdown("**Leads Per Day**")
                date_col = "scraped_date" if "scraped_date" in df_master.columns else "timestamp"
                if date_col in df_master.columns:
                    try:
                        df_master["date_only"] = pd.to_datetime(df_master[date_col].str[:10], errors="coerce")
                        daily = df_master.groupby("date_only").size().reset_index(name="Count")
                        fig = px.line(daily, x="date_only", y="Count", markers=True, color_discrete_sequence=["#2563EB"], height=280)
                        fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", margin=dict(t=10,b=10,l=10,r=10))
                        fig.update_xaxes(showgrid=False)
                        fig.update_yaxes(showgrid=False)
                        st.plotly_chart(fig, use_container_width=True)
                    except Exception as e:
                        st.info(f"Chart unavailable: {e}")

            with col2:
                st.markdown("**Users by Plan**")
                plan_counts = {}
                for u in all_users:
                    plan = u.get("plan", "Free")
                    plan_counts[plan] = plan_counts.get(plan, 0) + 1
                plan_df = pd.DataFrame(list(plan_counts.items()), columns=["Plan", "Users"])
                fig3 = px.pie(plan_df, names="Plan", values="Users", hole=0.4, color_discrete_sequence=px.colors.qualitative.Set2, height=280)
                fig3.update_layout(paper_bgcolor="rgba(0,0,0,0)", margin=dict(t=10,b=10,l=10,r=10))
                st.plotly_chart(fig3, use_container_width=True)

            # Scraper performance stats
            st.markdown("---")
            st.markdown("**Scraper Performance**")
            perf_col1, perf_col2, perf_col3, perf_col4 = st.columns(4)
            with perf_col1:
                avg_per_session = total_leads // max(len(all_users), 1)
                st.metric("Avg Leads/User", avg_per_session)
            with perf_col2:
                st.metric("Total Valid", valid_leads)
            with perf_col3:
                categories_count = df_master["category"].nunique() if "category" in df_master.columns else 0
                st.metric("Categories Scraped", categories_count)
            with perf_col4:
                sources = df_master["source"].nunique() if "source" in df_master.columns else 1
                st.metric("Data Sources", sources)

            # Lead quality report
            st.markdown("---")
            st.markdown("**Lead Quality Report**")
            if "validation_status" in df_master.columns:
                quality_data = {
                    "Valid": len(df_master[df_master["validation_status"] == "Valid"]),
                    "Invalid": len(df_master[df_master["validation_status"] == "Invalid"]),
                    "Pending": len(df_master[df_master["validation_status"] == "Pending"])
                }
                for status, count in quality_data.items():
                    pct = int(count / total_leads * 100) if total_leads > 0 else 0
                    st.progress(pct / 100, text=f"{status}: {count} leads ({pct}%)")
        else:
            st.info("Generate leads to see analytics")

    # ==========================================
    # TAB 6 — Revenue
    # ==========================================
    with tabs[5]:
        render_admin_billing()

    # ==========================================
    # TAB 7 — System Settings
    # ==========================================
    with tabs[6]:
        st.markdown("### ⚙️ System Settings")

        st.markdown("#### ☁️ Google Sheets Sync")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔄 Force Cloud Sync", use_container_width=True):
                with st.spinner("Syncing..."):
                    df_local = database.load_db()
                    if not df_local.empty:
                        success, msg = google_sheets.save_to_google_sheets(df_local.to_dict("records"))
                        st.success(f"✅ {msg}") if success else st.error(f"❌ {msg}")
                    else:
                        st.warning("No leads to sync")
        with col2:
            gs_status = "✅ Connected" if google_sheets.check_connection() else "❌ Offline"
            st.info(f"Google Sheets: {gs_status}")

        st.markdown("---")
        st.markdown("#### 🔑 API Keys Status")
        api_keys = {
            "SERPER_API_KEY": os.environ.get("SERPER_API_KEY", ""),
            "GEMINI_API_KEY": os.environ.get("GEMINI_API_KEY", ""),
            "APOLLO_API_KEY": os.environ.get("APOLLO_API_KEY", ""),
            "STRIPE_SECRET_KEY": os.environ.get("STRIPE_SECRET_KEY", ""),
            "APIFY_API_TOKEN": os.environ.get("APIFY_API_TOKEN", "")
        }
        col3, col4 = st.columns(2)
        for i, (key, value) in enumerate(api_keys.items()):
            with col3 if i % 2 == 0 else col4:
                if value:
                    masked = value[:8] + "..." + value[-4:]
                    st.success(f"✅ {key}: {masked}")
                else:
                    st.error(f"❌ {key}: Not configured")

        st.markdown("---")
        st.markdown("#### 💾 Database Info")
        db_col1, db_col2, db_col3 = st.columns(3)
        db_type = "PostgreSQL (Render)" if os.environ.get("DATABASE_URL") else "SQLite (Local)"
        with db_col1:
            st.metric("Database", db_type)
        with db_col2:
            st.metric("Total Leads", total_leads)
        with db_col3:
            st.metric("Valid Leads", valid_leads)

        st.markdown("---")
        st.markdown("#### 🗑️ Data Management")
        dm_col1, dm_col2, dm_col3 = st.columns(3)
        with dm_col1:
            csv_master = df_master.to_csv(index=False).encode("utf-8")
            st.download_button("📥 Master CSV", csv_master, "master.csv", "text/csv", use_container_width=True)
        with dm_col2:
            json_master = df_master.to_json(orient="records").encode("utf-8")
            st.download_button("📥 Master JSON", json_master, "master.json", "application/json", use_container_width=True)
        with dm_col3:
            if st.button("🚨 Wipe System", use_container_width=True):
                database.clear_all_leads()
                google_sheets.clear_sheet_data()
                st.success("✅ System wiped")
                time.sleep(1)
                st.rerun()

        st.markdown("---")
        st.markdown("#### ℹ️ About LeadPulse Pro")
        st.markdown("""
        | Item | Detail |
        |---|---|
        | **Version** | v1.0 — Phase 2 Complete |
        | **Project Code** | LGP-2025-001 |
        | **Build Days** | 16 of 21 complete |
        | **Stack** | Streamlit + Serper + Gemini + Stripe |
        | **Deployment** | Render Free Tier |
        | **AI Provider** | Google Gemini 1.5 Flash |
        """)

# ==========================================
# MAIN ROUTING
# ==========================================
with st.sidebar:
    st.markdown(f"""
        <div class="sidebar-logo">
            🚀 LeadPulse <span>Pro</span>
        </div>
        <div class="sidebar-divider"></div>
    """, unsafe_allow_html=True)
    
    # Show plan badge in sidebar
    plan_colors = {
        "Free": "#94A3B8",
        "Starter": "#22C55E",
        "Pro": "#3B82F6",
        "Enterprise": "#F59E0B"
    }
    current_plan = st.session_state.get("plan", "Free")
    plan_color = plan_colors.get(current_plan, "#94A3B8")
    st.markdown(f"""
        <div style="padding:0 1rem 1rem 1rem;">
            Logged in as: <strong>{st.session_state.username}</strong><br>
            Plan: <span style="color:{plan_color}; font-weight:700;">{current_plan}</span>
        </div>
    """, unsafe_allow_html=True)
    st.markdown('<div class="sidebar-divider"></div>', unsafe_allow_html=True)
    
    role_label = "Admin Workspace" if st.session_state.role == "admin" else "User Workspace"
    st.markdown(f'<div class="nav-item-active">🏠 {role_label}</div>', unsafe_allow_html=True)
    st.markdown("<br><br><br>", unsafe_allow_html=True)
    
    st.markdown(f"""
        <div style="padding: 1rem; background: rgba(255,255,255,0.03); border-radius: 8px;">
            <p style="margin:0; font-size: 0.7rem; color: #94A3B8 !important;">ENGINE STATUS</p>
            <p style="margin:0; font-weight: 700; color: {'#34D399' if not st.session_state.is_scraping else '#FB923C'} !important;">
                {'● IDLE' if not st.session_state.is_scraping else '● EXTRACTING...'}
            </p>
        </div>
    """, unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)
    
    # Render logout button from auth.py
    render_logout_button()

if st.session_state.role == "admin":
    show_admin_dashboard()
else:
    show_user_dashboard()
