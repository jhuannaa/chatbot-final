from flask import Flask, render_template, jsonify, request, session
import json
import requests
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'

OPENROUTER_API_KEY = "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"
DATABASE = 'users.db'

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        username TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL
    )''')
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS chat_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user TEXT NOT NULL,
        message TEXT NOT NULL,
        sender TEXT CHECK(sender IN ('user', 'bot')) NOT NULL,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )''')
    conn.commit()
    conn.close()

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/recipes.json")
def get_recipes():
    with open("recipes.json", "r", encoding="utf-8") as f:
        recipes = json.load(f)
    return jsonify(recipes)

@app.route("/chat", methods=["POST"])
def chat():
    user_input = request.json.get("message", "")
    username = session.get("username", "guest")

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }

    data = {
        "model": "openai/gpt-3.5-turbo-0613",  # changed to a safer, available model
        "messages": [
            {"role": "system", "content": "You are a helpful Filipino cooking assistant."},
            {"role": "user", "content": user_input}
        ]
    }

    try:
        response = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=data)
        if response.ok:
            reply = response.json()['choices'][0]['message']['content']
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute("INSERT INTO chat_history (user, message, sender) VALUES (?, ?, ?)", (username, user_input, "user"))
            cursor.execute("INSERT INTO chat_history (user, message, sender) VALUES (?, ?, ?)", (username, reply, "bot"))
            conn.commit()
            conn.close()
            return jsonify({"reply": reply})
        else:
            print("API Error:", response.status_code, response.text)
            return jsonify({"reply": "Sorry, something went wrong with the chatbot."}), 500
    except Exception as e:
        print("Exception:", e)
        return jsonify({"reply": "Chat service is currently unavailable."}), 500

@app.route("/signup", methods=["POST"])
def signup():
    data = request.json
    name = data.get("name")
    username = data.get("username")
    password = data.get("password")
    if not name or not username or not password:
        return jsonify({'success': False, 'message': 'Please fill in all fields.'})
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
    if cursor.fetchone():
        return jsonify({'success': False, 'message': 'Username already taken.'})
    password_hash = generate_password_hash(password)
    cursor.execute("INSERT INTO users (name, username, password_hash) VALUES (?, ?, ?)",
                   (name, username, password_hash))
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'message': 'Signup successful!'})

@app.route("/login", methods=["POST"])
def login():
    data = request.json
    username = data.get("username")
    password = data.get("password")
    if not username or not password:
        return jsonify({'success': False, 'message': 'Please fill in all fields.'})
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
    user = cursor.fetchone()
    if user and check_password_hash(user['password_hash'], password):
        session['username'] = username
        return jsonify({'success': True, 'message': f'Welcome back, {username}!', 'name': user['name']})
    else:
        return jsonify({'success': False, 'message': 'Invalid username or password.'})

@app.route("/logout", methods=["POST"])
def logout():
    session.pop("username", None)
    return jsonify({"success": True, "message": "Logged out"})

@app.route("/history", methods=["GET"])
def get_chat_history():
    username = session.get("username")
    if not username:
        return jsonify({"success": False, "message": "User not logged in"}), 401
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT message, sender, timestamp FROM chat_history WHERE user = ? ORDER BY timestamp ASC", (username,))
    messages = cursor.fetchall()
    conn.close()
    return jsonify([dict(msg) for msg in messages])

if __name__ == "__main__":
    init_db()
    app.run(debug=True)
