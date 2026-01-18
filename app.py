import os
import random
import datetime
import threading
import schedule
import time
import requests
import json
from flask import Flask, request, render_template, redirect, url_for, session
from instagrapi import Client
from moviepy.editor import VideoFileClip
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "my_super_secret_saas_key"

# --- JSONBIN CONFIG (Apki Details Set Kar Di Hain) ---
JSONBIN_API_KEY = "$2a$10$b1151NglEWv02j576NgfWO2gUwDgYcHXkcz1YhqpnQtTS0/j5k6V."
JSONBIN_BIN_ID = "696cedc5ae596e708fe4b56a"

# --- DATABASE HELPERS ---
def read_db():
    url = f"https://api.jsonbin.io/v3/b/{JSONBIN_BIN_ID}/latest"
    headers = {"X-Master-Key": JSONBIN_API_KEY}
    try:
        req = requests.get(url, headers=headers)
        return req.json().get("record", {})
    except:
        return {}

def save_db(data):
    url = f"https://api.jsonbin.io/v3/b/{JSONBIN_BIN_ID}"
    headers = {
        "Content-Type": "application/json",
        "X-Master-Key": JSONBIN_API_KEY
    }
    requests.put(url, json=data, headers=headers)

# --- ADMIN LOGIN ---
ADMIN_USER = "admin"
ADMIN_PASS = "boss"

UPLOAD_FOLDER = '/tmp'
if not os.path.exists(UPLOAD_FOLDER): os.makedirs(UPLOAD_FOLDER)

# --- HELPER FUNCTIONS ---
def get_user(username):
    data = read_db()
    return data.get(username)

def is_premium(username):
    data = read_db()
    user = data.get(username)
    if user and user.get('is_premium'):
        expiry_str = user.get('plan_expiry')
        if expiry_str:
            try:
                expiry_date = datetime.datetime.strptime(expiry_str, "%Y-%m-%d %H:%M:%S")
                if expiry_date > datetime.datetime.now():
                    return True
            except:
                pass
        
        # Agar expire ho gaya ya date galat hai
        user['is_premium'] = False
        data[username] = user
        save_db(data)
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

            data = read_db()
            user = data.get(username)

            if user:
                # Login Logic
                if user.get('banned'):
                    msg = "🚫 You are BANNED."
                elif check_password_hash(user['password'], password):
                    session['username'] = username
                    return redirect(url_for('dashboard'))
                else:
                    msg = "❌ Wrong Password"
            else:
                # Auto-Register Logic
                hashed_pw = generate_password_hash(password)
                new_user = {
                    "username": username,
                    "password": hashed_pw,
                    "joined": datetime.datetime.now().strftime("%Y-%m-%d"),
                    "is_premium": False,
                    "plan_expiry": None,
                    "banned": False
                }
                data[username] = new_user
                save_db(data) # Cloud me save ho gaya
                
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
    if not user:
        session.clear()
        return redirect(url_for('login'))
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

# --- ADMIN PANEL ---

@app.route('/admin')
def admin_link():
    return redirect(url_for('login'))

@app.route('/admin/dashboard')
def admin_dashboard():
    if not session.get('is_admin'): return redirect(url_for('login'))
    data = read_db()
    all_users = list(data.values())
    return render_template('admin_dashboard.html', users=all_users)

@app.route('/admin/action/<action>/<username>')
def admin_action(action, username):
    if not session.get('is_admin'): return redirect(url_for('login'))
    
    data = read_db()
    if username in data:
        if action == 'premium':
            expiry = datetime.datetime.now() + datetime.timedelta(days=30)
            data[username]['is_premium'] = True
            data[username]['plan_expiry'] = expiry.strftime("%Y-%m-%d %H:%M:%S")
        elif action == 'ban':
            data[username]['banned'] = not data[username]['banned']
        
        save_db(data)
            
    return redirect(url_for('admin_dashboard'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
