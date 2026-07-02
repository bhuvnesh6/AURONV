from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app import db
from routes.helpers import (
    calculate_auron_score, save_daily_score, get_streak,
    get_today_logs, get_rank_label, get_geo_from_ip, get_client_ip
)
from bson import ObjectId
from datetime import datetime, date, timedelta
import cloudinary, cloudinary.uploader, os
from bson.errors import InvalidId

user_bp = Blueprint("user", __name__)

cloudinary.config(
    cloud_name=os.environ.get("CLOUDINARY_CLOUD_NAME"),
    api_key=os.environ.get("CLOUDINARY_API_KEY"),
    api_secret=os.environ.get("CLOUDINARY_API_SECRET"),
)


def user_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != "user":
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)
    return decorated


# ── Dashboard ─────────────────────────────────────────────────────────────────

@user_bp.route("/dashboard")
@login_required
@user_required
def dashboard():
    uid    = current_user.id
    score  = calculate_auron_score(uid)
    save_daily_score(uid)
    streak = get_streak(uid)
    logs   = get_today_logs(uid)
    rank   = get_rank_label(score)
    unread = db.messages.count_documents({
        "client_id":    ObjectId(uid),
        "direction":    "trainer_to_user",
        "read_by_user": False,
    })
    # Assigned programs
    assigned_programs = list(db.assigned_programs.find({"user_id": ObjectId(uid)}))
    prog_ids  = [a["program_id"] for a in assigned_programs]
    programs  = list(db.programs.find({"_id": {"$in": prog_ids}})) if prog_ids else []
    return render_template("user/dashboard.html",
                           score=score, streak=streak, logs=logs,
                           rank=rank, unread=unread, programs=programs)


# ── Workouts ──────────────────────────────────────────────────────────────────

@user_bp.route("/workouts", methods=["GET", "POST"])
@login_required
@user_required
def workouts():
    uid = ObjectId(current_user.id)
    if request.method == "POST":
        action = request.form.get("action")
        if action == "create_workout":
            db.workouts.insert_one({
                "user_id":      uid,
                "date":         date.today().strftime("%Y-%m-%d"),
                "name":         request.form.get("workout_name", "Workout"),
                "duration_min": int(request.form.get("duration", 0) or 0),
                "notes":        request.form.get("notes", ""),
                "exercises":    [],
                "total_volume": 0,
                "created_at":   datetime.utcnow(),
            })
            save_daily_score(current_user.id)
            flash("Workout logged!", "success")
        elif action == "add_exercise":
            wid  = request.form.get("workout_id")
            sets = int(request.form.get("sets",   0) or 0)
            reps = int(request.form.get("reps",   0) or 0)
            wt   = float(request.form.get("weight", 0) or 0)
            db.workouts.update_one(
                {"_id": ObjectId(wid)},
                {"$push": {"exercises": {"name": request.form.get("ex_name", ""),
                    "sets": sets, "reps": reps, "weight_kg": wt,
                    "rest_sec": int(request.form.get("rest", 60) or 60)}},
                 "$inc": {"total_volume": sets * reps * wt}},
            )
            flash("Exercise added!", "success")
        return redirect(url_for("user.workouts"))

    workouts_list = list(db.workouts.find({"user_id": uid}).sort("date", -1).limit(30))
    return render_template("user/workouts.html", workouts=workouts_list)


# ── Nutrition ─────────────────────────────────────────────────────────────────

