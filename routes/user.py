from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app import db
from routes.helpers import (
    calculate_auron_score, save_daily_score, get_streak,
    get_today_logs, get_rank_label
)
from bson import ObjectId
from datetime import datetime, date, timedelta
import cloudinary
import cloudinary.uploader
import os

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


# ── Dashboard ────────────────────────────────────────────────────────────────

@user_bp.route("/dashboard")
@login_required
@user_required
def dashboard():
    uid = current_user.id
    score = calculate_auron_score(uid)
    save_daily_score(uid)
    streak = get_streak(uid)
    logs = get_today_logs(uid)
    rank = get_rank_label(score)
    return render_template(
        "user/dashboard.html",
        score=score, streak=streak, logs=logs, rank=rank
    )


# ── Workouts ─────────────────────────────────────────────────────────────────

@user_bp.route("/workouts", methods=["GET", "POST"])
@login_required
@user_required
def workouts():
    uid = ObjectId(current_user.id)

    if request.method == "POST":
        action = request.form.get("action")

        if action == "create_workout":
            workout = {
                "user_id": uid,
                "date": date.today().strftime("%Y-%m-%d"),
                "name": request.form.get("workout_name", "Workout"),
                "duration_min": int(request.form.get("duration", 0) or 0),
                "notes": request.form.get("notes", ""),
                "exercises": [],
                "total_volume": 0,
                "created_at": datetime.utcnow(),
            }
            db.workouts.insert_one(workout)
            save_daily_score(current_user.id)
            flash("Workout logged!", "success")

        elif action == "add_exercise":
            workout_id = request.form.get("workout_id")
            exercise = {
                "name": request.form.get("ex_name", ""),
                "sets": int(request.form.get("sets", 0) or 0),
                "reps": int(request.form.get("reps", 0) or 0),
                "weight_kg": float(request.form.get("weight", 0) or 0),
                "rest_sec": int(request.form.get("rest", 60) or 60),
            }
            volume = exercise["sets"] * exercise["reps"] * exercise["weight_kg"]
            db.workouts.update_one(
                {"_id": ObjectId(workout_id)},
                {
                    "$push": {"exercises": exercise},
                    "$inc": {"total_volume": volume},
                },
            )
            flash("Exercise added!", "success")

        return redirect(url_for("user.workouts"))

    workouts_list = list(
        db.workouts.find({"user_id": uid}).sort("date", -1).limit(30)
    )
    return render_template("user/workouts.html", workouts=workouts_list)


# ── Nutrition ─────────────────────────────────────────────────────────────────

@user_bp.route("/nutrition", methods=["GET", "POST"])
@login_required
@user_required
def nutrition():
    uid = ObjectId(current_user.id)
    date_str = date.today().strftime("%Y-%m-%d")

    if request.method == "POST":
        protein = float(request.form.get("protein_grams", 0) or 0)
        calories = float(request.form.get("calories", 0) or 0)
        meal_notes = request.form.get("meal_notes", "")

        existing = db.nutrition_logs.find_one({"user_id": uid, "date": date_str})
        if existing:
            db.nutrition_logs.update_one(
                {"_id": existing["_id"]},
                {
                    "$inc": {"protein_grams": protein, "calories": calories},
                    "$push": {"meals": {"notes": meal_notes, "protein": protein, "calories": calories, "time": datetime.utcnow().strftime("%H:%M")}},
                },
            )
        else:
            db.nutrition_logs.insert_one({
                "user_id": uid,
                "date": date_str,
                "protein_grams": protein,
                "calories": calories,
                "meals": [{"notes": meal_notes, "protein": protein, "calories": calories, "time": datetime.utcnow().strftime("%H:%M")}],
                "created_at": datetime.utcnow(),
            })
        save_daily_score(current_user.id)
        flash("Nutrition logged!", "success")
        return redirect(url_for("user.nutrition"))

    today_log = db.nutrition_logs.find_one({"user_id": uid, "date": date_str}) or {}
    history = list(db.nutrition_logs.find({"user_id": uid}).sort("date", -1).limit(7))
    user_doc = db.users.find_one({"_id": uid}) or {}
    return render_template("user/nutrition.html", today=today_log, history=history,
                           protein_goal=user_doc.get("protein_goal", 150))


