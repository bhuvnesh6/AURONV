"""
AURON Seed Script
=================
Run daily via cron. On first run: creates 100 users + 6 trainers.
Every run: logs realistic daily activities for all seed accounts.

Usage:
    python seed_data.py

Cron (daily at 2am server time):
    0 2 * * * cd /app && python seed_data.py >> /var/log/auron_seed.log 2>&1
"""

import os, csv, json, random, hashlib
from datetime import datetime, date, timedelta
from dotenv import load_dotenv
from pymongo import MongoClient
from bson import ObjectId

load_dotenv()

# ── Config ────────────────────────────────────────────────────────────────────

MONGO_URI    = os.environ.get("MONGO_URI")
SEED_FILE    = "seed_state.json"    # tracks created user/trainer IDs
PROFILES_CSV = "seed_profiles.csv"  # gender,img_url

CITIES = [
    {"city": "San Francisco", "state": "California",  "country": "United States"},
    {"city": "Seattle",       "state": "Washington",  "country": "United States"},
    {"city": "Los Angeles",   "state": "California",  "country": "United States"},
    {"city": "Vancouver",     "state": "British Columbia", "country": "Canada"},
    {"city": "Victoria",      "state": "British Columbia", "country": "Canada"},
    {"city": "Tofino",        "state": "British Columbia", "country": "Canada"},
]

MALE_FIRST   = ["James","Liam","Noah","Oliver","Ethan","Mason","Logan","Lucas","Aiden","Jackson",
                 "Sebastian","Carter","Owen","Wyatt","Dylan","Ryan","Nathan","Aaron","Tyler","Hunter",
                 "Brandon","Justin","Kevin","Derek","Marcus","Trevor","Colin","Gavin","Blake","Chase",
                 "Connor","Austin","Jordan","Cameron","Kyle","Travis","Shane","Cody","Alex","Brett"]
FEMALE_FIRST = ["Emma","Sophia","Olivia","Ava","Isabella","Mia","Charlotte","Amelia","Harper","Evelyn",
                 "Abigail","Emily","Elizabeth","Sofia","Madison","Avery","Ella","Scarlett","Grace","Chloe",
                 "Victoria","Riley","Aria","Lily","Aubrey","Zoey","Penelope","Layla","Nora","Hannah",
                 "Lillian","Addison","Aubrey","Ellie","Stella","Natalie","Zoe","Leah","Hazel","Violet"]
LAST_NAMES   = ["Smith","Johnson","Williams","Brown","Jones","Garcia","Miller","Davis","Wilson","Moore",
                 "Taylor","Anderson","Thomas","Jackson","White","Harris","Martin","Thompson","Young","King",
                 "Scott","Green","Adams","Baker","Nelson","Carter","Mitchell","Roberts","Turner","Phillips"]

WORKOUT_NAMES = ["Push Day","Pull Day","Leg Day","Upper Body","Lower Body","Full Body","Chest & Triceps",
                 "Back & Biceps","Shoulders","Cardio","HIIT","CrossFit WOD","Deadlift Session","Squat Day"]
EXERCISE_POOL = [
    {"name":"Bench Press","weight_range":(60,140),"sets":4,"reps":8},
    {"name":"Squat",      "weight_range":(80,180),"sets":4,"reps":6},
    {"name":"Deadlift",   "weight_range":(100,220),"sets":3,"reps":5},
    {"name":"Pull Up",    "weight_range":(0,30),  "sets":4,"reps":10},
    {"name":"OHP",        "weight_range":(40,100),"sets":4,"reps":8},
    {"name":"Row",        "weight_range":(60,120),"sets":3,"reps":10},
    {"name":"Curl",       "weight_range":(15,40), "sets":3,"reps":12},
    {"name":"Dip",        "weight_range":(0,40),  "sets":3,"reps":12},
    {"name":"Leg Press",  "weight_range":(120,300),"sets":4,"reps":10},
    {"name":"Lat Pulldown","weight_range":(50,100),"sets":3,"reps":12},
]

# ── Connect ───────────────────────────────────────────────────────────────────

client = MongoClient(MONGO_URI)
db     = client.auron
print(f"[AURON SEED] Connected — {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}")


# ── Load CSV ──────────────────────────────────────────────────────────────────

def load_profiles():
    male_imgs, female_imgs = [], []
    with open(PROFILES_CSV, newline="") as f:
        for row in csv.DictReader(f):
            if row["gender"].strip() == "male":
                male_imgs.append(row["img_url"].strip())
            else:
                female_imgs.append(row["img_url"].strip())
    return male_imgs, female_imgs


