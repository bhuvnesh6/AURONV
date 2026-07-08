from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from flask import current_app
from app import bcrypt
from routes.models import User, Trainer
from routes.helpers import get_geo_from_ip, get_client_ip
from datetime import datetime

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/")
def index():
    if current_user.is_authenticated:
        return redirect(url_for("trainer.dashboard" if current_user.role == "trainer" else "user.dashboard"))
    return render_template("landing.html")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("auth.index"))

    if request.method == "POST":
        email    = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        remember = bool(request.form.get("remember_me"))

        # Try users first, then trainers — single form, no role selector
        doc  = current_app.config["DB"].users.find_one({"email": email})
        if doc:
            person = User(doc)
        else:
            doc  = current_app.config["DB"].trainers.find_one({"email": email})
            person = Trainer(doc) if doc else None

        if person and bcrypt.check_password_hash(doc["password_hash"], password):
            login_user(person, remember=remember)
            next_page = request.args.get("next")
            return redirect(next_page or url_for(
                "trainer.dashboard" if person.role == "trainer" else "user.dashboard"
            ))
        flash("Invalid email or password.", "error")

    return render_template("login.html")


@auth_bp.route("/signup/user", methods=["GET", "POST"])
def signup_user():
    ref_code    = request.args.get("ref", "") or request.form.get("ref_code", "")
    trainer_ref = current_app.config["DB"].trainers.find_one({"invite_code": ref_code}) if ref_code else None

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email    = request.form.get("email",    "").strip().lower()
        phone    = request.form.get("phone",    "").strip()
        password = request.form.get("password", "")
        confirm  = request.form.get("confirm_password", "")
        city     = request.form.get("city",    "").strip()
        state    = request.form.get("state",   "").strip()
        country  = request.form.get("country", "").strip()

        if password != confirm:
            flash("Passwords do not match.", "error")
            return render_template("signup_user.html", ref_code=ref_code, trainer_ref=trainer_ref)

        # Check both collections for duplicate email/username
        if (current_app.config["DB"].users.find_one({"$or": [{"email": email}, {"username": username}]}) or
                current_app.config["DB"].trainers.find_one({"$or": [{"email": email}, {"username": username}]})):
            flash("Email or username already taken.", "error")
            return render_template("signup_user.html", ref_code=ref_code, trainer_ref=trainer_ref)

        if not country:
            geo     = get_geo_from_ip(get_client_ip(request))
            city    = city    or geo["city"]
            state   = state   or geo["state"]
            country = country or geo["country"]

        hashed   = bcrypt.generate_password_hash(password).decode("utf-8")
        user_doc = {
            "type":          "user",          # ← new field
            "username":      username,
            "email":         email,
            "phone":         phone,
            "password_hash": hashed,
            "goal":          request.form.get("goal",   ""),
            "weight":        request.form.get("weight", ""),
            "height":        request.form.get("height", ""),
            "age":           request.form.get("age",    ""),
            "gender":        request.form.get("gender", ""),
            "city":          city,
            "state":         state,
            "country":       country,
            "protein_goal":  150,
            "water_goal":    2500,
            "sleep_goal":    7,
            "steps_goal":    8000,
            "avatar_url":    "",
            "trainer_id":    "",
            "subscription":  {"plan": "free", "status": "inactive", "expires": None},
            "created_at":    datetime.utcnow(),
        }
        new_id = current_app.config["DB"].users.insert_one(user_doc).inserted_id

        if trainer_ref:
            current_app.config["DB"].trainers.update_one({"_id": trainer_ref["_id"]},
                                   {"$addToSet": {"clients": str(new_id)}})
            current_app.config["DB"].users.update_one({"_id": new_id},
                                {"$set": {"trainer_id": str(trainer_ref["_id"])}})

        user_doc["_id"] = new_id
        login_user(User(user_doc))
        msg = (f"Welcome! You've joined {trainer_ref['username']}'s team." if trainer_ref
               else "Welcome to AURON!")
        flash(msg, "success")
        return redirect(url_for("user.dashboard"))

    return render_template("signup_user.html", ref_code=ref_code, trainer_ref=trainer_ref)


