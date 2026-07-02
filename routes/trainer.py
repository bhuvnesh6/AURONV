from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app import db, bcrypt
from routes.helpers import calculate_auron_score, get_streak, get_compliance_for_client, get_rank_label
from bson import ObjectId
from datetime import datetime, date, timedelta
import cloudinary, cloudinary.uploader, os, secrets, string, json

trainer_bp = Blueprint("trainer", __name__)

cloudinary.config(
    cloud_name=os.environ.get("CLOUDINARY_CLOUD_NAME"),
    api_key=os.environ.get("CLOUDINARY_API_KEY"),
    api_secret=os.environ.get("CLOUDINARY_API_SECRET"),
)


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


def _gen_code():
    return ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(10))


# ── Dashboard ─────────────────────────────────────────────────────────────────

@trainer_bp.route("/dashboard")
@login_required
@trainer_required
def dashboard():
    trainer    = get_trainer_doc()
    client_ids = [ObjectId(c) for c in trainer.get("clients", [])]
    clients    = list(db.users.find({"_id": {"$in": client_ids}}))
    stats      = {"active_clients": len(clients), "avg_score": 0, "at_risk": [], "top_performers": []}
    scores     = []

    for c in clients:
        s                = calculate_auron_score(str(c["_id"]))
        c["today_score"] = s
        c["rank"]        = get_rank_label(s)
        scores.append(s)
        if s < 40:
            stats["at_risk"].append(c)

    if scores:
        stats["avg_score"] = round(sum(scores) / len(scores))
    stats["top_performers"] = sorted(clients, key=lambda x: x.get("today_score", 0), reverse=True)[:3]

    unread = db.messages.count_documents({
        "trainer_id": ObjectId(current_user.id),
        "direction":  "user_to_trainer",
        "read_by_trainer": False,
    })
    return render_template("trainer/dashboard.html",
                           trainer=trainer, clients=clients, stats=stats, unread=unread)


# ── Profile ───────────────────────────────────────────────────────────────────

@trainer_bp.route("/profile", methods=["GET", "POST"])
@login_required
@trainer_required
def profile():
    tid = ObjectId(current_user.id)
    if request.method == "POST":
        db.trainers.update_one({"_id": tid}, {"$set": {
            "business_name":    request.form.get("business_name",   "").strip(),
            "instagram":        request.form.get("instagram",       "").strip(),
            "specialization":   request.form.get("specialization",  ""),
            "years_experience": request.form.get("years_experience","").strip(),
            "bio":              request.form.get("bio",             "").strip(),
            "phone":            request.form.get("phone",           "").strip(),
            "city":             request.form.get("city",            "").strip(),
            "state":            request.form.get("state",           "").strip(),
            "country":          request.form.get("country",         "").strip(),
        }})
        flash("Profile updated!", "success")
        return redirect(url_for("trainer.profile"))

    trainer = db.trainers.find_one({"_id": tid}) or {}
    if not trainer.get("invite_code"):
        code = _gen_code()
        db.trainers.update_one({"_id": tid}, {"$set": {"invite_code": code}})
        trainer["invite_code"] = code

    invite_url   = request.host_url.rstrip("/") + f"/trainer/invite/{trainer['invite_code']}"
    client_count = len(trainer.get("clients", []))
    return render_template("trainer/profile.html",
                           trainer=trainer, client_count=client_count, invite_url=invite_url)


@trainer_bp.route("/profile/avatar", methods=["POST"])
@login_required
@trainer_required
def upload_avatar():
    tid  = ObjectId(current_user.id)
    file = request.files.get("avatar")
    if not file or not file.filename:
        flash("No file selected.", "error")
        return redirect(url_for("trainer.profile"))
    if file.content_type not in {"image/jpeg", "image/png", "image/webp"}:
        flash("Invalid file type.", "error")
        return redirect(url_for("trainer.profile"))
    try:
        r = cloudinary.uploader.upload(file, folder="auron/trainer_avatars",
            public_id=f"trainer_{current_user.id}", overwrite=True,
            transformation=[{"width": 400, "height": 400, "crop": "fill",
                             "gravity": "face", "quality": "auto"}])
        db.trainers.update_one({"_id": tid}, {"$set": {"avatar_url": r.get("secure_url", "")}})
        flash("Photo updated!", "success")
    except Exception as e:
        flash(f"Upload failed: {e}", "error")
    return redirect(url_for("trainer.profile"))


