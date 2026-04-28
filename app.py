import streamlit as st
import pandas as pd
import os
import subprocess
import sys
import json
import time
from datetime import datetime

import database
import google_sheets

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

# ==========================================
# SESSION STATE INITIALIZATION
# ==========================================
if 'authenticated' not in st.session_state: st.session_state.authenticated = False
if 'username' not in st.session_state: st.session_state.username = None
if 'role' not in st.session_state: st.session_state.role = None
if 'is_scraping' not in st.session_state: st.session_state.is_scraping = False
if 'session_leads' not in st.session_state: st.session_state.session_leads = []
if 'logs' not in st.session_state: st.session_state.logs = ""

# ==========================================
# SHARED UTILITIES
# ==========================================
def logout():
    database.log_action(st.session_state.username, "Logged Out")
    st.session_state.authenticated = False
    st.session_state.username = None
    st.session_state.role = None
    st.rerun()

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
def login_page():
    st.markdown("<br><br>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        st.markdown("""
            <div style="text-align: center; margin-bottom: 2rem;">
                <h1 style="font-size: 2.5rem; font-weight: 800; color: #0F172A;">🚀 LeadPulse <span>Pro</span></h1>
                <p style="color: #64748B;">Production Grade Lead Extraction Engine</p>
            </div>
        """, unsafe_allow_html=True)
        
        username = st.text_input("Username", placeholder="e.g. admin")
        password = st.text_input("Password", type="password")
        
        if st.button("Enter Dashboard"):
            role = database.verify_user(username, password)
            if role:
                st.session_state.authenticated = True
                st.session_state.username = username
                st.session_state.role = role
                database.log_action(username, "Logged In")
                st.rerun()
            else:
                st.error("Invalid Credentials")

# ==========================================
# GENERATION COMPONENT (SHARED)
# ==========================================
def generation_ui(label_suffix=""):
    st.markdown(f"### 🔍 Start New Extraction {label_suffix}")
    col1, col2 = st.columns([4, 1])
    query = col1.text_input(f"Target Keywords", placeholder="e.g. Real Estate Hyderabad", label_visibility="collapsed", key=f"q_{label_suffix}")
    
    if col2.button(f"Generate Leads", disabled=st.session_state.is_scraping, key=f"b_{label_suffix}"):
        if not query:
            st.warning("Please enter target keywords first.")
        else:
            st.session_state.is_scraping = True
            st.session_state.session_leads = []
            st.session_state.logs = ""
            database.log_action(st.session_state.username, f"Started Scraping: {query}")
            
            log_placeholder = st.empty()
            table_placeholder = st.empty()
            
            process = subprocess.Popen(
                [sys.executable, "scraper.py", query],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
            
            while True:
                line = process.stdout.readline()
                if not line and process.poll() is not None: break
                if line:
                    if line.startswith("LOG:"):
                        st.session_state.logs += line.replace("LOG:", "").strip() + "\n"
                        log_placeholder.markdown(f'<div class="log-box">{st.session_state.logs}</div>', unsafe_allow_html=True)
                    elif line.startswith("DATA:"):
                        try:
                            data = json.loads(line.replace("DATA:", "").strip())
                            st.session_state.session_leads.append(data)
                            with table_placeholder.container():
                                st.dataframe(pd.DataFrame(st.session_state.session_leads).iloc[::-1], use_container_width=True)
                        except: pass
            
            process.wait()
            st.session_state.is_scraping = False
            st.rerun()

# ==========================================
# USER DASHBOARD
# ==========================================
def show_user_dashboard():
    st.markdown('<h1 class="main-title">User Workspace</h1>', unsafe_allow_html=True)
    st.markdown('<p class="sub-title">Session results and lead monitoring</p>', unsafe_allow_html=True)
    
    total_db, today_db, quality_pct = get_stats()
    gs_connected = google_sheets.check_connection()
    
    c1, c2, c3, c4 = st.columns(4)
    with c1: st.markdown(f'<div class="metric-card"><div class="metric-label">Session Leads</div><div class="metric-value">{len(st.session_state.session_leads)}</div></div>', unsafe_allow_html=True)
    with c2: st.markdown(f'<div class="metric-card"><div class="metric-label">Data Accuracy</div><div class="metric-value">{quality_pct}%</div></div>', unsafe_allow_html=True)
    
    status_text = "ACTIVE" if st.session_state.is_scraping else "IDLE"
    status_badge = "badge-success" if st.session_state.is_scraping else "badge-idle"
    with c3: st.markdown(f'<div class="metric-card"><div class="metric-label">Engine Status</div><div class="metric-value"><span class="badge {status_badge}">{status_text}</span></div></div>', unsafe_allow_html=True)
    
    gs_color = "#22C55E" if gs_connected else "#EF4444"
    gs_text = "Connected" if gs_connected else "Offline"
    with c4: st.markdown(f'<div class="metric-card"><div class="metric-label">Cloud Sync</div><div class="metric-value" style="color: {gs_color}; font-size: 1.4rem;">{gs_text}</div></div>', unsafe_allow_html=True)
    
    st.markdown("<br><hr><br>", unsafe_allow_html=True)
    generation_ui()
    
    if not st.session_state.is_scraping and st.session_state.session_leads:
        st.markdown("### ⚡ Batch Results")
        df = pd.DataFrame(st.session_state.session_leads)
        user_cols = ["business_name", "address", "phone", "website", "rating", "review_count", "category", "timestamp"]
        st.dataframe(df[[c for c in user_cols if c in df.columns]], use_container_width=True)
        
        # Restore missing Export button
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Export Current Session Leads", csv, "session_leads.csv", "text/csv")

# ==========================================
# ADMIN DASHBOARD
# ==========================================
def show_admin_dashboard():
    st.markdown('<h1 class="main-title">Admin Dashboard</h1>', unsafe_allow_html=True)
    st.markdown('<p class="sub-title">Full system access and master database control</p>', unsafe_allow_html=True)
    
    total_db, today_db, quality_pct = get_stats()
    gs_connected = google_sheets.check_connection()
    
    c1, c2, c3, c4 = st.columns(4)
    with c1: st.markdown(f'<div class="metric-card"><div class="metric-label">Total Leads</div><div class="metric-value">{total_db}</div></div>', unsafe_allow_html=True)
    with c2: st.markdown(f'<div class="metric-card"><div class="metric-label">Today\'s Fresh</div><div class="metric-value">{today_db}</div></div>', unsafe_allow_html=True)
    with c3: st.markdown(f'<div class="metric-card"><div class="metric-label">Global Quality</div><div class="metric-value">{quality_pct}%</div></div>', unsafe_allow_html=True)
    
    gs_color = "#22C55E" if gs_connected else "#EF4444"
    gs_text = "Connected" if gs_connected else "Offline"
    with c4: st.markdown(f'<div class="metric-card"><div class="metric-label">Google Sheets</div><div class="metric-value" style="color: {gs_color}; font-size: 1.4rem;">{gs_text}</div></div>', unsafe_allow_html=True)
    
    st.markdown("<br><hr><br>", unsafe_allow_html=True)
    
    tabs = st.tabs(["🚀 Generate", "🗄️ Master Database", "📜 Activity Logs", "🛠️ System"])
    
    with tabs[0]:
        generation_ui("(Admin)")
        if not st.session_state.is_scraping and st.session_state.session_leads:
            st.markdown("### ⚡ Session Preview")
            st.dataframe(pd.DataFrame(st.session_state.session_leads), use_container_width=True)

    with tabs[1]:
        st.markdown("### Master Lead Repository")
        df_master = database.load_db()
        if not df_master.empty:
            st.dataframe(df_master, use_container_width=True)
            csv_master = df_master.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Export Master Repository", csv_master, "leadpulse_master.csv", "text/csv")
        else: st.info("No leads in database.")

    with tabs[2]:
        st.markdown("### User System Logs")
        st.dataframe(database.get_logs(), use_container_width=True)

    with tabs[3]:
        st.markdown("### Advanced Settings")
        if st.button("🔄 Force Cloud Sync"):
            with st.spinner("Syncing..."):
                df_local = database.load_db()
                if not df_local.empty:
                    success, msg = google_sheets.save_to_google_sheets(df_local.to_dict('records'))
                    if success: st.success(msg)
                    else: st.error(msg)
        
        st.markdown("---")
        if st.button("🚨 Wipe Entire System"):
            database.clear_all_leads()
            google_sheets.clear_sheet_data()
            st.success("Wipe Complete")
            time.sleep(1)
            st.rerun()

# ==========================================
# MAIN ROUTING
# ==========================================
if not st.session_state.authenticated:
    login_page()
else:
    # --- MODERN SIDEBAR ---
    with st.sidebar:
        # 1. Professional Logo
        st.markdown("""
            <div class="sidebar-logo">
                🚀 LeadPulse <span>Pro</span>
            </div>
            <div class="user-info">
                Logged in as: <strong>{un}</strong>
            </div>
            <div class="sidebar-divider"></div>
        """.format(un=st.session_state.username), unsafe_allow_html=True)
        
        # 2. Navigation / Active Item Highlight
        role_label = "Admin Workspace" if st.session_state.role == "admin" else "User Workspace"
        st.markdown(f'<div class="nav-item-active">🏠 {role_label}</div>', unsafe_allow_html=True)
        
        st.markdown("<br><br><br>", unsafe_allow_html=True)
        
        # 3. Status Info
        st.markdown(f"""
            <div style="padding: 1rem; background: rgba(255,255,255,0.03); border-radius: 8px;">
                <p style="margin:0; font-size: 0.7rem; color: #94A3B8 !important;">ENGINE STATUS</p>
                <p style="margin:0; font-weight: 700; color: {'#34D399' if not st.session_state.is_scraping else '#FB923C'} !important;">
                    {'● IDLE' if not st.session_state.is_scraping else '● EXTRACTING...'}
                </p>
            </div>
        """, unsafe_allow_html=True)
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        # 4. Logout Button (Styled)
        if st.button("Sign Out Session"):
            logout()

    # Dashboard Routing
    if st.session_state.role == "admin":
        show_admin_dashboard()
    else:
        show_user_dashboard()
