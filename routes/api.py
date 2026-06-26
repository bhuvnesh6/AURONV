from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from app import db
from routes.helpers import calculate_auron_score, save_daily_score, get_streak
from bson import ObjectId
from datetime import date

api_bp = Blueprint("api", __name__)


@api_bp.route("/score")
@login_required
def get_score():
    if current_user.role != "user":
        return jsonify({"error": "Users only"}), 403
    score = calculate_auron_score(current_user.id)
    streak = get_streak(current_user.id)
    return jsonify({"score": score, "streak": streak})


@api_bp.route("/messages/unread")
@login_required
def unread_messages():
    if current_user.role != "user":
        return jsonify({"count": 0})
    count = db.messages.count_documents({"recipient_id": ObjectId(current_user.id), "read": False})
    return jsonify({"count": count})


@api_bp.route("/messages/<msg_id>/read", methods=["POST"])
@login_required
def mark_read(msg_id):
    db.messages.update_one({"_id": ObjectId(msg_id)}, {"$set": {"read": True}})
    return jsonify({"ok": True})


@api_bp.route("/user/scores/weekly")
@login_required
def weekly_scores():
    if current_user.role != "user":
        return jsonify([])
    uid = ObjectId(current_user.id)
    today = date.today()
    result = []
    for i in range(6, -1, -1):
        from datetime import timedelta
        d = (today - timedelta(days=i)).strftime("%Y-%m-%d")
        rec = db.scores.find_one({"user_id": uid, "date": d})
        result.append({"date": d, "score": rec["score"] if rec else 0})
    return jsonify(result)