# ── Seed state ────────────────────────────────────────────────────────────────

def load_state():
    if os.path.exists(SEED_FILE):
        with open(SEED_FILE) as f:
            return json.load(f)
    return {"users": [], "trainers": [], "created": False}


def save_state(state):
    with open(SEED_FILE, "w") as f:
        json.dump(state, f, indent=2)


# ── Helpers ───────────────────────────────────────────────────────────────────

def rand_username(first, last):
    suffix = random.randint(10, 999)
    return f"{first.lower()}{last.lower()}{suffix}"


def fake_password_hash():
    # bcrypt hash of "Password123!" — all seed accounts share same pass
    from flask_bcrypt import Bcrypt
    b = Bcrypt()
    return b.generate_password_hash("SeedPass123!").decode("utf-8")


_pw_hash = None
def get_pw_hash():
    global _pw_hash
    if not _pw_hash:
        _pw_hash = fake_password_hash()
    return _pw_hash


def pick_name(gender):
    first = random.choice(MALE_FIRST if gender == "male" else FEMALE_FIRST)
    last  = random.choice(LAST_NAMES)
    return first, last


# ── Create trainers ───────────────────────────────────────────────────────────

TRAINER_SPECS = [
    {"gender":"male",   "specialization":"strength",     "business":"Iron Peak Training"},
    {"gender":"male",   "specialization":"bodybuilding",  "business":"Mass Blueprint"},
    {"gender":"male",   "specialization":"crossfit",      "business":"CrossCore Athletics"},
    {"gender":"male",   "specialization":"sports",        "business":"Elite Performance Hub"},
    {"gender":"female", "specialization":"weight_loss",   "business":"Lean Life Coaching"},
    {"gender":"female", "specialization":"general",       "business":"FitFlow Studio"},
]


def create_trainers(male_imgs, female_imgs, state):
    trainer_ids = []
    pw = get_pw_hash()

    for i, spec in enumerate(TRAINER_SPECS):
        gender   = spec["gender"]
        first, last = pick_name(gender)
        username = rand_username(first, last)
        email    = f"{username}@seedtrainer.auron"
        avatar   = (random.choice(male_imgs[-4:]) if gender == "male"
                    else random.choice(female_imgs[-2:]))
        city_info = random.choice(CITIES)
        years_exp = str(random.randint(3, 15))
        invite_code = hashlib.md5(f"trainer{i}{datetime.utcnow()}".encode()).hexdigest()[:10]

        doc = {
            "type":             "trainer",
            "username":         username,
            "email":            email,
            "phone":            "",
            "password_hash":    pw,
            "business_name":    spec["business"],
            "instagram":        f"@{username}",
            "years_experience": years_exp,
            "specialization":   spec["specialization"],
            "bio":              f"Professional coach with {years_exp} years experience.",
            "clients":          [],
            "avatar_url":       avatar,
            "invite_code":      invite_code,
            "city":             city_info["city"],
            "state":            city_info["state"],
            "country":          city_info["country"],
            "gender":           gender,
            "is_seed":          True,
            "subscription":     {"plan": "pro", "status": "active"},
            "created_at":       datetime.utcnow() - timedelta(days=random.randint(30, 180)),
        }
        result = db.trainers.insert_one(doc)
        tid = str(result.inserted_id)
        trainer_ids.append(tid)
        print(f"  ✓ Trainer: {username} ({spec['business']})")

    state["trainers"] = trainer_ids
    return trainer_ids


# ── Create users ──────────────────────────────────────────────────────────────

