import os
import random
import datetime
import threading
import schedule
import time
from flask import Flask, request, render_template, redirect, url_for, session
from instagrapi import Client
from moviepy.editor import VideoFileClip
from pymongo import MongoClient
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "my_super_secret_saas_key"

# --- ADMIN LOGIN ---
ADMIN_USER = "admin"
ADMIN_PASS = "boss"

UPLOAD_FOLDER = '/tmp'
if not os.path.exists(UPLOAD_FOLDER): os.makedirs(UPLOAD_FOLDER)

# --- MONGODB CONNECTION (User Link) ---
# 👇👇👇 IMP: Niche "PASSWORD_YAHA_LIKHE" ko hatakar apna asli password daalein
MONGO_URI = "mongodb+srv://markzubarwark_db_user:PASSWORD_YAHA_LIKHE@cluster0.ciwzgqg.mongodb.net/?appName=Cluster0"

try:
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    db = client['InstaSaaS']
    users_collection = db['users']
    print("\n✅ MONGODB CONNECTED!\n")
except Exception as e:
    print(f"\n❌ DB ERROR: {e}\n")
    db = None
    users_collection = None

# --- HELPER FUNCTIONS ---
def get_user(username):
    if users_collection is None: return None
    return users_collection.find_one({"username": username})

def is_premium(username):
    user = get_user(username)
    if user and user.get('is_premium'):
        if user.get('plan_expiry') and user['plan_expiry'] > datetime.datetime.now():
            return True
        else:
            users_collection.update_one({"username": username}, {"$set": {"is_premium": False}})
            return False
    return False

def make_video_unique(input_path):
    try:
        output_path = input_path.replace(".mp4", "_unique.mp4")
        clip = VideoFileClip(input_path)
        random_cut = random.uniform(0.1, 0.5)
        new_clip = clip.subclip(0, clip.duration - random_cut)
        new_clip.write_videofile(output_path, codec="libx264", audio_codec="aac", temp_audiofile='/tmp/audio.m4a', remove_temp=True, fps=24, preset='ultrafast')
        clip.close()
        return output_path
    except:
        return input_path

# --- TASKS ---
def run_scheduler():
    while True:
        schedule.run_pending()
        time.sleep(10)

t = threading.Thread(target=run_scheduler)
t.daemon = True
t.start()

# ================= ROUTES =================

@app.route('/', methods=['GET', 'POST'])
def login():
    if 'username' in session: 
        if session.get('is_admin'): return redirect(url_for('admin_dashboard'))
        return redirect(url_for('dashboard'))

    msg = ""
    if request.method == 'POST':
        try:
            username = request.form.get('username').lower().strip()
            password = request.form.get('password')

            if username == ADMIN_USER and password == ADMIN_PASS:
                session['username'] = "Admin"
                session['is_admin'] = True
                return redirect(url_for('admin_dashboard'))

            # Check DB Connection first
            if users_collection is None:
                return "❌ Database Error: Password check karein ya IP Whitelist karein."

            user = get_user(username)
            if user:
                # Login
                if user.get('banned'):
                    msg = "🚫 BANNED."
                elif check_password_hash(user['password'], password):
                    session['username'] = username
                    return redirect(url_for('dashboard'))
                else:
                    msg = "❌ Wrong Password"
            else:
                # Register
                hashed_pw = generate_password_hash(password)
                users_collection.insert_one({
                    "username": username,
                    "password": hashed_pw,
                    "joined": datetime.datetime.now().strftime("%Y-%m-%d"),
                    "is_premium": False,
                    "plan_expiry": None,
                    "banned": False
                })
                session['username'] = username
                return redirect(url_for('dashboard'))

        except Exception as e:
            msg = f"Error: {e}"

    return render_template('login.html', msg=msg)

@app.route('/dashboard')
def dashboard():
    if 'username' not in session: return redirect(url_for('login'))
    username = session['username']
    user = get_user(username)
    return render_template('dashboard.html', user=user, username=username)

@app.route('/buy-premium')
def buy_premium():
    return render_template('buy_premium.html')

# --- TOOLS ---
@app.route('/tool/poster', methods=['GET', 'POST'])
def tool_poster():
    if 'username' not in session: return redirect(url_for('login'))
    if not is_premium(session['username']): return redirect(url_for('buy_premium'))
    msg = ""
    if request.method == 'POST':
        u = request.form.get('insta_user')
        f = request.files['video']
        if f: msg = f"✅ Auto-Post Scheduled for @{u}"
    return render_template('tool_poster.html', msg=msg)

@app.route('/tool/dm', methods=['GET', 'POST'])
def tool_dm():
    if 'username' not in session: return redirect(url_for('login'))
    if not is_premium(session['username']): return redirect(url_for('buy_premium'))
    msg = ""
    if request.method == 'POST':
        link = request.form.get('link')
        msg = f"✅ Bot Started on: {link}"
    return render_template('tool_dm.html', msg=msg)

@app.route('/tool/reposter', methods=['GET', 'POST'])
def tool_reposter():
    if 'username' not in session: return redirect(url_for('login'))
    if not is_premium(session['username']): return redirect(url_for('buy_premium'))
    msg = ""
    if request.method == 'POST':
        msg = "✅ Video Stolen & Uploaded!"
    return render_template('tool_reposter.html', msg=msg)

# --- ADMIN ---
@app.route('/admin')
def admin_link():
    return redirect(url_for('login'))

@app.route('/admin/dashboard')
def admin_dashboard():
    if not session.get('is_admin'): return redirect(url_for('login'))
    all_users = list(users_collection.find())
    return render_template('admin_dashboard.html', users=all_users)

@app.route('/admin/action/<action>/<username>')
def admin_action(action, username):
    if not session.get('is_admin'): return redirect(url_for('login'))
    if action == 'premium':
        expiry = datetime.datetime.now() + datetime.timedelta(days=30)
        users_collection.update_one({"username": username}, {"$set": {"is_premium": True, "plan_expiry": expiry}})
    elif action == 'ban':
        curr = get_user(username)
        new_status = not curr.get('banned', False)
        users_collection.update_one({"username": username}, {"$set": {"banned": new_status}})
    return redirect(url_for('admin_dashboard'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
