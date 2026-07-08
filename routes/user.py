from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from flask import current_app
from routes.helpers import (
    calculate_auron_score, save_daily_score, get_streak,
    get_today_logs, get_rank_label, get_geo_from_ip, get_client_ip
)
from bson import ObjectId
from datetime import datetime, date, timedelta
import cloudinary, cloudinary.uploader, os

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
    unread = current_app.config["DB"].messages.count_documents({
        "client_id":    ObjectId(uid),
        "direction":    "trainer_to_user",
        "read_by_user": False,
    })
    # Assigned programs
    assigned_programs = list(current_app.config["DB"].assigned_programs.find({"user_id": ObjectId(uid)}))
    prog_ids  = [a["program_id"] for a in assigned_programs]
    programs  = list(current_app.config["DB"].programs.find({"_id": {"$in": prog_ids}})) if prog_ids else []
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
            current_app.config["DB"].workouts.insert_one({
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
            current_app.config["DB"].workouts.update_one(
                {"_id": ObjectId(wid)},
                {"$push": {"exercises": {"name": request.form.get("ex_name", ""),
                    "sets": sets, "reps": reps, "weight_kg": wt,
                    "rest_sec": int(request.form.get("rest", 60) or 60)}},
                 "$inc": {"total_volume": sets * reps * wt}},
            )
            flash("Exercise added!", "success")
        return redirect(url_for("user.workouts"))

    workouts_list = list(current_app.config["DB"].workouts.find({"user_id": uid}).sort("date", -1).limit(30))
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
        existing = current_app.config["DB"].nutrition_logs.find_one({"user_id": uid, "date": date_str})
        if existing:
            current_app.config["DB"].nutrition_logs.update_one({"_id": existing["_id"]},
                {"$inc": {"protein_grams": protein, "calories": calories},
                 "$push": {"meals": entry}})
        else:
            current_app.config["DB"].nutrition_logs.insert_one({"user_id": uid, "date": date_str,
                "protein_grams": protein, "calories": calories,
                "meals": [entry], "created_at": datetime.utcnow()})
        save_daily_score(current_user.id)
        flash("Nutrition logged!", "success")
        return redirect(url_for("user.nutrition"))

    today_log = current_app.config["DB"].nutrition_logs.find_one({"user_id": uid, "date": date_str}) or {}
    history   = list(current_app.config["DB"].nutrition_logs.find({"user_id": uid}).sort("date", -1).limit(7))
    user_doc  = current_app.config["DB"].users.find_one({"_id": uid}) or {}
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
    ex = current_app.config["DB"].water_logs.find_one({"user_id": uid, "date": date_str})
    if ex:
        current_app.config["DB"].water_logs.update_one({"_id": ex["_id"]}, {"$inc": {"amount_ml": amount}})
    else:
        current_app.config["DB"].water_logs.insert_one({"user_id": uid, "date": date_str,
                                   "amount_ml": amount, "created_at": datetime.utcnow()})
    save_daily_score(current_user.id)
    return redirect(url_for("user.dashboard"))


@user_bp.route("/steps", methods=["POST"])
@login_required
@user_required
def log_steps():
    uid = ObjectId(current_user.id)
    date_str = date.today().strftime("%Y-%m-%d")
    current_app.config["DB"].step_logs.update_one({"user_id": uid, "date": date_str},
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
    current_app.config["DB"].sleep_logs.update_one({"user_id": uid, "date": date_str},
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
    trainer_ids = current_app.config["DB"].messages.distinct("trainer_id", {"client_id": uid})
    threads     = []
    for tid in trainer_ids:
        trainer = current_app.config["DB"].trainers.find_one({"_id": tid},
                    {"username": 1, "avatar_url": 1, "business_name": 1}) or {}
        latest  = current_app.config["DB"].messages.find_one({"client_id": uid, "trainer_id": tid},
                    sort=[("created_at", -1)])
        unread  = current_app.config["DB"].messages.count_documents({
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
        active_trainer = current_app.config["DB"].trainers.find_one({"_id": ObjectId(active_tid)},
                           {"username": 1, "avatar_url": 1, "business_name": 1})
        thread_msgs = list(current_app.config["DB"].messages.find(
            {"client_id": uid, "trainer_id": ObjectId(active_tid)},
        ).sort("created_at", 1).limit(100))
        current_app.config["DB"].messages.update_many(
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
        current_app.config["DB"].progress_entries.insert_one(entry)
        flash("Progress entry saved!", "success")
        return redirect(url_for("user.timeline"))

    entries = list(current_app.config["DB"].progress_entries.find({"user_id": uid}).sort("date", -1).limit(24))
    return render_template("user/timeline.html", entries=entries)


# ── Leaderboard ───────────────────────────────────────────────────────────────

@user_bp.route("/leaderboard")
@login_required
@user_required
def leaderboard():
    scope  = request.args.get("scope",  "global")
    period = request.args.get("period", "daily")
    tab    = request.args.get("tab",    "athletes")

    # Location filter params from cascading selects
    filter_country = request.args.get("floc_country", "").strip()
    filter_state   = request.args.get("floc_state",   "").strip()
    filter_city    = request.args.get("floc_city",    "").strip()

    today    = date.today()
    date_str = today.strftime("%Y-%m-%d")
    uid      = ObjectId(current_user.id)
    user_doc = current_app.config["DB"].users.find_one({"_id": uid}) or {}

    if period == "weekly":
        from_date = (today - timedelta(days=7)).strftime("%Y-%m-%d")
    elif period == "monthly":
        from_date = (today - timedelta(days=30)).strftime("%Y-%m-%d")
    else:
        from_date = date_str

    # Build geo filter from explicit dropdown values (not user's own profile)
    geo_filter = {}
    if scope == "country" and filter_country:
        geo_filter = {"country": filter_country}
    elif scope == "state" and filter_country:
        gf = {"country": filter_country}
        if filter_state: gf["state"] = filter_state
        geo_filter = gf
    elif scope == "city" and filter_country:
        gf = {"country": filter_country}
        if filter_state: gf["state"] = filter_state
        if filter_city:  gf["city"]  = filter_city
        geo_filter = gf

    entries = []

    if tab == "athletes":
        if period == "daily":
            pipeline = [{"$match": {"date": date_str, **geo_filter}},
                        {"$sort": {"score": -1}}, {"$limit": 50}]
        else:
            pipeline = [{"$match": {"date": {"$gte": from_date}, **geo_filter}},
                        {"$group": {"_id": "$user_id", "avg_score": {"$avg": "$score"}}},
                        {"$sort": {"avg_score": -1}}, {"$limit": 50}]

        if scope == "team":
            trainer_doc = (current_app.config["DB"].trainers.find_one({"_id": ObjectId(user_doc["trainer_id"])})
                          if user_doc.get("trainer_id") else None)
            team_ids    = [ObjectId(c) for c in (trainer_doc or {}).get("clients", [])]
            if not team_ids:
                # No team — return empty immediately
                return render_template("user/leaderboard.html",
                                       entries=[], scope=scope, period=period,
                                       tab=tab, user_doc=user_doc,
                                       filter_country=filter_country,
                                       filter_state=filter_state,
                                       filter_city=filter_city)
            pipeline[0]["$match"]["user_id"] = {"$in": team_ids}

        raw = list(current_app.config["DB"].scores.aggregate(pipeline))
        rank = 0
        for r in raw:
            u_id = r.get("_id") or r.get("user_id")
            if not u_id:
                continue
            u = current_app.config["DB"].users.find_one({"_id": u_id},
                    {"username": 1, "avatar_url": 1, "city": 1, "country": 1}) or {}
            if not u.get("username"):
                continue  # skip orphaned score records
            rank += 1
            is_me = str(u_id) == str(uid)
            entries.append({
                "rank":       rank,
                "user_id":    str(u_id),
                "username":   u["username"],
                "avatar_url": u.get("avatar_url", ""),
                "location":   u.get("city", "") or u.get("country", ""),
                "score":      round(r.get("avg_score", r.get("score", 0))),
                "is_me":      is_me,
            })

        # Ensure current user appears even if not in top 50
        me_in_list = any(e["is_me"] for e in entries)
        if not me_in_list:
            my_score = calculate_auron_score(str(uid))
            entries.append({
                "rank":       "—",
                "user_id":    str(uid),
                "username":   user_doc.get("username", "You"),
                "avatar_url": user_doc.get("avatar_url", ""),
                "location":   user_doc.get("city", "") or user_doc.get("country", ""),
                "score":      my_score,
                "is_me":      True,
                "not_ranked": True,
            })

    else:  # trainers tab
        trainers = list(current_app.config["DB"].trainers.find({},
            {"username": 1, "business_name": 1, "avatar_url": 1,
             "clients": 1, "city": 1, "country": 1, "state": 1}))
        board = []
        for t in trainers:
            if scope == "country" and t.get("country") != user_doc.get("country"): continue
            if scope == "state"   and t.get("state")   != user_doc.get("state"):   continue
            if scope == "city"    and t.get("city")     != user_doc.get("city"):    continue
            cids   = [ObjectId(c) for c in t.get("clients", [])]
            if not cids:
                continue
            scores = []
            for cid in cids:
                if period == "daily":
                    rec = current_app.config["DB"].scores.find_one({"user_id": cid, "date": date_str})
                    scores.append(rec["score"] if rec else 0)
                else:
                    recs = list(current_app.config["DB"].scores.find({"user_id": cid, "date": {"$gte": from_date}}))
                    scores.append(sum(r["score"] for r in recs) / len(recs) if recs else 0)
            avg = round(sum(scores) / len(scores)) if scores else 0
            board.append({
                "trainer_id":    str(t["_id"]),
                "username":      t.get("username", ""),
                "business_name": t.get("business_name", ""),
                "avatar_url":    t.get("avatar_url", ""),
                "avg_score":     avg,
                "client_count":  len(cids),
                "location":      t.get("city", "") or t.get("country", ""),
            })
        board.sort(key=lambda x: x["avg_score"], reverse=True)
        for i, b in enumerate(board):
            b["rank"] = i + 1
        entries = board

    return render_template("user/leaderboard.html",
                           entries=entries, scope=scope, period=period,
                           tab=tab, user_doc=user_doc,
                           filter_country=filter_country,
                           filter_state=filter_state,
                           filter_city=filter_city)


# ── Profile ───────────────────────────────────────────────────────────────────

@user_bp.route("/profile", methods=["GET", "POST"])
@login_required
@user_required
def profile():
    uid = ObjectId(current_user.id)
    if request.method == "POST":
        current_app.config["DB"].users.update_one({"_id": uid}, {"$set": {
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

    user_doc = current_app.config["DB"].users.find_one({"_id": uid}) or {}
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
        current_app.config["DB"].users.update_one({"_id": uid}, {"$set": {"avatar_url": r.get("secure_url", "")}})
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
    current_app.config["DB"].users.update_one({"_id": ObjectId(current_user.id)}, {"$set": {"avatar_url": ""}})
    flash("Photo removed.", "info")
    return redirect(url_for("user.profile"))