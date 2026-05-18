import streamlit as st
st.set_page_config(
    page_title="LeadPulse Pro",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Force sidebar to always stay open using specific CSS styles (STEP 2)
st.markdown("""
<style>
/* Always show sidebar, never collapse */
[data-testid="stSidebar"] {
    display: block !important;
    visibility: visible !important;
    min-width: 260px !important;
    max-width: 260px !important;
    transform: translateX(0) !important;
    background: linear-gradient(180deg, #0f0c29 0%, #302b63 50%, #24243e 100%) !important;
}

/* Hide the collapse arrow button permanently */
[data-testid="collapsedControl"] {
    display: none !important;
}

/* Sidebar inner content transparent */
[data-testid="stSidebar"] > div:first-child {
    background: transparent !important;
    padding: 1.5rem 1rem !important;
}

/* Hide default Streamlit sidebar nav links */
[data-testid="stSidebarNav"] {
    display: none !important;
}

/* Nav button styles */
div[data-testid="stSidebar"] button {
    width: 100% !important;
    text-align: left !important;
    background: transparent !important;
    color: rgba(255,255,255,0.75) !important;
    border: none !important;
    padding: 10px 14px !important;
    border-radius: 10px !important;
    font-size: 14px !important;
    margin-bottom: 4px !important;
    transition: all 0.2s ease !important;
}

div[data-testid="stSidebar"] button:hover {
    background: rgba(255,255,255,0.08) !important;
    color: white !important;
}

/* Active nav button */
.active-nav button {
    background: linear-gradient(135deg, #6c3fc5 0%, #8b5cf6 100%) !important;
    color: white !important;
    font-weight: 600 !important;
    box-shadow: 0 4px 12px rgba(108, 63, 197, 0.4) !important;
}

/* Admin profile card */
.admin-profile {
    background: rgba(255,255,255,0.07);
    border-radius: 12px;
    padding: 12px;
    margin-bottom: 24px;
    display: flex;
    align-items: center;
    gap: 10px;
}

.admin-avatar {
    width: 38px;
    height: 38px;
    border-radius: 50%;
    background: linear-gradient(135deg, #f97316, #fb923c);
    display: flex;
    align-items: center;
    justify-content: center;
    font-weight: 700;
    color: white;
    font-size: 14px;
    flex-shrink: 0;
}

.section-label {
    color: rgba(255,255,255,0.3);
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 1.5px;
    margin: 20px 0 8px 4px;
}
</style>
""", unsafe_allow_html=True)

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
from scheduler import render_scheduler_ui, start_scheduler

# Initialize session
init_session()
if "user_nav" not in st.session_state:
    st.session_state["user_nav"] = "Generate"
if "admin_nav" not in st.session_state:
    st.session_state["admin_nav"] = "Generate"
if "admin_page" not in st.session_state:
    st.session_state["admin_page"] = "Generate"

# Initialize scheduler once
if "scheduler" not in st.session_state:
    st.session_state.scheduler = start_scheduler()

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
    st.markdown("""
    <style>
        /* Hide sidebar on login page */
        [data-testid="stSidebar"] { display: none !important; }
        [data-testid="stHeader"] { display: none !important; }
        
        /* Create the split layout */
        .login-split {
            position: fixed;
            top: 0; left: 0; width: 100vw; height: 100vh;
            display: flex;
            z-index: 0;
        }
        .login-left {
            width: 45%;
            background: linear-gradient(135deg, #2E1065 0%, #4C1D95 50%, #3B82F6 100%);
            padding: 60px;
            color: white;
            display: flex;
            flex-direction: column;
            justify-content: center;
        }
        .login-left h1 {
            font-size: 3rem;
            font-weight: 800;
            margin-bottom: 1rem;
            color: #fff !important;
        }
        .login-left p {
            font-size: 1.2rem;
            color: #E2E8F0;
            margin-bottom: 3rem;
        }
        .feature-list {
            list-style: none;
            padding: 0;
            margin: 0;
        }
        .feature-list li {
            font-size: 1.1rem;
            margin-bottom: 1.5rem;
            display: flex;
            align-items: center;
            gap: 12px;
            background: rgba(255,255,255,0.1);
            padding: 16px 20px;
            border-radius: 12px;
            border: 1px solid rgba(255,255,255,0.1);
            backdrop-filter: blur(10px);
        }
        .login-right-bg {
            width: 55%;
            background: #F8FAFC;
        }
        
        /* Position the actual Streamlit login form over the right side */
        .stApp {
            background: transparent !important;
        }
        [data-testid="stAppViewContainer"] {
            background: transparent !important;
            z-index: 10;
        }
        [data-testid="stMainBlockContainer"] {
            margin-left: 45%; /* Shift main content to the right */
            width: 55% !important;
            max-width: 55% !important;
            padding: 0 !important;
            display: flex;
            flex-direction: column;
            justify-content: center;
            min-height: 100vh;
        }
        
        /* Style the auth card */
        div[data-testid="column"]:nth-of-type(2) {
            background: white;
            padding: 40px;
            border-radius: 24px;
            box-shadow: 0 20px 40px rgba(0,0,0,0.08);
            width: 100% !important;
            max-width: 450px !important;
            margin: 0 auto !important;
        }
        
        /* Hide empty columns from auth.py */
        div[data-testid="column"]:nth-of-type(1),
        div[data-testid="column"]:nth-of-type(3) {
            display: none !important;
        }
        
        /* Login button gradient */
        div.stButton > button {
            background: linear-gradient(135deg, #4C1D95 0%, #3B82F6 100%) !important;
            border: none !important;
            color: white !important;
            padding: 12px !important;
            font-size: 16px !important;
            border-radius: 12px !important;
            font-weight: 600 !important;
        }
        div.stButton > button:hover {
            box-shadow: 0 8px 20px rgba(76, 29, 149, 0.3) !important;
            transform: translateY(-2px) !important;
        }
    </style>
    <div class="login-split">
        <div class="login-left">
            <h1>LeadPulse Pro</h1>
            <p>The ultimate lead extraction & intelligence platform.</p>
            <ul class="feature-list">
                <li>✨ AI-Powered Lead Generation</li>
                <li>✅ Data Accuracy & Validation</li>
                <li>🔒 Secure & Private</li>
                <li>📥 Export & Integrations</li>
            </ul>
        </div>
        <div class="login-right-bg"></div>
    </div>
    """, unsafe_allow_html=True)
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

# Startup sync complete

# ==========================================
# MODERN SAAS UI CSS
# ==========================================
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600&display=swap');
@import url('https://cdn.jsdelivr.net/npm/@tabler/icons-webfont@latest/tabler-icons.min.css');

* { font-family: 'Inter', sans-serif !important; }

/* ==================== BACKGROUND ==================== */
.stApp { background: #F8FAFC !important; }
[data-testid="stAppViewContainer"] { background: #F8FAFC !important; }
[data-testid="stHeader"] { background: transparent !important; }

/* ==================== SIDEBAR ==================== */
[data-testid="stSidebar"] {
    display: flex !important;
    background: linear-gradient(180deg, #1a1a4e 0%, #2d1b69 100%) !important;
    border-right: none !important;
    min-width: 260px !important;
    max-width: 260px !important;
    box-shadow: 4px 0 15px rgba(0,0,0,0.05) !important;
}
[data-testid="stSidebar"] * {
    color: rgba(255,255,255,0.7) !important;
}
[data-testid="stSidebar"] .stMarkdown h1,
[data-testid="stSidebar"] .stMarkdown h2,
[data-testid="stSidebar"] .stMarkdown h3 {
    color: #fff !important;
}
[data-testid="stHeader"] {
    display: flex !important;
    background: transparent !important;
}
[data-testid="collapsedSidebarIconButton"] {
    background: #7C3AED !important;
    color: white !important;
    border-radius: 50% !important;
    padding: 6px !important;
    box-shadow: 0 4px 10px rgba(124, 58, 237, 0.3) !important;
    transition: all 0.2s ease !important;
    z-index: 999999 !important;
}
[data-testid="collapsedSidebarIconButton"]:hover {
    background: #4F46E5 !important;
    transform: scale(1.1) !important;
}

/* ==================== SIDEBAR BUTTON NAVIGATION OVERRIDES ==================== */
[data-testid="stSidebar"] div.stButton > button {
    background: transparent !important;
    color: #ffffff !important;
    border: none !important;
    border-radius: 12px !important;
    padding: 10px 16px !important;
    font-size: 13px !important;
    font-weight: 500 !important;
    letter-spacing: normal !important;
    transition: all 0.2s ease !important;
    box-shadow: none !important;
    text-align: left !important;
    justify-content: flex-start !important;
    width: 100% !important;
    margin-bottom: 4px !important;
}
[data-testid="stSidebar"] div.stButton > button:hover {
    background: rgba(255, 255, 255, 0.08) !important;
    color: #ffffff !important;
    transform: none !important;
}
[data-testid="stSidebar"] div.stButton > button[data-testid*="primary"] {
    background: #6c3fc5 !important;
    color: #ffffff !important;
    box-shadow: 0 4px 12px rgba(108, 63, 197, 0.3) !important;
    font-weight: 600 !important;
    border: none !important;
}
[data-testid="stSidebar"] div.stButton > button[data-testid*="primary"]:hover {
    background: #5b32ab !important;
    box-shadow: 0 6px 16px rgba(108, 63, 197, 0.5) !important;
    transform: translateY(-1px) !important;
}

/* ==================== MAIN CONTENT ==================== */
[data-testid="stMainBlockContainer"] {
    padding: 24px 28px !important;
    max-width: 100% !important;
    margin-left: 0 !important;
    width: 100% !important;
    display: block !important;
}
.main-content {
    padding: 24px 28px !important;
}
.block-container {
    padding: 24px 28px !important;
    max-width: 100% !important;
}

/* ==================== TOPBAR ==================== */
.topbar {
    background: #fff;
    border-bottom: 0.5px solid #E2E8F0;
    padding: 0 28px;
    height: 52px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin: -24px -28px 24px -28px;
    position: sticky;
    top: 0;
    z-index: 100;
}
.topbar-title {
    font-size: 15px;
    font-weight: 500;
    color: #0F172A;
}

/* ==================== METRIC CARDS ==================== */
.metric-card {
    background: #fff;
    border: 0.5px solid #E2E8F0;
    border-radius: 10px;
    padding: 16px 18px;
    transition: box-shadow 0.15s;
}
.metric-card:hover {
    box-shadow: 0 4px 12px rgba(0,0,0,0.06);
}
.metric-label {
    font-size: 11px;
    font-weight: 500;
    color: #64748B;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    margin-bottom: 8px;
}
.metric-value {
    font-size: 26px;
    font-weight: 500;
    color: #0F172A;
    line-height: 1;
}
.metric-delta {
    font-size: 11px;
    color: #22C55E;
    margin-top: 4px;
}

/* ==================== CARDS ==================== */
.lp-card {
    background: #fff;
    border: 0.5px solid #E2E8F0;
    border-radius: 10px;
    padding: 20px;
    margin-bottom: 16px;
}
.lp-card-title {
    font-size: 12px;
    font-weight: 500;
    color: #64748B;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    margin-bottom: 16px;
}

/* ==================== BUTTONS ==================== */
div.stButton > button {
    background: #2563EB !important;
    color: #fff !important;
    border: none !important;
    border-radius: 8px !important;
    padding: 9px 18px !important;
    font-size: 13px !important;
    font-weight: 500 !important;
    letter-spacing: -0.1px !important;
    transition: all 0.15s !important;
    box-shadow: none !important;
}
div.stButton > button:hover {
    background: #1D4ED8 !important;
    box-shadow: 0 4px 12px rgba(37,99,235,0.25) !important;
    transform: translateY(-1px) !important;
}
div.stButton > button:disabled {
    background: #94A3B8 !important;
    cursor: not-allowed !important;
    transform: none !important;
}

/* ==================== INPUTS ==================== */
.stTextInput > div > div > input,
.stSelectbox > div > div,
.stMultiSelect > div > div {
    border: 0.5px solid #E2E8F0 !important;
    border-radius: 8px !important;
    background: #F8FAFC !important;
    font-size: 13px !important;
    color: #0F172A !important;
}
.stTextInput > div > div > input:focus {
    border-color: #2563EB !important;
    box-shadow: 0 0 0 3px rgba(37,99,235,0.1) !important;
}
.stTextInput label,
.stSelectbox label,
.stSlider label,
.stMultiSelect label {
    font-size: 12px !important;
    font-weight: 500 !important;
    color: #475569 !important;
    margin-bottom: 4px !important;
}

/* ==================== DATAFRAME ==================== */
.stDataFrame {
    border: 0.5px solid #E2E8F0 !important;
    border-radius: 10px !important;
    overflow: hidden !important;
}
.stDataFrame thead th {
    background: #F1F5F9 !important;
    font-size: 11px !important;
    font-weight: 500 !important;
    color: #64748B !important;
    text-transform: uppercase !important;
    letter-spacing: 0.06em !important;
    padding: 10px 16px !important;
    border-bottom: 0.5px solid #E2E8F0 !important;
}
.stDataFrame tbody td {
    font-size: 12px !important;
    color: #334155 !important;
    padding: 9px 16px !important;
    border-bottom: 0.5px solid #F1F5F9 !important;
}
.stDataFrame tbody tr:hover td {
    background: #F8FAFC !important;
}

/* ==================== TABS ==================== */
.stTabs [data-baseweb="tab-list"] {
    background: transparent !important;
    border-bottom: 0.5px solid #E2E8F0 !important;
    gap: 0 !important;
    padding: 0 !important;
}
.stTabs [data-baseweb="tab"] {
    background: transparent !important;
    border: none !important;
    padding: 10px 18px !important;
    font-size: 13px !important;
    font-weight: 400 !important;
    color: #64748B !important;
    border-bottom: 2px solid transparent !important;
    margin-bottom: -1px !important;
}
.stTabs [aria-selected="true"] {
    color: #2563EB !important;
    border-bottom-color: #2563EB !important;
    font-weight: 500 !important;
    background: transparent !important;
}
.stTabs [data-baseweb="tab-panel"] {
    padding: 20px 0 0 0 !important;
}

/* ==================== LOG BOX ==================== */
.log-box {
    background: #0F172A;
    color: #10B981;
    padding: 16px;
    border-radius: 8px;
    font-family: 'Monaco', 'Menlo', 'Consolas', monospace !important;
    font-size: 11px !important;
    line-height: 1.6;
    height: 220px;
    overflow-y: auto;
    border: 0.5px solid #1E293B;
    white-space: pre-wrap;
    word-break: break-all;
}

/* ==================== STATUS BADGES ==================== */
.badge {
    display: inline-flex;
    align-items: center;
    padding: 3px 10px;
    border-radius: 20px;
    font-size: 11px;
    font-weight: 500;
    gap: 4px;
}
.badge-valid { background: #DCFCE7; color: #16A34A; }
.badge-invalid { background: #FEE2E2; color: #DC2626; }
.badge-pending { background: #FEF9C3; color: #CA8A04; }
.badge-idle { background: #F1F5F9; color: #475569; }
.badge-active { background: #DBEAFE; color: #2563EB; }
.badge-enterprise { background: #FEF3C7; color: #B45309; }
.badge-pro { background: #EDE9FE; color: #7C3AED; }
.badge-starter { background: #DBEAFE; color: #2563EB; }
.badge-free { background: #F1F5F9; color: #64748B; }

/* ==================== SIDEBAR COMPONENTS ==================== */
.sidebar-logo {
    padding: 20px 16px 14px;
    border-bottom: 0.5px solid rgba(255,255,255,0.06);
}
.sidebar-logo h1 {
    font-size: 17px !important;
    font-weight: 500 !important;
    color: #fff !important;
    letter-spacing: -0.3px !important;
    margin: 0 !important;
}
.sidebar-logo p {
    font-size: 10px !important;
    color: rgba(255,255,255,0.3) !important;
    margin: 2px 0 0 !important;
}
.sidebar-user {
    padding: 12px 16px;
    border-bottom: 0.5px solid rgba(255,255,255,0.06);
    display: flex;
    align-items: center;
    gap: 10px;
}
.sidebar-avatar {
    width: 30px;
    height: 30px;
    border-radius: 50%;
    background: #2563EB;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 12px;
    font-weight: 500;
    color: #fff;
    flex-shrink: 0;
}
.sidebar-user-info { flex: 1; }
.sidebar-user-name {
    font-size: 12px;
    font-weight: 500;
    color: #fff !important;
}
.sidebar-user-plan {
    font-size: 10px;
    color: #22C55E !important;
}
.nav-item-active {
    background: rgba(37,99,235,0.12);
    border-left: 2px solid #2563EB;
    padding: 8px 16px;
    margin: 2px 0;
    border-radius: 0 6px 6px 0;
    font-size: 13px;
    font-weight: 500;
    color: #fff !important;
    display: flex;
    align-items: center;
    gap: 8px;
}
.engine-status-bar {
    padding: 12px 16px;
    border-top: 0.5px solid rgba(255,255,255,0.06);
    margin-top: auto;
}
.engine-dot {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: #22C55E;
    display: inline-block;
    margin-right: 6px;
}

/* ==================== PRIVACY BAR ==================== */
.privacy-bar {
    background: #EFF6FF;
    border: 0.5px solid #BFDBFE;
    border-radius: 8px;
    padding: 10px 14px;
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 12px;
    color: #1E40AF;
    margin-bottom: 16px;
}

/* ==================== AI INFO BOX ==================== */
.ai-info-box {
    background: #EFF6FF;
    border: 0.5px solid #BFDBFE;
    border-radius: 8px;
    padding: 10px 14px;
    font-size: 12px;
    color: #1E40AF;
    margin: 10px 0;
    display: flex;
    align-items: flex-start;
    gap: 8px;
}

/* ==================== PROGRESS BAR ==================== */
.stProgress > div > div {
    background: #2563EB !important;
    border-radius: 4px !important;
}
.stProgress > div {
    background: #E2E8F0 !important;
    border-radius: 4px !important;
    height: 6px !important;
}

/* ==================== ALERTS ==================== */
.stAlert {
    border-radius: 8px !important;
    border: 0.5px solid !important;
    font-size: 13px !important;
}
[data-baseweb="notification"] {
    border-radius: 8px !important;
}

/* ==================== METRICS (Streamlit native) ==================== */
[data-testid="stMetric"] {
    background: #fff !important;
    border: 0.5px solid #E2E8F0 !important;
    border-radius: 10px !important;
    padding: 14px 16px !important;
}
[data-testid="stMetricLabel"] {
    font-size: 11px !important;
    font-weight: 500 !important;
    color: #64748B !important;
    text-transform: uppercase !important;
    letter-spacing: 0.06em !important;
}
[data-testid="stMetricValue"] {
    font-size: 24px !important;
    font-weight: 500 !important;
    color: #0F172A !important;
}
[data-testid="stMetricDelta"] {
    font-size: 11px !important;
}

/* ==================== EXPANDERS ==================== */
.streamlit-expanderHeader {
    background: #F8FAFC !important;
    border: 0.5px solid #E2E8F0 !important;
    border-radius: 8px !important;
    font-size: 13px !important;
    font-weight: 500 !important;
    color: #334155 !important;
    padding: 10px 14px !important;
}
.streamlit-expanderContent {
    border: 0.5px solid #E2E8F0 !important;
    border-top: none !important;
    border-radius: 0 0 8px 8px !important;
    background: #fff !important;
    padding: 16px !important;
}

/* ==================== DIVIDERS ==================== */
hr {
    border: none !important;
    border-top: 0.5px solid #E2E8F0 !important;
    margin: 20px 0 !important;
}

/* ==================== TOGGLE ==================== */
.stCheckbox > label,
[data-testid="stToggle"] > label {
    font-size: 13px !important;
    color: #334155 !important;
}

/* ==================== SLIDER ==================== */
.stSlider [data-baseweb="slider"] [data-testid="stTickBar"] {
    color: #64748B !important;
    font-size: 11px !important;
}

/* ==================== DOWNLOAD BUTTON ==================== */
div.stDownloadButton > button {
    background: #F1F5F9 !important;
    color: #334155 !important;
    border: 0.5px solid #E2E8F0 !important;
    border-radius: 8px !important;
    font-size: 12px !important;
    font-weight: 500 !important;
}
div.stDownloadButton > button:hover {
    background: #E2E8F0 !important;
    transform: none !important;
    box-shadow: none !important;
}

/* ==================== SCROLLBAR ==================== */
::-webkit-scrollbar { width: 4px; height: 4px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: #CBD5E1; border-radius: 4px; }
::-webkit-scrollbar-thumb:hover { background: #94A3B8; }

/* ==================== TITLE ==================== */
.main-title {
    font-size: 20px !important;
    font-weight: 500 !important;
    color: #0F172A !important;
    letter-spacing: -0.3px !important;
    margin-bottom: 4px !important;
}
.sub-title {
    font-size: 13px !important;
    color: #64748B !important;
    margin-bottom: 20px !important;
    font-weight: 400 !important;
}

/* ==================== SECTION HEADERS ==================== */
h3 {
    font-size: 14px !important;
    font-weight: 500 !important;
    color: #0F172A !important;
    letter-spacing: -0.2px !important;
}

/* Hide Streamlit default branding */
#MainMenu { visibility: hidden; }
footer { visibility: hidden; }
header { visibility: hidden; }
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
            prompt = f"""You are a hyper-local area expert for India.
I need very specific sub-locations WITHIN the area "{region}" only.
Do NOT list areas from the broader city "{city}".
Focus only on what exists inside "{region}" itself.

For example if region is "KPHB":
Return things like: KPHB Phase 1, KPHB Phase 2, KPHB Phase 3, KPHB Phase 4, KPHB Phase 5, KPHB Phase 6, KPHB Road No 1, KPHB Road No 2, KPHB Main Road, Kukatpally Housing Board Colony

For example if region is "Banjara Hills":
Return things like: Banjara Hills Road No 1, Banjara Hills Road No 2, Banjara Hills Road No 3, Banjara Hills Road No 10, Banjara Hills Road No 12, Banjara Hills Road No 13

Now list specific sub-locations inside "{region}" where {keyword} businesses would be found.
Return ONLY a JSON array of strings. No other text. No markdown. No explanation."""
            response = model.generate_content(prompt)
            raw = response.text.strip().replace("```json","").replace("```","").strip()
            import json
            sub_regions = json.loads(raw)
            if isinstance(sub_regions, list) and len(sub_regions) > 0:
                specific_regions = sub_regions[:15]
        except Exception as e:
            st.session_state.logs += f"[SYS] AI sub-region failed: {e}\n"

    if specific_regions:
        return specific_regions[:25]
        
    region_lower = region.lower().strip()
    for key, regions in specific_area_fallback.items():
        if key in region_lower or region_lower in key:
            return regions
            
    city_lower = city.lower()
    for key, regions in city_hubs_fallback.items():
        if key in city_lower:
            return regions
            
    return [f"{region}", f"{region} Main Road", f"{region} Colony", f"{region} Extension"]

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
            if region.strip():
                st.markdown(f"""
                    <div class="ai-info-box">
                        🤖 AI will analyze your city/region and automatically search nearby sub-regions to improve lead coverage.
                    </div>
                """, unsafe_allow_html=True)

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
    st.markdown('<h1 class="main-title">LeadPulse Pro Workspace</h1>', unsafe_allow_html=True)
    st.markdown('<p class="sub-title">Generate leads, monitor quality, and manage exports securely.</p>', unsafe_allow_html=True)

    # Privacy bar
    st.markdown("""
        <div class="privacy-bar">
            🔒 Your lead data is protected — stored securely and never shared with third parties.
        </div>
    """, unsafe_allow_html=True)

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

    # Navigation display based on selected sidebar item
    current_nav = st.session_state.get("user_nav", "Generate")

    if current_nav == "Generate":
        generation_ui()
    elif current_nav == "My Leads":
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
            st.dataframe(df[[c for c in user_cols if c in df.columns]], hide_index=True)
            st.markdown("---")
            # Export UI
            render_export_ui(df, "Export My Leads")
        else:
            st.info("💡 Generate leads first to see your leads table.")
    elif current_nav == "Analytics":
        show_user_analytics(st.session_state.get("username", ""))
    elif current_nav == "Billing":
        render_billing_tab()

# ==========================================
# ADMIN DASHBOARD
# ==========================================
def show_admin_dashboard():
    st.markdown('<h1 class="main-title">LeadPulse Command Center</h1>', unsafe_allow_html=True)
    st.markdown('<p class="sub-title">Monitor users, revenue, subscriptions, and platform-wide lead intelligence.</p>', unsafe_allow_html=True)

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
    # Navigation display based on selected sidebar item
    current_nav = st.session_state.get("admin_nav", "Generate")

    if current_nav == "Generate":
        generation_ui("(Admin)")
        if not st.session_state.is_scraping and st.session_state.session_leads:
            st.markdown("### ⚡ Session Preview")
            st.dataframe(pd.DataFrame(st.session_state.session_leads), hide_index=True)

    elif current_nav == "Master Database":
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

    elif current_nav == "User Management":
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

    elif current_nav == "Activity Logs":
        st.markdown("### 📜 System Activity Logs")
        try:
            logs_df = database.get_logs()
            if not logs_df.empty:
                st.dataframe(logs_df, hide_index=True, use_container_width=True)
            else:
                st.info("No activity logs yet")
        except Exception as e:
            st.info(f"Logs unavailable: {e}")

    elif current_nav == "Analytics":
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

    elif current_nav == "Revenue & Billing":
        render_admin_billing()

    elif current_nav == "Scheduler":
        render_scheduler_ui(st.session_state.get("plan", "Free"))

    elif current_nav == "System Settings":
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
    # Logo
    st.markdown("""
    <div style="color:white; font-size:20px; font-weight:700; 
                margin-bottom:4px;">🚀 LeadPulse Pro</div>
    <div style="color:rgba(255,255,255,0.4); font-size:11px; 
                margin-bottom:20px;">Lead Engine v1.0</div>
    """, unsafe_allow_html=True)

    username = st.session_state.get("username", "user")
    plan = st.session_state.get("plan", "Free Plan")
    role = st.session_state.get("role", "user")
    initials = username[:2].upper() if username else "LP"

    if role == "admin":
        # Admin profile
        st.markdown(f"""
        <div class="admin-profile">
            <div class="admin-avatar">{initials}</div>
            <div>
                <div style="color:white; font-weight:600; 
                            font-size:14px;">{username}</div>
                <div style="color:#4ade80; font-size:11px;">{plan}</div>
            </div>
        </div>
        <div class="section-label">ADMIN WORKSPACE</div>
        """, unsafe_allow_html=True)

        # Navigation items
        nav_items = [
            ("🚀", "Generate"),
            ("🗄️", "Master Database"),
            ("👥", "User Management"),
            ("📋", "Activity Logs"),
            ("📊", "Analytics"),
            ("💰", "Revenue & Billing"),
            ("📅", "Scheduler"),
            ("⚙️", "Settings"),
        ]

        if "admin_page" not in st.session_state:
            st.session_state.admin_page = "Generate"

        for icon, page in nav_items:
            is_active = st.session_state.admin_page == page
            st.markdown(
                f'<div class="{"active-nav" if is_active else ""}">',
                unsafe_allow_html=True
            )
            if st.button(f"{icon}  {page}", key=f"admin_nav_{page}"):
                st.session_state.admin_page = page
                nav_target = "System Settings" if page == "Settings" else page
                st.session_state["admin_nav"] = nav_target
                st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)
    else:
        # User profile
        st.markdown(f"""
        <div class="admin-profile">
            <div class="admin-avatar" style="background: linear-gradient(135deg, #3b82f6, #60a5fa);">{initials}</div>
            <div>
                <div style="color:white; font-weight:600; 
                            font-size:14px;">{username}</div>
                <div style="color:#60a5fa; font-size:11px;">{plan}</div>
            </div>
        </div>
        <div class="section-label">USER WORKSPACE</div>
        """, unsafe_allow_html=True)

        # Navigation items
        user_items = [
            ("🚀", "Generate"),
            ("⚡", "My Leads"),
            ("📊", "Analytics"),
            ("💳", "Billing"),
        ]

        if "user_page" not in st.session_state:
            st.session_state.user_page = "Generate"

        for icon, page in user_items:
            is_active = st.session_state.user_page == page
            st.markdown(
                f'<div class="{"active-nav" if is_active else ""}">',
                unsafe_allow_html=True
            )
            if st.button(f"{icon}  {page}", key=f"user_nav_{page}"):
                st.session_state.user_page = page
                st.session_state["user_nav"] = page
                st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)

    # Engine status
    is_scraping = st.session_state.get("is_scraping", False)
    engine_color = "#FB923C" if is_scraping else "#22C55E"
    engine_text = "EXTRACTING..." if is_scraping else "IDLE"
    st.markdown(f"""
        <div style="margin-top:20px; padding: 12px; background: rgba(255,255,255,0.05); border-radius: 10px;">
            <div style="font-size:10px; color:rgba(255,255,255,0.30); margin-bottom:4px; font-weight:700; letter-spacing:1px;">ENGINE STATUS</div>
            <div style="display:flex; align-items:center; gap:6px; font-size:12px; color:{engine_color}; font-weight:500;">
                <div style="width:7px; height:7px; border-radius:50%; background:{engine_color};"></div>
                ● {engine_text}
            </div>
        </div>
    """, unsafe_allow_html=True)

    # Logout at bottom
    st.markdown("<div style='margin-top:40px;'>", unsafe_allow_html=True)
    if st.button("🚪  Logout", key="admin_logout" if role == "admin" else "user_logout"):
        st.session_state.clear()
        st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

if st.session_state.role == "admin":
    show_admin_dashboard()
else:
    show_user_dashboard()