@trainer_bp.route("/profile/avatar/remove", methods=["POST"])
@login_required
@trainer_required
def remove_avatar():
    try:
        cloudinary.uploader.destroy(f"auron/trainer_avatars/trainer_{current_user.id}")
    except Exception:
        pass
    db.trainers.update_one({"_id": ObjectId(current_user.id)}, {"$set": {"avatar_url": ""}})
    flash("Photo removed.", "info")
    return redirect(url_for("trainer.profile"))


@trainer_bp.route("/profile/regenerate-link", methods=["POST"])
@login_required
@trainer_required
def regenerate_invite():
    code = _gen_code()
    db.trainers.update_one({"_id": ObjectId(current_user.id)}, {"$set": {"invite_code": code}})
    flash("New invite link generated!", "success")
    return redirect(url_for("trainer.profile"))


# ── Clients ───────────────────────────────────────────────────────────────────

@trainer_bp.route("/clients")
@login_required
@trainer_required
def clients():
    trainer    = get_trainer_doc()
    client_ids = [ObjectId(c) for c in trainer.get("clients", [])]
    clients    = list(db.users.find({"_id": {"$in": client_ids}}))
    for c in clients:
        c["today_score"] = calculate_auron_score(str(c["_id"]))
        c["streak"]      = get_streak(str(c["_id"]))["current"]
        c["compliance"]  = get_compliance_for_client(str(c["_id"]))
        c["rank"]        = get_rank_label(c["today_score"])
    return render_template("trainer/clients.html", clients=clients)


@trainer_bp.route("/clients/search")
@login_required
@trainer_required
def search_clients():
    q = request.args.get("q", "").strip()
    if len(q) < 1:
        return jsonify([])
    trainer  = get_trainer_doc()
    existing = [ObjectId(c) for c in trainer.get("clients", [])]
    results  = list(db.users.find(
        {"username": {"$regex": q, "$options": "i"}, "_id": {"$nin": existing}},
        {"username": 1, "avatar_url": 1, "goal": 1, "city": 1, "country": 1}
    ).limit(8))
    return jsonify([{
        "id":         str(r["_id"]),
        "username":   r["username"],
        "avatar_url": r.get("avatar_url", ""),
        "goal":       r.get("goal", ""),
        "location":   r.get("city", "") or r.get("country", ""),
    } for r in results])


@trainer_bp.route("/clients/add", methods=["POST"])
@login_required
@trainer_required
def add_client():
    user_id  = request.form.get("user_id",  "").strip()
    username = request.form.get("username", "").strip()
    user     = (db.users.find_one({"_id": ObjectId(user_id)}) if user_id
                else db.users.find_one({"username": username}))
    if not user:
        flash("User not found.", "error")
    else:
        db.trainers.update_one({"_id": ObjectId(current_user.id)},
                               {"$addToSet": {"clients": str(user["_id"])}})
        db.users.update_one({"_id": user["_id"]},
                            {"$set": {"trainer_id": current_user.id}})
        flash(f"{user['username']} added to your team!", "success")
    return redirect(url_for("trainer.clients"))


@trainer_bp.route("/clients/remove/<client_id>", methods=["POST"])
@login_required
@trainer_required
def remove_client(client_id):
    db.trainers.update_one({"_id": ObjectId(current_user.id)},
                           {"$pull": {"clients": client_id}})
    db.users.update_one({"_id": ObjectId(client_id)},
                        {"$set": {"trainer_id": ""}})
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
    score      = calculate_auron_score(client_id)
    streak     = get_streak(client_id)
    compliance = get_compliance_for_client(client_id)
    rank       = get_rank_label(score)
    workouts   = list(db.workouts.find({"user_id": ObjectId(client_id)}).sort("date", -1).limit(10))
    progress   = list(db.progress_entries.find({"user_id": ObjectId(client_id)}).sort("date", -1).limit(6))
    thread     = list(db.messages.find({
        "trainer_id": ObjectId(current_user.id), "client_id": ObjectId(client_id)
    }).sort("created_at", 1).limit(50))
    # Assigned programs for this client
    assigned = list(db.assigned_programs.find({"user_id": ObjectId(client_id),
                                               "trainer_id": ObjectId(current_user.id)}))
    prog_ids  = [a["program_id"] for a in assigned]
    programs  = list(db.programs.find({"_id": {"$in": prog_ids}}))
    return render_template("trainer/client_detail.html",
                           client=client, score=score, streak=streak,
                           compliance=compliance, rank=rank,
                           workouts=workouts, progress=progress,
                           thread=thread, programs=programs)


