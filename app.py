import os
import sqlite3
from pathlib import Path
from werkzeug.security import check_password_hash, generate_password_hash
from flask import Flask, flash, g, redirect, render_template, request, session, url_for


BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "college0.db"
SCHEMA_PATH = BASE_DIR / "schema.sql"


app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "college0-dev-key")


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(_error):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    schema = SCHEMA_PATH.read_text(encoding="utf-8")
    db.executescript(schema)
    seed(db)
    db.commit()
    db.close()


def seed(db):
    registrar = db.execute("SELECT user_id FROM users WHERE email = ?", ("registrar@college0.edu",)).fetchone()
    if registrar is None:
        db.execute(
            "INSERT INTO users (email, password_hash, role) VALUES (?,?,?)",
            ("registrar@college0.edu", generate_password_hash("registrar123"), "registrar"),
        )

    student = db.execute("SELECT user_id FROM users WHERE email = ?", ("student@college0.edu",)).fetchone()
    if student is None:
        db.execute(
            "INSERT INTO users (email, password_hash, role) VALUES (?,?,?)",
            ("student@college0.edu", generate_password_hash("student123"), "student"),
        )
        sid = db.execute("SELECT user_id FROM users WHERE email = ?", ("student@college0.edu",)).fetchone()["user_id"]
        db.execute("INSERT INTO student_profiles (student_id, overall_gpa) VALUES (?, ?)", (sid, 3.2))

    instructor = db.execute("SELECT user_id FROM users WHERE email = ?", ("instructor@college0.edu",)).fetchone()
    if instructor is None:
        db.execute(
            "INSERT INTO users (email, password_hash, role) VALUES (?,?,?)",
            ("instructor@college0.edu", generate_password_hash("instructor123"), "instructor"),
        )
        iid = db.execute("SELECT user_id FROM users WHERE email = ?", ("instructor@college0.edu",)).fetchone()["user_id"]
        db.execute("INSERT INTO instructor_profiles (instructor_id, department) VALUES (?,?)", (iid, "CS"))

    if db.execute("SELECT semester_id FROM semesters").fetchone() is None:
        db.execute("INSERT INTO semesters (name, phase) VALUES (?,?)", ("Spring 2026", "registration"))
    semester_id = db.execute("SELECT semester_id FROM semesters ORDER BY semester_id DESC LIMIT 1").fetchone()["semester_id"]

    if db.execute("SELECT course_id FROM courses").fetchone() is None:
        db.execute("INSERT INTO courses (name, credits, is_required) VALUES (?,?,?)", ("Software Engineering", 3, 1))
        db.execute("INSERT INTO courses (name, credits, is_required) VALUES (?,?,?)", ("Database Systems", 3, 1))

    if db.execute("SELECT section_id FROM class_sections").fetchone() is None:
        iid = db.execute("SELECT user_id FROM users WHERE role='instructor' LIMIT 1").fetchone()["user_id"]
        for row in db.execute("SELECT course_id FROM courses").fetchall():
            db.execute(
                "INSERT INTO class_sections (course_id, semester_id, instructor_id, capacity, enrolled_count) VALUES (?,?,?,?,?)",
                (row["course_id"], semester_id, iid, 2, 0),
            )

    if db.execute("SELECT taboo_id FROM taboo_words").fetchone() is None:
        for word in ("stupid", "idiot", "hate", "dumb"):
            db.execute("INSERT INTO taboo_words (word) VALUES (?)", (word,))

    if db.execute("SELECT doc_id FROM ai_knowledge_documents").fetchone() is None:
        db.execute(
            "INSERT INTO ai_knowledge_documents (title, content, role_scope) VALUES (?,?,?)",
            ("Registration Policy", "Students can register during registration phase if they are active and not suspended.", "student"),
        )
        db.execute(
            "INSERT INTO ai_knowledge_documents (title, content, role_scope) VALUES (?,?,?)",
            ("Semester Lifecycle", "Phases follow setup -> registration -> running -> grading -> closed.", "public"),
        )


def current_user():
    user_id = session.get("user_id")
    if not user_id:
        return None
    return get_db().execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()


def role_required(*roles):
    user = current_user()
    return user is not None and user["role"] in roles


