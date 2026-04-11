import psycopg2
from flask import Flask, render_template, request, redirect, session, send_from_directory
import os

app = Flask(__name__, template_folder="templates")
app.secret_key = "secret123"

# DB CONNECTION
def get_conn():
    return psycopg2.connect(os.getenv("DATABASE_URL"))

# STATIC
@app.route('/css/<path:filename>')
def serve_css(filename):
    return send_from_directory(os.path.join(app.root_path, '../css'), filename)

@app.route('/js/<path:filename>')
def serve_js(filename):
    return send_from_directory(os.path.join(app.root_path, '../js'), filename)

# ---------------- HOME ----------------
@app.route("/")
def home():
    return render_template("index.html")

@app.route("/login")
def login():
    return render_template("login.html")

@app.route("/register")
def register():
    return render_template("register.html")

@app.route("/select-school")
def select_school():
    return render_template("select-school.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

# ---------------- REGISTER USER ----------------
@app.route("/register-user", methods=["POST"])
def register_user():

    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute(
        "INSERT INTO users (name, email, password, role, school) VALUES (%s,%s,%s,%s,%s)",
        (
            request.form.get("name"),
            request.form.get("email"),
            request.form.get("password"),
            request.form.get("role"),
            request.form.get("school")
        )
    )

    conn.commit()
    return redirect("/login")

# ---------------- LOGIN ----------------
@app.route("/login-user", methods=["POST"])
def login_user():
    conn = get_conn()
    cursor = conn.cursor()

    email = request.form.get("email")
    password = request.form.get("password")
    school = request.form.get("school")

    cursor.execute(
        "SELECT * FROM users WHERE email=%s AND school=%s",
        (email, school)
    )
    user = cursor.fetchone()

    if user:
        if user[2] == password:
            session['user'] = user[1]
            return redirect('/dashboard')
        else:
            return "Wrong password"
    else:
        return "User not found"
# ---------------- STUDENT ----------------
@app.route("/student")
def student_dashboard():

    if not session.get("user_email"):
        return redirect("/login")

    conn = get_conn()
    cursor = conn.cursor()

    # 🔹 Registered events (already there)
    cursor.execute("""
        SELECT e.title, e.description, e.date, e.location
        FROM registrations r
        JOIN events e ON r.event_id = e.id
        WHERE r.student_email=%s AND e.school=%s
    """, (session.get("user_email"), session.get("school")))

    registered_events = cursor.fetchall()

    # 🔥 NEW: Total events in this school
    cursor.execute(
        "SELECT COUNT(*) FROM events WHERE school=%s",
        (session.get("school"),)
    )
    total_events = cursor.fetchone()[0]

    # 🔥 NEW: Registered count
    registered_count = len(registered_events)

    return render_template(
        "student-dashboard.html",
        registered_events=registered_events,
        total_events=total_events,
        registered_count=registered_count,
        school=session.get("school")
    )

# ---------------- BROWSE EVENTS ----------------
@app.route("/browse-events")
def browse_events():

    if not session.get("school"):
        return redirect("/select-school")

    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT id, title, description, date, location FROM events WHERE school=%s",
        (session.get("school"),)
    )

    events = cursor.fetchall()

    return render_template("browse-events.html", events=events)

# ---------------- EVENT DETAILS ----------------
@app.route("/event-details/<int:event_id>")
def event_details(event_id):

    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT id, title, description, date, location FROM events WHERE id=%s AND school=%s",
        (event_id, session.get("school"))
    )

    event = cursor.fetchone()

    return render_template("event-details.html", event=event, event_id=event_id)

# ---------------- REGISTER EVENT ----------------
@app.route("/register-event", methods=["POST"])
def register_event():

    if not session.get("user_email"):
        return redirect("/login")

    conn = get_conn()
    cursor = conn.cursor()

    event_id = request.form.get("event_id")
    email = session.get("user_email")
    reg_type = request.form.get("type")
    group_name = request.form.get("group_name")
    members = request.form.get("members")

    # duplicate check
    cursor.execute(
        "SELECT * FROM registrations WHERE event_id=%s AND student_email=%s",
        (event_id, email)
    )

    if cursor.fetchone():
        return "Already registered"

    cursor.execute(
        """INSERT INTO registrations 
        (event_id, student_email, type, group_name, members) 
        VALUES (%s,%s,%s,%s,%s)""",
        (event_id, email, reg_type, group_name, members)
    )

    conn.commit()

    return redirect("/student")
# ---------------- TEACHER ----------------
@app.route("/teacher")
def teacher_dashboard():

    if not session.get("school"):
        return redirect("/login")

    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT id, title, category, description, location, status FROM suggestions WHERE school=%s",
        (session.get("school"),)
    )
    suggestions = cursor.fetchall()

    cursor.execute(
        "SELECT id, title, date, location FROM events WHERE school=%s",
        (session.get("school"),)
    )
    events = cursor.fetchall()

    return render_template("teacher-dashboard.html",
                           suggestions=suggestions,
                           events=events,
                           school=session.get("school"))