# ── Invite landing ────────────────────────────────────────────────────────────

@trainer_bp.route("/invite/<code>")
def invite_landing(code):
    trainer = db.trainers.find_one({"invite_code": code})
    if not trainer:
        flash("Invalid invite link.", "error")
        return redirect(url_for("auth.index"))
    return redirect(url_for("auth.signup_user", ref=code))


# ── Programs ──────────────────────────────────────────────────────────────────

@trainer_bp.route("/programs", methods=["GET", "POST"])
@login_required
@trainer_required
def programs():
    trainer      = get_trainer_doc()
    client_ids   = [ObjectId(c) for c in trainer.get("clients", [])]
    clients_list = list(db.users.find({"_id": {"$in": client_ids}}, {"username": 1, "avatar_url": 1}))

    if request.method == "POST":
        db.programs.insert_one({
            "trainer_id":  ObjectId(current_user.id),
            "name":        request.form.get("name", "New Program"),
            "description": request.form.get("description", ""),
            "days":        [],
            "created_at":  datetime.utcnow(),
        })
        flash("Program created!", "success")
        return redirect(url_for("trainer.programs"))

    progs        = list(db.programs.find({"trainer_id": ObjectId(current_user.id)}).sort("created_at", -1))
    clients_json = json.dumps([{"id": str(c["_id"]), "username": c["username"],
                                "avatar_url": c.get("avatar_url", "")} for c in clients_list])

    # Enrich programs with assigned-client info
    for p in progs:
        assigned = db.assigned_programs.find({"program_id": p["_id"],
                                              "trainer_id": ObjectId(current_user.id)})
        p["assigned_count"] = db.assigned_programs.count_documents(
            {"program_id": p["_id"], "trainer_id": ObjectId(current_user.id)})

    return render_template("trainer/programs.html",
                           programs=progs, clients_json=clients_json,
                           total_clients=len(clients_list))


@trainer_bp.route("/programs/<program_id>/assign", methods=["POST"])
@login_required
@trainer_required
def assign_program(program_id):
    assign_all = request.form.get("assign_all") == "1"
    trainer    = get_trainer_doc()

    if assign_all:
        client_ids = trainer.get("clients", [])
    else:
        client_ids = request.form.getlist("client_ids")

    for cid in client_ids:
        db.assigned_programs.update_one(
            {"user_id": ObjectId(cid), "program_id": ObjectId(program_id)},
            {"$set": {"trainer_id": ObjectId(current_user.id),
                      "assigned_at": datetime.utcnow()}},
            upsert=True,
        )
    flash(f"Program assigned to {len(client_ids)} client(s)!", "success")
    return redirect(url_for("trainer.programs"))


@trainer_bp.route("/programs/<program_id>/unassign/<client_id>", methods=["POST"])
@login_required
@trainer_required
def unassign_program(program_id, client_id):
    db.assigned_programs.delete_one({
        "user_id":    ObjectId(client_id),
        "program_id": ObjectId(program_id),
        "trainer_id": ObjectId(current_user.id),
    })
    flash("Program unassigned.", "info")
    return redirect(url_for("trainer.programs"))


# ── Messages ──────────────────────────────────────────────────────────────────