def issue_warning(db, user_id, reason, source):
    db.execute("INSERT INTO warning_events (user_id, reason, source) VALUES (?,?,?)", (user_id, reason, source))
    db.execute("UPDATE users SET warnings = warnings + 1 WHERE user_id = ?", (user_id,))
    count = db.execute("SELECT warnings FROM users WHERE user_id = ?", (user_id,)).fetchone()["warnings"]
    if count >= 3:
        db.execute("UPDATE users SET status = 'suspended' WHERE user_id = ?", (user_id,))


@app.route("/")
def public_dashboard():
    db = get_db()
    top_classes = db.execute(
        """
        SELECT c.name, IFNULL(AVG(r.stars), 0) AS avg_stars
        FROM courses c
        LEFT JOIN class_sections s ON s.course_id = c.course_id
        LEFT JOIN enrollments e ON e.section_id = s.section_id
        LEFT JOIN reviews r ON r.enrollment_id = e.enrollment_id AND r.published = 1
        GROUP BY c.course_id
        ORDER BY avg_stars DESC
        LIMIT 3
        """
    ).fetchall()
    top_students = db.execute(
        """
        SELECT u.email, sp.overall_gpa
        FROM student_profiles sp
        JOIN users u ON u.user_id = sp.student_id
        ORDER BY sp.overall_gpa DESC
        LIMIT 5
        """
    ).fetchall()
    return render_template("public_dashboard.html", top_classes=top_classes, top_students=top_students, user=current_user())


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        db = get_db()
        email = request.form["email"].strip().lower()
        password = request.form["password"]
        user = db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        if user and check_password_hash(user["password_hash"], password):
            session["user_id"] = user["user_id"]
            flash("Logged in successfully.", "success")
            return redirect(url_for("home"))
        flash("Invalid credentials.", "error")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("public_dashboard"))


@app.route("/home")
def home():
    user = current_user()
    if not user:
        return redirect(url_for("login"))
    role_to_route = {
        "student": "student_register_courses",
        "instructor": "instructor_waitlist",
        "registrar": "registrar_applications",
        "visitor": "public_dashboard",
    }
    return redirect(url_for(role_to_route.get(user["role"], "public_dashboard")))


@app.route("/apply/<role>", methods=["GET", "POST"])
def apply(role):
    if role not in ("student", "instructor"):
        return "Invalid role", 400
    if request.method == "POST":
        db = get_db()
        email = request.form["email"].strip().lower()
        prior_gpa = float(request.form.get("prior_gpa") or 0)
        exists = db.execute("SELECT user_id FROM users WHERE email = ?", (email,)).fetchone()
        if exists:
            flash("Email already exists in the system.", "error")
            return redirect(request.url)
        db.execute(
            "INSERT INTO applications (applicant_email, role, prior_gpa, status) VALUES (?,?,?,?)",
            (email, role, prior_gpa, "pending"),
        )
        db.commit()
        flash("Application submitted.", "success")
        return redirect(url_for("public_dashboard"))
    return render_template("apply.html", role=role)


@app.route("/registrar/applications", methods=["GET", "POST"])
def registrar_applications():
    if not role_required("registrar"):
        return redirect(url_for("login"))
    db = get_db()
    if request.method == "POST":
        app_id = int(request.form["application_id"])
        action = request.form["action"]
        app_row = db.execute("SELECT * FROM applications WHERE application_id = ?", (app_id,)).fetchone()
        if app_row is None:
            flash("Application not found.", "error")
            return redirect(request.url)
        if action == "approve":
            temp_pass = "Temp1234!"
            db.execute(
                "INSERT INTO users (email, password_hash, role, first_login_reset) VALUES (?,?,?,1)",
                (app_row["applicant_email"], generate_password_hash(temp_pass), app_row["role"]),
            )
            user_id = db.execute("SELECT user_id FROM users WHERE email = ?", (app_row["applicant_email"],)).fetchone()["user_id"]
            if app_row["role"] == "student":
                db.execute("INSERT INTO student_profiles (student_id) VALUES (?)", (user_id,))
            else:
                db.execute("INSERT INTO instructor_profiles (instructor_id) VALUES (?)", (user_id,))
            db.execute("UPDATE applications SET status='approved', decided_by=? WHERE application_id=?", (session["user_id"], app_id))
            flash(f"Approved. Temporary password: {temp_pass}", "success")
        else:
            reason = request.form.get("reason", "Rejected by registrar")
            db.execute(
                "UPDATE applications SET status='rejected', rejection_justification=?, decided_by=? WHERE application_id=?",
                (reason, session["user_id"], app_id),
            )
            flash("Application rejected.", "info")
        db.commit()
        return redirect(request.url)
    applications = db.execute("SELECT * FROM applications ORDER BY application_id DESC").fetchall()
    return render_template("registrar_applications.html", applications=applications, user=current_user())