@auth_bp.route("/signup/trainer", methods=["GET", "POST"])
def signup_trainer():
    if request.method == "POST":
        username       = request.form.get("username",         "").strip()
        email          = request.form.get("email",            "").strip().lower()
        phone          = request.form.get("phone",            "").strip()
        password       = request.form.get("password",         "")
        confirm        = request.form.get("confirm_password", "")
        business_name  = request.form.get("business_name",   "")
        instagram      = request.form.get("instagram",        "")
        years_exp      = request.form.get("years_experience", "")
        specialization = request.form.get("specialization",   "")
        city           = request.form.get("city",    "").strip()
        state          = request.form.get("state",   "").strip()
        country        = request.form.get("country", "").strip()

        if password != confirm:
            flash("Passwords do not match.", "error")
            return render_template("signup_trainer.html")

        if (current_app.config["DB"].users.find_one({"$or": [{"email": email}, {"username": username}]}) or
                current_app.config["DB"].trainers.find_one({"$or": [{"email": email}, {"username": username}]})):
            flash("Email or username already taken.", "error")
            return render_template("signup_trainer.html")

        if not country:
            geo     = get_geo_from_ip(get_client_ip(request))
            city    = city    or geo["city"]
            state   = state   or geo["state"]
            country = country or geo["country"]

        hashed      = bcrypt.generate_password_hash(password).decode("utf-8")
        trainer_doc = {
            "type":             "trainer",    # ← new field
            "username":         username,
            "email":            email,
            "phone":            phone,
            "password_hash":    hashed,
            "business_name":    business_name,
            "instagram":        instagram,
            "years_experience": years_exp,
            "specialization":   specialization,
            "bio":              "",
            "clients":          [],
            "avatar_url":       "",
            "invite_code":      "",
            "city":             city,
            "state":            state,
            "country":          country,
            "subscription":     {"plan": "free", "status": "inactive", "expires": None},
            "created_at":       datetime.utcnow(),
        }
        result = current_app.config["DB"].trainers.insert_one(trainer_doc)
        trainer_doc["_id"] = result.inserted_id
        login_user(Trainer(trainer_doc))
        flash("Welcome to AURON!", "success")
        return redirect(url_for("trainer.dashboard"))

    return render_template("signup_trainer.html")


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("auth.index"))


# ── Legal pages ───────────────────────────────────────────────────────────────

@auth_bp.route("/terms")
def terms():
    return render_template("legal/terms.html")

@auth_bp.route("/privacy")
def privacy():
    return render_template("legal/privacy.html")

@auth_bp.route("/refund")
def refund():
    return render_template("legal/refund.html")


# ── Public Profiles ───────────────────────────────────────────────────────────

@auth_bp.route("/profile/user/<user_id>")
@login_required
def public_user_profile(user_id):
    from bson import ObjectId
    from helpers import calculate_auron_score, get_streak, get_rank_label
    try:
        u = current_app.config["DB"].users.find_one({"_id": ObjectId(user_id)})
    except Exception:
        u = None
    if not u:
        flash("Profile not found.", "error")
        return redirect(url_for("auth.index"))

    score  = calculate_auron_score(str(u["_id"]))
    streak = get_streak(str(u["_id"]))
    rank   = get_rank_label(score)
    recent_workouts = list(current_app.config["DB"].workouts.find({"user_id": u["_id"]}).sort("date", -1).limit(5))
    progress = list(current_app.config["DB"].progress_entries.find({"user_id": u["_id"]}).sort("date", -1).limit(3))
    is_own = str(u["_id"]) == current_user.id

    # Weekly scores for mini chart
    from datetime import date, timedelta
    today   = date.today()
    weekly  = []
    for i in range(6, -1, -1):
        d   = (today - timedelta(days=i)).strftime("%Y-%m-%d")
        rec = current_app.config["DB"].scores.find_one({"user_id": u["_id"], "date": d})
        weekly.append({"date": d[-5:], "score": rec["score"] if rec else 0})

    return render_template("public/user_profile.html",
                           profile=u, score=score, streak=streak,
                           rank=rank, weekly=weekly,
                           recent_workouts=recent_workouts,
                           progress=progress, is_own=is_own)


@auth_bp.route("/profile/trainer/<trainer_id>")
@login_required
def public_trainer_profile(trainer_id):
    from bson import ObjectId
    from helpers import calculate_auron_score, get_rank_label
    try:
        t = current_app.config["DB"].trainers.find_one({"_id": ObjectId(trainer_id)})
    except Exception:
        t = None
    if not t:
        flash("Profile not found.", "error")
        return redirect(url_for("auth.index"))

    client_ids = [ObjectId(c) for c in t.get("clients", [])]
    clients    = list(current_app.config["DB"].users.find({"_id": {"$in": client_ids}},
                                    {"username": 1, "avatar_url": 1}))
    scores     = [calculate_auron_score(str(c["_id"])) for c in clients]
    avg_score  = round(sum(scores) / len(scores)) if scores else 0
    is_own     = str(t["_id"]) == current_user.id

    return render_template("public/trainer_profile.html",
                           profile=t, clients=clients, avg_score=avg_score,
                           client_count=len(clients), is_own=is_own)