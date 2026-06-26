import os
from flask import Flask
from pymongo import MongoClient
from dotenv import load_dotenv

from extensions import bcrypt, login_manager

load_dotenv()

mongo_client = None
db = None


def create_app():
    app = Flask(__name__)
    app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-me")

    # Extensions
    bcrypt.init_app(app)
    login_manager.init_app(app)

    login_manager.login_view = "auth.login"
    login_manager.login_message = "Please log in to access this page."

    # MongoDB
    global mongo_client, db
    mongo_client = MongoClient(os.environ.get("MONGO_URI"))
    db = mongo_client.auron

    # Import user loader AFTER db initialization
    import routes.user_loader

    # Blueprints
    from routes.auth import auth_bp
    from routes.user import user_bp
    from routes.trainer import trainer_bp
    from routes.api import api_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(user_bp, url_prefix="/user")
    app.register_blueprint(trainer_bp, url_prefix="/trainer")
    app.register_blueprint(api_bp, url_prefix="/api")

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True)