@app.route("/registrar/semester", methods=["GET", "POST"])
def registrar_semester():
    if not role_required("registrar"):
        return redirect(url_for("login"))
    db = get_db()
    sem = db.execute("SELECT * FROM semesters ORDER BY semester_id DESC LIMIT 1").fetchone()
    phase_order = ["setup", "registration", "running", "grading", "closed"]
    if request.method == "POST":
        idx = phase_order.index(sem["phase"])
        sem_next = phase_order[(idx + 1) % len(phase_order)]
        db.execute("UPDATE semesters SET phase = ? WHERE semester_id = ?", (sem_next, sem["semester_id"]))
        if sem["phase"] == "running":
            low_load = db.execute(
                """
                SELECT u.user_id
                FROM users u
                JOIN student_profiles sp ON sp.student_id = u.user_id
                WHERE u.role='student'
                """
            ).fetchall()
            for s in low_load:
                cnt = db.execute(
                    "SELECT COUNT(*) AS c FROM enrollments WHERE student_id=? AND status='enrolled'",
                    (s["user_id"],),
                ).fetchone()["c"]
                if cnt < 2:
                    issue_warning(db, s["user_id"], "Low course load during running phase", "lowload")
        db.commit()
        flash(f"Semester advanced to {sem_next}.", "success")
        return redirect(request.url)
    sem = db.execute("SELECT * FROM semesters ORDER BY semester_id DESC LIMIT 1").fetchone()
    return render_template("registrar_semester.html", sem=sem, user=current_user())


@app.route("/student/register", methods=["GET", "POST"])
def student_register_courses():
    if not role_required("student"):
        return redirect(url_for("login"))
    db = get_db()
    user = current_user()
    sem = db.execute("SELECT * FROM semesters ORDER BY semester_id DESC LIMIT 1").fetchone()
    if request.method == "POST":
        if user["status"] == "suspended":
            flash("Suspended students cannot register.", "error")
            return redirect(request.url)
        if sem["phase"] not in ("registration",):
            flash("Registration is not active.", "error")
            return redirect(request.url)
        section_id = int(request.form["section_id"])
        section = db.execute("SELECT * FROM class_sections WHERE section_id = ?", (section_id,)).fetchone()
        existing = db.execute(
            "SELECT enrollment_id FROM enrollments WHERE student_id=? AND section_id=? AND status IN ('enrolled','waitlisted')",
            (user["user_id"], section_id),
        ).fetchone()
        if existing:
            flash("Already enrolled/waitlisted in this section.", "error")
            return redirect(request.url)
        if section["enrolled_count"] < section["capacity"]:
            db.execute(
                "INSERT INTO enrollments (student_id, section_id, status) VALUES (?,?,'enrolled')",
                (user["user_id"], section_id),
            )
            db.execute("UPDATE class_sections SET enrolled_count = enrolled_count + 1 WHERE section_id = ?", (section_id,))
            flash("Enrolled successfully.", "success")
        else:
            pos = db.execute(
                "SELECT COUNT(*) AS c FROM enrollments WHERE section_id = ? AND status='waitlisted'",
                (section_id,),
            ).fetchone()["c"] + 1
            db.execute(
                "INSERT INTO enrollments (student_id, section_id, status, waitlist_position) VALUES (?,?,'waitlisted',?)",
                (user["user_id"], section_id, pos),
            )
            flash(f"Class full. Added to waitlist at position {pos}.", "info")
        db.commit()
        return redirect(request.url)

    sections = db.execute(
        """
        SELECT s.section_id, c.name AS course_name, s.capacity, s.enrolled_count
        FROM class_sections s
        JOIN courses c ON c.course_id = s.course_id
        WHERE s.status='active'
        """
    ).fetchall()
    my_enrollments = db.execute(
        """
        SELECT e.enrollment_id, c.name AS course_name, e.status, IFNULL(e.waitlist_position, '-') AS waitlist_position
        FROM enrollments e
        JOIN class_sections s ON s.section_id = e.section_id
        JOIN courses c ON c.course_id = s.course_id
        WHERE e.student_id = ?
        """,
        (user["user_id"],),
    ).fetchall()
    return render_template("student_register.html", sections=sections, enrollments=my_enrollments, sem=sem, user=user)


