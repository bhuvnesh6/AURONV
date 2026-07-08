"""
AURON — Billing Routes
=======================
Handles all Paddle payment flows.
No Paddle API logic here — all calls go through services/paddle.py
"""

from flask import (Blueprint, render_template, request, redirect,
                   url_for, flash, jsonify, current_app)
from flask_login import login_required, current_user
from services.paddle import (
    create_checkout, get_price_id, cancel_subscription,
    get_customer_portal_url, verify_webhook, parse_webhook_event
)
from bson import ObjectId
from datetime import datetime
import os

billing_bp = Blueprint("billing", __name__)

APP_URL = os.environ.get("APP_URL", "http://localhost:5051")


def _uid():
    return ObjectId(current_user.id)


def _col():
    db = current_app.config["DB"]
    return db.trainers if current_user.role == "trainer" else db.users


# ── Pricing page ──────────────────────────────────────────────────────────────

@billing_bp.route("/pricing")
def pricing():
    return render_template("pricing.html",
                           client_token=os.environ.get("PADDLE_CLIENT_TOKEN", ""),
                           paddle_env=os.environ.get("PADDLE_ENV", "sandbox"))


# ── Subscribe ─────────────────────────────────────────────────────────────────

@billing_bp.route("/subscribe")
@login_required
def subscribe():
    cycle    = request.args.get("cycle", "monthly")
    price_id = get_price_id(cycle)

    if not price_id:
        flash("Billing is not configured yet. Please contact support.", "error")
        return redirect(url_for("billing.pricing"))

    try:
        result       = create_checkout(
            price_id    = price_id,
            user_email  = current_user.email,
            user_id     = current_user.id,
            success_url = f"{APP_URL}/billing/success",
            cancel_url  = f"{APP_URL}/billing/cancel",
        )
        checkout_url = result.get("data", {}).get("url", "")
        if not checkout_url:
            raise ValueError("No checkout URL returned")
        return redirect(checkout_url)

    except Exception as e:
        flash(f"Could not start checkout: {e}", "error")
        return redirect(url_for("billing.pricing"))


# ── Success ───────────────────────────────────────────────────────────────────

@billing_bp.route("/billing/success")
@login_required
def success():
    return render_template("billing/success.html")


# ── Cancel ────────────────────────────────────────────────────────────────────

@billing_bp.route("/billing/cancel")
def cancel():
    return render_template("billing/cancel.html")


# ── Customer portal ───────────────────────────────────────────────────────────

@billing_bp.route("/billing/portal")
@login_required
def customer_portal():
    col  = _col()
    user = col.find_one({"_id": _uid()}) or {}
    cid  = user.get("paddle_customer_id", "")

    if not cid:
        flash("No active subscription found.", "error")
        return redirect(url_for("billing.pricing"))

    try:
        portal_url = get_customer_portal_url(cid)
        return redirect(portal_url)
    except Exception as e:
        flash(f"Could not open billing portal: {e}", "error")
        return redirect(url_for("billing.pricing"))


# ── Cancel subscription ───────────────────────────────────────────────────────

@billing_bp.route("/billing/cancel-subscription", methods=["POST"])
@login_required
def cancel_sub():
    col  = _col()
    user = col.find_one({"_id": _uid()}) or {}
    sid  = user.get("paddle_subscription_id", "")

    if not sid:
        flash("No active subscription found.", "error")
        return redirect(url_for("billing.pricing"))

    try:
        cancel_subscription(sid)
        col.update_one({"_id": _uid()}, {"$set": {"subscription.status": "canceling"}})
        flash("Subscription cancelled. You keep access until the end of your billing period.", "info")
    except Exception as e:
        flash(f"Could not cancel: {e}", "error")

    return redirect(url_for("billing.pricing"))


# ── Paddle Webhook ────────────────────────────────────────────────────────────

@billing_bp.route("/webhook/paddle", methods=["POST"])
def paddle_webhook():
    raw_body  = request.get_data()
    signature = request.headers.get("Paddle-Signature", "")

    if not verify_webhook(raw_body, signature):
        current_app.logger.warning("Paddle webhook: invalid signature")
        return "", 400

    try:
        body = request.get_json(force=True) or {}
    except Exception:
        return "", 400

    event = parse_webhook_event(body)
    etype = event["event_type"]
    uid   = event.get("user_id", "")

    current_app.logger.info(f"Paddle webhook received: {etype} user={uid}")

    if etype in ("subscription.created", "transaction.completed"):
        _handle_subscription_activated(event, uid)
    elif etype == "subscription.updated":
        _handle_subscription_updated(event, uid)
    elif etype in ("subscription.canceled", "subscription.paused"):
        _handle_subscription_canceled(event, uid)
    elif etype == "subscription.resumed":
        _handle_subscription_activated(event, uid)

    return "", 200


# ── Webhook handlers ──────────────────────────────────────────────────────────

def _find_user_doc(user_id: str, paddle_customer_id: str):
    db = current_app.config["DB"]
    for col in [db.users, db.trainers]:
        if user_id:
            try:
                doc = col.find_one({"_id": ObjectId(user_id)})
                if doc:
                    return col, doc
            except Exception:
                pass
        if paddle_customer_id:
            doc = col.find_one({"paddle_customer_id": paddle_customer_id})
            if doc:
                return col, doc
    return None, None


def _handle_subscription_activated(event: dict, user_id: str):
    col, doc = _find_user_doc(user_id, event.get("paddle_customer_id", ""))
    if not col or not doc:
        return
    col.update_one({"_id": doc["_id"]}, {"$set": {
        "subscription.plan":                   "pro",
        "subscription.status":                 "active",
        "subscription.paddle_customer_id":     event.get("paddle_customer_id", ""),
        "subscription.paddle_subscription_id": event.get("paddle_subscription_id", ""),
        "subscription.paddle_price_id":        event.get("paddle_price_id", ""),
        "subscription.next_billing":           event.get("next_billing", ""),
        "subscription.activated_at":           datetime.utcnow().isoformat(),
    }})


def _handle_subscription_updated(event: dict, user_id: str):
    col, doc = _find_user_doc(user_id, event.get("paddle_customer_id", ""))
    if not col or not doc:
        return
    col.update_one({"_id": doc["_id"]}, {"$set": {
        "subscription.status":          event.get("status", "active"),
        "subscription.next_billing":    event.get("next_billing", ""),
        "subscription.paddle_price_id": event.get("paddle_price_id", ""),
    }})


def _handle_subscription_canceled(event: dict, user_id: str):
    col, doc = _find_user_doc(user_id, event.get("paddle_customer_id", ""))
    if not col or not doc:
        return
    col.update_one({"_id": doc["_id"]}, {"$set": {
        "subscription.plan":         "free",
        "subscription.status":       "canceled",
        "subscription.next_billing": "",
    }})