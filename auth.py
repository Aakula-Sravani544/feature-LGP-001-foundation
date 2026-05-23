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
    """Render the beautiful login page UI."""
    import streamlit.components.v1 as components
    
    # Hide all streamlit chrome
    st.markdown('''
<style>
#MainMenu,footer,header{visibility:hidden !important;}
[data-testid="collapsedControl"]{display:none !important;}
[data-testid="stSidebar"]{display:none !important;}
.main .block-container{
    padding:0 !important;
    max-width:100% !important;
    overflow:hidden !important;
}
.stApp{
    overflow:hidden !important;
    background:#0a0520 !important;
}
</style>
''', unsafe_allow_html=True)

    # Read login error if any
    login_error = st.session_state.get(
        "login_error", "")

    # ── FULL PAGE HTML ──────────────────────
    components.html(f'''
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8"/>
<style>
*{{margin:0;padding:0;box-sizing:border-box;
   font-family:-apple-system,BlinkMacSystemFont,
   'Segoe UI',sans-serif;}}
html,body{{
    width:100%;height:100vh;
    overflow:hidden;
    background:linear-gradient(135deg,
        #0a0520 0%,#1a0a4a 50%,#0f0635 100%);
}}
.wrap{{display:flex;width:100%;height:100vh;}}

.left{{
    flex:1.1;padding:40px 44px;
    display:flex;flex-direction:column;
    justify-content:center;overflow:hidden;
}}
.logo{{display:flex;align-items:center;
       gap:10px;margin-bottom:32px;}}
.logo-box{{
    width:42px;height:42px;background:#5b21b6;
    border-radius:11px;display:flex;
    align-items:center;justify-content:center;
    font-size:20px;
}}
.logo-name{{font-size:20px;font-weight:700;
            color:white;}}
.logo-name span{{color:#a78bfa;}}
.headline{{font-size:38px;font-weight:800;
           color:white;line-height:1.2;
           margin-bottom:14px;}}
.subtext{{font-size:14px;
          color:rgba(255,255,255,0.5);
          line-height:1.7;margin-bottom:30px;}}
.features{{display:flex;flex-direction:column;
           gap:14px;margin-bottom:30px;}}
.feat{{display:flex;align-items:center;gap:12px;}}
.feat-icon{{
    width:38px;height:38px;flex-shrink:0;
    background:rgba(91,33,182,0.45);
    border-radius:9px;display:flex;
    align-items:center;justify-content:center;
    font-size:17px;
}}
.feat-title{{color:white;font-weight:600;
             font-size:13px;}}
.feat-sub{{color:rgba(255,255,255,0.4);
           font-size:12px;}}
.trust{{display:flex;gap:20px;padding-top:16px;
        border-top:1px solid rgba(255,255,255,0.08);}}
.trust span{{color:rgba(255,255,255,0.35);
             font-size:12px;}}

.right{{
    flex:0.9;display:flex;align-items:center;
    justify-content:center;padding:24px;
    overflow:hidden;
}}
.card{{
    background:white;border-radius:18px;
    padding:28px 28px;width:100%;max-width:420px;
    box-shadow:0 20px 60px rgba(0,0,0,0.4);
}}
.card-title{{text-align:center;font-size:22px;
             font-weight:800;color:#111827;
             margin-bottom:4px;}}
.card-sub{{text-align:center;font-size:13px;
           color:#6b7280;margin-bottom:18px;}}
.tabs{{display:flex;background:#f3f4f6;
       border-radius:11px;padding:4px;
       gap:4px;margin-bottom:16px;}}
.tab{{flex:1;padding:8px;text-align:center;
      border-radius:9px;cursor:pointer;
      font-size:13px;font-weight:500;
      color:#6b7280;border:none;
      background:transparent;display:flex;
      align-items:center;justify-content:center;
      gap:5px;transition:all 0.15s;}}
.tab.active{{background:white;color:#5b21b6;
             font-weight:700;
             box-shadow:0 1px 4px rgba(0,0,0,0.12);}}
.flabel{{display:block;font-size:13px;
         font-weight:600;color:#111827;
         margin-bottom:4px;}}
.finput{{
    width:100%;padding:10px 12px;
    border:1.5px solid #e5e7eb;
    border-radius:9px;font-size:13px;
    color:#111827;outline:none;
    margin-bottom:12px;
    transition:border-color 0.2s;
}}
.finput:focus{{
    border-color:#6d28d9;
    box-shadow:0 0 0 3px rgba(109,40,217,0.1);
}}
.frow{{display:flex;justify-content:space-between;
       align-items:center;margin-bottom:14px;}}
.remember{{display:flex;align-items:center;
           gap:7px;font-size:13px;color:#374151;}}
.forgot{{color:#5b21b6;font-size:13px;
         font-weight:500;cursor:pointer;
         text-decoration:none;}}
.loginbtn{{
    width:100%;padding:12px;
    background:#5b21b6;color:white;
    border:none;border-radius:11px;
    font-size:15px;font-weight:600;
    cursor:pointer;margin-bottom:12px;
    transition:background 0.2s;
}}
.loginbtn:hover{{background:#4c1d95;}}
.divider{{text-align:center;color:#9ca3af;
          font-size:13px;margin-bottom:10px;}}
.regtext{{text-align:center;font-size:13px;
          color:#374151;}}
.regtext a{{color:#5b21b6;font-weight:600;
            text-decoration:none;}}
.errmsg{{
    background:#fef2f2;
    border:1px solid #fecaca;color:#dc2626;
    padding:8px 12px;border-radius:8px;
    font-size:13px;margin-bottom:10px;
    display:{'block' if login_error else 'none'};
}}
</style>
</head>
<body>
<div class="wrap">

  <div class="left">
    <div class="logo">
      <div class="logo-box">📊</div>
      <div class="logo-name">
        LeadPulse <span>Pro</span></div>
    </div>
    <div class="headline">
      AI-Powered<br>Lead Generation<br>Platform
    </div>
    <div class="subtext">
      Generate verified leads faster with<br>
      AI-powered enrichment.
    </div>
    <div class="features">
      <div class="feat">
        <div class="feat-icon">👥</div>
        <div>
          <div class="feat-title">
            Smart Lead Discovery</div>
          <div class="feat-sub">
            Find high-quality leads in seconds
          </div>
        </div>
      </div>
      <div class="feat">
        <div class="feat-icon">📈</div>
        <div>
          <div class="feat-title">
            AI Enrichment</div>
          <div class="feat-sub">
            Get enriched data and insights
          </div>
        </div>
      </div>
      <div class="feat">
        <div class="feat-icon">🛡️</div>
        <div>
          <div class="feat-title">
            Data Verification</div>
          <div class="feat-sub">
            Ensure accuracy and reliability
          </div>
        </div>
      </div>
      <div class="feat">
        <div class="feat-icon">🔒</div>
        <div>
          <div class="feat-title">
            Secure and Reliable</div>
          <div class="feat-sub">
            Enterprise-grade security
          </div>
        </div>
      </div>
    </div>
    <div class="trust">
      <span>🛡️ Secure Access</span>
      <span>🔒 Encrypted Data</span>
      <span>☁️ 99.9% Uptime</span>
    </div>
  </div>

  <div class="right">
    <div class="card">
      <div class="card-title">Welcome Back!</div>
      <div class="card-sub">
        Sign in to access your account</div>

      <div class="tabs">
        <button class="tab active"
                id="adminTab"
                onclick="switchTab('admin')">
          🛡️ Admin Portal
        </button>
        <button class="tab"
                id="userTab"
                onclick="switchTab('user')">
          👤 User Workspace
        </button>
      </div>

      <div class="errmsg" id="errMsg">
        {login_error if login_error 
         else 'Invalid credentials'}
      </div>

      <form id="loginForm"
            onsubmit="handleLogin(event)">
        <input type="hidden"
               id="portalVal" value="admin"/>
        <label class="flabel">Username</label>
        <input type="text" class="finput"
               id="uInput"
               placeholder="Enter your username"
               required autocomplete="username"/>
        <label class="flabel">Password</label>
        <input type="password" class="finput"
               id="pInput"
               placeholder="Enter your password"
               required
               autocomplete="current-password"/>
        <div class="frow">
          <label class="remember">
            <input type="checkbox"/> Remember me
          </label>
          <a class="forgot" href="#">
            Forgot Password?</a>
        </div>
        <button type="submit" class="loginbtn">
          ➜ Login
        </button>
      </form>

      <div class="divider">or</div>
      <div class="regtext">
        Don't have an account?
        <a href="#">Register now</a>
      </div>
    </div>
  </div>
</div>

<script>
function switchTab(p){{
  document.getElementById(
    'portalVal').value = p;
  document.getElementById('adminTab')
    .classList.toggle('active', p==='admin');
  document.getElementById('userTab')
    .classList.toggle('active', p==='user');
  document.getElementById('errMsg')
    .style.display = 'none';
}}

function handleLogin(e){{
  e.preventDefault();
  var u = document.getElementById(
    'uInput').value.trim();
  var p = document.getElementById(
    'pInput').value;
  var portal = document.getElementById(
    'portalVal').value;
  if(!u || !p) return;
  var url = new URL(
    window.parent.location.href);
  url.searchParams.set('lgn_u', u);
  url.searchParams.set('lgn_p', p);
  url.searchParams.set('lgn_portal', portal);
  window.parent.location.href = url.toString();
}}
</script>
</body>
</html>
''', height=680, scrolling=False)

def render_logout_button():
    """Render logout button in sidebar."""
    if st.button("Sign Out Session", use_container_width=True):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()
