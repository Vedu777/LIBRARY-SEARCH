from flask import Flask, render_template, request, jsonify, session, redirect
import subprocess
import json
import os
from datetime import timedelta

app = Flask(__name__, template_folder='templates', static_folder='static')
app.secret_key = 'library_search_secret_key_2026'
app.config['SESSION_COOKIE_AGE'] = timedelta(hours=24)

# ===== PATH FIX (VERY IMPORTANT) =====
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_EXECUTABLE = os.path.abspath(
    os.path.join(BASE_DIR, '..', 'backend', 'library.exe')
)

BACKEND_PROCESS = None
USE_MOCK_BACKEND = False
MOCK_BOOKS = []

# ================= MOCK BACKEND =================

def load_mock_books():
    global MOCK_BOOKS
    csv_path = os.path.join(BASE_DIR, '..', 'data', 'books.csv')
    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            lines = f.read().splitlines()[1:]
            for line in lines:
                parts = line.split(',')
                if len(parts) >= 4:
                    MOCK_BOOKS.append({
                        'isbn': parts[0],
                        'title': parts[1],
                        'author': parts[2],
                        'category': parts[3],
                        'copies': int(parts[4]) if len(parts) > 4 else 1
                    })
    except:
        MOCK_BOOKS = []

# ================= BACKEND PROCESS =================

def start_backend():
    global BACKEND_PROCESS, USE_MOCK_BACKEND

    if not os.path.exists(BACKEND_EXECUTABLE):
        print("⚠ Backend executable not found. Using mock backend.")
        USE_MOCK_BACKEND = True
        return

    if BACKEND_PROCESS is None:
        BACKEND_PROCESS = subprocess.Popen(
            [BACKEND_EXECUTABLE],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )
        # Consume "Library System Ready" banner so first readline() gets actual JSON
        _ = BACKEND_PROCESS.stdout.readline()

def send_to_backend(payload):
    try:
        if USE_MOCK_BACKEND:
            if not MOCK_BOOKS:
                load_mock_books()

            action = payload.get("action")
            if action == "search":
                q = payload.get("query", "").lower()
                results = [
                    {
                        "isbn": b["isbn"],
                        "title": b["title"],
                        "author": b["author"],
                        "category": b["category"],
                        "availableCopies": b["copies"],
                        "totalCopies": b["copies"],
                        "relevanceScore": 1
                    }
                    for b in MOCK_BOOKS if q in b["title"].lower()
                ]
                return {"success": True, "results": results, "count": len(results)}

            if action == "personalized_recommendations":
                recent = payload.get("recentISBNs", [])
                exclude = set(recent)
                results = [
                    {"isbn": b["isbn"], "title": b["title"], "author": b["author"],
                     "category": b["category"], "availableCopies": b["copies"],
                     "totalCopies": b["copies"], "relevanceScore": 1}
                    for b in MOCK_BOOKS[:12] if b["isbn"] not in exclude
                ][:6]
                return {"success": True, "results": results, "count": len(results)}

            return {"success": True, "message": "Mock action OK"}

        start_backend()
        BACKEND_PROCESS.stdin.write(json.dumps(payload) + "\n")
        BACKEND_PROCESS.stdin.flush()

        response = BACKEND_PROCESS.stdout.readline()
        if not response:
            return {"success": False, "message": "Backend not responding"}

        return json.loads(response)

    except Exception as e:
        return {"success": False, "message": str(e)}

# ================= ROUTES =================

@app.route('/')
def index():
    return render_template('login.html')

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    user_id = data.get('userID')
    name = data.get('name', 'User')
    user_type = data.get('userType', 'student')
    
    session['user_id'] = user_id
    session['name'] = name
    session['user_type'] = user_type
    
    return jsonify({"success": True})

@app.route('/home')
def home():
    if 'user_id' not in session:
        return redirect('/')
    return render_template('home.html', name=session.get('name'), user_type=session.get('user_type'))

@app.route('/profile')
def profile():
    if 'user_id' not in session:
        return redirect('/')
    return render_template('profile.html', name=session.get('name'), user_type=session.get('user_type'), user_id=session.get('user_id'))

@app.route('/search')
def search():
    if 'user_id' not in session:
        return redirect('/')
    return render_template('search.html', name=session.get('name'), user_type=session.get('user_type'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

@app.route('/api/search', methods=['POST'])
def api_search():
    data = request.get_json()
    return jsonify(send_to_backend({
        "action": "search",
        "query": data.get("query"),
        "type": data.get("type", "title")
    }))

@app.route('/api/issue', methods=['POST'])
def api_issue():
    data = request.get_json()
    return jsonify(send_to_backend({
        "action": "issue",
        "userID": session['user_id'],
        "isbn": data.get("isbn")
    }))

@app.route('/api/return', methods=['POST'])
def api_return():
    data = request.get_json()
    return jsonify(send_to_backend({
        "action": "return",
        "userID": session['user_id'],
        "isbn": data.get("isbn")
    }))

@app.route('/api/reserve', methods=['POST'])
def api_reserve():
    data = request.get_json()
    return jsonify(send_to_backend({
        "action": "reserve",
        "userID": session['user_id'],
        "isbn": data.get("isbn")
    }))

@app.route('/api/recommendations')
def api_recommendations():
    return jsonify(send_to_backend({
        "action": "recommendations",
        "isbn": request.args.get("isbn"),
        "limit": 6
    }))

@app.route('/api/recommendations/personalized', methods=['POST'])
def api_recommendations_personalized():
    if 'user_id' not in session:
        return jsonify({"success": False, "message": "Not authenticated"}), 401
    data = request.get_json() or {}
    recent_isbns = data.get("recentISBNs", [])
    return jsonify(send_to_backend({
        "action": "personalized_recommendations",
        "userID": session.get("user_id"),
        "recentISBNs": recent_isbns,
        "limit": 6
    }))

@app.route('/api/undo', methods=['POST'])
def api_undo():
    return jsonify(send_to_backend({"action": "undo"}))

@app.route('/api/profile', methods=['GET'])
def api_profile():
    if 'user_id' not in session:
        return jsonify({"success": False, "message": "Not authenticated"}), 401
    
    result = send_to_backend({
        "action": "profile",
        "userID": session.get('user_id')
    })
    return jsonify(result)

# ================= MAIN =================

if __name__ == '__main__':
    start_backend()
    app.run(debug=True, port=5000)
