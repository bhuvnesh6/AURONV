import os
from flask import Flask
from flask_bcrypt import Bcrypt
from flask_login import LoginManager
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

bcrypt        = Bcrypt()
login_manager = LoginManager()


def create_app():
    app = Flask(__name__)
    app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-me")

    # ── MongoDB — connect FIRST ───────────────────────────────────────────────
    mongo_uri = os.environ.get("MONGO_URI")
    if not mongo_uri:
        raise RuntimeError("MONGO_URI is not set in .env")

    mongo_client     = MongoClient(mongo_uri)
    db               = mongo_client.auron
    app.config["DB"] = db  # store on app so all blueprints get it via current_app

    try:
        db.command("ping")
        print("[AURON] MongoDB connected ✓")
    except Exception as e:
        raise RuntimeError(f"MongoDB connection failed: {e}")

    # ── Extensions ────────────────────────────────────────────────────────────
    bcrypt.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view    = "auth.login"
    login_manager.login_message = "Please log in to access this page."

    # ── User loader ───────────────────────────────────────────────────────────
    from bson   import ObjectId
    from routes.models import User, Trainer

    @login_manager.user_loader
    def load_user(user_id_str):
        try:
            prefix, oid_str = user_id_str.split(":", 1)
            oid = ObjectId(oid_str)
        except Exception:
            return None
        if prefix == "trainer":
            doc = db.trainers.find_one({"_id": oid})
            return Trainer(doc) if doc else None
        doc = db.users.find_one({"_id": oid})
        return User(doc) if doc else None

    # ── Blueprints ────────────────────────────────────────────────────────────
    from routes.auth    import auth_bp
    from routes.user    import user_bp
    from routes.trainer import trainer_bp
    from routes.api     import api_bp
    from routes.billing import billing_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(user_bp,    url_prefix="/user")
    app.register_blueprint(trainer_bp, url_prefix="/trainer")
    app.register_blueprint(api_bp,     url_prefix="/api")
    app.register_blueprint(billing_bp)

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)