@app.route("/instructor/waitlist", methods=["GET", "POST"])
def instructor_waitlist():
    if not role_required("instructor"):
        return redirect(url_for("login"))
    db = get_db()
    user = current_user()
    if request.method == "POST":
        enrollment_id = int(request.form["enrollment_id"])
        row = db.execute(
            """
            SELECT e.enrollment_id, e.section_id, cs.instructor_id
            FROM enrollments e
            JOIN class_sections cs ON cs.section_id = e.section_id
            WHERE e.enrollment_id = ? AND e.status='waitlisted'
            """,
            (enrollment_id,),
        ).fetchone()
        if row and row["instructor_id"] == user["user_id"]:
            db.execute("UPDATE enrollments SET status='enrolled', waitlist_position=NULL WHERE enrollment_id=?", (enrollment_id,))
            db.execute("UPDATE class_sections SET enrolled_count = enrolled_count + 1 WHERE section_id=?", (row["section_id"],))
            db.commit()
            flash("Waitlisted student admitted.", "success")
        else:
            flash("Cannot admit this record.", "error")
        return redirect(request.url)

    waitlisted = db.execute(
        """
        SELECT e.enrollment_id, u.email AS student_email, c.name AS course_name, e.waitlist_position
        FROM enrollments e
        JOIN users u ON u.user_id = e.student_id
        JOIN class_sections s ON s.section_id = e.section_id
        JOIN courses c ON c.course_id = s.course_id
        WHERE e.status='waitlisted' AND s.instructor_id=?
        ORDER BY e.waitlist_position ASC
        """,
        (user["user_id"],),
    ).fetchall()
    return render_template("instructor_waitlist.html", waitlisted=waitlisted, user=user)


@app.route("/student/review", methods=["GET", "POST"])
def student_review():
    if not role_required("student"):
        return redirect(url_for("login"))
    db = get_db()
    user = current_user()
    if request.method == "POST":
        enrollment_id = int(request.form["enrollment_id"])
        stars = int(request.form["stars"])
        text = request.form["text"].strip()
        taboo_words = [r["word"] for r in db.execute("SELECT word FROM taboo_words").fetchall()]
        lowered = text.lower()
        taboo_hits = sum(1 for word in taboo_words if word in lowered)
        published = 1
        if taboo_hits >= 3:
            published = 0
            issue_warning(db, user["user_id"], "Review contains 3+ taboo words", "review")
            issue_warning(db, user["user_id"], "Review contains 3+ taboo words", "review")
            flash("Review blocked (3+ taboo words). Two warnings issued.", "error")
        elif taboo_hits >= 1:
            for word in taboo_words:
                text = text.replace(word, "*" * len(word)).replace(word.capitalize(), "*" * len(word))
            issue_warning(db, user["user_id"], "Review contains taboo language", "review")
            flash("Review published with masking. One warning issued.", "info")
        else:
            flash("Review published.", "success")
        db.execute(
            "INSERT INTO reviews (enrollment_id, stars, text, published, taboo_count) VALUES (?,?,?,?,?)",
            (enrollment_id, stars, text, published, taboo_hits),
        )
        db.commit()
        return redirect(request.url)

    enrollments = db.execute(
        """
        SELECT e.enrollment_id, c.name AS course_name
        FROM enrollments e
        JOIN class_sections s ON s.section_id = e.section_id
        JOIN courses c ON c.course_id = s.course_id
        WHERE e.student_id = ? AND e.status='enrolled'
        """,
        (user["user_id"],),
    ).fetchall()
    return render_template("student_review.html", enrollments=enrollments, user=user)


