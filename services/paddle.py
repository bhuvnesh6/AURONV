"""
AURON — Paddle Billing Service
================================
Pure API functions. No Flask imports. No route logic.
All functions raise exceptions on failure — let callers handle them.

Paddle API docs: https://developer.paddle.com/api-reference
"""

import os
import hashlib
import hmac
import json
import requests as http_requests
from datetime import datetime

PADDLE_API_KEY     = os.environ.get("PADDLE_API_KEY", "")
PADDLE_CLIENT_TOKEN = os.environ.get("PADDLE_CLIENT_TOKEN", "")
PADDLE_WEBHOOK_SECRET = os.environ.get("PADDLE_WEBHOOK_SECRET", "")
PADDLE_PRICE_ID_MONTHLY   = os.environ.get("PADDLE_PRICE_ID_MONTHLY", "")
PADDLE_PRICE_ID_QUARTERLY = os.environ.get("PADDLE_PRICE_ID_QUARTERLY", "")
PADDLE_PRICE_ID_ANNUAL    = os.environ.get("PADDLE_PRICE_ID_ANNUAL", "")

# Sandbox vs Production
PADDLE_ENV = os.environ.get("PADDLE_ENV", "sandbox")  # "sandbox" or "production"
BASE_URL   = (
    "https://api.paddle.com"
    if PADDLE_ENV == "production"
    else "https://sandbox-api.paddle.com"
)


def _headers():
    return {
        "Authorization": f"Bearer {PADDLE_API_KEY}",
        "Content-Type":  "application/json",
    }


# ── Checkout ──────────────────────────────────────────────────────────────────

def create_checkout(price_id: str, user_email: str, user_id: str,
                    success_url: str, cancel_url: str) -> dict:
    """
    Create a Paddle checkout session.
    Returns the full response dict including checkout.url to redirect the user.
    """
    payload = {
        "items": [{"price_id": price_id, "quantity": 1}],
        "customer": {"email": user_email},
        "custom_data": {"user_id": user_id},
        "success_url": success_url,
        "cancel_url":  cancel_url,
    }
    r = http_requests.post(f"{BASE_URL}/transactions", headers=_headers(),
                           json=payload, timeout=10)
    r.raise_for_status()
    return r.json()


def get_price_id(billing_cycle: str) -> str:
    """Map billing cycle string to Paddle price ID."""
    return {
        "monthly":   PADDLE_PRICE_ID_MONTHLY,
        "quarterly": PADDLE_PRICE_ID_QUARTERLY,
        "annual":    PADDLE_PRICE_ID_ANNUAL,
    }.get(billing_cycle, PADDLE_PRICE_ID_MONTHLY)


# ── Customer ──────────────────────────────────────────────────────────────────

def get_customer(paddle_customer_id: str) -> dict:
    r = http_requests.get(f"{BASE_URL}/customers/{paddle_customer_id}",
                          headers=_headers(), timeout=10)
    r.raise_for_status()
    return r.json().get("data", {})


# ── Subscription ──────────────────────────────────────────────────────────────

def get_subscription(paddle_subscription_id: str) -> dict:
    r = http_requests.get(f"{BASE_URL}/subscriptions/{paddle_subscription_id}",
                          headers=_headers(), timeout=10)
    r.raise_for_status()
    return r.json().get("data", {})


def cancel_subscription(paddle_subscription_id: str) -> dict:
    """Cancel at end of billing period."""
    payload = {"effective_from": "next_billing_period"}
    r = http_requests.post(
        f"{BASE_URL}/subscriptions/{paddle_subscription_id}/cancel",
        headers=_headers(), json=payload, timeout=10,
    )
    r.raise_for_status()
    return r.json().get("data", {})


def get_customer_portal_url(paddle_customer_id: str) -> str:
    """Generate a Paddle customer portal URL for managing billing."""
    r = http_requests.post(
        f"{BASE_URL}/customers/{paddle_customer_id}/portal-sessions",
        headers=_headers(), json={}, timeout=10,
    )
    r.raise_for_status()
    data = r.json().get("data", {})
    return data.get("urls", {}).get("general", {}).get("overview", "")


# ── Webhook verification ───────────────────────────────────────────────────────

def verify_webhook(raw_body: bytes, paddle_signature_header: str) -> bool:
    """
    Verify Paddle webhook signature.
    Header format: ts=TIMESTAMP;h1=SIGNATURE
    Paddle docs: https://developer.paddle.com/webhooks/signature-verification
    """
    if not PADDLE_WEBHOOK_SECRET:
        return False
    try:
        parts = dict(item.split("=", 1) for item in paddle_signature_header.split(";"))
        ts        = parts.get("ts", "")
        h1        = parts.get("h1", "")
        signed_payload = f"{ts}:{raw_body.decode('utf-8')}"
        expected  = hmac.new(
            PADDLE_WEBHOOK_SECRET.encode("utf-8"),
            signed_payload.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(expected, h1)
    except Exception:
        return False


# ── Event parsing ─────────────────────────────────────────────────────────────

def parse_webhook_event(body: dict) -> dict:
    """
    Extract the fields AURON needs from any Paddle webhook event.
    Returns a normalized dict regardless of event type.
    """
    event_type = body.get("event_type", "")
    data       = body.get("data", {})

    result = {
        "event_type":            event_type,
        "paddle_subscription_id": data.get("id", "") if "subscription" in event_type else data.get("subscription_id", ""),
        "paddle_customer_id":    data.get("customer_id", ""),
        "paddle_price_id":       "",
        "status":                data.get("status", ""),
        "next_billing":          "",
        "user_id":               "",
    }

    # Extract price ID
    items = data.get("items", [])
    if items:
        result["paddle_price_id"] = items[0].get("price", {}).get("id", "")

    # Next billing date
    billing_period = data.get("current_billing_period", {})
    if billing_period:
        result["next_billing"] = billing_period.get("ends_at", "")

    # Custom data (we store user_id here at checkout)
    custom_data = data.get("custom_data", {})
    if isinstance(custom_data, dict):
        result["user_id"] = custom_data.get("user_id", "")

    return result