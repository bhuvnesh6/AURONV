from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app import db
from routes.helpers import calculate_auron_score, get_streak, get_compliance_for_client, get_rank_label
from bson import ObjectId
from datetime import datetime, date, timedelta

trainer_bp = Blueprint("trainer", __name__)


def trainer_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != "trainer":
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)
    return decorated


def get_trainer_doc():
    return db.trainers.find_one({"_id": ObjectId(current_user.id)}) or {}


# ── Dashboard ─────────────────────────────────────────────────────────────────

@trainer_bp.route("/dashboard")
@login_required
@trainer_required
def dashboard():
    trainer = get_trainer_doc()
    client_ids = [ObjectId(cid) for cid in trainer.get("clients", [])]
    clients = list(db.users.find({"_id": {"$in": client_ids}}))

    date_str = date.today().strftime("%Y-%m-%d")
    stats = {"active_clients": len(clients), "avg_score": 0, "at_risk": [], "top_performers": []}

    scores = []
    for c in clients:
        s = calculate_auron_score(str(c["_id"]))
        c["today_score"] = s
        c["rank"] = get_rank_label(s)
        scores.append(s)
        if s < 40:
            stats["at_risk"].append(c)

    if scores:
        stats["avg_score"] = round(sum(scores) / len(scores))

    stats["top_performers"] = sorted(clients, key=lambda x: x.get("today_score", 0), reverse=True)[:3]

    recent_msgs = list(db.messages.find(
        {"trainer_id": ObjectId(current_user.id)},
    ).sort("created_at", -1).limit(5))

    return render_template(
        "trainer/dashboard.html",
        trainer=trainer,
        clients=clients,
        stats=stats,
        recent_msgs=recent_msgs,
    )


# ── Clients ───────────────────────────────────────────────────────────────────

@trainer_bp.route("/clients")
@login_required
@trainer_required
def clients():
    trainer = get_trainer_doc()
    client_ids = [ObjectId(cid) for cid in trainer.get("clients", [])]
    clients = list(db.users.find({"_id": {"$in": client_ids}}))

    for c in clients:
        c["today_score"] = calculate_auron_score(str(c["_id"]))
        c["streak"] = get_streak(str(c["_id"]))["current"]
        c["compliance"] = get_compliance_for_client(str(c["_id"]))
        c["rank"] = get_rank_label(c["today_score"])

    return render_template("trainer/clients.html", clients=clients)


@trainer_bp.route("/clients/add", methods=["POST"])
@login_required
@trainer_required
def add_client():
    username = request.form.get("username", "").strip()
    user = db.users.find_one({"username": username})
    if not user:
        flash("User not found.", "error")
    else:
        db.trainers.update_one(
            {"_id": ObjectId(current_user.id)},
            {"$addToSet": {"clients": str(user["_id"])}},
        )
        flash(f"{username} added as client!", "success")
    return redirect(url_for("trainer.clients"))


@trainer_bp.route("/clients/remove/<client_id>", methods=["POST"])
@login_required
@trainer_required
def remove_client(client_id):
    db.trainers.update_one(
        {"_id": ObjectId(current_user.id)},
        {"$pull": {"clients": client_id}},
    )
    flash("Client removed.", "info")
    return redirect(url_for("trainer.clients"))


@trainer_bp.route("/clients/<client_id>")
@login_required
@trainer_required
def client_detail(client_id):
    client = db.users.find_one({"_id": ObjectId(client_id)})
    if not client:
        flash("Client not found.", "error")
        return redirect(url_for("trainer.clients"))

    score = calculate_auron_score(client_id)
    streak = get_streak(client_id)
    compliance = get_compliance_for_client(client_id)
    rank = get_rank_label(score)
    workouts = list(db.workouts.find({"user_id": ObjectId(client_id)}).sort("date", -1).limit(10))
    progress = list(db.progress_entries.find({"user_id": ObjectId(client_id)}).sort("date", -1).limit(6))

    return render_template(
        "trainer/client_detail.html",
        client=client, score=score, streak=streak,
        compliance=compliance, rank=rank,
        workouts=workouts, progress=progress,
    )


