import streamlit as st
from scheduler import render_scheduler_ui, start_scheduler
st.set_page_config(
    page_title="LeadPulse Pro",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Force sidebar to always stay open using specific CSS styles (STEP 2)
st.markdown("""
<style>
#MainMenu {visibility: hidden !important;}
footer {visibility: hidden !important;}
header {visibility: hidden !important;}

[data-testid="stSidebar"] {
    display: block !important;
    visibility: visible !important;
    transform: translateX(0) !important;
    min-width: 280px !important;
    max-width: 280px !important;
    background: #0d1117 !important;
}
[data-testid="stSidebar"] > div:first-child {
    background: #0d1117 !important;
    padding: 1.5rem 1rem !important;
}
[data-testid="collapsedControl"] {
    display: none !important;
}
[data-testid="stSidebarNav"] {
    display: none !important;
}

div[data-testid="stSidebar"] 
div[data-testid="stVerticalBlock"] {
    gap: 0rem !important;
}
div[data-testid="stSidebar"] .stButton {
    margin: 0 !important;
    padding: 0 !important;
}
div[data-testid="stSidebar"] .stButton > button {
    width: 100% !important;
    text-align: left !important;
    padding: 10px 14px !important;
    margin: 2px 0 !important;
    min-height: 40px !important;
    height: auto !important;
    font-size: 14px !important;
    border-radius: 8px !important;
    border: none !important;
    background: #1e3a5f !important;
    color: white !important;
    font-weight: 600 !important;
}

.main .block-container {
    padding: 1.5rem 2rem !important;
    background: #f8fafc !important;
}

.stTabs [data-baseweb="tab-list"] {
    border-bottom: 2px solid #e5e7eb !important;
    gap: 0 !important;
}
.stTabs [data-baseweb="tab"] {
    padding: 10px 18px !important;
    font-size: 14px !important;
    color: #6b7280 !important;
    border-radius: 0 !important;
    border-bottom: 3px solid transparent !important;
    margin-bottom: -2px !important;
}
.stTabs [aria-selected="true"] {
    color: #ef4444 !important;
    font-weight: 700 !important;
    border-bottom: 3px solid #ef4444 !important;
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
import logging

logger = logging.getLogger("app")

# Load environment variables
load_dotenv()

import database
import google_sheets
# Import new auth module
from auth import (
    init_session, render_logout_button,
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

if "is_extracting" not in st.session_state:
    st.session_state["is_extracting"] = False

if "session_leads" not in st.session_state:
    st.session_state["session_leads"] = []

if "collected_count" not in st.session_state:
    st.session_state["collected_count"] = 0

if "target_leads" not in st.session_state:
    st.session_state["target_leads"] = 0

if "current_query" not in st.session_state:
    st.session_state["current_query"] = ""

if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

# Fix Streamlit native blur/disabled overlay issue
if not st.session_state.get("is_extracting", False):
    st.markdown("""
    <style>
    /* Remove Streamlit default blur/overlay during normal interactions */
    [data-testid="stAppViewContainer"],
    [data-testid="stMainBlockContainer"],
    .stApp,
    [data-testid="stSidebar"],
    .main,
    .block-container,
    form, button {
        opacity: 1 !important;
        filter: blur(0px) !important;
        pointer-events: auto !important;
    }
    /* Hide Streamlit running modal backdrop */
    [data-testid="stModalBackdrop"] {
        display: none !important;
    }
    </style>
    """, unsafe_allow_html=True)
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
if st.session_state.authenticated and not st.session_state.get("is_extracting", False) and check_session_expiry():
    st.warning("Session expired. Please login again.")
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()
# ==========================================
# LOGIN PAGE
# ==========================================
def render_login_page():
    """Premium login page — click Admin or User card to reveal credentials."""
    from auth import login, register_user

    st.markdown("""
    <style>
    .stApp { background: #0F172A !important; }
    [data-testid="stAppViewContainer"] { background: #0F172A !important; }
    [data-testid="stSidebar"] { display: none !important; }
    [data-testid="stHeader"] { background: transparent !important; }
    .block-container {
        max-width: 560px !important;
        margin: 0 auto !important;
        padding: 2rem 1rem !important;
    }
    div.stButton > button {
        border-radius: 8px !important;
        font-weight: 500 !important;
        font-size: 13px !important;
        border: none !important;
        width: 100% !important;
    }
    .stTextInput > div > div > input {
        background: #ffffff !important;
        border: 1px solid #cbd5e1 !important;
        color: #000000 !important;
        border-radius: 8px !important;
        font-size: 13px !important;
    }
    .stTextInput > div > div > input::placeholder {
        color: #94a3b8 !important;
    }
    .stTextInput label {
        color: rgba(255,255,255,0.4) !important;
        font-size: 11px !important;
        text-transform: uppercase !important;
        letter-spacing: 0.07em !important;
        font-weight: 500 !important;
    }
    .stAlert {
        border-radius: 8px !important;
        font-size: 12px !important;
    }
    /* Expander styling using high-specificity selectors to force white text */
    [data-testid="stExpander"] {
        border: none !important;
        background: transparent !important;
        box-shadow: none !important;
    }
    [data-testid="stExpander"] summary {
        background: rgba(255,255,255,0.04) !important;
        border: 0.5px solid rgba(255,255,255,0.08) !important;
        border-radius: 8px !important;
        padding: 10px 14px !important;
    }
    [data-testid="stExpander"] summary * {
        color: #ffffff !important;
        font-weight: 500 !important;
        font-size: 13px !important;
    }
    [data-testid="stExpander"] summary svg {
        fill: #ffffff !important;
        color: #ffffff !important;
    }
    [data-testid="stExpander"] div[role="region"] {
        background: rgba(255,255,255,0.02) !important;
        border: 0.5px solid rgba(255,255,255,0.08) !important;
        border-top: none !important;
        border-radius: 0 0 8px 8px !important;
        padding: 16px !important;
    }
    </style>
    """, unsafe_allow_html=True)

    # Logo
    st.markdown("""
        <div style="text-align:center; padding:2rem 0 1.5rem;">
            <div style="font-size:24px; font-weight:500; color:#fff; letter-spacing:-0.4px; margin-bottom:6px;">
                🚀 LeadPulse Pro
            </div>
            <div style="font-size:12px; color:rgba(255,255,255,0.3);">
                Production Grade Lead Extraction Engine
            </div>
        </div>
    """, unsafe_allow_html=True)

    # Two clickable cards
    col1, col2 = st.columns(2, gap="medium")

    with col1:
        st.markdown("""
            <div style="background:#1E293B; border:0.5px solid rgba(255,255,255,0.08);
                border-top:2px solid #F59E0B; border-radius:14px; padding:18px 16px;
                text-align:center; cursor:pointer; margin-bottom:10px;">
                <div style="font-size:10px; font-weight:500; padding:2px 10px;
                    background:rgba(245,158,11,0.15); color:#F59E0B; border-radius:20px;
                    display:inline-block; margin-bottom:10px; letter-spacing:0.05em;">
                    ADMIN
                </div>
                <div style="font-size:36px; margin-bottom:8px;">🛡️</div>
                <div style="font-size:14px; font-weight:500; color:#fff; margin-bottom:4px;">
                    Admin Console
                </div>
                <div style="font-size:11px; color:rgba(255,255,255,0.3); line-height:1.5;">
                    Platform management, users and system control
                </div>
            </div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown("""
            <div style="background:#1E293B; border:0.5px solid rgba(255,255,255,0.08);
                border-top:2px solid #2563EB; border-radius:14px; padding:18px 16px;
                text-align:center; cursor:pointer; margin-bottom:10px;">
                <div style="font-size:10px; font-weight:500; padding:2px 10px;
                    background:rgba(37,99,235,0.15); color:#60A5FA; border-radius:20px;
                    display:inline-block; margin-bottom:10px; letter-spacing:0.05em;">
                    USER
                </div>
                <div style="font-size:36px; margin-bottom:8px;">👤</div>
                <div style="font-size:14px; font-weight:500; color:#fff; margin-bottom:4px;">
                    User Workspace
                </div>
                <div style="font-size:11px; color:rgba(255,255,255,0.3); line-height:1.5;">
                    Generate leads, export data and manage plan
                </div>
            </div>
        """, unsafe_allow_html=True)

    # Login mode selector
    login_mode = st.session_state.get("login_mode", None)

    col3, col4 = st.columns(2, gap="medium")
    with col3:
        if st.button("🛡️ Login as Admin", key="select_admin", use_container_width=True):
            st.session_state.login_mode = "admin"
            st.rerun()
    with col4:
        if st.button("👤 Login as User", key="select_user", use_container_width=True):
            st.session_state.login_mode = "user"
            st.rerun()

    # Show credentials form based on selection
    if login_mode == "admin":
        st.markdown("""
            <div style="background:#1E293B; border:0.5px solid rgba(255,255,255,0.08);
                border-top:2px solid #F59E0B; border-radius:14px;
                padding:20px 20px 8px; margin-top:4px;">
                <div style="display:flex; align-items:center; gap:8px; margin-bottom:14px;">
                    <span style="font-size:18px;">🛡️</span>
                    <span style="font-size:14px; font-weight:500; color:#fff;">
                        Admin credentials
                    </span>
                </div>
            </div>
        """, unsafe_allow_html=True)

        admin_user = st.text_input("Username", placeholder="admin", key="admin_u")
        admin_pass = st.text_input("Password", type="password", placeholder="••••••••", key="admin_p")

        col5, col6 = st.columns([3, 1])
        with col5:
            if st.button("→ Enter Admin Console", key="admin_submit", use_container_width=True):
                if not admin_user or not admin_pass:
                    st.error("Enter username and password")
                else:
                    success, role, plan = login(admin_user, admin_pass)
                    if success and role == "admin":
                        st.session_state.authenticated = True
                        st.session_state.username = admin_user
                        st.session_state.role = role
                        st.session_state.plan = plan
                        st.session_state.login_time = datetime.now()
                        st.session_state.login_mode = None
                        st.rerun()
                    elif success and role != "admin":
                        st.error("This account does not have admin access")
                    else:
                        st.error("Invalid admin credentials")
        with col6:
            if st.button("✕ Cancel", key="cancel_admin", use_container_width=True):
                st.session_state.login_mode = None
                st.rerun()

    elif login_mode == "user":
        st.markdown("""
            <div style="background:#1E293B; border:0.5px solid rgba(255,255,255,0.08);
                border-top:2px solid #2563EB; border-radius:14px;
                padding:20px 20px 8px; margin-top:4px;">
                <div style="display:flex; align-items:center; gap:8px; margin-bottom:14px;">
                    <span style="font-size:18px;">👤</span>
                    <span style="font-size:14px; font-weight:500; color:#fff;">
                        User credentials
                    </span>
                </div>
            </div>
        """, unsafe_allow_html=True)

        user_user = st.text_input("Username", placeholder="your username", key="user_u")
        user_pass = st.text_input("Password", type="password", placeholder="••••••••", key="user_p")

        col7, col8 = st.columns([3, 1])
        with col7:
            if st.button("→ Enter Workspace", key="user_submit", use_container_width=True):
                if not user_user or not user_pass:
                    st.error("Enter username and password")
                else:
                    success, role, plan = login(user_user, user_pass)
                    if success:
                        st.session_state.authenticated = True
                        st.session_state.username = user_user
                        st.session_state.role = role
                        st.session_state.plan = plan
                        st.session_state.login_time = datetime.now()
                        st.session_state.login_mode = None
                        st.rerun()
                    else:
                        st.error("Invalid username or password")
        with col8:
            if st.button("✕ Cancel", key="cancel_user", use_container_width=True):
                st.session_state.login_mode = None
                st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)

    # Register section
    st.markdown("""
        <div style="background:#1E293B; border:0.5px solid rgba(255,255,255,0.07);
            border-radius:10px; padding:12px 16px;
            display:flex; align-items:center; justify-content:space-between;
            margin-bottom:10px;">
            <div>
                <div style="font-size:12px; font-weight:500; color:#fff; margin-bottom:2px;">
                    New to LeadPulse Pro?
                </div>
                <div style="font-size:11px; color:rgba(255,255,255,0.3);">
                    50 leads/session free — no credit card needed
                </div>
            </div>
        </div>
    """, unsafe_allow_html=True)

    with st.expander("Create free account"):
        reg_user = st.text_input("Username", placeholder="min 3 characters", key="reg_user")
        reg_pass = st.text_input("Password", type="password", placeholder="min 6 characters", key="reg_pass")
        reg_name = st.text_input("Full name", placeholder="Your name", key="reg_name")
        reg_email = st.text_input("Email", placeholder="your@email.com", key="reg_email")
        if st.button("Create account", key="reg_btn", use_container_width=True):
            if not reg_user or not reg_pass:
                st.error("Username and password required")
            else:
                success, msg = register_user(
                    reg_user, reg_pass,
                    role="user", plan="Free",
                    name=reg_name, email=reg_email
                )
                st.success(msg + " — Login using User card above") if success else st.error(msg)

    # Privacy bar
    st.markdown("""
        <div style="text-align:center; font-size:11px;
            color:rgba(255,255,255,0.2); margin-top:12px; padding:10px;">
            🔒 Your data is encrypted and never shared — secured by LeadPulse Pro
        </div>
    """, unsafe_allow_html=True)

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

# Startup sync complete

# Initialize scheduler once
if "scheduler" not in st.session_state:
    st.session_state.scheduler = start_scheduler()

# ==========================================
# MODERN SAAS UI CSS
# ==========================================
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600&display=swap');
@import url('https://cdn.jsdelivr.net/npm/@tabler/icons-webfont@latest/tabler-icons.min.css');

html, body, [data-testid="stAppViewContainer"], .main, .stMarkdown, p, h1, h2, h3, h4, h5, h6, label {
    font-family: 'Inter', sans-serif !important;
}

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

/* Native progress bars will render beautifully */

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
    """Always reload fresh stats from database."""
    try:
        df = database.load_db()
        if df.empty:
            return 0, 0, 0
        total = len(df)
        today = datetime.now().strftime("%Y-%m-%d")
        date_col = "scraped_date" if "scraped_date" in df.columns else None
        if date_col:
            today_count = len(df[df[date_col].astype(str).str.startswith(today)])
        else:
            today_count = 0
        valid = len(df[df["validation_status"] == "Valid"]) if "validation_status" in df.columns else 0
        quality_pct = int((valid / total * 100)) if total > 0 else 0
        return total, today_count, quality_pct
    except Exception as e:
        logger.debug(f"get_stats error: {e}")
        return 0, 0, 0

# ==========================================
# LOGIN PAGE PLACEHOLDER
# ==========================================
# (Function moved higher to prevent NameError on startup execution)

def normalize_str(val):
    if not val:
        return ""
    return "".join(c for c in str(val).lower() if c.isalnum())

def get_lead_keys(lead):
    name = lead.get("name") or lead.get("business_name")
    name_norm = normalize_str(name)
    if not name_norm:
        return []
    keys = []
    phone = lead.get("phone")
    phone_norm = normalize_str(phone)
    if phone_norm:
        keys.append(f"np_{name_norm}_{phone_norm}")
    maps_url = lead.get("google_maps_url") or lead.get("maps_url")
    maps_url_norm = normalize_str(maps_url)
    if maps_url_norm:
        keys.append(f"nm_{name_norm}_{maps_url_norm}")
    address = lead.get("address")
    address_norm = normalize_str(address)
    if address_norm:
        keys.append(f"na_{name_norm}_{address_norm}")
    return keys

def is_duplicate_lead(lead1, lead2):
    keys1 = get_lead_keys(lead1)
    keys2 = get_lead_keys(lead2)
    if not keys1 or not keys2:
        return False
    return not set(keys1).isdisjoint(keys2)

def is_db_duplicate_lead(lead1, lead2):
    name1 = normalize_str(lead1.get("name") or lead1.get("business_name"))
    name2 = normalize_str(lead2.get("name") or lead2.get("business_name"))
    if not name1 or name1 != name2:
        return False
    phone1 = normalize_str(lead1.get("phone"))
    phone2 = normalize_str(lead2.get("phone"))
    if phone1 and phone2 and phone1 == phone2:
        return True
    url1 = normalize_str(lead1.get("google_maps_url") or lead1.get("maps_url"))
    url2 = normalize_str(lead2.get("google_maps_url") or lead2.get("maps_url"))
    if url1 and url2 and url1 == url2:
        return True
    return False

def get_query_variants(keyword):
    kw_lower = keyword.lower()
    variants = [keyword]
    if "hotel" in kw_lower:
        variants.extend(["Budget hotels", "Lodges", "Guest houses", "Service apartments"])
    elif "restaurant" in kw_lower or "food" in kw_lower or "cafe" in kw_lower:
        variants.extend(["Family restaurants", "Cafes", "Biryani restaurants", "Fast food restaurants"])
    elif "hospital" in kw_lower or "clinic" in kw_lower or "doctor" in kw_lower:
        variants.extend(["Clinics", "Medical centers", "Health care", "Doctors"])
    elif "school" in kw_lower or "college" in kw_lower or "coaching" in kw_lower:
        variants.extend(["Coaching centers", "Academies", "Institutes", "Training centers"])
    elif "real estate" in kw_lower or "property" in kw_lower or "builder" in kw_lower:
        variants.extend(["Property dealers", "Builders", "Real estate agents", "Apartments"])
    else:
        variants.extend([f"Best {keyword}", f"Top {keyword}", f"Local {keyword}", f"Affordable {keyword}"])
    return variants


def get_sub_regions_ai(keyword: str, region: str, city: str) -> list:
    """
    Use Gemini AI to generate detailed sub-regions for a given area.
    Falls back to hardcoded sub-regions and city-wide hubs if needed.
    Nested areas (e.g. Banjara Hills, Kukatpally) are expanded to their sub-regions/roads.
    """
    specific_area_fallback = {
        "kphb": ["KPHB Phase 1", "KPHB Phase 2", "KPHB Phase 3", "KPHB Phase 4", "KPHB Phase 5", "KPHB Phase 6", "KPHB Phase 7", "KPHB Phase 8", "KPHB Phase 9", "KPHB Main Road", "Kukatpally Main Road", "JNTU Road KPHB", "KPHB Colony"],
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
        "hyderabad": ["KPHB", "Kukatpally", "JNTU Road", "Hitech City", "Madhapur", "Gachibowli", "Kondapur", "Miyapur", "Ameerpet", "Banjara Hills", "Hyderabad"],
        "chennai": ["T Nagar", "Anna Nagar", "Adyar", "Velachery", "Nungambakkam", "Mylapore", "Tambaram", "OMR", "Porur", "Chromepet"],
        "bangalore": ["Koramangala", "Indiranagar", "Whitefield", "Electronic City", "Jayanagar", "HSR Layout", "Marathahalli", "JP Nagar", "Bannerghatta", "BTM Layout"],
        "vijayawada": ["Benz Circle", "MG Road", "Governorpet", "Labbipet", "Patamata", "Gunadala", "Suryaraopet", "Eluru Road", "Auto Nagar", "Kandrika"],
        "guntur": ["Brodipet", "Arundelpet", "Kothapet", "AT Agraharam", "Old Town", "Amaravathi Road", "Vidyanagar", "Nallapadu", "Naaz Centre", "Brindavan Gardens"],
    }

    specific_regions = []
    
    # 1. Try Gemini AI first
    gemini_key = os.environ.get("GEMINI_API_KEY", "")
    if gemini_key and region.strip():
        try:
            import google.generativeai as genai
            genai.configure(api_key=gemini_key)
            prompt = f"""You are a local area expert for {city}, India.
For the area "{region}" in {city}, list all specific sub-areas, phases, road numbers, sectors, and localities where {keyword} businesses might be found.
Be very specific — include road numbers, phase numbers, colony names, sector numbers.
Return ONLY a JSON array of strings. No other text. No markdown."""

            models_to_try = ["gemini-2.0-flash", "gemini-1.5-flash-latest", "gemini-pro"]
            response = None
            for model_name in models_to_try:
                try:
                    model = genai.GenerativeModel(model_name)
                    response = model.generate_content(prompt)
                    if response and response.text:
                        break
                except Exception as model_err:
                    pass

            if response:
                raw = response.text.strip().replace("```json","").replace("```","").strip()
                import json
                res = json.loads(raw)
                if isinstance(res, list) and len(res) > 0:
                    specific_regions = res[:15]
        except Exception as e:
            st.session_state.logs += f"[SYS] AI sub-region generation unavailable. Using fallback sub-regions...\n"

    # 2. Try Hardcoded area fallback if AI failed or not used
    if not specific_regions and region.strip():
        region_lower = region.lower()
        for key, regions in specific_area_fallback.items():
            if key in region_lower:
                specific_regions = list(regions)
                break

    # 3. Get City Hubs Fallback
    city_hubs = []
    city_lower = city.lower()
    for key, regions in city_hubs_fallback.items():
        if key in city_lower:
            city_hubs = regions
            break

    # 4. Combine and Expand Nesting
    specific_sub_regions = []
    fallback_areas = []
    seen = set()
    
    # 4a. Add specific sub-regions first
    for r in specific_regions:
        if r.lower() not in seen:
            specific_sub_regions.append(r)
            seen.add(r.lower())

    # If no specific sub-regions found, just put the user's query region as the first specific sub-region
    if not specific_sub_regions and region.strip():
        specific_sub_regions.append(region.strip())
        seen.add(region.strip().lower())

    # 4b. Add parent region to fallbacks
    region_norm = normalize_str(region)
    if region.strip() and region.strip().lower() not in seen:
        fallback_areas.append(region.strip())
        seen.add(region.strip().lower())

    # Add 'near' parent region fallback
    if region.strip():
        fallback_areas.append(f"near {region.strip()}")

    # 4c. Add city hubs as fallback (excluding the user's primary region to prevent duplicate processing of it)
    for r in city_hubs:
        r_lower = r.lower()
        r_norm = normalize_str(r)
        
        # Skip the user's primary region or matches to avoid duplication
        if region_norm and (region_norm in r_lower or r_lower in region_norm or r_norm in region_norm):
            continue
            
        matched_fallback_key = None
        for key in specific_area_fallback.keys():
            if key in r_lower or r_lower in key:
                matched_fallback_key = key
                break
                
        if matched_fallback_key:
            # Expand this hub into its sub-regions
            for sub_area in specific_area_fallback[matched_fallback_key]:
                sub_area_lower = sub_area.lower()
                if region_norm and (region_norm in sub_area_lower or sub_area_lower in region_norm):
                    continue
                if sub_area_lower not in seen:
                    fallback_areas.append(sub_area)
                    seen.add(sub_area_lower)
        else:
            if r_lower not in seen:
                fallback_areas.append(r)
                seen.add(r_lower)

    # 4d. Add empty string as city-wide fallback
    if "" not in seen:
        fallback_areas.append("")

    return specific_sub_regions, fallback_areas


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
            from subscription import can_use_linkedin
            current_plan = st.session_state.get("plan", "Free")
            linkedin_allowed = can_use_linkedin(current_plan)

            source_options = ["Google Maps"]
            if linkedin_allowed:
                source_options.append("LinkedIn")
            else:
                source_options.append("LinkedIn 🔒 (Starter+)")

            source = st.selectbox(
                "Source",
                source_options,
                key=f"src_{label_suffix}"
            )

            # Block LinkedIn if not allowed
            if "LinkedIn 🔒" in source:
                st.warning(f"🔒 LinkedIn requires Starter plan. You are on {current_plan}.")
                source = "Google Maps"

        # Row 2 — City and Region
        c3_col, c4_col = st.columns(2)
        with c3_col:
            city = st.text_input(
                "City",
                placeholder="e.g. Hyderabad",
                key=f"city_{label_suffix}"
            )
        with c4_col:
            region = st.text_input(
                "Region / Area",
                placeholder="e.g. KPHB, Banjara Hills",
                key=f"region_{label_suffix}"
            )

        # Row 3 — Max leads, AI toggle, Source
        c5, c6, c7 = st.columns([2, 1, 1])
        with c5:
            # Slider limits per plan — exact values from Day 12 subscription
            plan_slider_limits = {
                "Free": 50,
                "Starter": 200,
                "Pro": 1000,
                "Enterprise": 999999
            }

            current_plan = st.session_state.get("plan", "Free")
            plan_max = plan_slider_limits.get(current_plan, 50)

            if plan_max >= 999999:
                plan_label = "Unlimited"
                options = list(range(10, 110, 10)) + list(range(150, 550, 50)) + [1000, 2000, 5000, 10000, 50000, 100000, 999999]
            elif plan_max >= 1000:
                plan_label = str(plan_max)
                options = list(range(10, 110, 10)) + list(range(150, plan_max + 1, 50))
            elif plan_max >= 200:
                plan_label = str(plan_max)
                options = list(range(10, plan_max + 1, 10))
            else:
                plan_label = str(plan_max)
                options = list(range(10, plan_max + 1, 10))

            options = sorted(list(set(options)))
            slider_default = min(50, options[-1])
            if slider_default not in options:
                slider_default = options[0]

            max_leads = st.select_slider(
                f"Max Leads / Session (Plan limit: {plan_label})",
                options=options,
                value=slider_default,
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
            btn_generate = False
            btn_resume = False
            
            # Show Resume if extraction stopped mid-way
            if not st.session_state.get("is_extracting", False) and st.session_state.get("remaining_leads", 0) > 0 and len(st.session_state.get("session_leads", [])) > 0:
                btn_resume = st.button(
                    f"▶️ Resume Extraction ({st.session_state.get('collected_leads', 0)}/{st.session_state.get('target_leads', 0)})",
                    key=f"btn_resume_{label_suffix}",
                    use_container_width=True
                )
            else:
                btn_generate = st.button(
                    "🚀 Generate Leads",
                    disabled=st.session_state.get("is_extracting", False),
                    key=f"btn_{label_suffix}",
                    use_container_width=True
                )

    if btn_generate:
        if max_leads > max_allowed:
            st.error(f"Your {current_plan} plan allows max {max_allowed} leads per session.")
            render_upgrade_banner(current_plan)
            return

        # Handle LinkedIn source
        if "LinkedIn" in source and "🔒" not in source:
            if not can_use_linkedin(current_plan):
                st.error(get_upgrade_message(current_plan, "linkedin"))
                render_upgrade_banner(current_plan)
                return

            keyword = custom_keyword.strip() if custom_keyword.strip() else category

            if not city.strip():
                st.warning("Please enter a city name.")
                return

            st.session_state.is_extracting = True
            st.session_state.session_leads = []
            st.session_state.logs = ""

            progress_bar = st.progress(0)
            status_text = st.empty()
            log_placeholder = st.empty()
            metrics_placeholder = st.empty()
            table_placeholder = st.empty()

            with metrics_placeholder.container():
                mc1, mc2, mc3 = st.columns(3)
                m1 = mc1.empty()
                m2 = mc2.empty()
                m3 = mc3.empty()

            status_text.text(f"🔍 Searching LinkedIn: {keyword} in {city}...")
            st.session_state.logs += f"[SYS] Starting LinkedIn scraper...\n"
            log_placeholder.markdown(
                f'<div class="log-box">{st.session_state.logs}</div>',
                unsafe_allow_html=True
            )

            try:
                from linkedin_scraper import scrape_linkedin
                import pandas as pd
                profiles = scrape_linkedin(keyword, city, limit=max_leads)

                st.session_state.logs += f"[SYS] LinkedIn returned {len(profiles)} profiles\n"
                log_placeholder.markdown(
                    f'<div class="log-box">{st.session_state.logs}</div>',
                    unsafe_allow_html=True
                )

                for i, profile in enumerate(profiles):
                    st.session_state.session_leads.append(profile)
                    progress_bar.progress((i+1)/max(len(profiles),1))
                    status_text.text(f"LinkedIn: {i+1}/{len(profiles)} profiles collected...")
                    m1.metric("Total Scraped", i+1)
                    m2.metric("Valid Leads", i+1)
                    m3.metric("Duplicates Skipped", 0)
                    st.session_state.logs += f"[SYS] ✅ {profile.get('name','')[:40]}\n"

                    with table_placeholder.container():
                        df_view = pd.DataFrame(st.session_state.session_leads)
                        linkedin_cols = [c for c in [
                            "name", "description", "email",
                            "website", "category", "validation_status"
                        ] if c in df_view.columns]
                        st.dataframe(
                            df_view[linkedin_cols] if linkedin_cols else df_view,
                            hide_index=True
                        )

                # Save to database
                if st.session_state.session_leads:
                    database.save_to_db(st.session_state.session_leads)
                    try:
                        success, msg = google_sheets.save_to_google_sheets(
                            st.session_state.session_leads
                        )
                        if success:
                            st.success(f"✅ {len(profiles)} LinkedIn profiles saved!")
                        else:
                            st.warning(f"Saved locally. Sheets: {msg}")
                    except Exception as e:
                        st.warning(f"Sheets sync: {e}")
                else:
                    st.warning("LinkedIn returned 0 profiles. Try different keyword or city.")

            except Exception as e:
                st.error(f"LinkedIn error: {e}")
                st.session_state.logs += f"[SYS] LinkedIn error: {e}\n"

            st.session_state.is_extracting = False
            import time as _time
            _time.sleep(1)
            st.rerun()
            return

        keyword = custom_keyword.strip() if custom_keyword.strip() else category
        if not city:
            st.warning("Please enter a city name.")
            return

        st.session_state.is_extracting = True
        st.session_state.target_leads = max_leads
        st.session_state.collected_leads = 0
        st.session_state.remaining_leads = max_leads
        st.session_state.session_leads = []
        st.session_state.logs = ""
        st.session_state.completed_batches = 0
        
        # State machine init
        st.session_state.keyword = keyword
        st.session_state.city = city
        st.session_state.region = region
        
        status_text = st.empty()
        status_text.text(f"🤖 AI analyzing sub-regions for {region or city}...")
        st.session_state.specific_sub_regions, st.session_state.fallback_areas = get_sub_regions_ai(keyword, region or city, city)
        
        st.session_state.phase = 1
        st.session_state.area_idx = 0
        st.session_state.fallback_idx = 0
        st.session_state.q_idx = 0
        st.session_state.consecutive_zero_yields = 0
        st.session_state.area_duplicates = 0
        
        st.rerun()

    if btn_resume:
        st.session_state.is_extracting = True
        st.session_state.setdefault("area_duplicates", 0)
        st.rerun()

    if st.session_state.get("is_extracting", False):
        progress_bar = st.progress(min(st.session_state.collected_leads / st.session_state.target_leads, 1.0) if st.session_state.target_leads else 0.0)
        status_text = st.empty()
        stop_placeholder = st.empty()
        log_placeholder = st.empty()
        metrics_placeholder = st.empty()
        table_placeholder = st.empty()

        with stop_placeholder.container():
            if st.button("⏹️ Stop Extraction", key=f"stop_{label_suffix}_{label_suffix}"):
                st.session_state.is_extracting = False
                st.warning("Extraction stopped by user. You can resume later.")
                import time as _time
                _time.sleep(2)
                st.rerun()

        with metrics_placeholder.container():
            m1, m2, m3 = st.columns(3)
            m1_metric = m1.empty()
            m2_metric = m2.empty()
            m3_metric = m3.empty()
            
        m1_metric.metric("Total Scraped", st.session_state.collected_leads)
        valid_count = len([x for x in st.session_state.session_leads if x.get("validation_status") == "Valid"])
        m2_metric.metric("Valid Leads", valid_count)
        
        try:
            df_db = database.load_db()
            db_leads_list = df_db.to_dict(orient="records")
        except:
            db_leads_list = []

        seen_session_ids = set()
        for l in st.session_state.session_leads:
            for k in get_lead_keys(l):
                seen_session_ids.add(k)

        # Batch execution
        batch_target = 10
        fast_mode = st.session_state.target_leads >= 50
        if fast_mode and "fast_mode_logged" not in st.session_state:
            st.session_state.logs += "[SYS] Fast Mode Enabled\n"
            st.session_state["fast_mode_logged"] = True
            
        initial_collected = st.session_state.collected_leads
        batch_collected = 0
        duplicates_skipped = 0
        
        # UI log refresh
        log_placeholder.markdown(f'<div class="log-box">{st.session_state.logs[-3000:]}</div>', unsafe_allow_html=True)
        
        while st.session_state.get("is_extracting", False) and st.session_state.collected_leads < st.session_state.target_leads:
            
            # Determine Query
            query = ""
            current_sub_region = ""
            
            if st.session_state.phase == 1:
                if st.session_state.area_idx >= len(st.session_state.specific_sub_regions):
                    st.session_state.phase = 2
                    st.session_state.logs += "[SYS] All sub-regions attempted. Starting broader fallback...\n"
                    log_placeholder.markdown(f'<div class="log-box">{st.session_state.logs[-3000:]}</div>', unsafe_allow_html=True)
                    continue
                    
                current_sub_region = st.session_state.specific_sub_regions[st.session_state.area_idx]
                query = f"{st.session_state.keyword} in {current_sub_region} {st.session_state.city}"
                st.session_state.logs += f"[SYS] Sub-region attempted: {current_sub_region} | Query: {query}\n"
                
            elif st.session_state.phase == 2:
                if st.session_state.fallback_idx >= len(st.session_state.fallback_areas):
                    st.session_state.phase = 3
                    break
                    
                fallback_area = st.session_state.fallback_areas[st.session_state.fallback_idx]
                query_variants = get_query_variants(st.session_state.keyword)
                
                max_q = 2 if fast_mode else len(query_variants)
                if st.session_state.q_idx >= max_q:
                    st.session_state.fallback_idx += 1
                    st.session_state.q_idx = 0
                    st.session_state.consecutive_zero_yields = 0
                    continue
                    
                q_variant = query_variants[st.session_state.q_idx]
                if q_variant.startswith("Top ") and any(v.startswith("Best ") for v in query_variants):
                    st.session_state.logs += f"[SYS] Skipping similar query: {q_variant} because Best {st.session_state.keyword} already used\n"
                    st.session_state.q_idx += 1
                    continue
                    
                if fallback_area:
                    query = f"{q_variant} in {fallback_area} {st.session_state.city}"
                else:
                    query = f"{q_variant} in {st.session_state.city}"
                st.session_state.logs += f"[SYS] Fallback Query: {query}\n"
                current_sub_region = fallback_area
                
            else:
                break
                
            status_text.text(f"🔄 Scraping: {query} ({st.session_state.collected_leads}/{st.session_state.target_leads})")
            log_placeholder.markdown(f'<div class="log-box">{st.session_state.logs[-3000:]}</div>', unsafe_allow_html=True)
            
            ai_flag = "1" if use_ai else "0"
            # Keep batch small to prevent Render memory crash
            sub_batch_target = min(batch_target, st.session_state.target_leads - st.session_state.collected_leads, batch_target - batch_collected)
            
            import subprocess
            import sys
            import json
            import os
            process = subprocess.Popen(
                [sys.executable, "-u", "scraper.py", query, str(sub_batch_target), ai_flag],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True,
                env={**os.environ, "PYTHONUNBUFFERED": "1"}
            )

            leads_found_this_query = 0
            duplicates_skipped_this_query = 0
            unique_added_this_query = 0

            for line in process.stdout:
                line = line.strip()
                if line.startswith("DATA:"):
                    try:
                        data = json.loads(line.replace("DATA:", "").strip())
                        leads_found_this_query += 1

                        is_session_dup = False
                        data_keys = get_lead_keys(data)
                        for k in data_keys:
                            if k in seen_session_ids:
                                is_session_dup = True
                                break
                        
                        if is_session_dup:
                            st.session_state.logs += f"[SYS] Session duplicate skipped: {data.get('name', 'Unknown')}\n"
                            duplicates_skipped_this_query += 1
                            duplicates_skipped += 1
                            st.session_state.area_duplicates += 1
                            if duplicates_skipped_this_query >= 5:
                                st.session_state.logs += f"[SYS] Duplicate-heavy query skipped\n"
                                process.terminate()
                                break
                        else:
                            is_db_dup = False
                            for db_lead in db_leads_list:
                                if is_db_duplicate_lead(data, db_lead):
                                    is_db_dup = True
                                    break

                            for k in data_keys:
                                seen_session_ids.add(k)
                                
                            st.session_state.session_leads.append(data)
                            
                            if is_db_dup:
                                st.session_state.logs += f"[SYS] Existing DB duplicate allowed in session: {data.get('name', 'Unknown')}\n"
                            else:
                                database.save_to_db([data])
                                db_leads_list.append(data)
                                
                            unique_added_this_query += 1
                            st.session_state.collected_leads = len(st.session_state.session_leads)
                            st.session_state.remaining_leads = st.session_state.target_leads - st.session_state.collected_leads
                            batch_collected += 1
                            
                            if batch_collected >= batch_target:
                                st.session_state.completed_batches += 1
                                google_sheets.save_to_google_sheets(st.session_state.session_leads)
                                batch_collected = 0
                                st.session_state.logs += f"[SYS] Batch completed {st.session_state.collected_leads}/{st.session_state.target_leads}\n"
                                st.session_state.logs += f"[SYS] Saved progress: {st.session_state.collected_leads}/{st.session_state.target_leads}\n"
                                st.session_state.logs += f"[SYS] Resume available if interrupted\n"

                        valid_count = len([x for x in st.session_state.session_leads if x.get("validation_status") == "Valid"])
                        m1_metric.metric("Total Scraped", st.session_state.collected_leads)
                        m2_metric.metric("Valid Leads", valid_count)
                        m3_metric.metric("Duplicates Skipped", duplicates_skipped)
                        progress_bar.progress(min(st.session_state.collected_leads / st.session_state.target_leads, 1.0))

                        with table_placeholder.container():
                            import pandas as pd
                            df_view = pd.DataFrame(st.session_state.session_leads).iloc[::-1]
                            cols = [c for c in ["name", "phone", "email", "sub_region", "validation_status"] if c in df_view.columns]
                            st.dataframe(df_view[cols] if cols else df_view, hide_index=True)
                    except Exception as e:
                        import logging
                        logging.debug(f"Data parse error: {e}")

                elif line.startswith("LOG:"):
                    msg = line.replace("LOG:", "").strip()
                    st.session_state.logs += f"[SYS] {msg}\n"
                    log_placeholder.markdown(f'<div class="log-box">{st.session_state.logs[-3000:]}</div>', unsafe_allow_html=True)

            process.wait()
            
            import time as _time
            _time.sleep(1)  # Let Render recover memory between batches

            if st.session_state.phase == 1:
                if st.session_state.get("area_duplicates", 0) > 5:
                    st.session_state.logs += f"[SYS] Duplicate threshold reached for {current_sub_region}. Moving to next area...\n"
                st.session_state.area_idx += 1
                st.session_state.area_duplicates = 0
                if st.session_state.area_idx < len(st.session_state.specific_sub_regions):
                    next_area = st.session_state.specific_sub_regions[st.session_state.area_idx]
                    st.session_state.logs += f"[SYS] Moving to next area: {next_area}\n"
                
            elif st.session_state.phase == 2:
                if unique_added_this_query == 0:
                    st.session_state.consecutive_zero_yields += 1
                else:
                    st.session_state.consecutive_zero_yields = 0

                if st.session_state.get("area_duplicates", 0) > 5 or st.session_state.consecutive_zero_yields >= 2:
                    if st.session_state.get("area_duplicates", 0) > 5:
                        st.session_state.logs += f"[SYS] Duplicate threshold reached for {current_sub_region}. Moving to next area...\n"
                    st.session_state.fallback_idx += 1
                    st.session_state.q_idx = 0
                    st.session_state.consecutive_zero_yields = 0
                    st.session_state.area_duplicates = 0
                    if st.session_state.fallback_idx < len(st.session_state.fallback_areas):
                        next_area = st.session_state.fallback_areas[st.session_state.fallback_idx]
                        st.session_state.logs += f"[SYS] Moving to next area: {next_area}\n"
                else:
                    st.session_state.q_idx += 1
                    
            log_placeholder.markdown(f'<div class="log-box">{st.session_state.logs[-3000:]}</div>', unsafe_allow_html=True)
            
        # End of extraction
        if st.session_state.get("is_extracting", False):
            st.session_state.is_extracting = False
            st.session_state.remaining_leads = 0
            if st.session_state.collected_leads >= st.session_state.target_leads:
                st.session_state.logs += f"[SYS] Target reached: {st.session_state.collected_leads}/{st.session_state.target_leads}\n"
                st.success("✅ 100 leads generated successfully.")
            else:
                st.session_state.logs += f"[SYS] All fallback areas exhausted. Final total: {st.session_state.collected_leads}/{st.session_state.target_leads}\n"
            
            log_placeholder.markdown(f'<div class="log-box">{st.session_state.logs[-3000:]}</div>', unsafe_allow_html=True)
            status_text.text("✅ Extraction Complete! Syncing to Cloud...")
            success, msg = google_sheets.save_to_google_sheets(st.session_state.session_leads)
            import time as _time
            _time.sleep(2)
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
        try:
            df_hist = database.load_db()
            if not df_hist.empty and "scraped_date" in df_hist.columns:
                df_hist["date_only"] = pd.to_datetime(
                    df_hist["scraped_date"].astype(str).str[:10],
                    errors="coerce"
                )
                session_history = df_hist.groupby("date_only").agg(
                    leads_collected=("lead_id", "count"),
                    valid_leads=("validation_status", lambda x: (x == "Valid").sum()),
                    categories=(
                        "category",
                        lambda x: ", ".join([str(i) for i in x.dropna().unique()[:3]])
                    )
                ).reset_index()
                session_history = session_history.sort_values("date_only", ascending=False).head(10)
                session_history.columns = ["Date", "Leads Collected", "Valid Leads", "Categories"]
                st.dataframe(session_history, hide_index=True, use_container_width=True)
            else:
                st.info("No session history yet")
        except Exception as e:
            st.info(f"Session history loading: {e}")

    except ImportError:
        st.error("Plotly not installed. Add 'plotly' to requirements.txt")
    except Exception as e:
        st.error(f"Analytics error: {e}")

def show_user_dashboard():
    # Privacy bar
    st.markdown('''
        <div class="privacy-bar">
            🛡️ Your lead data is protected — stored securely and never shared with third parties.
        </div>
    ''', unsafe_allow_html=True)

    # Metric cards at top
    total_db, today_db, quality_pct = get_stats()
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(f'<div class="metric-card"><div class="metric-label">Session Leads</div><div class="metric-value">{len(st.session_state.session_leads)}</div></div>', unsafe_allow_html=True)
    with c2:
        st.markdown(f'<div class="metric-card"><div class="metric-label">Data Accuracy</div><div class="metric-value">{quality_pct}%</div></div>', unsafe_allow_html=True)
    with c3:
        status_text = "ACTIVE" if st.session_state.get("is_extracting", False) else "IDLE"
        st.markdown(f'<div class="metric-card"><div class="metric-label">Engine Status</div><div class="metric-value">{status_text}</div></div>', unsafe_allow_html=True)
    with c4:
        gs_connected = google_sheets.check_connection()
        gs_text = "Connected" if gs_connected else "Offline"
        st.markdown(f'<div class="metric-card"><div class="metric-label">Cloud Sync</div><div class="metric-value">{gs_text}</div></div>', unsafe_allow_html=True)

    st.markdown("<br><hr><br>", unsafe_allow_html=True)

    # 4 horizontal tabs matching My Leads etc.
    tab1, tab2, tab3, tab4 = st.tabs([
        "🚀 Generate",
        "📋 My Leads",
        "📊 Analytics",
        "💰 Billing"
    ])

    with tab1:
        generation_ui()
        if not st.session_state.get("is_extracting", False) and st.session_state.get("session_leads", []):
            st.markdown("### ⚡ Session Preview")
            import pandas as pd
            st.dataframe(pd.DataFrame(st.session_state.session_leads), hide_index=True)

    with tab2:
        if st.session_state.session_leads:
            st.markdown("### 📋 My Leads Table")
            import pandas as pd
            df = pd.DataFrame(st.session_state.session_leads)
            status_filter = st.multiselect(
                "Filter by Status",
                options=df["validation_status"].unique() if "validation_status" in df.columns else [],
                key="usr_filt_status"
            )
            if status_filter and "validation_status" in df.columns:
                df = df[df["validation_status"].isin(status_filter)]
            user_cols = ["name", "address", "phone", "email", "rating", "reviews", "category", "validation_status"]
            st.dataframe(df[[c for c in user_cols if c in df.columns]], hide_index=True)
            st.markdown("---")
            render_export_ui(df, "Export My Leads")
        else:
            st.info("💡 Generate leads first to see your leads table.")

    with tab3:
        show_user_analytics(st.session_state.get("username", ""))

    with tab4:
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
        "⏰ Scheduler",
        "🛠️ System Settings"
    ])

    # ==========================================
    # TAB 1 — Generate
    # ==========================================
    with tabs[0]:
        generation_ui("(Admin)")
        if not st.session_state.get("is_extracting", False) and st.session_state.get("session_leads", []):
            st.markdown("### ⚡ Session Preview")
            st.dataframe(pd.DataFrame(st.session_state.session_leads), hide_index=True)

    # ==========================================
    # TAB 2 — Master Database
    # ==========================================
    with tabs[1]:
        st.markdown("### 🗄️ Master Lead Repository")
        df_master = database.load_db()
        if df_master.empty:
            st.info("No leads in database yet. Generate leads first.")
        else:
            st.markdown(f"**Total: {len(df_master)} leads**")
            # filters
            col1, col2, col3 = st.columns(3)
            with col1:
                status_filter = st.multiselect(
                    "Filter by Status",
                    options=df_master["validation_status"].unique().tolist() if "validation_status" in df_master.columns else [],
                    key="master_status_filter"
                )
            with col2:
                cat_filter = st.multiselect(
                    "Filter by Category",
                    options=df_master["category"].dropna().unique().tolist() if "category" in df_master.columns else [],
                    key="master_cat_filter"
                )
            with col3:
                search = st.text_input("Search name", key="master_search")

            filtered = df_master.copy()
            if status_filter and "validation_status" in filtered.columns:
                filtered = filtered[filtered["validation_status"].isin(status_filter)]
            if cat_filter and "category" in filtered.columns:
                filtered = filtered[filtered["category"].isin(cat_filter)]
            if search and "name" in filtered.columns:
                filtered = filtered[filtered["name"].str.contains(search, case=False, na=False)]

            st.markdown(f"Showing **{len(filtered)}** of **{len(df_master)}** leads")
            display_cols = ["name", "phone", "email", "category", "rating", "sub_region", "validation_status", "scraped_date"]
            show_cols = [c for c in display_cols if c in filtered.columns]
            st.dataframe(filtered[show_cols], hide_index=True, use_container_width=True)

            col4, col5 = st.columns(2)
            with col4:
                csv = filtered.to_csv(index=False).encode("utf-8")
                st.download_button("📥 Export CSV (Quick Download)", csv, "master_leads.csv", "text/csv", use_container_width=True)
            with col5:
                json_data = filtered.to_json(orient="records").encode("utf-8")
                st.download_button("📥 Export JSON (Quick Download)", json_data, "master_leads.json", "application/json", use_container_width=True)

            st.markdown("---")
            with st.expander("📥 Advanced Export Tools (Excel, PDF, Google Sheets)", expanded=True):
                from export_module import render_export_ui
                render_export_ui(filtered, "Export Master Database")

    # ==========================================
    # TAB 3 — User Management (CRUD)
    # ==========================================
    with tabs[2]:
        st.markdown("### 👥 User Management")
        from auth import get_all_users, register_user, delete_user, update_user_plan, update_password

        # Always reload fresh
        all_users_list = get_all_users()
        if all_users_list:
            df_users = pd.DataFrame(all_users_list)
            display_user_cols = ["username", "role", "plan", "name", "email", "created_at"]
            show_user_cols = [c for c in display_user_cols if c in df_users.columns]
            st.dataframe(df_users[show_user_cols], hide_index=True, use_container_width=True)
            st.markdown(f"**Total users: {len(all_users_list)}**")
        else:
            st.info("No users found")

        st.markdown("---")

        # CRUD operations
        st.markdown("#### 🛠️ Account Actions")

        with st.expander("➕ Create New User", expanded=False):
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

        with st.expander("✏️ Edit User Plan", expanded=False):
            edit_username = st.text_input("Username to edit", key="crud_edit_name")
            new_plan = st.selectbox("New Plan", ["Free", "Starter", "Pro", "Enterprise"], key="crud_edit_plan")
            if st.button("Update Plan", key="crud_update"):
                if update_user_plan(edit_username, new_plan):
                    st.success(f"Plan updated for {edit_username}")
                    st.rerun()
                else:
                    st.error("User not found")

        with st.expander("🔑 Reset Password", expanded=False):
            reset_user = st.text_input("Username", key="crud_reset_name")
            reset_pass = st.text_input("New Password", type="password", key="crud_reset_pass")
            if st.button("Reset Password", key="crud_reset"):
                if update_password(reset_user, reset_pass):
                    st.success(f"Password reset for {reset_user}")
                else:
                    st.error("User not found")

        with st.expander("🚫 Suspend / Delete User", expanded=False):
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
            df_analytics = database.load_db()
            total_analytics = len(df_analytics)
            if total_analytics > 0 and "validation_status" in df_analytics.columns:
                for status in ["Valid", "Invalid", "Pending"]:
                    count = len(df_analytics[df_analytics["validation_status"] == status])
                    pct = int(count / total_analytics * 100) if total_analytics > 0 else 0
                    st.progress(pct / 100, text=f"{status}: {count} leads ({pct}%)")
            else:
                st.info("Generate leads to see quality report")
        else:
            st.info("Generate leads to see analytics")

    # ==========================================
    # TAB 6 — Revenue
    # ==========================================
    with tabs[5]:
        st.markdown("### 💰 Revenue Dashboard")
        from auth import get_all_users
        all_users_rev = get_all_users()
        plan_revenue = {"Free": 0, "Starter": 29, "Pro": 79, "Enterprise": 500}
        mrr = sum(plan_revenue.get(u.get("plan", "Free"), 0) for u in all_users_rev)
        plan_counts = {}
        for u in all_users_rev:
            p = u.get("plan", "Free")
            plan_counts[p] = plan_counts.get(p, 0) + 1

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Monthly Revenue (MRR)", f"${mrr}")
        c2.metric("Total Users", len(all_users_rev))
        paid = sum(1 for u in all_users_rev if u.get("plan","Free") != "Free")
        c3.metric("Paid Users", paid)
        c4.metric("Free Users", plan_counts.get("Free", 0))

        st.markdown("---")
        st.markdown("**Users by Plan:**")
        plan_df = pd.DataFrame([
            {"Plan": k, "Users": v, "Monthly Revenue": f"${v * plan_revenue.get(k,0)}"}
            for k, v in plan_counts.items()
        ])
        st.dataframe(plan_df, hide_index=True, use_container_width=True)

    # ==========================================
    # TAB 7 — Scheduler
    # ==========================================
    with tabs[6]:
        render_scheduler_ui(st.session_state.get("plan", "Free"))

    # ==========================================
    # TAB 8 — System Settings
    # ==========================================
    with tabs[7]:
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


with st.sidebar:
    st.markdown("""
    <div style="color:white; font-size:20px; 
                font-weight:700; margin-bottom:20px;">
        🚀 LeadPulse  Pro
    </div>
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
    
    # after user info section add live stats
    try:
        # Force fresh stats on every render
        total_db, today_db, quality_pct = get_stats()
        df_live = database.load_db()
        valid_live = len(df_live[df_live["validation_status"] == "Valid"]) if "validation_status" in df_live.columns else 0
        st.markdown(f"""
            <div style="padding:0 8px; font-size:11px; color:rgba(255,255,255,0.4);">
                <div style="margin-bottom:4px;">📊 Total leads: <span style="color:rgba(255,255,255,0.7);">{total_db}</span></div>
                <div>✅ Valid: <span style="color:#22C55E;">{valid_live}</span></div>
            </div>
        """, unsafe_allow_html=True)
    except:
        pass
    
    if st.button("🏠  Admin Workspace", 
                 key="nav_admin_workspace"):
        st.session_state.admin_page = "Generate"
        st.rerun()
    
    st.markdown("""
    <hr style="border-color:rgba(255,255,255,0.1); 
               margin-top:20px; margin-bottom:12px;"/>
    <div style="color:#64748b; font-size:11px; 
                font-weight:600; margin-bottom:8px;">
        ENGINE STATUS
    </div>
    <div style="color:#4ade80; font-size:13px; 
                font-weight:600; margin-bottom:24px;">
        ● IDLE
    </div>
    """, unsafe_allow_html=True)
    
    if st.button("Sign Out Session", 
                 key="admin_signout",
                 type="primary",
                 use_container_width=True):
        st.session_state.clear()
        st.rerun()

if st.session_state.role == "admin":
    show_admin_dashboard()
else:
    show_user_dashboard()
