"""
Day 12 — Subscription Enforcement
Plan tiers with feature gates and lead caps
"""

# Plan definitions from PDF Section 8.1
PLANS = {
    "Free": {
        "leads_per_session": 50,
        "sessions_per_month": 5,
        "google_maps": True,
        "linkedin": False,
        "website_scraper": "basic",
        "ai_scoring": False,
        "outreach_generator": False,
        "scheduled_scraping": False,
        "crm_push": False,
        "data_retention_days": 30,
        "team_members": 1,
        "export_formats": ["csv", "json"],
        "price": "$0"
    },
    "Starter": {
        "leads_per_session": 200,
        "sessions_per_month": 30,
        "google_maps": True,
        "linkedin": True,
        "website_scraper": "full",
        "ai_scoring": True,
        "outreach_generator": False,
        "scheduled_scraping": False,
        "crm_push": False,
        "data_retention_days": 90,
        "team_members": 3,
        "export_formats": ["csv", "json", "excel"],
        "price": "$29/mo"
    },
    "Pro": {
        "leads_per_session": 1000,
        "sessions_per_month": 999,
        "google_maps": True,
        "linkedin": True,
        "website_scraper": "full",
        "ai_scoring": True,
        "outreach_generator": True,
        "scheduled_scraping": True,
        "crm_push": False,
        "data_retention_days": 365,
        "team_members": 10,
        "export_formats": ["csv", "json", "excel", "pdf"],
        "price": "$79/mo"
    },
    "Enterprise": {
        "leads_per_session": 999999,
        "sessions_per_month": 999999,
        "google_maps": True,
        "linkedin": True,
        "website_scraper": "full",
        "ai_scoring": True,
        "outreach_generator": True,
        "scheduled_scraping": True,
        "crm_push": True,
        "data_retention_days": 999999,
        "team_members": 999,
        "export_formats": ["csv", "json", "excel", "pdf", "google_sheets"],
        "price": "Custom"
    }
}


def get_plan(plan_name: str) -> dict:
    """Get plan details by name."""
    return PLANS.get(plan_name, PLANS["Free"])


def get_max_leads(plan_name: str) -> int:
    """Get max leads per session for plan."""
    return get_plan(plan_name).get("leads_per_session", 50)


def can_use_linkedin(plan_name: str) -> bool:
    """Check if plan allows LinkedIn scraper."""
    return get_plan(plan_name).get("linkedin", False)


def can_use_ai(plan_name: str) -> bool:
    """Check if plan allows AI scoring."""
    return get_plan(plan_name).get("ai_scoring", False)


def can_use_scheduled(plan_name: str) -> bool:
    """Check if plan allows scheduled scraping."""
    return get_plan(plan_name).get("scheduled_scraping", False)


def can_use_outreach(plan_name: str) -> bool:
    """Check if plan allows outreach generator."""
    return get_plan(plan_name).get("outreach_generator", False)


def can_export_format(plan_name: str, format: str) -> bool:
    """Check if plan allows specific export format."""
    return format in get_plan(plan_name).get("export_formats", ["csv"])


def get_upgrade_message(plan_name: str, feature: str) -> str:
    """Get upgrade message for locked feature."""
    messages = {
        "linkedin": f"LinkedIn Scraper requires Starter plan or above. You are on {plan_name}.",
        "ai_scoring": f"AI Scoring requires Starter plan or above. You are on {plan_name}.",
        "scheduled_scraping": f"Scheduled Scraping requires Pro plan or above. You are on {plan_name}.",
        "outreach_generator": f"Outreach Generator requires Pro plan or above. You are on {plan_name}.",
        "leads_cap": f"You have reached your {plan_name} plan limit.",
    }
    return messages.get(feature, f"This feature requires a higher plan.")


def render_upgrade_banner(plan_name: str) -> None:
    """Show upgrade banner with plan comparison."""
    import streamlit as st
    st.warning(f"""
    ⚠️ You are on the **{plan_name}** plan.
    Upgrade to unlock more leads, AI scoring, LinkedIn scraper and more.
    """)
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("""
        **Starter — $29/mo**
        - 200 leads/session
        - LinkedIn scraper
        - AI scoring
        - 90 day retention
        """)
    with col2:
        st.markdown("""
        **Pro — $79/mo**
        - 1000 leads/session
        - Outreach generator
        - Scheduled scraping
        - 1 year retention
        """)
    with col3:
        st.markdown("""
        **Enterprise — Custom**
        - Unlimited leads
        - CRM direct push
        - Priority support
        - Custom retention
        """)