# ── Programs ──────────────────────────────────────────────────────────────────

@trainer_bp.route("/programs", methods=["GET", "POST"])
@login_required
@trainer_required
def programs():
    if request.method == "POST":
        program = {
            "trainer_id": ObjectId(current_user.id),
            "name": request.form.get("name", "New Program"),
            "description": request.form.get("description", ""),
            "days": [],
            "created_at": datetime.utcnow(),
        }
        db.programs.insert_one(program)
        flash("Program created!", "success")
        return redirect(url_for("trainer.programs"))

    progs = list(db.programs.find({"trainer_id": ObjectId(current_user.id)}).sort("created_at", -1))
    return render_template("trainer/programs.html", programs=progs)


@trainer_bp.route("/programs/<program_id>/assign", methods=["POST"])
@login_required
@trainer_required
def assign_program(program_id):
    client_ids = request.form.getlist("client_ids")
    for cid in client_ids:
        db.assigned_programs.update_one(
            {"user_id": ObjectId(cid), "program_id": ObjectId(program_id)},
            {"$set": {"trainer_id": ObjectId(current_user.id), "assigned_at": datetime.utcnow()}},
            upsert=True,
        )
    flash("Program assigned!", "success")
    return redirect(url_for("trainer.programs"))


# ── Messages ──────────────────────────────────────────────────────────────────

@trainer_bp.route("/messages", methods=["GET", "POST"])
@login_required
@trainer_required
def messages():
    trainer = get_trainer_doc()
    client_ids = [ObjectId(cid) for cid in trainer.get("clients", [])]
    clients = list(db.users.find({"_id": {"$in": client_ids}}, {"username": 1}))

    if request.method == "POST":
        msg_type = request.form.get("msg_type", "individual")
        content = request.form.get("content", "").strip()
        if not content:
            flash("Message cannot be empty.", "error")
            return redirect(url_for("trainer.messages"))

        if msg_type == "broadcast":
            recipients = [str(c["_id"]) for c in clients]
        else:
            recipients = request.form.getlist("recipients")

        for rid in recipients:
            db.messages.insert_one({
                "trainer_id": ObjectId(current_user.id),
                "recipient_id": ObjectId(rid),
                "content": content,
                "read": False,
                "created_at": datetime.utcnow(),
            })
        flash(f"Message sent to {len(recipients)} client(s).", "success")
        return redirect(url_for("trainer.messages"))

    msgs = list(db.messages.find({"trainer_id": ObjectId(current_user.id)}).sort("created_at", -1).limit(50))
    for m in msgs:
        u = db.users.find_one({"_id": m["recipient_id"]}, {"username": 1})
        m["recipient_username"] = u["username"] if u else "Unknown"

    return render_template("trainer/messages.html", clients=clients, messages=msgs)


# ── Leaderboard ───────────────────────────────────────────────────────────────

@trainer_bp.route("/leaderboard")
@login_required
@trainer_required
def leaderboard():
    date_str = date.today().strftime("%Y-%m-%d")
    trainers = list(db.trainers.find({}, {"username": 1, "business_name": 1, "clients": 1}))
    board = []
    for t in trainers:
        cids = [ObjectId(c) for c in t.get("clients", [])]
        if not cids:
            continue
        scores = [calculate_auron_score(str(c)) for c in cids]
        avg = round(sum(scores) / len(scores)) if scores else 0
        board.append({
            "username": t.get("username"),
            "business_name": t.get("business_name", ""),
            "avg_score": avg,
            "client_count": len(cids),
        })
    board.sort(key=lambda x: x["avg_score"], reverse=True)
    for i, b in enumerate(board):
        b["rank"] = i + 1

    return render_template("trainer/leaderboard.html", board=board)