# ── Water ─────────────────────────────────────────────────────────────────────

@user_bp.route("/water", methods=["POST"])
@login_required
@user_required
def log_water():
    uid = ObjectId(current_user.id)
    date_str = date.today().strftime("%Y-%m-%d")
    amount = int(request.form.get("amount_ml", 0) or 0)

    existing = db.water_logs.find_one({"user_id": uid, "date": date_str})
    if existing:
        db.water_logs.update_one({"_id": existing["_id"]}, {"$inc": {"amount_ml": amount}})
    else:
        db.water_logs.insert_one({"user_id": uid, "date": date_str, "amount_ml": amount, "created_at": datetime.utcnow()})

    save_daily_score(current_user.id)
    return redirect(url_for("user.dashboard"))


# ── Steps ─────────────────────────────────────────────────────────────────────

@user_bp.route("/steps", methods=["POST"])
@login_required
@user_required
def log_steps():
    uid = ObjectId(current_user.id)
    date_str = date.today().strftime("%Y-%m-%d")
    steps = int(request.form.get("steps", 0) or 0)

    db.step_logs.update_one(
        {"user_id": uid, "date": date_str},
        {"$set": {"steps": steps, "updated_at": datetime.utcnow()}, "$setOnInsert": {"created_at": datetime.utcnow()}},
        upsert=True,
    )
    save_daily_score(current_user.id)
    return redirect(url_for("user.dashboard"))


# ── Sleep ─────────────────────────────────────────────────────────────────────

@user_bp.route("/sleep", methods=["POST"])
@login_required
@user_required
def log_sleep():
    uid = ObjectId(current_user.id)
    date_str = date.today().strftime("%Y-%m-%d")
    hours = float(request.form.get("hours", 0) or 0)
    quality = request.form.get("quality", "good")

    db.sleep_logs.update_one(
        {"user_id": uid, "date": date_str},
        {"$set": {"hours": hours, "quality": quality, "updated_at": datetime.utcnow()}, "$setOnInsert": {"created_at": datetime.utcnow()}},
        upsert=True,
    )
    save_daily_score(current_user.id)
    return redirect(url_for("user.dashboard"))


# ── Timeline / Progress ───────────────────────────────────────────────────────

@user_bp.route("/timeline", methods=["GET", "POST"])
@login_required
@user_required
def timeline():
    uid = ObjectId(current_user.id)

    if request.method == "POST":
        entry = {
            "user_id": uid,
            "date": date.today().strftime("%Y-%m-%d"),
            "weight": request.form.get("weight", ""),
            "body_fat": request.form.get("body_fat", ""),
            "bench_pr": request.form.get("bench_pr", ""),
            "deadlift_pr": request.form.get("deadlift_pr", ""),
            "squat_pr": request.form.get("squat_pr", ""),
            "pushups": request.form.get("pushups", ""),
            "pullups": request.form.get("pullups", ""),
            "notes": request.form.get("notes", ""),
            "photo_url": "",
            "created_at": datetime.utcnow(),
        }

        if "photo" in request.files and request.files["photo"].filename:
            photo = request.files["photo"]
            try:
                result = cloudinary.uploader.upload(photo, folder="auron/progress")
                entry["photo_url"] = result.get("secure_url", "")
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
    date_str = date.today().strftime("%Y-%m-%d")
    period = request.args.get("period", "daily")
    tab = request.args.get("tab", "athletes")

    if period == "weekly":
        week_ago = (date.today() - timedelta(days=7)).strftime("%Y-%m-%d")
        pipeline = [
            {"$match": {"date": {"$gte": week_ago}}},
            {"$group": {"_id": "$user_id", "avg_score": {"$avg": "$score"}}},
            {"$sort": {"avg_score": -1}},
            {"$limit": 50},
        ]
    else:
        pipeline = [
            {"$match": {"date": date_str}},
            {"$sort": {"score": -1}},
            {"$limit": 50},
        ]

    raw = list(db.scores.aggregate(pipeline))
    entries = []
    for i, r in enumerate(raw):
        uid = r["_id"]
        u = db.users.find_one({"_id": uid}, {"username": 1, "avatar_url": 1})
        if u:
            entries.append({
                "rank": i + 1,
                "username": u.get("username", "Unknown"),
                "avatar_url": u.get("avatar_url", ""),
                "score": round(r.get("avg_score", r.get("score", 0))),
            })

    return render_template("user/leaderboard.html", entries=entries, period=period, tab=tab)


