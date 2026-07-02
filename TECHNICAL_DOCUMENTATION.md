# AURON.V0 - Technical Documentation

## 📋 Table of Contents
1. [Project Overview](#project-overview)
2. [Architecture & Tech Stack](#architecture--tech-stack)
3. [Project Structure](#project-structure)
4. [Database Schema](#database-schema)
5. [Detailed Route Documentation](#detailed-route-documentation)
6. [Helper Functions & Utilities](#helper-functions--utilities)
7. [Authentication & Security](#authentication--security)
8. [Setup & Installation](#setup--installation)

---

## 🎯 Project Overview

**AURON.V0** is a comprehensive health and fitness tracking application built with Flask. It supports two main user roles:
- **Users (Athletes)**: Track workouts, nutrition, sleep, water intake, and steps
- **Trainers**: Manage clients, create workout programs, send messages, and monitor progress

The application uses a **AURON Score** system (0-100) that combines five key metrics:
- Workouts (30 pts)
- Protein intake (20 pts)
- Sleep (20 pts)
- Steps (15 pts)
- Water intake (15 pts)

---

## 🏗️ Architecture & Tech Stack

### Backend
- **Framework**: Flask 3.0.3
- **Authentication**: Flask-Login 0.6.3, Flask-Bcrypt 1.0.1
- **Database**: MongoDB 4.7.3
- **File Storage**: Cloudinary 1.40.0

### Frontend
- **Templating**: Jinja2 (HTML)
- **Styling**: CSS
- **Client-side**: JavaScript
- **Progressive Web App**: Service Worker support

### Key Dependencies
- `python-dotenv`: Environment variable management
- `email-validator`: Email validation
- `gunicorn`: Production server
- `Werkzeug`: WSGI utilities

---

## 📁 Project Structure

AURON.V0/ ├── app.py # Flask app initialization & blueprints registration ├── extensions.py # Flask extension initialization (bcrypt, login_manager) ├── requirements.txt # Python dependencies ├── .env # Environment variables (SECRET_KEY, MONGO_URI, etc.) ├── routes/ │ ├── init.py │ ├── auth.py # Authentication routes (login, signup, logout) │ ├── user.py # User/athlete dashboard & tracking routes │ ├── trainer.py # Trainer dashboard & client management routes │ ├── api.py # JSON API endpoints for AJAX calls │ ├── helpers.py # Utility functions (scoring, streaks, compliance) │ ├── models.py # User & Trainer classes for Flask-Login │ └── user_loader.py # Flask-Login user loader callback ├── templates/ │ ├── base.html # Base template with navbar & layout │ ├── landing.html # Landing/index page │ ├── login.html # Login form │ ├── signup_user.html # User registration form │ ├── signup_trainer.html # Trainer registration form │ ├── leaderboard_trainer.html # Trainer leaderboard │ ├── user/ │ │ ├── dashboard.html # User main dashboard │ │ ├── workouts.html # Workout logging & history │ │ ├── nutrition.html # Nutrition tracking │ │ ├── profile.html # User profile & settings │ │ ├── timeline.html # Progress photos & metrics │ │ └── leaderboard.html # User leaderboard & rankings │ └── trainer/ │ ├── dashboard.html # Trainer main dashboard │ ├── clients.html # Client list & management │ ├── client_detail.html # Individual client profile │ ├── programs.html # Workout program creation │ ├── messages.html # Message clients │ └── leaderboard.html # Trainer rankings ├── static/ │ ├── js/ # JavaScript files │ ├── css/ # CSS stylesheets │ ├── service-worker.js # PWA service worker │ ├── manifest.json # PWA manifest │ └── offline.html # Offline fallback page └── pycache/ # Python cache directory

Code

---

## 🗄️ Database Schema

### Collections

#### **users**
```javascript
{
  _id: ObjectId,
  username: String (unique),
  email: String (unique),
  phone: String,
  password_hash: String,
  goal: String,           // Fitness goal
  weight: String,         // Current weight
  height: String,         // Height
  age: String,
  gender: String,
  protein_goal: Number (default: 150),
  water_goal: Number (default: 2500),
  sleep_goal: Number (default: 7),
  steps_goal: Number (default: 8000),
  avatar_url: String,     // Cloudinary URL
  created_at: DateTime
}
trainers
JavaScript
{
  _id: ObjectId,
  username: String (unique),
  email: String (unique),
  phone: String,
  password_hash: String,
  business_name: String,
  instagram: String,
  years_experience: String,
  specialization: String,
  clients: [String],      // Array of user IDs (as strings)
  avatar_url: String,
  created_at: DateTime
}
workouts
JavaScript
{
  _id: ObjectId,
  user_id: ObjectId,
  date: String (YYYY-MM-DD),
  name: String,
  duration_min: Number,
  notes: String,
  exercises: [
    {
      name: String,
      sets: Number,
      reps: Number,
      weight_kg: Number,
      rest_sec: Number
    }
  ],
  total_volume: Number,   // Total: sets × reps × weight
  created_at: DateTime
}
nutrition_logs
JavaScript
{
  _id: ObjectId,
  user_id: ObjectId,
  date: String (YYYY-MM-DD),
  protein_grams: Number,
  calories: Number,
  meals: [
    {
      notes: String,
      protein: Number,
      calories: Number,
      time: String (HH:MM)
    }
  ],
  created_at: DateTime
}
water_logs
JavaScript
{
  _id: ObjectId,
  user_id: ObjectId,
  date: String (YYYY-MM-DD),
  amount_ml: Number,
  created_at: DateTime
}
sleep_logs
JavaScript
{
  _id: ObjectId,
  user_id: ObjectId,
  date: String (YYYY-MM-DD),
  hours: Number,
  quality: String (good/average/poor),
  created_at: DateTime,
  updated_at: DateTime
}
step_logs
JavaScript
{
  _id: ObjectId,
  user_id: ObjectId,
  date: String (YYYY-MM-DD),
  steps: Number,
  created_at: DateTime,
  updated_at: DateTime
}
scores
JavaScript
{
  _id: ObjectId,
  user_id: ObjectId,
  date: String (YYYY-MM-DD),
  score: Number (0-100),
  updated_at: DateTime
}
progress_entries
JavaScript
{
  _id: ObjectId,
  user_id: ObjectId,
  date: String (YYYY-MM-DD),
  weight: String,
  body_fat: String,
  bench_pr: String,
  deadlift_pr: String,
  squat_pr: String,
  pushups: String,
  pullups: String,
  notes: String,
  photo_url: String,      // Cloudinary URL
  created_at: DateTime
}
programs
JavaScript
{
  _id: ObjectId,
  trainer_id: ObjectId,
  name: String,
  description: String,
  days: [Object],         // Workout days
  created_at: DateTime
}
assigned_programs
JavaScript
{
  _id: ObjectId,
  user_id: ObjectId,
  program_id: ObjectId,
  trainer_id: ObjectId,
  assigned_at: DateTime
}
messages
JavaScript
{
  _id: ObjectId,
  trainer_id: ObjectId,
  recipient_id: ObjectId,
  content: String,
  read: Boolean,
  created_at: DateTime
}
📍 Detailed Route Documentation
🔐 Authentication Routes (routes/auth.py)
Blueprint: auth_bp | No URL Prefix

Route	Method	Function	Purpose
/	GET	index()	Landing page
/login	GET, POST	login()	User/trainer login
/signup/user	GET, POST	signup_user()	User registration
/signup/trainer	GET, POST	signup_trainer()	Trainer registration
/logout	GET	logout()	User logout
Detailed Endpoints:
POST /login

Form fields: role (user/trainer), email, password, remember_me
Authenticates user, checks bcrypt password hash
Redirects to appropriate dashboard
Supports "next" parameter for post-login redirect
POST /signup/user

Form fields: username, email, phone, password, confirm_password, goal, weight, height, age, gender
Creates user with default goals: 150g protein, 2500ml water, 7hr sleep, 8000 steps
Checks for duplicate email/username
Auto-logs in after registration
POST /signup/trainer

Form fields: username, email, phone, password, confirm_password, business_name, instagram, years_experience, specialization
Creates trainer with empty clients list
Auto-logs in after registration
👤 User Routes (routes/user.py)
Blueprint: user_bp | URL Prefix: /user

Route	Method	Function	Purpose
/dashboard	GET	dashboard()	Main user dashboard
/workouts	GET, POST	workouts()	Workout logging & history
/nutrition	GET, POST	nutrition()	Nutrition tracking
/water	POST	log_water()	Log water intake
/steps	POST	log_steps()	Log steps
/sleep	POST	log_sleep()	Log sleep
/timeline	GET, POST	timeline()	Progress photos & metrics
/leaderboard	GET	leaderboard()	Rankings & competition
/profile	GET, POST	profile()	User settings & goals
/profile/avatar	POST	upload_avatar()	Upload profile photo
/profile/avatar/remove	POST	remove_avatar()	Remove profile photo
Detailed Endpoints:
GET /user/dashboard

Calculates AURON score, streak, today's logs
Shows current rank label (Elite/Gold/Silver/Bronze/Iron)
Displays today's progress for all 5 metrics
POST /user/workouts

Actions: create_workout, add_exercise
Stores workout with exercises, calculates total volume
Triggers daily score recalculation
POST /user/nutrition

Logs protein and calories for meals
Allows updating existing day's nutrition
Groups meals by date
POST /user/water

Simple ML amount logging
Updates or creates water log entry for the day
Recalculates daily score
POST /user/timeline

Uploads progress photos to Cloudinary
Stores metrics: weight, body fat, PRs (bench, deadlift, squat), pushups, pullups
Shows last 24 entries
GET /user/leaderboard

Two periods: daily or weekly
Aggregates scores from MongoDB
Displays top 50 ranked athletes
Shows username, avatar, and score
POST /user/profile

Updates fitness goals: protein_goal, water_goal, sleep_goal, steps_goal
Updates personal info: goal, weight, height
POST /user/profile/avatar

Uploads to Cloudinary with face detection crop
Stores as auron/avatars/user_{id}
Updates database with secure_url
🏋️ Trainer Routes (routes/trainer.py)
Blueprint: trainer_bp | URL Prefix: /trainer

Route	Method	Function	Purpose
/dashboard	GET	dashboard()	Trainer main dashboard
/clients	GET, POST	clients()	View & manage clients
/clients/add	POST	add_client()	Add user as client
/clients/remove/<client_id>	POST	remove_client()	Remove client
/clients/<client_id>	GET	client_detail()	View client profile
/programs	GET, POST	programs()	Create workout programs
/programs/<program_id>/assign	POST	assign_program()	Assign program to clients
/messages	GET, POST	messages()	Send messages to clients
/leaderboard	GET	leaderboard()	Trainer rankings
Detailed Endpoints:
GET /trainer/dashboard

Shows active clients count
Calculates average client score
Identifies at-risk clients (score < 40)
Shows top 3 performers
Recent messages sent (last 5)
POST /trainer/clients/add

Adds user by username to trainer's client list
Uses MongoDB $addToSet to avoid duplicates
Shows user not found error if username doesn't exist
GET /trainer/clients/<client_id>

Shows comprehensive client profile
Displays: today's score, current streak, compliance %
Shows last 10 workouts, last 6 progress photos
Includes rank label and compliance breakdown
POST /trainer/programs

Creates new workout program
Programs start with empty days array
Stores trainer_id for access control
POST /trainer/programs/<program_id>/assign

Assigns program to multiple clients
Creates/updates assigned_programs collection
Records assignment timestamp
POST /trainer/messages

Two modes: broadcast (all clients) or individual (selected)
Stores messages in messages collection
Marked as unread by default
Shows count of recipients
GET /trainer/leaderboard

Aggregates all trainers' average client scores
Ranks trainers by avg_score descending
Shows business_name and client count
Top page trainer shown first
🔌 API Routes (routes/api.py)
Blueprint: api_bp | URL Prefix: /api

Route	Method	Function	Purpose
/api/score	GET	get_score()	Get current score (JSON)
/api/messages/unread	GET	unread_messages()	Count unread messages
/api/messages/<msg_id>/read	POST	mark_read()	Mark message as read
/api/user/scores/weekly	GET	weekly_scores()	Get last 7 days scores
Detailed Endpoints:
GET /api/score

Returns JSON: {score: Number, streak: {current: Number, longest: Number}}
Users only (403 error for trainers)
GET /api/messages/unread

Returns JSON: {count: Number}
Returns 0 for non-users
GET /api/user/scores/weekly

Returns array of 7 objects: [{date: "YYYY-MM-DD", score: Number}, ...]
Last 7 days including today
Returns empty array for non-users
🛠️ Helper Functions & Utilities (routes/helpers.py)
calculate_auron_score(user_id, target_date=None)
Purpose: Calculate AURON score (0-100) for a user on a specific date

Scoring Breakdown:

Workout exists: +30 pts
Protein: +20 pts (ratio based on goal)
Sleep: +20 pts (ratio based on goal)
Steps: +15 pts (ratio based on goal)
Water: +15 pts (ratio based on goal)
Max: 100 pts
Returns: Integer (0-100)

save_daily_score(user_id, target_date=None)
Purpose: Calculate and persist daily score to database

Stores in: scores collection with {user_id, date, score, updated_at}

Returns: Calculated score

get_streak(user_id, threshold=80)
Purpose: Calculate current and longest streak (consecutive days ≥ threshold score)

Returns: {current: Number, longest: Number}

Looks back up to 365 days
Handles today not-yet-completed scenario
get_today_logs(user_id)
Purpose: Aggregate all today's logged metrics for a user

Returns:

Python
{
  "workout": {...},
  "protein": Number,
  "protein_goal": Number,
  "water": Number,
  "water_goal": Number,
  "sleep": Number,
  "sleep_goal": Number,
  "steps": Number,
  "steps_goal": Number
}
get_rank_label(score)
Purpose: Convert AURON score to rank label

Mapping:

90-100: "Elite"
75-89: "Gold"
60-74: "Silver"
40-59: "Bronze"
0-39: "Iron"
get_compliance_for_client(user_id, days=7)
Purpose: Calculate compliance % for each metric over last N days

Returns:

Python
{
  "workout": Percentage,
  "protein": Percentage,
  "water": Percentage,
  "sleep": Percentage,
  "steps": Percentage
}
Example: 5/7 days = 71%

🔐 Authentication & Security
User Models (routes/models.py)
User Class
Represents a regular athlete user

Implements UserMixin for Flask-Login
get_id(): Returns user:{ObjectId} format
id property: Returns just the ObjectId string
Static methods: get_by_id(), get_by_email(), get_by_username()
Trainer Class
Represents a fitness trainer

Similar structure to User class
get_id(): Returns trainer:{ObjectId} format
Identifies trainer role via role property
Login System (routes/user_loader.py)
Flask-Login callback to load user from session
Parses ID to determine user type (user vs trainer)
Returns appropriate User or Trainer object
Password Security
Uses Flask-Bcrypt for password hashing
Passwords hashed with bcrypt.generate_password_hash()
Checked with bcrypt.check_password_hash()
12-round salt cost (bcrypt default)
Decorators
@user_required: Restricts routes to authenticated users (not trainers) @trainer_required: Restricts routes to authenticated trainers (not users) @login_required: Flask-Login decorator for authentication check

Environment Variables (.env)
Code
SECRET_KEY=<your-flask-secret>
MONGO_URI=mongodb+srv://<user>:<pass>@<cluster>.mongodb.net/
CLOUDINARY_CLOUD_NAME=<your-cloudinary-name>
CLOUDINARY_API_KEY=<your-cloudinary-key>
CLOUDINARY_API_SECRET=<your-cloudinary-secret>
🚀 Setup & Installation
Prerequisites
Python 3.8+
MongoDB Atlas account
Cloudinary account (for image uploads)
Installation Steps
Clone repository

bash
git clone https://github.com/bhuvnesh6/AURON.V0.git
cd AURON.V0
Create virtual environment

bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
Install dependencies

bash
pip install -r requirements.txt
Configure environment

bash
cp .env.example .env
# Edit .env with your credentials
Run application

bash
python app.py
App runs on http://localhost:5000
Debug mode enabled by default
Production Deployment
bash
gunicorn app:app --workers 4 --bind 0.0.0.0:8000
📝 Development Workflow
Adding a New Route
Create function in appropriate blueprint file

Python
@blueprint.route("/path", methods=["GET", "POST"])
@login_required
@user_required  # or @trainer_required
def my_function():
    # Implementation
    return render_template("template.html")
Create corresponding template in templates/ directory

Add to documentation in this file

Adding a New Database Collection
Document schema in Database Schema section
Use MongoDB queries via app.db.collection_name
Index frequently queried fields for performance
Common Database Patterns
Create:

Python
db.collection.insert_one({...})
Read:

Python
doc = db.collection.find_one({"field": value})
docs = list(db.collection.find({"field": value}))
Update:

Python
db.collection.update_one({"_id": ObjectId(id)}, {"$set": {...}})
db.collection.update_one({"_id": ObjectId(id)}, {"$inc": {"field": amount}})
Delete:

Python
db.collection.delete_one({"_id": ObjectId(id)})
🐛 Troubleshooting
MongoDB Connection Issues
Verify MONGO_URI in .env
Ensure IP is whitelisted in MongoDB Atlas
Check network connectivity
Cloudinary Upload Failures
Verify API credentials in .env
Check file size limits (default: 100MB)
Ensure file type is supported (JPEG, PNG, WebP, GIF)
Login Not Working
Clear browser cookies/cache
Check bcrypt password hashing
Verify user exists in database
Check role-based decorators
📚 Additional Resources
Flask Documentation: https://flask.palletsprojects.com/
MongoDB Documentation: https://docs.mongodb.com/
Cloudinary Documentation: https://cloudinary.com/documentation
Flask-Login: https://flask-login.readthedocs.io/