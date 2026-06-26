from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from extensions import bcrypt
from routes.models import User, Trainer
from datetime import datetime
import app

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/")
def index():
    return render_template("landing.html")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():

    if current_user.is_authenticated:
        return redirect(url_for("auth.index"))

    if request.method == "POST":

        role = request.form.get("role")
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        remember = bool(request.form.get("remember_me"))

        if role == "trainer":
            doc = app.db.trainers.find_one({"email": email})
            person = Trainer(doc) if doc else None
        else:
            doc = app.db.users.find_one({"email": email})
            person = User(doc) if doc else None

        if person and bcrypt.check_password_hash(
            doc["password_hash"],
            password
        ):
            login_user(person, remember=remember)

            next_page = request.args.get("next")

            if role == "trainer":
                return redirect(
                    next_page or url_for("trainer.dashboard")
                )

            return redirect(
                next_page or url_for("user.dashboard")
            )

        flash("Invalid email or password.", "error")

    return render_template("login.html")


@auth_bp.route("/signup/user", methods=["GET", "POST"])
def signup_user():

    if request.method == "POST":

        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip().lower()
        phone = request.form.get("phone", "").strip()

        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")

        goal = request.form.get("goal", "")
        weight = request.form.get("weight", "")
        height = request.form.get("height", "")
        age = request.form.get("age", "")
        gender = request.form.get("gender", "")

        if password != confirm:
            flash("Passwords do not match.", "error")
            return render_template("signup_user.html")

        existing = app.db.users.find_one({
            "$or": [
                {"email": email},
                {"username": username}
            ]
        })

        if existing:
            flash("Email or username already registered.", "error")
            return render_template("signup_user.html")

        hashed = bcrypt.generate_password_hash(
            password
        ).decode("utf-8")

        user_doc = {
            "username": username,
            "email": email,
            "phone": phone,
            "password_hash": hashed,
            "goal": goal,
            "weight": weight,
            "height": height,
            "age": age,
            "gender": gender,
            "protein_goal": 150,
            "water_goal": 2500,
            "sleep_goal": 7,
            "steps_goal": 8000,
            "avatar_url": "",
            "created_at": datetime.utcnow()
        }

        result = app.db.users.insert_one(user_doc)

        user_doc["_id"] = result.inserted_id

        user_obj = User(user_doc)

        login_user(user_obj)

        flash("Welcome to AURON!", "success")

        return redirect(url_for("user.dashboard"))

    return render_template("signup_user.html")


@auth_bp.route("/signup/trainer", methods=["GET", "POST"])
def signup_trainer():

    if request.method == "POST":

        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip().lower()
        phone = request.form.get("phone", "").strip()

        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")

        business_name = request.form.get("business_name", "")
        instagram = request.form.get("instagram", "")
        years_exp = request.form.get("years_experience", "")
        specialization = request.form.get("specialization", "")

        if password != confirm:
            flash("Passwords do not match.", "error")
            return render_template("signup_trainer.html")

        existing = app.db.trainers.find_one({
            "$or": [
                {"email": email},
                {"username": username}
            ]
        })

        if existing:
            flash("Email or username already registered.", "error")
            return render_template("signup_trainer.html")

        hashed = bcrypt.generate_password_hash(
            password
        ).decode("utf-8")

        trainer_doc = {
            "username": username,
            "email": email,
            "phone": phone,
            "password_hash": hashed,
            "business_name": business_name,
            "instagram": instagram,
            "years_experience": years_exp,
            "specialization": specialization,
            "clients": [],
            "avatar_url": "",
            "created_at": datetime.utcnow()
        }

        result = app.db.trainers.insert_one(
            trainer_doc
        )

        trainer_doc["_id"] = result.inserted_id

        trainer_obj = Trainer(trainer_doc)

        login_user(trainer_obj)

        flash("Welcome to AURON!", "success")

        return redirect(
            url_for("trainer.dashboard")
        )

    return render_template("signup_trainer.html")


@auth_bp.route("/logout")
@login_required
def logout():

    logout_user()

    return redirect(
        url_for("auth.index")
    )