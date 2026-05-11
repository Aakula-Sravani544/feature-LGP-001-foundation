"""
Day 13 — Stripe Integration
Test mode payment processing
Subscription checkout links per plan
Webhook listener for plan updates
"""

import os
import json
import logging
import streamlit as st
from typing import Tuple

logger = logging.getLogger(__name__)

# Stripe keys from environment
STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
APP_URL = os.environ.get("APP_URL", "https://leadpulse-pro.onrender.com")

# Stripe test price IDs — replace with real ones from Stripe dashboard
STRIPE_PRICE_IDS = {
    "Starter": os.environ.get("STRIPE_STARTER_PRICE_ID", "price_starter_test"),
    "Pro": os.environ.get("STRIPE_PRO_PRICE_ID", "price_pro_test"),
    "Enterprise": os.environ.get("STRIPE_ENTERPRISE_PRICE_ID", "price_enterprise_test")
}


def create_checkout_session(
    plan_name: str,
    username: str
) -> Tuple[bool, str]:
    """
    Create Stripe checkout session for a plan.
    Returns: (success, checkout_url)
    """
    if not STRIPE_SECRET_KEY:
        return False, "Stripe not configured. Add STRIPE_SECRET_KEY to Render environment."

    try:
        import stripe
        stripe.api_key = STRIPE_SECRET_KEY

        price_id = STRIPE_PRICE_IDS.get(plan_name, "")
        if not price_id or "test" in price_id:
            # Return test checkout URL if no real price ID
            return True, f"https://buy.stripe.com/test_{plan_name.lower()}"

        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[{
                "price": price_id,
                "quantity": 1
            }],
            mode="subscription",
            success_url=f"{APP_URL}?payment=success&plan={plan_name}&user={username}",
            cancel_url=f"{APP_URL}?payment=cancelled",
            client_reference_id=username,
            metadata={
                "username": username,
                "plan": plan_name
            },
            subscription_data={
                "trial_period_days": 7
            }
        )
        return True, session.url

    except Exception as e:
        logger.error(f"Stripe checkout error: {e}")
        return False, str(e)


def handle_webhook(payload: str, sig_header: str) -> Tuple[bool, str]:
    """
    Handle Stripe webhook events.
    Updates user plan on subscription events.
    """
    if not STRIPE_SECRET_KEY:
        return False, "Stripe not configured"

    try:
        import stripe
        stripe.api_key = STRIPE_SECRET_KEY

        event = stripe.Webhook.construct_event(
            payload, sig_header, STRIPE_WEBHOOK_SECRET
        )

        event_type = event["type"]
        logger.info(f"Stripe webhook: {event_type}")

        if event_type in [
            "checkout.session.completed",
            "customer.subscription.created",
            "customer.subscription.updated"
        ]:
            session_data = event["data"]["object"]
            username = session_data.get("client_reference_id") or \
                      session_data.get("metadata", {}).get("username", "")
            plan = session_data.get("metadata", {}).get("plan", "Starter")

            if username:
                from auth import update_user_plan
                update_user_plan(username, plan)
                logger.info(f"Plan updated: {username} → {plan}")
                return True, f"Plan updated for {username}"

        elif event_type == "customer.subscription.deleted":
            session_data = event["data"]["object"]
            username = session_data.get("metadata", {}).get("username", "")
            if username:
                from auth import update_user_plan
                update_user_plan(username, "Free")
                logger.info(f"Plan downgraded: {username} → Free")
                return True, f"Plan downgraded for {username}"

        return True, f"Event {event_type} processed"

    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return False, str(e)


def check_payment_success() -> None:
    """
    Check URL params for payment success and update plan.
    Called on app load.
    """
    try:
        params = st.query_params
        if params.get("payment") == "success":
            plan = params.get("plan", "Starter")
            username = params.get("user", "")

            if username and username == st.session_state.get("username"):
                from auth import update_user_plan
                update_user_plan(username, plan)
                st.session_state.plan = plan
                st.success(f"✅ Payment successful! Your plan has been upgraded to {plan}.")
                st.query_params.clear()

        elif params.get("payment") == "cancelled":
            st.warning("Payment cancelled. Your plan has not changed.")
            st.query_params.clear()
    except:
        pass


