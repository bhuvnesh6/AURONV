from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from app import db
from routes.helpers import calculate_auron_score, save_daily_score, get_streak
from bson import ObjectId
from datetime import date, timedelta, datetime

api_bp = Blueprint("api", __name__)


@api_bp.route("/score")
@login_required
def get_score():
    if current_user.role != "user":
        return jsonify({"error": "Users only"}), 403
    score  = calculate_auron_score(current_user.id)
    streak = get_streak(current_user.id)
    return jsonify({"score": score, "streak": streak})


@api_bp.route("/user/scores/weekly")
@login_required
def weekly_scores():
    if current_user.role != "user":
        return jsonify([])
    uid    = ObjectId(current_user.id)
    today  = date.today()
    result = []
    for i in range(6, -1, -1):
        d   = (today - timedelta(days=i)).strftime("%Y-%m-%d")
        rec = db.scores.find_one({"user_id": uid, "date": d})
        result.append({"date": d, "score": rec["score"] if rec else 0})
    return jsonify(result)


# ── Messages (user side) ──────────────────────────────────────────────────────

@api_bp.route("/messages/unread")
@login_required
def unread_messages():
    if current_user.role != "user":
        return jsonify({"count": 0})
    count = db.messages.count_documents({
        "client_id":    ObjectId(current_user.id),
        "direction":    "trainer_to_user",
        "read_by_user": False,
    })
    return jsonify({"count": count})


@api_bp.route("/messages/inbox")
@login_required
def inbox():
    """Returns the user's full inbox — threads grouped by trainer."""
    if current_user.role != "user":
        return jsonify([])

    uid    = ObjectId(current_user.id)
    # Find all trainers who have messaged this user
    thread_keys = db.messages.distinct("trainer_id", {"client_id": uid})
    threads = []
    for tid in thread_keys:
        trainer = db.trainers.find_one({"_id": tid}, {"username": 1, "avatar_url": 1, "business_name": 1})
        if not trainer:
            continue
        latest = db.messages.find_one(
            {"client_id": uid, "trainer_id": tid},
            sort=[("created_at", -1)]
        )
        unread = db.messages.count_documents({
            "client_id": uid, "trainer_id": tid,
            "direction": "trainer_to_user", "read_by_user": False,
        })
        threads.append({
            "trainer_id":       str(tid),
            "trainer_username": trainer.get("username", ""),
            "trainer_avatar":   trainer.get("avatar_url", ""),
            "business_name":    trainer.get("business_name", ""),
            "latest_content":   latest.get("content", "") if latest else "",
            "latest_time":      latest["created_at"].isoformat() if latest and latest.get("created_at") else "",
            "unread":           unread,
        })
    threads.sort(key=lambda x: x["latest_time"], reverse=True)
    return jsonify(threads)


@api_bp.route("/messages/thread/<trainer_id>")
@login_required
def get_thread(trainer_id):
    if current_user.role != "user":
        return jsonify([])
    uid  = ObjectId(current_user.id)
    tid  = ObjectId(trainer_id)
    msgs = list(db.messages.find(
        {"client_id": uid, "trainer_id": tid},
        sort=[("created_at", 1)]
    ).limit(100))
    # Mark as read
    db.messages.update_many(
        {"client_id": uid, "trainer_id": tid,
         "direction": "trainer_to_user", "read_by_user": False},
        {"$set": {"read_by_user": True}},
    )
    return jsonify([{
        "id":        str(m["_id"]),
        "direction": m.get("direction", "trainer_to_user"),
        "content":   m.get("content", ""),
        "time":      m["created_at"].strftime("%b %d, %H:%M") if m.get("created_at") else "",
    } for m in msgs])


@api_bp.route("/messages/send", methods=["POST"])
@login_required
def user_send_message():
    """User sends a message to their trainer (or any trainer by ID)."""
    if current_user.role != "user":
        return jsonify({"error": "Users only"}), 403

    data       = request.get_json() or {}
    trainer_id = data.get("trainer_id", "")
    content    = data.get("content",    "").strip()
    recipient  = data.get("recipient",  "")   # "trainer" username for open DM

    if not content:
        return jsonify({"error": "Empty message"}), 400

    uid = ObjectId(current_user.id)

    # Resolve trainer
    if trainer_id:
        tid = ObjectId(trainer_id)
    elif recipient:
        t   = db.trainers.find_one({"username": recipient})
        tid = t["_id"] if t else None
    else:
        # Default: message own trainer
        user_doc = db.users.find_one({"_id": uid}) or {}
        tid_str  = user_doc.get("trainer_id")
        tid      = ObjectId(tid_str) if tid_str else None

    if not tid:
        return jsonify({"error": "Trainer not found"}), 404

    db.messages.insert_one({
        "trainer_id":        tid,
        "client_id":         uid,
        "direction":         "user_to_trainer",
        "content":           content,
        "read_by_trainer":   False,
        "created_at":        datetime.utcnow(),
    })
    return jsonify({"ok": True})