def create_users(male_imgs, female_imgs, trainer_ids, state):
    user_ids = []
    pw       = get_pw_hash()

    # 55 male, 45 female
    genders = ["male"] * 55 + ["female"] * 45
    random.shuffle(genders)

    male_pool   = male_imgs[:55]
    female_pool = female_imgs[:45]
    male_idx, female_idx = 0, 0

    goals = ["lose_fat", "build_muscle", "maintain", "performance"]

    for i, gender in enumerate(genders):
        first, last = pick_name(gender)
        username    = rand_username(first, last)
        email       = f"{username}@seeduser.auron"

        if gender == "male":
            avatar = male_pool[male_idx % len(male_pool)]
            male_idx += 1
        else:
            avatar = female_pool[female_idx % len(female_pool)]
            female_idx += 1

        city_info   = random.choice(CITIES)
        trainer_id  = random.choice(trainer_ids)
        created_ago = random.randint(5, 60)

        doc = {
            "type":          "user",
            "username":      username,
            "email":         email,
            "phone":         "",
            "password_hash": pw,
            "goal":          random.choice(goals),
            "weight":        str(random.randint(55, 110)),
            "height":        str(random.randint(160, 195)),
            "age":           str(random.randint(18, 45)),
            "gender":        gender,
            "city":          city_info["city"],
            "state":         city_info["state"],
            "country":       city_info["country"],
            "protein_goal":  random.choice([130, 150, 170, 200]),
            "water_goal":    random.choice([2000, 2500, 3000]),
            "sleep_goal":    random.choice([7, 7.5, 8]),
            "steps_goal":    random.choice([7000, 8000, 10000]),
            "avatar_url":    avatar,
            "trainer_id":    trainer_id,
            "is_seed":       True,
            "subscription":  {"plan": "pro", "status": "active"},
            "created_at":    datetime.utcnow() - timedelta(days=created_ago),
        }
        result = db.users.insert_one(doc)
        uid = str(result.inserted_id)
        user_ids.append({"id": uid, "trainer_id": trainer_id})

        # Add to trainer's clients list
        db.trainers.update_one(
            {"_id": ObjectId(trainer_id)},
            {"$addToSet": {"clients": uid}}
        )

    state["users"] = user_ids
    print(f"  ✓ Created {len(user_ids)} users, distributed across {len(trainer_ids)} trainers")
    return user_ids


# ── Daily log activities ──────────────────────────────────────────────────────

def log_day_for_user(uid_str, user_doc, target_date):
    """Log realistic activities for one user on a given date."""
    uid      = ObjectId(uid_str)
    date_str = target_date.strftime("%Y-%m-%d")

    # Decide which activities happen today (realistic: not 100% compliance)
    does_workout  = random.random() < 0.75
    does_nutrition= random.random() < 0.80
    does_water    = random.random() < 0.85
    does_sleep    = random.random() < 0.90
    does_steps    = random.random() < 0.80

    protein_goal = user_doc.get("protein_goal", 150)
    water_goal   = user_doc.get("water_goal",   2500)
    sleep_goal   = user_doc.get("sleep_goal",   7)
    steps_goal   = user_doc.get("steps_goal",   8000)

    # Workout
    if does_workout and not db.workouts.find_one({"user_id": uid, "date": date_str}):
        exercises = random.sample(EXERCISE_POOL, random.randint(3, 6))
        ex_docs   = []
        total_vol = 0
        for ex in exercises:
            w   = random.randint(*ex["weight_range"])
            s   = ex["sets"]
            r   = ex["reps"] + random.randint(-2, 2)
            total_vol += s * r * w
            ex_docs.append({"name": ex["name"], "sets": s, "reps": r,
                            "weight_kg": w, "rest_sec": random.choice([60,90,120])})
        db.workouts.insert_one({
            "user_id":      uid,
            "date":         date_str,
            "name":         random.choice(WORKOUT_NAMES),
            "duration_min": random.randint(35, 90),
            "notes":        "",
            "exercises":    ex_docs,
            "total_volume": total_vol,
            "created_at":   datetime.combine(target_date, datetime.min.time()),
        })

    # Nutrition
    if does_nutrition and not db.nutrition_logs.find_one({"user_id": uid, "date": date_str}):
        logged_protein  = protein_goal * random.uniform(0.7, 1.1)
        logged_calories = random.randint(1800, 3200)
        db.nutrition_logs.insert_one({
            "user_id":       uid,
            "date":          date_str,
            "protein_grams": round(logged_protein, 1),
            "calories":      logged_calories,
            "meals":         [],
            "created_at":    datetime.combine(target_date, datetime.min.time()),
        })

    # Water
    if does_water and not db.water_logs.find_one({"user_id": uid, "date": date_str}):
        logged_water = water_goal * random.uniform(0.6, 1.1)
        db.water_logs.insert_one({
            "user_id":   uid,
            "date":      date_str,
            "amount_ml": int(logged_water),
            "created_at": datetime.combine(target_date, datetime.min.time()),
        })

    # Sleep
    if does_sleep and not db.sleep_logs.find_one({"user_id": uid, "date": date_str}):
        logged_sleep = sleep_goal * random.uniform(0.7, 1.05)
        db.sleep_logs.insert_one({
            "user_id":    uid,
            "date":       date_str,
            "hours":      round(logged_sleep, 1),
            "quality":    random.choice(["great","good","good","fair"]),
            "created_at": datetime.combine(target_date, datetime.min.time()),
        })

    # Steps
    if does_steps and not db.step_logs.find_one({"user_id": uid, "date": date_str}):
        logged_steps = int(steps_goal * random.uniform(0.5, 1.3))
        db.step_logs.insert_one({
            "user_id":    uid,
            "date":       date_str,
            "steps":      logged_steps,
            "created_at": datetime.combine(target_date, datetime.min.time()),
        })

    # Calculate and save score
    _save_score(uid, uid_str, date_str, user_doc,
                does_workout, does_nutrition, does_water, does_sleep, does_steps)


