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
        .login-card {
            background: white !important;
            padding: 40px !important;
            border-radius: 16px !important;
            box-shadow: 0 10px 25px rgba(0, 0, 0, 0.05) !important;
            text-align: center;
            margin: auto;
        }
        .login-title {
            font-size: 2.2rem !important;
            font-weight: 800 !important;
            color: #0F172A !important;
            margin-bottom: 10px !important;
        }
        .portal-title {
            font-size: 1.4rem !important;
            font-weight: 700 !important;
            color: #1E293B !important;
            margin-bottom: 5px !important;
        }
        .subtitle {
            font-size: 1rem !important;
            color: #64748B !important;
            margin-bottom: 25px !important;
        }
        </style>
    """, unsafe_allow_html=True)

def show_portal_selection():
    inject_login_styles()
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown('<div class="login-card">', unsafe_allow_html=True)
        st.markdown('<h1 class="login-title">🚀 LeadPulse Pro</h1>', unsafe_allow_html=True)
        st.markdown('<p class="subtitle">Select your workspace access</p>', unsafe_allow_html=True)
        
        if st.button("🛡️ Admin Portal", use_container_width=True):
            st.session_state.current_portal = 'admin'
            st.rerun()
        st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
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
        return None, None, None, None, authenticator
    
    inject_login_styles()
    
    # Show login form for the selected portal
    portal_name = "Admin" if st.session_state.current_portal == 'admin' else "User"
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown(f'<div class="login-card">', unsafe_allow_html=True)
        st.markdown(f'<h2 class="portal-title">{portal_name} Portal Login</h2>', unsafe_allow_html=True)
        st.markdown('<p class="subtitle">Secure access to LeadPulse Pro</p>', unsafe_allow_html=True)
        
        # Safely handle login() result for different versions
        result = authenticator.login(
            location='main',
            fields={'Form name': f'{portal_name} Login'}
        )
        st.markdown('</div>', unsafe_allow_html=True)
        
        # Back button below card
        if st.button("← Back to Selection", key="back_nav"):
            st.session_state.current_portal = None
            st.rerun()
    
    if result is None:
        name = st.session_state.get("name")
        authentication_status = st.session_state.get("authentication_status")
        username = st.session_state.get("username")
    else:
        name, authentication_status, username = result
    
    role = None
    if authentication_status:
        # Check actual role from config
        config = load_config()
        role = config['credentials']['usernames'][username].get('role')
        
        if role != st.session_state.current_portal:
            st.error(f"Access Denied: You do not have {st.session_state.current_portal} privileges.")
            st.session_state['authentication_status'] = None
            st.session_state['username'] = None
            return name, None, username, None, authenticator
        
        st.session_state.authenticated = True
        st.session_state.role = role
        st.session_state.username = username
        
    return name, authentication_status, username, role, authenticator
