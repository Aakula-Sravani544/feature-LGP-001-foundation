import streamlit as st
import pandas as pd
import os
import subprocess
import sys
import json
from datetime import datetime

import database

st.set_page_config(
    page_title="LeadPulse Pro | Production Lead Engine",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');
    html, body, [class*="css"] { font-family: 'Plus Jakarta Sans', sans-serif; }
    .stApp { background-color: #FFFFFF; }
    .metric-card { background: white; padding: 24px; border-radius: 15px; border: 1px solid #F3F4F6; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05); text-align: center; }
    .metric-label { color: #6B7280; font-size: 0.75rem; font-weight: 700; text-transform: uppercase; margin-bottom: 8px; }
    .metric-value { color: #111827; font-size: 2rem; font-weight: 800; }
    .log-box { background-color: #111827; color: #10B981; padding: 20px; border-radius: 12px; font-family: 'Courier New', monospace; font-size: 0.85rem; height: 300px; overflow-y: auto; }
    div.stButton > button:first-child { background-color: #FF4B4B !important; color: white !important; border: none !important; border-radius: 12px !important; padding: 12px 24px !important; font-weight: 700 !important; width: 100%; }
    div.stButton > button:hover { background-color: #E03E3E !important; }
    </style>
    """, unsafe_allow_html=True)

if 'is_scraping' not in st.session_state: st.session_state.is_scraping = False
if 'session_leads' not in st.session_state: st.session_state.session_leads = []
if 'logs' not in st.session_state: st.session_state.logs = ""

def get_stats():
    try:
        df = database.load_db()
        total = len(df)
        today = 0
        quality = 0
        if total > 0:
            today_str = datetime.now().strftime("%Y-%m-%d")
            today = len(df[df['scraped_at'].str.contains(today_str, na=False)])
            valid = len(df[(df['phone'] != 'N/A') | (df['website'] != 'N/A')])
            quality = int((valid / total) * 100)
        return total, today, quality
    except:
        return 0, 0, 0

with st.sidebar:
    st.markdown("### LeadPulse <span>Pro</span>", unsafe_allow_html=True)
    workspace = st.radio("Workspace", ["User Dashboard", "Admin Dashboard"])
    st.markdown("---")
    st.markdown(f"Engine: :{'orange' if st.session_state.is_scraping else 'green'}[**{'Active' if st.session_state.is_scraping else 'Idle'}**]")

total_db, today_db, quality_pct = get_stats()

if workspace == "User Dashboard":
    st.title("User Dashboard")
    
    c1, c2, c3, c4 = st.columns(4)
    with c1: st.markdown(f'<div class="metric-card"><div class="metric-label">Total Leads</div><div class="metric-value">{total_db}</div></div>', unsafe_allow_html=True)
    with c2: st.markdown(f'<div class="metric-card"><div class="metric-label">Session Leads</div><div class="metric-value">{len(st.session_state.session_leads)}</div></div>', unsafe_allow_html=True)
    with c3: st.markdown(f'<div class="metric-card"><div class="metric-label">Data Quality</div><div class="metric-value">{quality_pct}%</div></div>', unsafe_allow_html=True)
    with c4: st.markdown(f'<div class="metric-card"><div class="metric-label">Engine Status</div><div class="metric-value">{"Active" if st.session_state.is_scraping else "Idle"}</div></div>', unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)

    col1, col2 = st.columns([4, 1])
    query = col1.text_input("Enter Query", placeholder="Dentists Hyderabad", label_visibility="collapsed")
    if col2.button("Generate Leads", disabled=st.session_state.is_scraping):
        if query:
            st.session_state.is_scraping = True
            st.session_state.session_leads = []
            st.session_state.logs = ""
            
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
                if not line and process.poll() is not None:
                    break
                if line:
                    if line.startswith("LOG:"):
                        st.session_state.logs += line.replace("LOG:", "").strip() + "\n"
                        log_placeholder.markdown(f'<div class="log-box">{st.session_state.logs}</div>', unsafe_allow_html=True)
                    elif line.startswith("DATA:"):
                        try:
                            data = json.loads(line.replace("DATA:", "").strip())
                            st.session_state.session_leads.append(data)
                            with table_placeholder.container():
                                st.dataframe(pd.DataFrame(st.session_state.session_leads).iloc[::-1], width='stretch')
                        except: pass
            
            process.wait()
            st.session_state.is_scraping = False
            st.rerun()

    if not st.session_state.is_scraping and st.session_state.session_leads:
        st.markdown("### Fresh Session Results")
        st.dataframe(pd.DataFrame(st.session_state.session_leads), width='stretch')

else:
    st.title("Admin Dashboard")
    st.markdown("### Master Database")
    
    try:
        df = database.load_db()
        st.write(f"**Total Leads:** {len(df)}")
        st.write(f"**Today Leads:** {today_db}")
        if not df.empty:
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button("Export CSV", csv, "leadpulse_master.csv", "text/csv")
            st.dataframe(df, width='stretch')
        else:
            st.info("No data in database.")
    except Exception as e:
        st.error(f"Error loading database: {str(e)}")