@user_bp.route("/nutrition", methods=["GET", "POST"])
@login_required
@user_required
def nutrition():
    uid      = ObjectId(current_user.id)
    date_str = date.today().strftime("%Y-%m-%d")
    if request.method == "POST":
        protein  = float(request.form.get("protein_grams", 0) or 0)
        calories = float(request.form.get("calories",      0) or 0)
        entry    = {"notes": request.form.get("meal_notes", ""), "protein": protein,
                    "calories": calories, "time": datetime.utcnow().strftime("%H:%M")}
        existing = db.nutrition_logs.find_one({"user_id": uid, "date": date_str})
        if existing:
            db.nutrition_logs.update_one({"_id": existing["_id"]},
                {"$inc": {"protein_grams": protein, "calories": calories},
                 "$push": {"meals": entry}})
        else:
            db.nutrition_logs.insert_one({"user_id": uid, "date": date_str,
                "protein_grams": protein, "calories": calories,
                "meals": [entry], "created_at": datetime.utcnow()})
        save_daily_score(current_user.id)
        flash("Nutrition logged!", "success")
        return redirect(url_for("user.nutrition"))

    today_log = db.nutrition_logs.find_one({"user_id": uid, "date": date_str}) or {}
    history   = list(db.nutrition_logs.find({"user_id": uid}).sort("date", -1).limit(7))
    user_doc  = db.users.find_one({"_id": uid}) or {}
    return render_template("user/nutrition.html", today=today_log, history=history,
                           protein_goal=user_doc.get("protein_goal", 150))


# ── Quick logs ────────────────────────────────────────────────────────────────

@user_bp.route("/water", methods=["POST"])
@login_required
@user_required
def log_water():
    uid = ObjectId(current_user.id)
    date_str = date.today().strftime("%Y-%m-%d")
    amount = int(request.form.get("amount_ml", 0) or 0)
    ex = db.water_logs.find_one({"user_id": uid, "date": date_str})
    if ex:
        db.water_logs.update_one({"_id": ex["_id"]}, {"$inc": {"amount_ml": amount}})
    else:
        db.water_logs.insert_one({"user_id": uid, "date": date_str,
                                   "amount_ml": amount, "created_at": datetime.utcnow()})
    save_daily_score(current_user.id)
    return redirect(url_for("user.dashboard"))


@user_bp.route("/steps", methods=["POST"])
@login_required
@user_required
def log_steps():
    uid = ObjectId(current_user.id)
    date_str = date.today().strftime("%Y-%m-%d")
    db.step_logs.update_one({"user_id": uid, "date": date_str},
        {"$set": {"steps": int(request.form.get("steps", 0) or 0),
                  "updated_at": datetime.utcnow()},
         "$setOnInsert": {"created_at": datetime.utcnow()}}, upsert=True)
    save_daily_score(current_user.id)
    return redirect(url_for("user.dashboard"))


@user_bp.route("/sleep", methods=["POST"])
@login_required
@user_required
def log_sleep():
    uid = ObjectId(current_user.id)
    date_str = date.today().strftime("%Y-%m-%d")
    db.sleep_logs.update_one({"user_id": uid, "date": date_str},
        {"$set": {"hours": float(request.form.get("hours", 0) or 0),
                  "quality": request.form.get("quality", "good"),
                  "updated_at": datetime.utcnow()},
         "$setOnInsert": {"created_at": datetime.utcnow()}}, upsert=True)
    save_daily_score(current_user.id)
    return redirect(url_for("user.dashboard"))


# ── Inbox ─────────────────────────────────────────────────────────────────────

@user_bp.route("/inbox")
@login_required
@user_required
def inbox():
    uid         = ObjectId(current_user.id)
    trainer_ids = db.messages.distinct("trainer_id", {"client_id": uid})
    threads     = []
    for tid in trainer_ids:
        trainer = db.trainers.find_one({"_id": tid},
                    {"username": 1, "avatar_url": 1, "business_name": 1}) or {}
        latest  = db.messages.find_one({"client_id": uid, "trainer_id": tid},
                    sort=[("created_at", -1)])
        unread  = db.messages.count_documents({
            "client_id": uid, "trainer_id": tid,
            "direction": "trainer_to_user", "read_by_user": False,
        })
        threads.append({"trainer_id": str(tid), "trainer": trainer,
                        "latest": latest, "unread": unread})
    threads.sort(key=lambda x: x["latest"]["created_at"] if x.get("latest") else datetime.min,
                 reverse=True)

    active_tid     = request.args.get("t", "")
    thread_msgs    = []
    active_trainer = None
    if active_tid:
        active_trainer = db.trainers.find_one({"_id": ObjectId(active_tid)},
                           {"username": 1, "avatar_url": 1, "business_name": 1})
        thread_msgs = list(db.messages.find(
            {"client_id": uid, "trainer_id": ObjectId(active_tid)},
        ).sort("created_at", 1).limit(100))
        db.messages.update_many(
            {"client_id": uid, "trainer_id": ObjectId(active_tid),
             "direction": "trainer_to_user", "read_by_user": False},
            {"$set": {"read_by_user": True}},
        )

    return render_template("user/inbox.html",
                           threads=threads, thread_msgs=thread_msgs,
                           active_tid=active_tid, active_trainer=active_trainer)