# ── Profile ───────────────────────────────────────────────────────────────────

@user_bp.route("/profile", methods=["GET", "POST"])
@login_required
@user_required
def profile():
    uid = ObjectId(current_user.id)

    if request.method == "POST":
        updates = {
            "protein_goal": int(request.form.get("protein_goal", 150) or 150),
            "water_goal": int(request.form.get("water_goal", 2500) or 2500),
            "sleep_goal": float(request.form.get("sleep_goal", 7) or 7),
            "steps_goal": int(request.form.get("steps_goal", 8000) or 8000),
            "goal": request.form.get("goal", ""),
            "weight": request.form.get("weight", ""),
            "height": request.form.get("height", ""),
        }
        db.users.update_one({"_id": uid}, {"$set": updates})
        flash("Profile updated!", "success")
        return redirect(url_for("user.profile"))

    user_doc = db.users.find_one({"_id": uid}) or {}
    score = calculate_auron_score(current_user.id)
    streak = get_streak(current_user.id)
    rank = get_rank_label(score)
    return render_template("user/profile.html", user=user_doc, score=score, streak=streak, rank=rank)


# ── Avatar Upload ─────────────────────────────────────────────────────────────

@user_bp.route("/profile/avatar", methods=["POST"])
@login_required
@user_required
def upload_avatar():
    uid = ObjectId(current_user.id)

    if "avatar" not in request.files or not request.files["avatar"].filename:
        flash("No file selected.", "error")
        return redirect(url_for("user.profile"))

    file = request.files["avatar"]

    # Validate file type
    allowed = {"image/jpeg", "image/png", "image/webp", "image/gif"}
    if file.content_type not in allowed:
        flash("Invalid file type. Use JPEG, PNG, or WebP.", "error")
        return redirect(url_for("user.profile"))

    try:
        # Upload to Cloudinary with face-aware square crop
        result = cloudinary.uploader.upload(
            file,
            folder="auron/avatars",
            public_id=f"user_{current_user.id}",  # deterministic → overwrites old photo
            overwrite=True,
            transformation=[
                {"width": 400, "height": 400, "crop": "fill", "gravity": "face", "quality": "auto"},
            ],
            resource_type="image",
        )
        avatar_url = result.get("secure_url", "")
        if not avatar_url:
            raise ValueError("No URL returned from Cloudinary")

        db.users.update_one({"_id": uid}, {"$set": {"avatar_url": avatar_url}})
        flash("Profile photo updated!", "success")

    except Exception as e:
        flash(f"Upload failed: {str(e)}", "error")

    return redirect(url_for("user.profile"))


# ── Remove Avatar ─────────────────────────────────────────────────────────────

@user_bp.route("/profile/avatar/remove", methods=["POST"])
@login_required
@user_required
def remove_avatar():
    uid = ObjectId(current_user.id)
    try:
        cloudinary.uploader.destroy(f"auron/avatars/user_{current_user.id}")
    except Exception:
        pass  # If not found on Cloudinary, still clear from DB
    db.users.update_one({"_id": uid}, {"$set": {"avatar_url": ""}})
    flash("Profile photo removed.", "info")
    return redirect(url_for("user.profile"))