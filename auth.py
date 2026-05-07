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

def show_portal_selection():
    st.markdown("<br><br>", unsafe_allow_html=True)
    st.markdown("<h1 style='text-align: center; color: #0F172A;'>LeadPulse Pro 🚀</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: #64748B;'>Select your portal to continue</p>", unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button("🛡️ Admin Portal", use_container_width=True):
            st.session_state.current_portal = 'admin'
            st.rerun()
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("👤 User Portal", use_container_width=True):
            st.session_state.current_portal = 'user'
            st.rerun()

def authenticate():
    if 'current_portal' not in st.session_state:
        st.session_state.current_portal = None
    
    authenticator = get_authenticator()
    
    if st.session_state.current_portal is None:
        show_portal_selection()
        return None, None, None, authenticator
    
    # Show login form for the selected portal
    portal_name = "Admin" if st.session_state.current_portal == 'admin' else "User"
    
    # Safely handle login() result for different versions
    result = authenticator.login(
        location='main',
        fields={'Form name': f'{portal_name} Login'}
    )
    
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
            if st.button("Back to Selection"):
                st.session_state.current_portal = None
                st.rerun()
            return name, None, username, authenticator
        
        st.session_state.authenticated = True
        st.session_state.role = user_role
        st.session_state.username = username
        
    elif authentication_status is False:
        st.error('Username/password is incorrect')
        if st.button("← Back to Selection"):
            st.session_state.current_portal = None
            st.rerun()
    elif authentication_status is None:
        if st.button("← Back to Selection"):
            st.session_state.current_portal = None
            st.rerun()
            
    return name, authentication_status, username, authenticator
