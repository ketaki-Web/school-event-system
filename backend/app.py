import psycopg2
from flask import Flask, render_template, request, redirect, session, send_from_directory, flash, url_for
import os
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

app = Flask(__name__, template_folder="templates")
app.secret_key = os.getenv("SECRET_KEY", "fallback_secret_key_123")

# DB CONNECTION
def get_conn():
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        # Fallback for local testing if not using docker/railway
        db_url = "postgresql://postgres:postgres@localhost:5432/school_db"
    
    try:
        conn = psycopg2.connect(db_url)
        return conn
    except Exception as e:
        print(f"CRITICAL: Could not connect to database. URL: {db_url}")
        print(f"Error: {e}")
        raise e

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
    # Get email from query params for persistence
    email = request.args.get("email", "")
    return render_template("login.html", email=email)

@app.route("/register")
def register():
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM colleges")
    colleges = cursor.fetchall()
    conn.close()
    return render_template("register.html", colleges=colleges)

@app.route("/select-school")
def select_school():
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT name, location FROM colleges")
    colleges = cursor.fetchall()
    conn.close()
    return render_template("select-school.html", colleges=colleges)

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

# ---------------- REGISTER USER ----------------
@app.route("/register-user", methods=["POST"])
def register_user():
    conn = None
    try:
        conn = get_conn()
        cursor = conn.cursor()

        # Teachers cannot register themselves
        role = request.form.get("role")
        status = 'approved' if role == 'teacher' else 'pending' # Actually teachers now added by admin only

        cursor.execute(
            "INSERT INTO users (name, email, password, role, school, status) VALUES (%s,%s,%s,%s,%s,%s)",
            (
                request.form.get("name"),
                request.form.get("email"),
                request.form.get("password"),
                role,
                request.form.get("school").strip() if request.form.get("school") else "",
                status
            )
        )

        conn.commit()
        return redirect("/login")
    except psycopg2.IntegrityError:
        if conn: conn.rollback()
        flash("Email already registered! Please use a different email or try logging in.", "danger")
        return redirect("/register")
    except Exception as e:
        if conn: conn.rollback()
        flash(f"Database Error: {str(e)}", "danger")
        return redirect("/register")
    finally:
        if conn: conn.close()

# ---------------- LOGIN ----------------
@app.route("/login-user", methods=["POST"])
def login_user():
    conn = None
    try:
        conn = get_conn()
        cursor = conn.cursor()

        email = request.form.get("email")
        password = request.form.get("password")
        school = request.form.get("school")

        # Admin login check (admin doesnt need school)
        cursor.execute(
            "SELECT id, name, email, password, role, school, status FROM users WHERE email=%s",
            (email,)
        )
        user = cursor.fetchone()
        
        if user:
            if user[3] == password:
                # Check for approval
                if user[6] != 'approved':
                    flash("Your account is still pending approval from your school teacher.", "warning")
                    return redirect(url_for("login", email=email))

                # Check if it is admin or if school matches
                if user[4] == 'admin' or user[5] == school:
                    session['user'] = user[1]
                    session['user_email'] = user[2]
                    session['role'] = user[4]
                    session['school'] = user[5].strip() if user[5] else ""
                    
                    if user[4] == 'admin':
                        return redirect('/admin')
                    elif user[4] == 'teacher':
                        return redirect('/teacher')
                    else:
                        return redirect('/student')
                else:
                    flash("Incorrect school selection for this account", "warning")
                    return redirect(url_for("login", email=email))
            else:
                flash("Wrong password", "danger")
                return redirect(url_for("login", email=email))
        else:
            flash("User not found", "danger")
            return redirect("/login")
    except Exception as e:
        flash(f"Database Error: {str(e)}", "danger")
        return redirect("/login")
    finally:
        if conn: conn.close()
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

    conn.close()

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
    conn.close()

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
    conn.close()

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
        conn.close()
        return "Already registered"

    cursor.execute(
        """INSERT INTO registrations 
        (event_id, student_email, type, group_name, members) 
        VALUES (%s,%s,%s,%s,%s)""",
        (event_id, email, reg_type, group_name, members)
    )

    conn.commit()
    conn.close()

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
    
    # 🔥 NEW: LIST PENDING STUDENTS
    cursor.execute(
        "SELECT id, name, email FROM users WHERE school=%s AND role='student' AND status='pending'",
        (session.get("school"),)
    )
    pending_students = cursor.fetchall()

    conn.close()

    return render_template("teacher-dashboard.html",
                           suggestions=suggestions,
                           events=events,
                           pending_students=pending_students,
                           school=session.get("school"))

