import queue
from flask import Flask, render_template, request, redirect, url_for, session, g, flash, jsonify, Response
from collections import Counter
import sqlite3
from wordcloud import WordCloud
from print_db import main
import os
import psycopg2
import psycopg2.extras
import time

app = Flask(__name__)
app.secret_key = 'your_secret_key'
DATABASE = 'users.db'

#Secret word to be used at the venue
EVENT_PASSPHRASE = "DPRIN"

"""Database helper"""
def get_db():
    if "db" not in g:
        db_url = os.environ.get("DATABASE_URL")

        if not db_url:
            raise RuntimeError("DATABASE_URL is not set. Did you configure your environment variables?")

        # Ensure psycopg2 understands the SSL requirement (Render enforces it)
        if db_url.startswith("postgres://"):
            db_url = db_url.replace("postgres://", "postgresql://", 1)

        g.db = psycopg2.connect(
            db_url,
            cursor_factory=psycopg2.extras.RealDictCursor,
            sslmode="require"  # Render requires SSL
        )
    return g.db

"""Database helper function: closes DB"""
def close_db(e=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()

@app.before_request
def load_logged_in_user():
    user_id = session.get("user_id")
    if user_id:
        db = get_db()
        g.user = db.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    else:
        g.user = None


@app.route('/login_attendee', methods=['GET', 'POST'])
def login_attendee():
    if request.method == 'POST':
        passkey = request.form['passkey'].strip()
        first_name = request.form['first_name'].strip()
        last_name = request.form.get('last_name', "").strip().lower()
        organisation = request.form.get('organisation', "").strip()

        if passkey != EVENT_PASSPHRASE:
            return render_template('login_attendee.html', error="Invalid passkey")

        if not last_name:
            return render_template('login_attendee.html', error="Please enter your email address")

        if not first_name:
            return render_template('login_attendee.html', error="Please enter your first name")

        db = get_db()
        # Check if already registered
        user = db.execute(
            "SELECT * FROM users WHERE LOWER(first_name)=? AND LOWER(last_name)=? AND is_admin=0",
            (first_name.lower(), last_name)
        ).fetchone()
        existing = db.execute("SELECT * FROM users WHERE last_name = ?", (last_name,)).fetchone()
        if existing:
            return render_template("login_attendee.html", error="Email already in use, try a different one")

        if not user:
            db.execute(
                "INSERT INTO users (first_name, last_name, organisation, is_admin) VALUES (?, ?, ?, 0)",
                (first_name, last_name, organisation)
            )
            db.commit()
            user = db.execute(
                "SELECT * FROM users WHERE first_name=? AND LOWER(last_name)=? AND is_admin=0",
                (first_name, last_name)
            ).fetchone()

        session['user_id'] = user['id']
        return redirect(url_for('home'))

    return render_template('login_attendee.html')

@app.route('/login_admin', methods=['GET', 'POST'])
def login_admin():
    if request.method == 'POST':
        first_name = request.form['first_name'].strip()
        password = request.form['password']

        db = get_db()
        user = db.execute(
            "SELECT * FROM users WHERE LOWER(first_name)=? AND password=? AND is_admin=1",
            (first_name.lower(), password)
        ).fetchone()

        if user:
            session['user_id'] = user['id']
            return redirect(url_for('home'))
        return render_template('login_admin.html', error="Invalid admin credentials")
    main()
    return render_template('login_admin.html')

@app.route("/login_attendee_quick", methods=["GET", "POST"])
def login_attendee_quick():
    if request.method == "POST":
        email = request.form.get("last_name", "").strip().lower()
        first_name = request.form.get("first_name", "").strip()

        if not first_name:
            return render_template("login_attendee_quick.html", error="Please enter your first name")
        if not email:
            return render_template("login_attendee_quick.html", error="Please enter your email address")

        db = get_db()
        user = db.execute("SELECT * FROM users WHERE last_name = ? AND first_name = ?", (email, first_name)).fetchone()

        if user:
            session["first_name"] = user["first_name"]
            session["last_name"] = user["last_name"]
            return redirect(url_for("home"))
        else:
            return render_template("login_attendee_quick.html", error="No user found with those details. Please register first.")

    return render_template("login_attendee_quick.html")
@app.route('/')
def home():
    if not g.user:
        return redirect(url_for("login_attendee"))

    return render_template("home.html", username=g.user["first_name"])

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

@app.route('/agenda')
def agenda():
    return render_template('agenda.html', username=g.user['first_name'] if g.user else None)

@app.route('/about')
def about():
    return render_template('about.html', username=g.user['first_name'] if g.user else None)


@app.route('/submit_question', methods=['GET', 'POST'])
def submit_question():
    if not g.user:
        return redirect(url_for('login_attendee'))
    db = get_db()
    if request.method == 'POST':
        question = request.form['question']
        recipient = request.form['recipient']
        db.execute("INSERT INTO questions (username, user_id, question, recipient) VALUES (?,?, ?, ?)",
                   (g.user['first_name'],g.user['id'], question, recipient))
        db.commit()
        return redirect(url_for('submit_question'))
    my_questions = db.execute("SELECT * FROM questions WHERE user_id=? ORDER BY created_at DESC",
                               (g.user['id'],)).fetchall()
    return render_template('questions.html', username=g.user['first_name'], my_questions=my_questions)

@app.route('/admin_questions', methods=['GET', 'POST'])
def admin_questions():
    if not g.user or g.user['is_admin'] == 0:
        return redirect(url_for('home'))
    db = get_db()
    if request.method == 'POST':
        q_id = request.form.get('question_id')
        db.execute("UPDATE questions SET answered=1 WHERE id=?", (q_id,))
        db.commit()
        return redirect(url_for('admin_questions'))
    questions = db.execute("SELECT * FROM questions ORDER BY created_at DESC").fetchall()
    return render_template('admin_questions.html', questions=questions, username=g.user['first_name'])

#version 2 function not in use
@app.route('/interactive_sessionv2', methods=['GET', 'POST'])
def interactive_sessionv2():
    if not g.user:
        return redirect(url_for('login_attendee'))

    db = get_db()
    username = g.user['first_name']

    # Handle poll submission
    if request.method == 'POST':
        if 'reset' in request.form:
            db.execute("DELETE FROM poll_votes WHERE username=?", (username,))
            db.commit()
        else:
            selected = request.form.getlist('options')
            if len(selected) > 2:
                flash("You can only choose up to 2 options.")
                return redirect(url_for('interactive_session'))
            db.execute("DELETE FROM poll_votes WHERE username=?", (username,))
            if len(selected) <= 2:
                # Remove old votes
                db.execute("DELETE FROM poll_votes WHERE username=?", (username,))
                # Insert new votes
                for option in selected:
                    db.execute("INSERT INTO poll_votes (username, option) VALUES (?, ?)", (username, option))
                db.commit()

    # Fetch user’s current votes
    my_votes = [row['option'] for row in db.execute("SELECT option FROM poll_votes WHERE username=?", (username,)).fetchall()]

    return render_template("interactive_session.html", username=username, my_votes=my_votes)
@app.route("/interactive_session_data")
def interactive_session_data():
    db = get_db()

    # Who's in the room
    rows = db.execute(
        "SELECT organisation, COUNT(*) as count FROM users WHERE is_admin=0 GROUP BY organisation"
    ).fetchall()
    room_data = {row["organisation"]: row["count"] for row in rows}
    print("room data: ",room_data)
    return jsonify({
        "room_data": room_data
    })

@app.route("/poll_results")
def poll_results():
    db = get_db()
    results = db.execute("""
        SELECT option, COUNT(*) as votes
        FROM poll_votes
        GROUP BY option
    """).fetchall()
    print("DEBUG poll_results:", results)
    data = {row["option"]: row["votes"] for row in results}
    return jsonify(data)

@app.route('/interactive_session', methods=['GET', 'POST'])
def interactive_session():
    if not hasattr(g, "user") or g.user is None:
        return redirect(url_for('login'))
    print("Using version 1")
    db = get_db()
    user_id = g.user['id']
    username = g.user['first_name']

    # --- Poll submission handling (existing) ---
    if request.method == 'POST' and 'options' in request.form:
        if 'reset' in request.form:
            db.execute("DELETE FROM poll_votes WHERE user_id=?", (user_id,))
            db.commit()
        else:
            selected = request.form.getlist('options')
            if len(selected) > 2:
                flash("You can only choose up to 2 options.")
                return redirect(url_for('interactive_session'))
            db.execute("DELETE FROM poll_votes WHERE user_id=?", (user_id,))
            for option in selected:
                db.execute("INSERT INTO poll_votes (user_id, option) VALUES (?, ?)", (user_id, option))
            db.commit()
        notify_all("poll")

    # --- Interests submission handling ---
    if request.method == 'POST' and 'interest1' in request.form:
        # Delete old interests for this user
        db.execute("DELETE FROM interests WHERE user_id=?", (user_id,))
        # Insert up to 3 new interests
        for field in ['interest1', 'interest2', 'interest3']:
            phrase = request.form.get(field, "").strip()
            if phrase:
                phrase = phrase.lower()
                db.execute("INSERT INTO interests (user_id, phrase) VALUES (?, ?)", (user_id, phrase))
        db.commit()
        notify_all("wordcloud")
    # Fetch user’s current votes
    my_votes = [row['option'] for row in db.execute(
        "SELECT option FROM poll_votes WHERE user_id=?", (user_id,)
    ).fetchall()]

    # Fetch user’s current interests
    my_interests = [row['phrase'] for row in db.execute(
        "SELECT phrase FROM interests WHERE user_id=?", (user_id,)
    ).fetchall()]

    return render_template("interactive_session.html", username=username,
                           my_votes=my_votes, my_interests=my_interests)

#makes the word cloud image
@app.route("/wordcloud_data")
def wordcloud_data():
    db = get_db()
    words = [row["phrase"].lower() for row in db.execute("SELECT phrase FROM interests").fetchall()]
    if not words:
        words = ["No data yet"]

    counter = Counter(words)
    wordcloud = WordCloud(
        width=800,
        height=400,
        prefer_horizontal=1.0,
        max_font_size=None,  # let it scale up freely
        relative_scaling=0,  # stop shrinking smaller words too aggressively
        normalize_plurals=False,
        collocations=False,
        background_color="white"
    ).generate(" ".join(words))
    return jsonify(counter)

subscribers = set()

@app.route("/events")
def events():
    def stream():
        q = queue.Queue()
        subscribers.add(q)
        try:
            while True:
                data = q.get()
                yield f"data: {data}\n\n"
        except GeneratorExit:
            subscribers.remove(q)
    return Response(stream(), mimetype="text/event-stream")


def notify_all(event_type):
    # send a small JSON object to all subscribers
    import json
    msg = json.dumps({"event": event_type})
    for q in list(subscribers):
        try:
            q.put_nowait(msg)
        except:
            pass

@app.route("/interactive_session_admin", methods=["GET", "POST"])
def interactive_session_admin():
    if not hasattr(g, "user") or g.user is None:
        return redirect(url_for("login"))

    # allow admins only
    if not g.user["is_admin"]:
        flash("You do not have permission to access this page.")
        return redirect(url_for("home"))

    db = get_db()

    if request.method == "POST":
        selected = request.form.getlist("options")
        if len(selected) > 2:
            flash("You can only choose up to 2 options.")
            return redirect(url_for("interactive_session_admin"))

        # save votes
        db.executemany(
            "INSERT INTO poll_votes (id, option) VALUES (?, ?)",
            [(g.user["id"], choice) for choice in selected],
        )
        db.commit()
        flash("Your votes have been recorded.")
        return redirect(url_for("interactive_session_admin"))

    return render_template("interactive_session_admin.html", username=g.user["first_name"])

@app.route("/poll_votes_table")
def poll_votes_table():
    if not hasattr(g, "user") or g.user is None or not g.user["is_admin"]:
        return redirect(url_for("login"))

    db = get_db()
    rows = db.execute("""
        SELECT u.first_name AS username, v.user_id, v.option, v.timestamp
        FROM poll_votes v
        JOIN users u ON v.user_id = u.id
        ORDER BY v.timestamp DESC
    """).fetchall()
    return render_template("poll_votes_table.html", rows=rows, username=g.user["first_name"])

@app.route("/interests_table")
def interests_table():
    if not hasattr(g, "user") or g.user is None or not g.user["is_admin"]:
        return redirect(url_for("login"))

    db = get_db()
    rows = db.execute("""
        SELECT u.first_name AS username, v.phrase, v.timestamp
        FROM interests v
        JOIN users u ON v.username = u.first_name
        ORDER BY v.timestamp DESC
    """).fetchall()

    return render_template("interests_table.html", rows=rows, username=g.user["first_name"])
@app.route("/attendees")
def attendees():
    if not g.user or not g.user["is_admin"]:
        flash("Admins only.")
        return redirect(url_for("home"))

    db = get_db()
    rows = db.execute("""
        SELECT id, first_name, last_name, organisation, timestamp
        FROM users
        WHERE is_admin = 0
        ORDER BY timestamp DESC
    """).fetchall()

    return render_template("attendees.html", attendees=rows)


if __name__ == '__main__':
    app.run(debug=True)