@trainer_bp.route("/messages", methods=["GET", "POST"])
@login_required
@trainer_required
def messages():
    trainer    = get_trainer_doc()
    client_ids = [ObjectId(c) for c in trainer.get("clients", [])]
    clients    = list(db.users.find({"_id": {"$in": client_ids}}, {"username": 1, "avatar_url": 1}))

    if request.method == "POST":
        msg_type     = request.form.get("msg_type", "individual")
        content      = request.form.get("content",  "").strip()
        recipient_id = request.form.get("recipient_id", "")

        if not content:
            flash("Message cannot be empty.", "error")
            return redirect(url_for("trainer.messages"))

        if msg_type == "broadcast":
            recipients = [str(c["_id"]) for c in clients]
        elif recipient_id:
            recipients = [recipient_id]
        else:
            recipients = request.form.getlist("recipients")

        for rid in recipients:
            db.messages.insert_one({
                "trainer_id":   ObjectId(current_user.id),
                "client_id":    ObjectId(rid),
                "direction":    "trainer_to_user",
                "content":      content,
                "read_by_user": False,
                "created_at":   datetime.utcnow(),
            })
        flash(f"Message sent to {len(recipients)} athlete(s).", "success")
        return redirect(url_for("trainer.messages"))

    active_client_id = request.args.get("client", "")
    conversations    = []
    for c in clients:
        latest = db.messages.find_one(
            {"trainer_id": ObjectId(current_user.id), "client_id": c["_id"]},
            sort=[("created_at", -1)])
        unread = db.messages.count_documents({
            "trainer_id": ObjectId(current_user.id), "client_id": c["_id"],
            "direction": "user_to_trainer", "read_by_trainer": False,
        })
        conversations.append({"client": c, "latest": latest, "unread": unread})
    conversations.sort(key=lambda x: (
        -x["unread"],
        x["latest"]["created_at"] if x.get("latest") else datetime.min
    ))

    thread        = []
    active_client = None
    if active_client_id:
        active_client = db.users.find_one({"_id": ObjectId(active_client_id)},
                                          {"username": 1, "avatar_url": 1})
        thread = list(db.messages.find({
            "trainer_id": ObjectId(current_user.id),
            "client_id":  ObjectId(active_client_id),
        }).sort("created_at", 1).limit(100))
        db.messages.update_many(
            {"trainer_id": ObjectId(current_user.id), "client_id": ObjectId(active_client_id),
             "direction": "user_to_trainer", "read_by_trainer": False},
            {"$set": {"read_by_trainer": True}},
        )

    return render_template("trainer/messages.html",
                           clients=clients, conversations=conversations,
                           thread=thread, active_client=active_client,
                           active_client_id=active_client_id)


# ── Leaderboard ───────────────────────────────────────────────────────────────

@trainer_bp.route("/leaderboard")
@login_required
@trainer_required
def leaderboard():
    tab    = request.args.get("tab",    "trainers")
    period = request.args.get("period", "daily")

    trainers = list(db.trainers.find({},
                    {"username": 1, "business_name": 1, "clients": 1, "avatar_url": 1}))
    board = []
    today    = date.today()
    date_str = today.strftime("%Y-%m-%d")
    if period == "weekly":
        from_date = (today - timedelta(days=7)).strftime("%Y-%m-%d")
    elif period == "monthly":
        from_date = (today - timedelta(days=30)).strftime("%Y-%m-%d")
    else:
        from_date = date_str

    for t in trainers:
        cids = [ObjectId(c) for c in t.get("clients", [])]
        if not cids:
            continue
        scores = []
        for cid in cids:
            if period == "daily":
                rec = db.scores.find_one({"user_id": cid, "date": date_str})
                scores.append(rec["score"] if rec else 0)
            else:
                recs = list(db.scores.find({"user_id": cid, "date": {"$gte": from_date}}))
                scores.append(round(sum(r["score"] for r in recs) / len(recs)) if recs else 0)
        avg = round(sum(scores) / len(scores)) if scores else 0
        board.append({
            "id":            str(t["_id"]),
            "username":      t.get("username"),
            "business_name": t.get("business_name", ""),
            "avatar_url":    t.get("avatar_url", ""),
            "avg_score":     avg,
            "client_count":  len(cids),
        })
    board.sort(key=lambda x: x["avg_score"], reverse=True)
    for i, b in enumerate(board):
        b["rank"] = i + 1
    return render_template("trainer/leaderboard.html", board=board, tab=tab, period=period)