# ── Timeline ──────────────────────────────────────────────────────────────────

@user_bp.route("/timeline", methods=["GET", "POST"])
@login_required
@user_required
def timeline():
    uid = ObjectId(current_user.id)
    if request.method == "POST":
        entry = {
            "user_id": uid, "date": date.today().strftime("%Y-%m-%d"),
            "weight": request.form.get("weight", ""), "body_fat": request.form.get("body_fat", ""),
            "bench_pr": request.form.get("bench_pr", ""), "deadlift_pr": request.form.get("deadlift_pr", ""),
            "squat_pr": request.form.get("squat_pr", ""), "pushups": request.form.get("pushups", ""),
            "pullups": request.form.get("pullups", ""), "notes": request.form.get("notes", ""),
            "photo_url": "", "created_at": datetime.utcnow(),
        }
        if "photo" in request.files and request.files["photo"].filename:
            try:
                r = cloudinary.uploader.upload(request.files["photo"], folder="auron/progress")
                entry["photo_url"] = r.get("secure_url", "")
            except Exception:
                pass
        db.progress_entries.insert_one(entry)
        flash("Progress entry saved!", "success")
        return redirect(url_for("user.timeline"))

    entries = list(db.progress_entries.find({"user_id": uid}).sort("date", -1).limit(24))
    return render_template("user/timeline.html", entries=entries)


# ── Leaderboard ───────────────────────────────────────────────────────────────

