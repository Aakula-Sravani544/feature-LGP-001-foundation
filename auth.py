"""
Day 11 — Authentication System
Features:
- Hashed passwords using bcrypt
- Login / Logout / Register flows
- Session state management
- Role-based access: admin / user
- 24 hour session expiry
- YAML config storage
"""

import os
import yaml
import bcrypt
import streamlit as st
from datetime import datetime, timedelta
from typing import Optional, Tuple
import logging

logger = logging.getLogger(__name__)

# Auth config file path
AUTH_CONFIG_FILE = "data/auth_config.yaml"

# Default users — admin and user
DEFAULT_USERS = {
    "admin": {
        "password": bcrypt.hashpw("admin123".encode(), bcrypt.gensalt()).decode(),
        "role": "admin",
        "plan": "Enterprise",
        "name": "Admin User",
        "email": "admin@leadpulse.com",
        "created_at": datetime.now().strftime("%Y-%m-%d")
    },
    "user": {
        "password": bcrypt.hashpw("user123".encode(), bcrypt.gensalt()).decode(),
        "role": "user",
        "plan": "Starter",
        "name": "Regular User",
        "email": "user@leadpulse.com",
        "created_at": datetime.now().strftime("%Y-%m-%d")
    }
}


def load_auth_config() -> dict:
    """Load auth config from YAML file. Creates default if not exists."""
    os.makedirs(os.path.dirname(AUTH_CONFIG_FILE), exist_ok=True)
    if os.path.exists(AUTH_CONFIG_FILE):
        try:
            with open(AUTH_CONFIG_FILE, "r") as f:
                return yaml.safe_load(f) or {"users": DEFAULT_USERS}
        except Exception as e:
            logger.error(f"Failed to load auth config: {e}")
            
    # If it doesn't exist or failed to load, create it with default users
    default_config = {"users": DEFAULT_USERS}
    save_auth_config(default_config)
    return default_config


def save_auth_config(config: dict) -> bool:
    """Save auth config to YAML file."""
    try:
        with open(AUTH_CONFIG_FILE, "w") as f:
            yaml.dump(config, f, default_flow_style=False)
        return True
    except Exception as e:
        logger.error(f"Failed to save auth config: {e}")
        return False


def hash_password(password: str) -> str:
    """Hash password using bcrypt."""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    """Verify password against bcrypt hash."""
    try:
        return bcrypt.checkpw(password.encode(), hashed.encode())
    except Exception:
        return False


def login(username: str, password: str) -> Tuple[bool, str, str]:
    """
    Verify login credentials.
    Returns: (success, role, plan)
    """
    config = load_auth_config()
    users = config.get("users", {})

    if username not in users:
        return False, "", ""

    user = users[username]
    if verify_password(password, user.get("password", "")):
        return True, user.get("role", "user"), user.get("plan", "Free")

    return False, "", ""


def register_user(
    username: str,
    password: str,
    role: str = "user",
    plan: str = "Free",
    name: str = "",
    email: str = ""
) -> Tuple[bool, str]:
    """
    Register a new user.
    Returns: (success, message)
    """
    config = load_auth_config()
    users = config.get("users", {})

    if username in users:
        return False, f"Username '{username}' already exists"

    if len(username) < 3:
        return False, "Username must be at least 3 characters"

    if len(password) < 6:
        return False, "Password must be at least 6 characters"

    users[username] = {
        "password": hash_password(password),
        "role": role,
        "plan": plan,
        "name": name or username,
        "email": email,
        "created_at": datetime.now().strftime("%Y-%m-%d")
    }

    config["users"] = users
    if save_auth_config(config):
        return True, f"User '{username}' created successfully"
    return False, "Failed to save user"


def update_user_plan(username: str, plan: str) -> bool:
    """Update user subscription plan."""
    config = load_auth_config()
    users = config.get("users", {})

    if username not in users:
        return False

    users[username]["plan"] = plan
    config["users"] = users
    return save_auth_config(config)


def update_password(username: str, new_password: str) -> bool:
    """Update user password."""
    config = load_auth_config()
    users = config.get("users", {})

    if username not in users:
        return False

    users[username]["password"] = hash_password(new_password)
    config["users"] = users
    return save_auth_config(config)


def delete_user(username: str) -> bool:
    """Delete a user account."""
    config = load_auth_config()
    users = config.get("users", {})

    if username not in users:
        return False
    if username == "admin":
        return False

    del users[username]
    config["users"] = users
    return save_auth_config(config)


def get_all_users() -> list:
    """Get all users for admin management."""
    config = load_auth_config()
    users = config.get("users", {})
    result = []
    for username, data in users.items():
        result.append({
            "username": username,
            "role": data.get("role", "user"),
            "plan": data.get("plan", "Free"),
            "name": data.get("name", username),
            "email": data.get("email", ""),
            "created_at": data.get("created_at", "")
        })
    return result


def get_user_info(username: str) -> dict:
    """Get info for a specific user."""
    config = load_auth_config()
    users = config.get("users", {})
    return users.get(username, {})


def check_session_expiry() -> bool:
    """Check if current session has expired (24 hours)."""
    login_time = st.session_state.get("login_time")
    if not login_time:
        return True
    expiry = login_time + timedelta(hours=24)
    if datetime.now() > expiry:
        return True
    return False


def init_session():
    """Initialize all session state variables."""
    defaults = {
        "authenticated": False,
        "username": None,
        "role": None,
        "plan": None,
        "login_time": None,
        "is_scraping": False,
        "session_leads": [],
        "logs": ""
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def render_login_page():
    """Render the login page UI."""
    st.markdown("<br><br>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 1.5, 1])

    with col2:
        st.markdown("""
            <div style="text-align:center; margin-bottom:2rem;">
                <h1 style="font-size:2.5rem; font-weight:800; color:#0F172A;">
                    🚀 LeadPulse Pro
                </h1>
                <p style="color:#64748B;">Production Grade Lead Extraction Engine</p>
            </div>
        """, unsafe_allow_html=True)

        tab1, tab2 = st.tabs(["Login", "Register"])

        with tab1:
            username = st.text_input("Username", placeholder="e.g. admin", key="login_user")
            password = st.text_input("Password", type="password", key="login_pass")

            if st.button("Enter Dashboard", use_container_width=True, key="login_btn"):
                if not username or not password:
                    st.error("Please enter username and password")
                else:
                    success, role, plan = login(username, password)
                    if success:
                        st.session_state.authenticated = True
                        st.session_state.username = username
                        st.session_state.role = role
                        st.session_state.plan = plan
                        st.session_state.login_time = datetime.now()
                        st.success(f"Welcome back, {username}!")
                        st.rerun()
                    else:
                        st.error("Invalid username or password")

        with tab2:
            new_username = st.text_input("Username", placeholder="min 3 characters", key="reg_user")
            new_password = st.text_input("Password", type="password", placeholder="min 6 characters", key="reg_pass")
            new_name = st.text_input("Full Name", placeholder="Your name", key="reg_name")
            new_email = st.text_input("Email", placeholder="your@email.com", key="reg_email")

            if st.button("Create Account", use_container_width=True, key="reg_btn"):
                if not new_username or not new_password:
                    st.error("Username and password are required")
                else:
                    success, msg = register_user(
                        new_username, new_password,
                        role="user", plan="Free",
                        name=new_name, email=new_email
                    )
                    if success:
                        st.success(msg + " — Please login")
                    else:
                        st.error(msg)


def render_logout_button():
    """Render logout button in sidebar."""
    if st.button("Sign Out Session", use_container_width=True):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()
