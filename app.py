import os
import random
import datetime
import threading
import schedule
import time
from flask import Flask, request, render_template, redirect, url_for, session, flash
from instagrapi import Client
from moviepy.editor import VideoFileClip
from pymongo import MongoClient
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "my_super_secret_saas_key"

# --- CONFIG ---
ADMIN_PASSWORD = "admin"
UPLOAD_FOLDER = '/tmp'
if not os.path.exists(UPLOAD_FOLDER): os.makedirs(UPLOAD_FOLDER)

# --- MONGODB CONNECTION ---
MONGO_URI = "mongodb+srv://ramu9045690509_db_user:J1g4r069@jigar069.ud3vuw7.mongodb.net/?appName=Jigar069"
client = MongoClient(MONGO_URI)
db = client['InstaSaaS']
users_collection = db['users']

# --- HELPER FUNCTIONS ---
def get_user(email):
    return users_collection.find_one({"email": email})

def is_premium(email):
    user = get_user(email)
    if user and user.get('is_premium'):
        if user.get('plan_expiry') and user['plan_expiry'] > datetime.datetime.now():
            return True
        else:
            users_collection.update_one({"email": email}, {"$set": {"is_premium": False}})
            return False
    return False

# --- TASKS ---
def run_scheduler():
    while True:
        schedule.run_pending()
        time.sleep(10)

t = threading.Thread(target=run_scheduler)
t.daemon = True
t.start()

# ================= ROUTES =================

@app.route('/')
def home():
    if 'user_email' in session: return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    msg = ""
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        user = get_user(email)
        
        if user:
            if user.get('banned'):
                msg = "🚫 Account Banned by Admin."
            elif check_password_hash(user['password'], password):
                session['user_email'] = email
                return redirect(url_for('dashboard'))
            else:
                msg = "❌ Incorrect Password"
        else:
            msg = "❌ User not found. Please Register first."
            
    return render_template('login.html', msg=msg)

@app.route('/register', methods=['GET', 'POST'])
def register():
    msg = ""
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        if get_user(email):
            msg = "⚠️ Email already registered! Go to Login."
        else:
            # Create New User
            hashed_pw = generate_password_hash(password)
            users_collection.insert_one({
                "email": email,
                "password": hashed_pw,
                "joined": datetime.datetime.now().strftime("%Y-%m-%d"),
                "is_premium": False,
                "plan_expiry": None,
                "banned": False
            })
            msg = "✅ Account Created! Please Login."
            
    return render_template('register.html', msg=msg)

@app.route('/dashboard')
def dashboard():
    if 'user_email' not in session: return redirect(url_for('login'))
    email = session['user_email']
    user = get_user(email)
    return render_template('dashboard.html', user=user, email=email)

@app.route('/buy-premium')
def buy_premium():
    return render_template('buy_premium.html')

# ================= TOOLS (LOCKED) =================
# Note: 'user_mobile' ko replace karke 'user_email' kar diya hai

@app.route('/tool/poster', methods=['GET', 'POST'])
def tool_poster():
    if 'user_email' not in session: return redirect(url_for('login'))
    if not is_premium(session['user_email']): return redirect(url_for('buy_premium'))
    msg = ""
    if request.method == 'POST':
        u = request.form.get('username')
        f = request.files['video']
        if f: msg = f"✅ Auto-Post Scheduled for @{u}"
    return render_template('tool_poster.html', msg=msg)

@app.route('/tool/dm', methods=['GET', 'POST'])
def tool_dm():
    if 'user_email' not in session: return redirect(url_for('login'))
    if not is_premium(session['user_email']): return redirect(url_for('buy_premium'))
    msg = ""
    if request.method == 'POST':
        link = request.form.get('link')
        msg = f"✅ Bot Started on: {link}"
    return render_template('tool_dm.html', msg=msg)

@app.route('/tool/reposter', methods=['GET', 'POST'])
def tool_reposter():
    if 'user_email' not in session: return redirect(url_for('login'))
    if not is_premium(session['user_email']): return redirect(url_for('buy_premium'))
    msg = ""
    if request.method == 'POST':
        msg = "✅ Video Stolen & Uploaded!"
    return render_template('tool_reposter.html', msg=msg)

# ================= ADMIN PANEL =================

@app.route('/admin', methods=['GET', 'POST'])
def admin_login():
    msg = ""
    if request.method == 'POST':
        if request.form.get('password') == ADMIN_PASSWORD:
            session['is_admin'] = True
            return redirect(url_for('admin_dashboard'))
        else:
            msg = "❌ Invalid Password"
    return render_template('admin_login.html', msg=msg)

@app.route('/admin/dashboard')
def admin_dashboard():
    if not session.get('is_admin'): return redirect(url_for('admin_login'))
    all_users = list(users_collection.find())
    return render_template('admin_dashboard.html', users=all_users)

@app.route('/admin/action/<action>/<email>')
def admin_action(action, email):
    if not session.get('is_admin'): return redirect(url_for('admin_login'))
    
    if action == 'premium':
        expiry = datetime.datetime.now() + datetime.timedelta(days=30)
        users_collection.update_one({"email": email}, {"$set": {"is_premium": True, "plan_expiry": expiry}})
    elif action == 'ban':
        curr = get_user(email)
        new_status = not curr.get('banned', False)
        users_collection.update_one({"email": email}, {"$set": {"banned": new_status}})
            
    return redirect(url_for('admin_dashboard'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
  