@user_bp.route("/leaderboard")
@login_required
@user_required
def leaderboard():
    scope  = request.args.get("scope",  "global")
    period = request.args.get("period", "daily")
    tab    = request.args.get("tab",    "athletes")

    # ── Location filter params from dropdowns ──
    filter_country = request.args.get("filter_country", "").strip()
    filter_state   = request.args.get("filter_state",   "").strip()
    filter_city    = request.args.get("filter_city",    "").strip()

    today    = date.today()
    date_str = today.strftime("%Y-%m-%d")

    uid      = ObjectId(current_user.id)
    user_doc = db.users.find_one({"_id": uid}) or {}

    if period == "weekly":
        from_date = (today - timedelta(days=7)).strftime("%Y-%m-%d")
    elif period == "monthly":
        from_date = (today - timedelta(days=30)).strftime("%Y-%m-%d")
    else:
        from_date = date_str

    # ── Build geo_filter ──
    # Dropdown filters take priority over scope-based filters
    geo_filter = {}

    if filter_country or filter_state or filter_city:
        # User applied explicit dropdown filters
        if filter_country:
            geo_filter["country"] = filter_country
        if filter_state:
            geo_filter["state"] = filter_state
        if filter_city:
            geo_filter["city"] = filter_city
    else:
        # Fall back to scope-based geo filter
        if scope == "country":
            geo_filter = {"country": user_doc.get("country", "")}
        elif scope == "state":
            geo_filter = {
                "country": user_doc.get("country", ""),
                "state":   user_doc.get("state",   "")
            }
        elif scope == "city":
            geo_filter = {
                "country": user_doc.get("country", ""),
                "city":    user_doc.get("city",    "")
            }

    entries      = []
    filter_empty = False   # flag → show "uncharted territory" empty state

    # ==========================================================
    # ATHLETES
    # ==========================================================
    if tab == "athletes":

        if period == "daily":
            pipeline = [
                {"$match": {"date": date_str, **geo_filter}},
                {"$group": {"_id": "$user_id", "score": {"$max": "$score"}}},
                {"$sort":  {"score": -1}},
                {"$limit": 50}
            ]
        else:
            pipeline = [
                {"$match": {"date": {"$gte": from_date}, **geo_filter}},
                {"$group": {"_id": "$user_id", "avg_score": {"$avg": "$score"}}},
                {"$sort":  {"avg_score": -1}},
                {"$limit": 50}
            ]

        # Team filter
        if scope == "team":
            team_ids = []
            if user_doc.get("trainer_id"):
                trainer = db.trainers.find_one({"_id": ObjectId(user_doc["trainer_id"])})
                if trainer:
                    for cid in trainer.get("clients", []):
                        try:
                            team_ids.append(ObjectId(cid))
                        except Exception:
                            pass
            pipeline[0]["$match"]["user_id"] = {"$in": team_ids}

        raw = list(db.scores.aggregate(pipeline))

        rank = 1
        for r in raw:
            u_id = r.get("_id")
            if not u_id:
                continue
            if isinstance(u_id, str):
                try:
                    u_id = ObjectId(u_id)
                except InvalidId:
                    continue

            user = db.users.find_one(
                {"_id": u_id},
                {"username": 1, "avatar_url": 1, "city": 1, "country": 1}
            )
            if not user:
                continue

            entries.append({
                "rank":       rank,
                "user_id":    str(u_id),
                "username":   user.get("username", "Unknown"),
                "avatar_url": user.get("avatar_url", ""),
                "location":   user.get("city") or user.get("country", ""),
                "score":      round(r.get("avg_score", r.get("score", 0))),
                "is_me":      str(u_id) == str(uid)
            })
            rank += 1

        # Detect filter-driven empty (dropdown filters applied but no results)
        if not entries and (filter_country or filter_state or filter_city):
            filter_empty = True

        # Always show current user at bottom if not already ranked
        if not filter_empty and not any(e["is_me"] for e in entries):
            my_score = calculate_auron_score(str(uid))
            entries.append({
                "rank":       "—",
                "user_id":    str(uid),
                "username":   user_doc.get("username", "You"),
                "avatar_url": user_doc.get("avatar_url", ""),
                "location":   user_doc.get("city") or user_doc.get("country", ""),
                "score":      my_score,
                "is_me":      True,
                "not_ranked": True
            })

    # ==========================================================
    # TRAINERS
    # ==========================================================
    else:
        trainers = list(db.trainers.find(
            {},
            {
                "username": 1, "business_name": 1, "avatar_url": 1,
                "clients": 1, "country": 1, "state": 1, "city": 1
            }
        ))

        board = []
        for trainer in trainers:

            # Dropdown filters take priority
            if filter_country and trainer.get("country") != filter_country:
                continue
            if filter_state and trainer.get("state") != filter_state:
                continue
            if filter_city and trainer.get("city") != filter_city:
                continue

            # Scope-based filters (only when no dropdown filter active)
            if not (filter_country or filter_state or filter_city):
                if scope == "country" and trainer.get("country") != user_doc.get("country"):
                    continue
                if scope == "state" and trainer.get("state") != user_doc.get("state"):
                    continue
                if scope == "city" and trainer.get("city") != user_doc.get("city"):
                    continue

            client_scores = []
            for cid in trainer.get("clients", []):
                try:
                    cid = ObjectId(cid)
                except Exception:
                    continue

                if period == "daily":
                    score_doc = db.scores.find_one({"user_id": cid, "date": date_str})
                    client_scores.append(score_doc["score"] if score_doc else 0)
                else:
                    docs = list(db.scores.find({"user_id": cid, "date": {"$gte": from_date}}))
                    avg  = sum(d["score"] for d in docs) / len(docs) if docs else 0
                    client_scores.append(avg)

            if not client_scores:
                continue

            board.append({
                "trainer_id":   str(trainer["_id"]),
                "username":     trainer.get("username", ""),
                "business_name": trainer.get("business_name", ""),
                "avatar_url":   trainer.get("avatar_url", ""),
                "avg_score":    round(sum(client_scores) / len(client_scores)),
                "client_count": len(client_scores),
                "location":     trainer.get("city") or trainer.get("country", "")
            })

        board.sort(key=lambda x: x["avg_score"], reverse=True)
        for i, item in enumerate(board):
            item["rank"] = i + 1

        entries = board

        if not entries and (filter_country or filter_state or filter_city):
            filter_empty = True

    return render_template(
        "user/leaderboard.html",
        entries=entries,
        scope=scope,
        period=period,
        tab=tab,
        user_doc=user_doc,
        filter_empty=filter_empty,
        filter_country=filter_country,
        filter_state=filter_state,
        filter_city=filter_city,
    )