# --- CRUD: APPROVE STUDENT ---
@app.route("/teacher/approve-student/<int:id>")
def approve_student(id):
    if session.get("role") != "teacher":
        return redirect("/login")
    
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET status='approved' WHERE id=%s AND school=%s", (id, session.get("school")))
    conn.commit()
    conn.close()
    flash("Student approved successfully!", "success")
    return redirect("/teacher")

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
        WHERE TRIM(e.school) = %s
    """, (session.get("school").strip() if session.get("school") else "",))

    data = cursor.fetchall()
    conn.close()

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
    conn.close()

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
    conn.close()

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
    conn.close()

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
    conn.close()
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
    conn.close()

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

# ---------------- ADMIN ----------------
@app.route("/admin")
def admin_dashboard():
    if session.get("role") != "admin":
        return redirect("/login")
    
    conn = get_conn()
    cursor = conn.cursor()
    
    cursor.execute("SELECT id, name, location FROM colleges")
    colleges = cursor.fetchall()
    
    cursor.execute("SELECT id, name, email, school FROM users WHERE role='teacher'")
    teachers = cursor.fetchall()
    
    conn.close()
    return render_template("admin-dashboard.html", colleges=colleges, teachers=teachers)

@app.route("/admin/add-college", methods=["POST"])
def add_college():
    if session.get("role") != "admin":
        return redirect("/login")
    
    name = request.form.get("name")
    location = request.form.get("location")
    
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO colleges (name, location) VALUES (%s, %s)", (name, location))
    conn.commit()
    conn.close()
    return redirect("/admin")

@app.route("/admin/add-teacher", methods=["POST"])
def add_teacher():
    if session.get("role") != "admin":
        return redirect("/login")
    
    name = request.form.get("name")
    email = request.form.get("email")
    password = request.form.get("password")
    school = request.form.get("school")
    
    conn = get_conn()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO users (name, email, password, role, school, status) VALUES (%s, %s, %s, %s, %s, %s)",
            (name, email, password, "teacher", school, "approved")
        )
        conn.commit()
    except Exception as e:
        conn.rollback()
        return f"Error adding teacher: {e}"
    finally:
        conn.close()
    
    return redirect("/admin")

# --- CRUD: DELETE COLLEGE ---
@app.route("/admin/delete-college/<int:id>")
def delete_college(id):
    if session.get("role") != "admin":
        return redirect("/login")
    
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM colleges WHERE id=%s", (id,))
    conn.commit()
    conn.close()
    return redirect("/admin")

# --- CRUD: UPDATE COLLEGE ---
@app.route("/admin/update-college", methods=["POST"])
def update_college():
    if session.get("role") != "admin":
        return redirect("/login")
    
    college_id = request.form.get("id")
    name = request.form.get("name")
    location = request.form.get("location")
    
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("UPDATE colleges SET name=%s, location=%s WHERE id=%s", (name, location, college_id))
    conn.commit()
    conn.close()
    return redirect("/admin")

# --- CRUD: DELETE TEACHER ---
@app.route("/admin/delete-teacher/<int:id>")
def delete_teacher(id):
    if session.get("role") != "admin":
        return redirect("/login")
    
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM users WHERE id=%s AND role='teacher'", (id,))
    conn.commit()
    conn.close()
    return redirect("/admin")

# --- CRUD: UPDATE TEACHER ---
@app.route("/admin/update-teacher", methods=["POST"])
def update_teacher():
    if session.get("role") != "admin":
        return redirect("/login")
    
    teacher_id = request.form.get("id")
    name = request.form.get("name")
    email = request.form.get("email")
    school = request.form.get("school")
    
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET name=%s, email=%s, school=%s WHERE id=%s AND role='teacher'", 
                   (name, email, school, teacher_id))
    conn.commit()
    conn.close()
    return redirect("/admin")

def init_db():
    conn = None
    try:
        conn = get_conn()
        cursor = conn.cursor()

        # Update: Added colleges table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS colleges (
            id SERIAL PRIMARY KEY,
            name TEXT UNIQUE,
            location TEXT
        );
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            name TEXT,
            email TEXT UNIQUE,
            password TEXT,
            role TEXT,
            school TEXT,
            status TEXT DEFAULT 'approved'
        );
        """)
        
        # 🔥 AUTO-MIGRATE: Add status column if it doesn't exist (for existing tables)
        try:
            cursor.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'approved';")
            conn.commit()
        except Exception:
            conn.rollback()

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id SERIAL PRIMARY KEY,
            title TEXT,
            description TEXT,
            date TEXT,
            school TEXT,
            location TEXT
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
            category TEXT,
            description TEXT,
            location TEXT,
            status TEXT,
            school TEXT
        );
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS results (
            id SERIAL PRIMARY KEY,
            event_name TEXT,
            winner_name TEXT,
            position TEXT,
            school TEXT
        );
        """)

        # 🔥 AUTO-SEED ADMIN
        admin_email = os.getenv("ADMIN_EMAIL", "admin@school.com")
        admin_pass = os.getenv("ADMIN_PASSWORD", "admin123")
        admin_name = os.getenv("ADMIN_NAME", "System Admin")

        cursor.execute("SELECT * FROM users WHERE email = %s", (admin_email,))
        if not cursor.fetchone():
            cursor.execute(
                "INSERT INTO users (name, email, password, role, school, status) VALUES (%s, %s, %s, %s, %s, %s)",
                (admin_name, admin_email, admin_pass, "admin", "System", "approved")
            )
            print(f"Admin user seeded: {admin_email}")

        conn.commit()
    except Exception as e:
        print(f"Failed to initialize database: {e}")
    finally:
        if conn:
            conn.close()


# Initialize DB
init_db()

@app.route("/reset-db")
def reset_db():
    conn = None
    try:
        conn = get_conn()
        cursor = conn.cursor()
        cursor.execute("DROP TABLE IF EXISTS users, events, registrations, suggestions, results, colleges CASCADE;")
        conn.commit()
    except Exception as e:
        if conn: conn.rollback()
        return f"Error resetting DB: {e}", 500
    finally:
        if conn: conn.close()
        
    init_db()
    return "<h3>Database tables successfully wiped and re-created!</h3><p>The missing columns have been fixed. <a href='/register'>Go Register</a></p>"

# ---------------- RUN ----------------
if __name__ == "__main__":
    # app.run below

    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))