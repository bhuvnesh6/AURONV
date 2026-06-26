print("USER_LOADER FILE IMPORTED")

from extensions import login_manager
import app

from routes.models import User, Trainer
from bson import ObjectId

print("REGISTERING USER LOADER")


@login_manager.user_loader
def load_user(user_id_str):

    try:
        prefix, oid_str = user_id_str.split(":", 1)
        oid = ObjectId(oid_str)
    except Exception:
        return None

    if prefix == "trainer":
        doc = app.db.trainers.find_one({"_id": oid})
        return Trainer(doc) if doc else None

    doc = app.db.users.find_one({"_id": oid})
    return User(doc) if doc else Noneclear