# ── Trainer search (for client add modal) ─────────────────────────────────────

@api_bp.route("/trainers/search")
@login_required
def search_trainers():
    """User can search trainers by username to DM them from leaderboard."""
    q = request.args.get("q", "").strip()
    if len(q) < 2:
        return jsonify([])
    results = list(db.trainers.find(
        {"username": {"$regex": q, "$options": "i"}},
        {"username": 1, "avatar_url": 1, "business_name": 1}
    ).limit(6))
    return jsonify([{
        "id":            str(r["_id"]),
        "username":      r.get("username", ""),
        "avatar_url":    r.get("avatar_url", ""),
        "business_name": r.get("business_name", ""),
    } for r in results])


# ── Public leaderboard (landing page) ─────────────────────────────────────────

@api_bp.route("/public/leaderboard")
def public_leaderboard():
    tab      = request.args.get("tab",    "athletes")
    period   = request.args.get("period", "daily")
    today    = date.today()
    date_str = today.strftime("%Y-%m-%d")
    if period == "weekly":
        from_date = (today - timedelta(days=7)).strftime("%Y-%m-%d")
    elif period == "monthly":
        from_date = (today - timedelta(days=30)).strftime("%Y-%m-%d")
    else:
        from_date = date_str
    entries = []

    if tab == "athletes":
        if period == "daily":
            raw = list(db.scores.find({"date": date_str}).sort("score", -1).limit(10))
        else:
            raw = list(db.scores.aggregate([
                {"$match": {"date": {"$gte": from_date}}},
                {"$group": {"_id": "$user_id", "score": {"$avg": "$score"}}},
                {"$sort": {"score": -1}}, {"$limit": 10}
            ]))
        for r in raw:
            u_id = r.get("user_id") or r.get("_id")
            if not u_id: continue
            u = db.users.find_one({"_id": u_id},
                {"username":1,"avatar_url":1,"city":1,"country":1}) or {}
            if not u.get("username"): continue
            entries.append({
                "name":       u["username"],
                "user_id":    str(u_id),
                "avatar_url": u.get("avatar_url",""),
                "location":   u.get("city","") or u.get("country",""),
                "score":      round(r.get("score", 0)),
            })
    else:
        trainers = list(db.trainers.find({},
            {"username":1,"business_name":1,"avatar_url":1,"clients":1,"city":1,"country":1}))
        board = []
        for t in trainers:
            cids = [ObjectId(c) for c in t.get("clients", [])]
            if not cids: continue
            scores = []
            for cid in cids:
                if period == "daily":
                    rec = db.scores.find_one({"user_id": cid, "date": date_str})
                    scores.append(rec["score"] if rec else 0)
                else:
                    recs = list(db.scores.find({"user_id": cid, "date": {"$gte": from_date}}))
                    scores.append(round(sum(r["score"] for r in recs)/len(recs)) if recs else 0)
            avg = round(sum(scores)/len(scores)) if scores else 0
            board.append({
                "name":         t.get("business_name") or t.get("username",""),
                "trainer_id":   str(t["_id"]),
                "avatar_url":   t.get("avatar_url",""),
                "location":     t.get("city","") or t.get("country",""),
                "score":        avg,
                "client_count": len(cids),
            })
        board.sort(key=lambda x: x["score"], reverse=True)
        entries = board[:10]

    return jsonify(entries)


# ── Trainer unread count (for badge polling) ───────────────────────────────────

@api_bp.route("/trainer/unread")
@login_required
def trainer_unread():
    if current_user.role != "trainer":
        return jsonify({"count": 0})
    count = db.messages.count_documents({
        "trainer_id":      ObjectId(current_user.id),
        "direction":       "user_to_trainer",
        "read_by_trainer": False,
    })
    return jsonify({"count": count})