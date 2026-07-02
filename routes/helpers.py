from datetime import datetime, date, timedelta
from bson import ObjectId
from app import db
import requests as http_requests


# ─────────────────────────────────────────────
#  AURON SCORE
# ─────────────────────────────────────────────

def calculate_auron_score(user_id, target_date=None):
    if target_date is None:
        target_date = date.today()

    uid      = ObjectId(user_id)
    date_str = target_date.strftime("%Y-%m-%d")
    score    = 0

    workout = db.workouts.find_one({"user_id": uid, "date": date_str})
    if workout:
        score += 30

    user         = db.users.find_one({"_id": uid}) or {}
    protein_goal = user.get("protein_goal", 150)
    nutrition    = db.nutrition_logs.find_one({"user_id": uid, "date": date_str})
    if nutrition:
        ratio  = min(nutrition.get("protein_grams", 0) / max(protein_goal, 1), 1.0)
        score += round(ratio * 20)

    sleep_goal = user.get("sleep_goal", 7)
    sleep      = db.sleep_logs.find_one({"user_id": uid, "date": date_str})
    if sleep:
        ratio  = min(sleep.get("hours", 0) / max(sleep_goal, 1), 1.0)
        score += round(ratio * 20)

    steps_goal = user.get("steps_goal", 8000)
    steps      = db.step_logs.find_one({"user_id": uid, "date": date_str})
    if steps:
        ratio  = min(steps.get("steps", 0) / max(steps_goal, 1), 1.0)
        score += round(ratio * 15)

    water_goal = user.get("water_goal", 2500)
    water      = db.water_logs.find_one({"user_id": uid, "date": date_str})
    if water:
        ratio  = min(water.get("amount_ml", 0) / max(water_goal, 1), 1.0)
        score += round(ratio * 15)

    return min(score, 100)


def save_daily_score(user_id, target_date=None):
    if target_date is None:
        target_date = date.today()
    score    = calculate_auron_score(user_id, target_date)
    uid      = ObjectId(user_id)
    date_str = target_date.strftime("%Y-%m-%d")

    user = db.users.find_one({"_id": uid}) or {}
    db.scores.update_one(
        {"user_id": uid, "date": date_str},
        {"$set": {
            "score":      score,
            "updated_at": datetime.utcnow(),
            "city":       user.get("city", ""),
            "state":      user.get("state", ""),
            "country":    user.get("country", ""),
        }},
        upsert=True,
    )
    return score


# ─────────────────────────────────────────────
#  STREAK
# ─────────────────────────────────────────────

def get_streak(user_id, threshold=80):
    uid            = ObjectId(user_id)
    today          = date.today()
    current_streak = 0
    longest_streak = 0
    temp_streak    = 0
    check_date     = today

    for _ in range(365):
        date_str = check_date.strftime("%Y-%m-%d")
        record   = db.scores.find_one({"user_id": uid, "date": date_str})
        if record and record.get("score", 0) >= threshold:
            temp_streak   += 1
            longest_streak = max(longest_streak, temp_streak)
            if check_date == today or current_streak > 0:
                current_streak = temp_streak
        else:
            if check_date == today:
                check_date -= timedelta(days=1)
                continue
            temp_streak = 0
        check_date -= timedelta(days=1)

    return {"current": current_streak, "longest": longest_streak}


# ─────────────────────────────────────────────
#  TODAY LOGS
# ─────────────────────────────────────────────

def get_today_logs(user_id):
    uid      = ObjectId(user_id)
    date_str = date.today().strftime("%Y-%m-%d")
    user     = db.users.find_one({"_id": uid}) or {}

    workout   = db.workouts.find_one({"user_id": uid, "date": date_str})
    nutrition = db.nutrition_logs.find_one({"user_id": uid, "date": date_str}) or {}
    water     = db.water_logs.find_one({"user_id": uid, "date": date_str})     or {}
    sleep     = db.sleep_logs.find_one({"user_id": uid, "date": date_str})     or {}
    steps     = db.step_logs.find_one({"user_id": uid, "date": date_str})      or {}

    return {
        "workout":      workout,
        "protein":      nutrition.get("protein_grams", 0),
        "protein_goal": user.get("protein_goal", 150),
        "water":        water.get("amount_ml", 0),
        "water_goal":   user.get("water_goal", 2500),
        "sleep":        sleep.get("hours", 0),
        "sleep_goal":   user.get("sleep_goal", 7),
        "steps":        steps.get("steps", 0),
        "steps_goal":   user.get("steps_goal", 8000),
    }


# ─────────────────────────────────────────────
#  RANK / COMPLIANCE
# ─────────────────────────────────────────────

def get_rank_label(score):
    if score >= 90: return "Elite"
    if score >= 75: return "Gold"
    if score >= 60: return "Silver"
    if score >= 40: return "Bronze"
    return "Iron"


def get_compliance_for_client(user_id, days=7):
    uid     = ObjectId(user_id)
    today   = date.today()
    results = {"workout": 0, "protein": 0, "water": 0, "sleep": 0, "steps": 0}

    for i in range(days):
        d = (today - timedelta(days=i)).strftime("%Y-%m-%d")
        if db.workouts.find_one({"user_id": uid, "date": d}):       results["workout"] += 1
        if db.nutrition_logs.find_one({"user_id": uid, "date": d}): results["protein"] += 1
        if db.water_logs.find_one({"user_id": uid, "date": d}):     results["water"]   += 1
        if db.sleep_logs.find_one({"user_id": uid, "date": d}):     results["sleep"]   += 1
        if db.step_logs.find_one({"user_id": uid, "date": d}):      results["steps"]   += 1

    return {k: round((v / days) * 100) for k, v in results.items()}


# ─────────────────────────────────────────────
#  GEO-IP  (free, no key required)
# ─────────────────────────────────────────────

def get_geo_from_ip(ip: str) -> dict:
    """Return {city, state, country, country_code} from visitor IP.
    Falls back to empty strings on any error."""
    try:
        if ip in ("127.0.0.1", "::1", "localhost"):
            return {"city": "", "state": "", "country": "", "country_code": ""}
        r = http_requests.get(f"http://ip-api.com/json/{ip}?fields=country,regionName,city,countryCode",
                              timeout=2)
        if r.status_code == 200:
            d = r.json()
            return {
                "city":         d.get("city", ""),
                "state":        d.get("regionName", ""),
                "country":      d.get("country", ""),
                "country_code": d.get("countryCode", ""),
            }
    except Exception:
        pass
    return {"city": "", "state": "", "country": "", "country_code": ""}


def get_client_ip(request) -> str:
    xff = request.headers.get("X-Forwarded-For", "")
    if xff:
        return xff.split(",")[0].strip()
    return request.remote_addr or ""