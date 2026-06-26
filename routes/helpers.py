from datetime import datetime, date, timedelta
from bson import ObjectId
from app import db


def calculate_auron_score(user_id, target_date=None):
    """
    AURON Score breakdown (0-100):
    Workout  : 30 pts
    Protein  : 20 pts
    Sleep    : 20 pts
    Steps    : 15 pts
    Water    : 15 pts
    """
    if target_date is None:
        target_date = date.today()

    uid = ObjectId(user_id)
    date_str = target_date.strftime("%Y-%m-%d")

    score = 0

    # --- Workout (30 pts) ---
    workout = db.workouts.find_one({"user_id": uid, "date": date_str})
    if workout:
        score += 30

    # --- Protein (20 pts) ---
    user = db.users.find_one({"_id": uid})
    protein_goal = user.get("protein_goal", 150) if user else 150
    nutrition = db.nutrition_logs.find_one({"user_id": uid, "date": date_str})
    if nutrition:
        logged_protein = nutrition.get("protein_grams", 0)
        ratio = min(logged_protein / max(protein_goal, 1), 1.0)
        score += round(ratio * 20)

    # --- Sleep (20 pts) ---
    sleep_goal = user.get("sleep_goal", 7) if user else 7
    sleep = db.sleep_logs.find_one({"user_id": uid, "date": date_str})
    if sleep:
        logged_sleep = sleep.get("hours", 0)
        ratio = min(logged_sleep / max(sleep_goal, 1), 1.0)
        score += round(ratio * 20)

    # --- Steps (15 pts) ---
    steps_goal = user.get("steps_goal", 8000) if user else 8000
    steps = db.step_logs.find_one({"user_id": uid, "date": date_str})
    if steps:
        logged_steps = steps.get("steps", 0)
        ratio = min(logged_steps / max(steps_goal, 1), 1.0)
        score += round(ratio * 15)

    # --- Water (15 pts) ---
    water_goal = user.get("water_goal", 2500) if user else 2500
    water = db.water_logs.find_one({"user_id": uid, "date": date_str})
    if water:
        logged_water = water.get("amount_ml", 0)
        ratio = min(logged_water / max(water_goal, 1), 1.0)
        score += round(ratio * 15)

    return min(score, 100)


def save_daily_score(user_id, target_date=None):
    if target_date is None:
        target_date = date.today()

    score = calculate_auron_score(user_id, target_date)
    uid = ObjectId(user_id)
    date_str = target_date.strftime("%Y-%m-%d")

    db.scores.update_one(
        {"user_id": uid, "date": date_str},
        {"$set": {"score": score, "updated_at": datetime.utcnow()}},
        upsert=True,
    )
    return score


def get_streak(user_id, threshold=80):
    uid = ObjectId(user_id)
    today = date.today()
    current_streak = 0
    longest_streak = 0
    temp_streak = 0
    check_date = today

    # Look back up to 365 days
    for _ in range(365):
        date_str = check_date.strftime("%Y-%m-%d")
        record = db.scores.find_one({"user_id": uid, "date": date_str})
        if record and record.get("score", 0) >= threshold:
            temp_streak += 1
            longest_streak = max(longest_streak, temp_streak)
            if check_date == today or current_streak > 0:
                current_streak = temp_streak
        else:
            if check_date == today:
                # Today not yet done, still count yesterday's streak
                check_date -= timedelta(days=1)
                continue
            temp_streak = 0
        check_date -= timedelta(days=1)

    return {"current": current_streak, "longest": longest_streak}


def get_today_logs(user_id):
    uid = ObjectId(user_id)
    date_str = date.today().strftime("%Y-%m-%d")
    user = db.users.find_one({"_id": uid}) or {}

    workout = db.workouts.find_one({"user_id": uid, "date": date_str})
    nutrition = db.nutrition_logs.find_one({"user_id": uid, "date": date_str}) or {}
    water = db.water_logs.find_one({"user_id": uid, "date": date_str}) or {}
    sleep = db.sleep_logs.find_one({"user_id": uid, "date": date_str}) or {}
    steps = db.step_logs.find_one({"user_id": uid, "date": date_str}) or {}

    return {
        "workout": workout,
        "protein": nutrition.get("protein_grams", 0),
        "protein_goal": user.get("protein_goal", 150),
        "water": water.get("amount_ml", 0),
        "water_goal": user.get("water_goal", 2500),
        "sleep": sleep.get("hours", 0),
        "sleep_goal": user.get("sleep_goal", 7),
        "steps": steps.get("steps", 0),
        "steps_goal": user.get("steps_goal", 8000),
    }


def get_rank_label(score):
    if score >= 90:
        return "Elite"
    elif score >= 75:
        return "Gold"
    elif score >= 60:
        return "Silver"
    elif score >= 40:
        return "Bronze"
    else:
        return "Iron"


def get_compliance_for_client(user_id, days=7):
    uid = ObjectId(user_id)
    today = date.today()
    results = {"workout": 0, "protein": 0, "water": 0, "sleep": 0, "steps": 0}
    counts = {k: 0 for k in results}

    for i in range(days):
        d = (today - timedelta(days=i)).strftime("%Y-%m-%d")
        if db.workouts.find_one({"user_id": uid, "date": d}):
            results["workout"] += 1
        if db.nutrition_logs.find_one({"user_id": uid, "date": d}):
            results["protein"] += 1
        if db.water_logs.find_one({"user_id": uid, "date": d}):
            results["water"] += 1
        if db.sleep_logs.find_one({"user_id": uid, "date": d}):
            results["sleep"] += 1
        if db.step_logs.find_one({"user_id": uid, "date": d}):
            results["steps"] += 1

    return {k: round((v / days) * 100) for k, v in results.items()}