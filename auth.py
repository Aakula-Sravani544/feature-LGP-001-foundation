import streamlit as st
import streamlit_authenticator as stauth
import yaml
from yaml.loader import SafeLoader
import os

def load_config():
    config_path = os.path.join(os.path.dirname(__file__), 'config.yaml')
    with open(config_path) as file:
        config = yaml.load(file, Loader=SafeLoader)
    return config

def get_authenticator():
    config = load_config()
    authenticator = stauth.Authenticate(
        config['credentials'],
        config['cookie']['name'],
        config['cookie']['key'],
        config['cookie']['expiry_days']
    )
    return authenticator

def inject_login_styles():
    st.markdown("""
        <style>
        /* Hide sidebar and header on login */
        [data-testid="stSidebar"], [data-testid="stHeader"] { visibility: hidden; }
        
        /* Full page gradient background */
        .stApp {
            background: linear-gradient(135deg, #0F172A 0%, #1D4ED8 50%, #E0F2FE 100%) !important;
            background-attachment: fixed !important;
        }

        /* Center container */
        .main .block-container {
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            padding: 0 !important;
        }

        /* Card layout */
        .login-card {
            background: white !important;
            padding: 40px !important;
            border-radius: 16px !important;
            box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.25) !important;
            width: 100% !important;
            max-width: 420px !important;
            text-align: center;
            margin-bottom: 20px;
        }

        .login-title {
            font-size: 2rem !important;
            font-weight: 800 !important;
            color: #0F172A !important;
            margin-bottom: 8px !important;
        }

        .portal-title {
            font-size: 1.25rem !important;
            font-weight: 700 !important;
            color: #1E293B !important;
            margin-bottom: 4px !important;
        }

        .subtitle {
            font-size: 0.9rem !important;
            color: #64748B !important;
            margin-bottom: 24px !important;
        }

        /* Form input styling */
        .stTextInput input {
            border-radius: 8px !important;
            padding: 12px !important;
            border: 1px solid #E2E8F0 !important;
        }

        /* Primary button styling */
        div.stButton > button:first-child {
            background: linear-gradient(135deg, #2563EB 0%, #1D4ED8 100%) !important;
            color: white !important;
            border-radius: 8px !important;
            padding: 12px !important;
            font-weight: 600 !important;
            border: none !important;
            width: 100% !important;
            transition: transform 0.2s;
        }
        div.stButton > button:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(37, 99, 235, 0.2) !important;
        }

        /* Back button styling */
        .back-btn button {
            background: transparent !important;
            color: #F8FAFC !important;
            border: 1px solid rgba(255,255,255,0.2) !important;
            font-size: 0.85rem !important;
            width: auto !important;
            margin-top: 10px !important;
        }
        </style>
    """, unsafe_allow_html=True)

def show_portal_selection():
    inject_login_styles()
    
    st.markdown('<div class="login-card">', unsafe_allow_html=True)
    st.markdown('<h1 class="login-title">🚀 LeadPulse Pro</h1>', unsafe_allow_html=True)
    st.markdown('<h2 class="portal-title">Welcome Back</h2>', unsafe_allow_html=True)
    st.markdown('<p class="subtitle">Select your portal to continue</p>', unsafe_allow_html=True)
    
    if st.button("🛡️ Admin Portal", use_container_width=True):
        st.session_state.current_portal = 'admin'
        st.rerun()
    st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)
    if st.button("👤 User Portal", use_container_width=True):
        st.session_state.current_portal = 'user'
        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

def authenticate():
    if 'current_portal' not in st.session_state:
        st.session_state.current_portal = None
    
    authenticator = get_authenticator()
    
    if st.session_state.current_portal is None:
        show_portal_selection()
        return None, None, None, authenticator
    
    inject_login_styles()
    
    # Header above card
    st.markdown('<h1 style="color: white; font-weight: 800; margin-bottom: 20px;">🚀 LeadPulse Pro</h1>', unsafe_allow_html=True)
    
    # Show login form for the selected portal
    portal_name = "Admin" if st.session_state.current_portal == 'admin' else "User"
    
    st.markdown(f'<div class="login-card">', unsafe_allow_html=True)
    st.markdown(f'<h2 class="portal-title">{portal_name} Portal Login</h2>', unsafe_allow_html=True)
    st.markdown('<p class="subtitle">Secure access to your dashboard</p>', unsafe_allow_html=True)
    
    # Safely handle login() result for different versions
    result = authenticator.login(
        location='main',
        fields={'Form name': f'{portal_name} Login'}
    )
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    if result is None:
        # Support newer/older versions where it updates session_state instead of returning tuple
        name = st.session_state.get("name")
        authentication_status = st.session_state.get("authentication_status")
        username = st.session_state.get("username")
    else:
        # Result is the tuple
        name, authentication_status, username = result
    
    if authentication_status:
        # Check if user role matches the selected portal
        config = load_config()
        user_role = config['credentials']['usernames'][username].get('role')
        
        if user_role != st.session_state.current_portal:
            st.error(f"Access Denied: You do not have {st.session_state.current_portal} privileges.")
            # Clear authentication status to prevent auto-login
            st.session_state['authentication_status'] = None
            st.session_state['username'] = None
            st.markdown('<div class="back-btn">', unsafe_allow_html=True)
            if st.button("Back to Selection"):
                st.session_state.current_portal = None
                st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)
            return name, None, username, authenticator
        
        st.session_state.authenticated = True
        st.session_state.role = user_role
        st.session_state.username = username
        
    elif authentication_status is False:
        st.error('Username/password is incorrect')
        st.markdown('<div class="back-btn">', unsafe_allow_html=True)
        if st.button("← Back to Portal Selection", key="back_err"):
            st.session_state.current_portal = None
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
    elif authentication_status is None:
        st.markdown('<div class="back-btn">', unsafe_allow_html=True)
        if st.button("← Back to Portal Selection", key="back_none"):
            st.session_state.current_portal = None
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
            
    return name, authentication_status, username, authenticator