# ---------------- ADD EVENT ----------------
@app.route("/add-event", methods=["GET", "POST"])
def add_event():

    if request.method == "GET":
        return render_template("add-event.html")

    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute(
        "INSERT INTO events (title, description, date, location, school) VALUES (%s,%s,%s,%s,%s)",
        (
            request.form.get("title"),
            request.form.get("description"),
            request.form.get("date"),
            request.form.get("location"),
            session.get("school")
        )
    )

    conn.commit()
    return redirect("/teacher")

@app.route("/view-registrations")
def view_registrations():

    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT e.title, r.student_email, r.type, r.group_name, r.members
        FROM registrations r
        JOIN events e ON r.event_id = e.id
        WHERE e.school = %s
    """, (session.get("school"),))

    data = cursor.fetchall()

    return render_template("view-registrations.html", registrations=data)

# ---------------- MANAGE EVENTS ----------------
@app.route("/manage-events")
def manage_events():

    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT id, title, description, date, location FROM events WHERE school=%s",
        (session.get("school"),)
    )

    events = cursor.fetchall()

    return render_template("manage-events.html", events=events)

# ---------------- DELETE EVENT ----------------
@app.route("/delete-event/<int:id>")
def delete_event(id):

    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM events WHERE id=%s", (id,))
    conn.commit()

    return redirect("/manage-events")
@app.route("/edit-event/<int:id>")
def edit_event_page(id):

    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT id, title, description, date, location FROM events WHERE id=%s",
        (id,)
    )

    event = cursor.fetchone()

    return render_template("edit-event.html", event=event)

# ---------------- ADD RESULT ----------------
@app.route("/add-result", methods=["GET", "POST"])
def add_result():

    if request.method == "GET":
        return render_template("add-result.html")

    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute(
        "INSERT INTO results (event_name, winner_name, position, school) VALUES (%s,%s,%s,%s)",
        (
            request.form.get("event_name"),
            request.form.get("winner_name"),
            request.form.get("position"),
            session.get("school")
        )
    )

    conn.commit()
    return redirect("/teacher")

# ---------------- VIEW RESULTS ----------------
@app.route("/results")
def results():

    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT event_name, winner_name, position FROM results WHERE school=%s",
        (session.get("school"),)
    )

    data = cursor.fetchall()

    return render_template("results.html", results=data)

# ---------------- SUGGEST EVENT ----------------
@app.route("/suggest-event")
def suggest_event_page():
    return render_template("suggest-event.html")

@app.route("/submit-suggestion", methods=["POST"])
def submit_suggestion():

    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute(
        "INSERT INTO suggestions (title, category, description, location, school, status) VALUES (%s,%s,%s,%s,%s,%s)",
        (
            request.form.get("title"),
            request.form.get("category"),
            request.form.get("description"),
            request.form.get("location"),
            session.get("school"),
            "pending"
        )
    )

    conn.commit()
    return redirect("/student")

# ---------------- APPROVE ----------------
@app.route("/approve-suggestion/<int:id>")
def approve_suggestion(id):

    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute("SELECT title, description, location FROM suggestions WHERE id=%s", (id,))
    s = cursor.fetchone()

    if s:
        cursor.execute(
            "INSERT INTO events (title, description, date, location, school) VALUES (%s,%s,CURRENT_DATE,%s,%s)",
            (s[0], s[1], s[2], session.get("school"))
        )

        cursor.execute("UPDATE suggestions SET status='approved' WHERE id=%s", (id,))

    conn.commit()
    return redirect("/teacher")

# ---------------- REJECT ----------------
@app.route("/reject-suggestion/<int:id>")
def reject_suggestion(id):

    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute("UPDATE suggestions SET status='rejected' WHERE id=%s", (id,))
    conn.commit()

    return redirect("/teacher")

@app.route("/update-event/<int:id>", methods=["POST"])
def update_event(id):

    conn = get_conn()   # ✅ THIS WAS MISSING
    cursor = conn.cursor()

    title = request.form.get("title")
    description = request.form.get("description")
    date = request.form.get("date")
    location = request.form.get("location")

    cursor.execute(
        "UPDATE events SET title=%s, description=%s, date=%s, location=%s WHERE id=%s",
        (title, description, date, location, id)
    )

    conn.commit()

    return redirect("/manage-events")

def init_db():
    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY,
        name TEXT,
        email TEXT UNIQUE,
        password TEXT,
        role TEXT,
        school TEXT
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS events (
        id SERIAL PRIMARY KEY,
        title TEXT,
        description TEXT,
        date TEXT,
        school TEXT
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS registrations (
        id SERIAL PRIMARY KEY,
        event_id INTEGER,
        student_email TEXT,
        type TEXT,
        group_name TEXT,
        members TEXT
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS suggestions (
        id SERIAL PRIMARY KEY,
        title TEXT,
        description TEXT,
        location TEXT,
        status TEXT,
        school TEXT
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS results (
        id SERIAL PRIMARY KEY,
        event_id INTEGER,
        winner TEXT,
        school TEXT
    );
    """)

    conn.commit()


# ---------------- RUN ----------------
if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))