# ── Profile ───────────────────────────────────────────────────────────────────

@user_bp.route("/profile", methods=["GET", "POST"])
@login_required
@user_required
def profile():
    uid = ObjectId(current_user.id)
    if request.method == "POST":
        db.users.update_one({"_id": uid}, {"$set": {
            "protein_goal": int(request.form.get("protein_goal", 150) or 150),
            "water_goal":   int(request.form.get("water_goal",   2500) or 2500),
            "sleep_goal":   float(request.form.get("sleep_goal", 7)   or 7),
            "steps_goal":   int(request.form.get("steps_goal",   8000) or 8000),
            "goal":         request.form.get("goal",    ""),
            "weight":       request.form.get("weight",  ""),
            "height":       request.form.get("height",  ""),
            "age":          request.form.get("age",     ""),
            "gender":       request.form.get("gender",  ""),
            "city":         request.form.get("city",    "").strip(),
            "state":        request.form.get("state",   "").strip(),
            "country":      request.form.get("country", "").strip(),
        }})
        flash("Profile updated!", "success")
        return redirect(url_for("user.profile"))

    user_doc = db.users.find_one({"_id": uid}) or {}
    score    = calculate_auron_score(current_user.id)
    streak   = get_streak(current_user.id)
    rank     = get_rank_label(score)
    return render_template("user/profile.html",
                           user=user_doc, score=score, streak=streak, rank=rank)


@user_bp.route("/profile/avatar", methods=["POST"])
@login_required
@user_required
def upload_avatar():
    uid  = ObjectId(current_user.id)
    file = request.files.get("avatar")
    if not file or not file.filename:
        flash("No file selected.", "error")
        return redirect(url_for("user.profile"))
    if file.content_type not in {"image/jpeg", "image/png", "image/webp", "image/gif"}:
        flash("Invalid file type.", "error")
        return redirect(url_for("user.profile"))
    try:
        r = cloudinary.uploader.upload(file, folder="auron/avatars",
            public_id=f"user_{current_user.id}", overwrite=True,
            transformation=[{"width": 400, "height": 400, "crop": "fill",
                             "gravity": "face", "quality": "auto"}])
        db.users.update_one({"_id": uid}, {"$set": {"avatar_url": r.get("secure_url", "")}})
        flash("Photo updated!", "success")
    except Exception as e:
        flash(f"Upload failed: {e}", "error")
    return redirect(url_for("user.profile"))


@user_bp.route("/profile/avatar/remove", methods=["POST"])
@login_required
@user_required
def remove_avatar():
    try:
        cloudinary.uploader.destroy(f"auron/avatars/user_{current_user.id}")
    except Exception:
        pass
    db.users.update_one({"_id": ObjectId(current_user.id)}, {"$set": {"avatar_url": ""}})
    flash("Photo removed.", "info")
    return redirect(url_for("user.profile"))