def _save_score(uid, uid_str, date_str, user_doc,
                has_workout, has_nutrition, has_water, has_sleep, has_steps):
    score = 0
    if has_workout:
        score += 30

    protein_goal = user_doc.get("protein_goal", 150)
    if has_nutrition:
        n = db.nutrition_logs.find_one({"user_id": uid, "date": date_str}) or {}
        ratio  = min(n.get("protein_grams", 0) / max(protein_goal, 1), 1.0)
        score += round(ratio * 20)

    sleep_goal = user_doc.get("sleep_goal", 7)
    if has_sleep:
        s = db.sleep_logs.find_one({"user_id": uid, "date": date_str}) or {}
        ratio  = min(s.get("hours", 0) / max(sleep_goal, 1), 1.0)
        score += round(ratio * 20)

    steps_goal = user_doc.get("steps_goal", 8000)
    if has_steps:
        st = db.step_logs.find_one({"user_id": uid, "date": date_str}) or {}
        ratio   = min(st.get("steps", 0) / max(steps_goal, 1), 1.0)
        score  += round(ratio * 15)

    water_goal = user_doc.get("water_goal", 2500)
    if has_water:
        w = db.water_logs.find_one({"user_id": uid, "date": date_str}) or {}
        ratio  = min(w.get("amount_ml", 0) / max(water_goal, 1), 1.0)
        score += round(ratio * 15)

    score = min(score, 100)
    db.scores.update_one(
        {"user_id": uid, "date": date_str},
        {"$set": {
            "score":      score,
            "city":       user_doc.get("city", ""),
            "state":      user_doc.get("state", ""),
            "country":    user_doc.get("country", ""),
            "updated_at": datetime.utcnow(),
        }},
        upsert=True,
    )


# ── Backfill historical logs ──────────────────────────────────────────────────

def backfill_history(user_ids):
    """On first run: fill last 14 days of history so leaderboards aren't empty."""
    today = date.today()
    print(f"  Backfilling 14 days of history for {len(user_ids)} users…")
    for entry in user_ids:
        uid_str  = entry["id"]
        user_doc = db.users.find_one({"_id": ObjectId(uid_str)}) or {}
        for days_ago in range(14, 0, -1):
            target = today - timedelta(days=days_ago)
            log_day_for_user(uid_str, user_doc, target)
    print("  ✓ Backfill complete")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    state = load_state()

    male_imgs, female_imgs = load_profiles()
    print(f"[AURON SEED] Profiles loaded — {len(male_imgs)}M / {len(female_imgs)}F")

    if not state.get("created"):
        print("[AURON SEED] First run — creating seed accounts…")
        trainer_ids = create_trainers(male_imgs, female_imgs, state)
        user_ids    = create_users(male_imgs, female_imgs, trainer_ids, state)
        state["created"] = True
        save_state(state)
        backfill_history(user_ids)
        print("[AURON SEED] ✓ Seed accounts created and history backfilled")
    else:
        print("[AURON SEED] Seed accounts exist — logging today's activities…")

    # Daily log for today
    today    = date.today()
    user_ids = state.get("users", [])
    logged   = 0

    for entry in user_ids:
        uid_str  = entry["id"]
        user_doc = db.users.find_one({"_id": ObjectId(uid_str)}) or {}
        if not user_doc:
            continue
        log_day_for_user(uid_str, user_doc, today)
        logged += 1

    print(f"[AURON SEED] ✓ Logged today's activities for {logged} seed users")
    print(f"[AURON SEED] Done — {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")


if __name__ == "__main__":
    main()