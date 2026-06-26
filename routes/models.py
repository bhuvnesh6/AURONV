from flask_login import UserMixin
from app import db
from bson import ObjectId
from datetime import datetime


class User(UserMixin):
    def __init__(self, user_doc):
        self._doc = user_doc

    def get_id(self):
        return f"user:{str(self._doc['_id'])}"

    @property
    def id(self):
        return str(self._doc["_id"])

    @property
    def username(self):
        return self._doc.get("username")

    @property
    def email(self):
        return self._doc.get("email")

    @property
    def role(self):
        return "user"

    @property
    def doc(self):
        return self._doc

    @staticmethod
    def get_by_id(user_id):
        doc = db.users.find_one({"_id": ObjectId(user_id)})
        return User(doc) if doc else None

    @staticmethod
    def get_by_email(email):
        doc = db.users.find_one({"email": email})
        return User(doc) if doc else None

    @staticmethod
    def get_by_username(username):
        doc = db.users.find_one({"username": username})
        return User(doc) if doc else None


class Trainer(UserMixin):
    def __init__(self, trainer_doc):
        self._doc = trainer_doc

    def get_id(self):
        return f"trainer:{str(self._doc['_id'])}"

    @property
    def id(self):
        return str(self._doc["_id"])

    @property
    def username(self):
        return self._doc.get("username")

    @property
    def email(self):
        return self._doc.get("email")

    @property
    def role(self):
        return "trainer"

    @property
    def doc(self):
        return self._doc

    @staticmethod
    def get_by_id(trainer_id):
        doc = db.trainers.find_one({"_id": ObjectId(trainer_id)})
        return Trainer(doc) if doc else None

    @staticmethod
    def get_by_email(email):
        doc = db.trainers.find_one({"email": email})
        return Trainer(doc) if doc else None

    @staticmethod
    def get_by_username(username):
        doc = db.trainers.find_one({"username": username})
        return Trainer(doc) if doc else None