@app.route("/instructor/grades", methods=["GET", "POST"])
def instructor_grades():
    if not role_required("instructor"):
        return redirect(url_for("login"))
    db = get_db()
    user = current_user()
    sem = db.execute("SELECT * FROM semesters ORDER BY semester_id DESC LIMIT 1").fetchone()
    if request.method == "POST":
        if sem["phase"] != "grading":
            flash("Grades can only be submitted during grading phase.", "error")
            return redirect(request.url)
        enrollment_id = int(request.form["enrollment_id"])
        letter = request.form["letter_grade"]
        points_map = {"A": 4.0, "B": 3.0, "C": 2.0, "D": 1.0, "F": 0.0}
        points = points_map.get(letter, 0.0)
        db.execute("INSERT INTO grade_records (enrollment_id, letter_grade, grade_points) VALUES (?,?,?)", (enrollment_id, letter, points))
        db.execute("UPDATE enrollments SET status='completed' WHERE enrollment_id=?", (enrollment_id,))
        db.commit()
        flash("Grade submitted.", "success")
        return redirect(request.url)

    enrollments = db.execute(
        """
        SELECT e.enrollment_id, u.email AS student_email, c.name AS course_name
        FROM enrollments e
        JOIN class_sections s ON s.section_id = e.section_id
        JOIN users u ON u.user_id = e.student_id
        JOIN courses c ON c.course_id = s.course_id
        WHERE s.instructor_id = ? AND e.status='enrolled'
        """,
        (user["user_id"],),
    ).fetchall()
    return render_template("instructor_grades.html", enrollments=enrollments, sem=sem, user=user)


@app.route("/complaints", methods=["GET", "POST"])
def complaints():
    user = current_user()
    if user is None:
        return redirect(url_for("login"))
    db = get_db()
    if request.method == "POST":
        if "target_id" in request.form:
            target_id = int(request.form["target_id"])
            if target_id == user["user_id"]:
                flash("You cannot file a complaint against yourself.", "error")
                return redirect(request.url)
            db.execute(
                "INSERT INTO complaints (filed_by, target_id, description, requested_action) VALUES (?,?,?,?)",
                (user["user_id"], target_id, request.form["description"], request.form["requested_action"]),
            )
            db.commit()
            flash("Complaint filed.", "success")
        elif role_required("registrar"):
            complaint_id = int(request.form["complaint_id"])
            resolution = request.form["resolution"]
            action = request.form["action"]
            row = db.execute("SELECT * FROM complaints WHERE complaint_id=?", (complaint_id,)).fetchone()
            if row:
                if action == "warn":
                    issue_warning(db, row["target_id"], "Complaint resolved with warning", "complaint")
                elif action == "suspend":
                    db.execute("UPDATE users SET status='suspended' WHERE user_id=?", (row["target_id"],))
                db.execute(
                    "UPDATE complaints SET status='resolved', resolution=?, resolved_by=? WHERE complaint_id=?",
                    (resolution, user["user_id"], complaint_id),
                )
                db.commit()
                flash("Complaint resolved.", "success")
        return redirect(request.url)

    targets = db.execute("SELECT user_id, email, role FROM users WHERE user_id != ?", (user["user_id"],)).fetchall()
    all_complaints = db.execute(
        """
        SELECT c.*, f.email AS filer_email, t.email AS target_email
        FROM complaints c
        JOIN users f ON f.user_id = c.filed_by
        JOIN users t ON t.user_id = c.target_id
        ORDER BY c.complaint_id DESC
        """
    ).fetchall()
    return render_template("complaints.html", targets=targets, complaints=all_complaints, user=user)


@app.route("/ai", methods=["GET", "POST"])
def ai_assistant():
    user = current_user()
    role = user["role"] if user else "visitor"
    answer = None
    warning = False
    sources = []
    if request.method == "POST":
        q = request.form["question"].strip().lower()
        db = get_db()
        docs = db.execute(
            """
            SELECT * FROM ai_knowledge_documents
            WHERE role_scope IN ('public', ?)
            """,
            (role,),
        ).fetchall()
        for d in docs:
            if any(token in d["content"].lower() for token in q.split()):
                answer = d["content"]
                sources.append(d["title"])
                break
        if answer is None:
            warning = True
            answer = "Fallback response: I could not confidently ground this answer in local knowledge documents."
    return render_template("ai_assistant.html", user=user, role=role, answer=answer, warning=warning, sources=sources)


@app.route("/health")
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