def render_billing_tab() -> None:
    """Render the billing/upgrade tab in user dashboard."""
    current_plan = st.session_state.get("plan", "Free")
    username = st.session_state.get("username", "")

    st.markdown("### 💳 Subscription & Billing")
    st.markdown(f"**Current Plan:** {current_plan}")
    st.markdown("---")

    plans_info = [
        {
            "name": "Free",
            "price": "$0",
            "leads": "50 leads/session",
            "features": ["Google Maps", "Basic export", "5 sessions/month"]
        },
        {
            "name": "Starter",
            "price": "$29/mo",
            "leads": "200 leads/session",
            "features": ["Google Maps", "LinkedIn", "AI Scoring", "Excel export", "30 sessions/month"]
        },
        {
            "name": "Pro",
            "price": "$79/mo",
            "leads": "1000 leads/session",
            "features": ["All Starter features", "Outreach generator", "Scheduled scraping", "PDF export"]
        },
        {
            "name": "Enterprise",
            "price": "Custom",
            "leads": "Unlimited",
            "features": ["All Pro features", "CRM push", "Priority support", "Custom retention"]
        }
    ]

    cols = st.columns(4)
    for i, plan in enumerate(plans_info):
        with cols[i]:
            is_current = plan["name"] == current_plan
            border_color = "#2563EB" if is_current else "#E2E8F0"
            st.markdown(f"""
                <div style="border:2px solid {border_color}; border-radius:12px; padding:16px; text-align:center;">
                    <h3>{plan['name']}</h3>
                    <h2 style="color:#2563EB;">{plan['price']}</h2>
                    <p>{plan['leads']}</p>
                </div>
            """, unsafe_allow_html=True)
            for feature in plan["features"]:
                st.markdown(f"✅ {feature}")

            if is_current:
                st.success("Current Plan")
            elif plan["name"] != "Free":
                if st.button(f"Upgrade to {plan['name']}", key=f"upgrade_{plan['name']}"):
                    success, url = create_checkout_session(plan["name"], username)
                    if success:
                        st.markdown(f"[Click here to complete payment →]({url})")
                    else:
                        st.error(url)
            else:
                if current_plan != "Free":
                    st.button("Downgrade to Free", key="downgrade_free")

    st.markdown("---")
    st.markdown("""
    **Test Mode Active** — Use test card: `4242 4242 4242 4242`
    Expiry: any future date | CVV: any 3 digits
    """)


def render_admin_billing() -> None:
    """Render billing overview in admin dashboard."""
    st.markdown("### 💰 Revenue Dashboard")

    from auth import get_all_users
    users = get_all_users()

    plan_counts = {"Free": 0, "Starter": 0, "Pro": 0, "Enterprise": 0}
    plan_revenue = {"Free": 0, "Starter": 29, "Pro": 79, "Enterprise": 0}

    total_mrr = 0
    for user in users:
        plan = user.get("plan", "Free")
        plan_counts[plan] = plan_counts.get(plan, 0) + 1
        total_mrr += plan_revenue.get(plan, 0)

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Monthly Revenue (MRR)", f"${total_mrr}")
    with col2:
        st.metric("Total Users", len(users))
    with col3:
        paid = sum(1 for u in users if u.get("plan", "Free") != "Free")
        st.metric("Paid Users", paid)
    with col4:
        st.metric("Free Users", plan_counts.get("Free", 0))

    st.markdown("**Users by Plan:**")
    import pandas as pd
    plan_df = pd.DataFrame([
        {"Plan": k, "Users": v, "MRR": f"${v * plan_revenue.get(k,0)}"}
        for k, v in plan_counts.items()
    ])
    st.dataframe(plan_df, hide_index=True)
