from flask import Flask, render_template, request, session, redirect
import os
from werkzeug.utils import secure_filename
import mysql.connector

app = Flask(__name__)

# =========================================================
# SECRET KEY AND UPLOAD FOLDER
# =========================================================

app.secret_key = "student_management_secret_key"

UPLOAD_FOLDER = "uploads"

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)


# =========================================================
# MYSQL CONNECTION
# =========================================================

def get_db_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="9210",
        database="student_management"
    )


# =========================================================
# HOME PAGE
# =========================================================

@app.route("/")
def home():
    return render_template("index.html")


# =========================================================
# STUDENT REGISTRATION
# =========================================================

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        name = request.form["name"]
        email = request.form["email"]
        password = request.form["password"]
        course = request.form["course"]

        db = get_db_connection()
        cursor = db.cursor()

        sql = """
            INSERT INTO students (name, email, password, course)
            VALUES (%s, %s, %s, %s)
        """

        values = (name, email, password, course)

        cursor.execute(sql, values)
        db.commit()

        cursor.close()
        db.close()

        return "Registration successful! <a href='/login'>Login here</a>"

    return render_template("register.html")


# =========================================================
# STUDENT LOGIN
# =========================================================

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form["email"]
        password = request.form["password"]

        db = get_db_connection()
        cursor = db.cursor()

        sql = """
            SELECT * FROM students
            WHERE email = %s AND password = %s
        """

        cursor.execute(sql, (email, password))

        student = cursor.fetchone()

        cursor.close()
        db.close()

        if student:

            # Clear any existing faculty session
            session.pop("faculty_id", None)
            session.pop("faculty_name", None)

            # Create student session
            session["student_id"] = student[0]

            return redirect("/dashboard")

        return "Invalid email or password."

    return render_template("login.html")


# =========================================================
# FACULTY LOGIN
# =========================================================

@app.route("/faculty-login", methods=["GET", "POST"])
def faculty_login():

    if request.method == "POST":

        email = request.form["email"]
        password = request.form["password"]

        db = get_db_connection()
        cursor = db.cursor()

        sql = """
            SELECT * FROM faculty
            WHERE email = %s AND password = %s
        """

        cursor.execute(sql, (email, password))

        faculty = cursor.fetchone()

        cursor.close()
        db.close()

        if faculty:

            # Clear any existing student session
            session.pop("student_id", None)

            # Create faculty session
            session["faculty_id"] = faculty[0]
            session["faculty_name"] = faculty[1]

            return redirect("/faculty-dashboard")

        return "Invalid faculty email or password."

    return render_template("faculty_login.html")


# =========================================================
# STUDENT DASHBOARD
# =========================================================

@app.route("/dashboard")
def dashboard():

    if "student_id" not in session:
        return redirect("/login")

    # Prevent faculty from accessing student dashboard
    if "faculty_id" in session:
        return redirect("/faculty-dashboard")

    db = get_db_connection()
    cursor = db.cursor()

    sql = """
        SELECT * FROM students
        WHERE id = %s
    """

    cursor.execute(sql, (session["student_id"],))

    student = cursor.fetchone()

    cursor.close()
    db.close()

    if student:

        return render_template(
            "dashboard.html",
            name=student[1]
        )

    return redirect("/login")


# =========================================================
# FACULTY DASHBOARD
# =========================================================

@app.route("/faculty-dashboard")
def faculty_dashboard():

    if "faculty_id" not in session or "student_id" in session:
        session.pop("student_id", None)
        return redirect("/faculty-login")

    return render_template(
        "faculty_dashboard.html",
        name=session["faculty_name"]
    )


# =========================================================
# STUDENT PROFILE
# =========================================================

@app.route("/profile")
def profile():

    if "student_id" not in session:
        return redirect("/login")

    db = get_db_connection()
    cursor = db.cursor()

    sql = """
        SELECT * FROM students
        WHERE id = %s
    """

    cursor.execute(sql, (session["student_id"],))

    student = cursor.fetchone()

    cursor.close()
    db.close()

    if student:

        return render_template(
            "profile.html",
            student=student
        )

    return redirect("/login")


# =========================================================
# STUDENT ATTENDANCE VIEW
# =========================================================

@app.route("/my_attendance")
def my_attendance():

    # Only logged-in students can access
    if "student_id" not in session:
        return redirect("/login")

    db = get_db_connection()
    cursor = db.cursor()

    # Get attendance records for logged-in student
    cursor.execute("""
        SELECT date, status
        FROM attendance
        WHERE student_id = %s
        ORDER BY date DESC
    """, (session["student_id"],))

    attendance_records = cursor.fetchall()

    cursor.close()
    db.close()

    # Calculate attendance
    total_days = len(attendance_records)

    present_days = sum(
        1 for record in attendance_records
        if record[1] == "Present"
    )

    if total_days > 0:
        percentage = round(
            (present_days / total_days) * 100, 2
        )
    else:
        percentage = 0

    return render_template(
        "my_attendance.html",
        attendance_records=attendance_records,
        total_days=total_days,
        present_days=present_days,
        percentage=percentage
    )


# =========================================================
# FACULTY TAKE / EDIT ATTENDANCE
# =========================================================

@app.route("/faculty-attendance", methods=["GET", "POST"])
def faculty_attendance():

    # Only faculty can access this page
    if "faculty_id" not in session or "student_id" in session:
        session.pop("student_id", None)
        return redirect("/faculty-login")

    db = get_db_connection()
    cursor = db.cursor()

    # -----------------------------------------------------
    # SAVE / UPDATE ATTENDANCE
    # -----------------------------------------------------

    if request.method == "POST":

        attendance_date = request.form["date"]

        # Get all students
        cursor.execute("""
            SELECT id, name, email, course
            FROM students
            ORDER BY name
        """)

        students = cursor.fetchall()

        for student in students:

            student_id = student[0]

            status = request.form.get(
                f"status_{student_id}"
            )

            # Check if attendance already exists
            cursor.execute("""
                SELECT id
                FROM attendance
                WHERE student_id = %s
                AND date = %s
            """, (
                student_id,
                attendance_date
            ))

            existing = cursor.fetchone()

            if existing:

                # Update existing attendance
                cursor.execute("""
                    UPDATE attendance
                    SET status = %s
                    WHERE id = %s
                """, (
                    status,
                    existing[0]
                ))

            else:

                # Insert new attendance
                cursor.execute("""
                    INSERT INTO attendance
                    (student_id, date, status)
                    VALUES (%s, %s, %s)
                """, (
                    student_id,
                    attendance_date,
                    status
                ))

        db.commit()

        cursor.close()
        db.close()

        # Return to same date after saving
        return redirect(
            f"/faculty-attendance?date={attendance_date}"
        )

    # -----------------------------------------------------
    # GET SELECTED DATE
    # -----------------------------------------------------

    selected_date = request.args.get("date")

    # Get all students
    cursor.execute("""
        SELECT id, name, email, course
        FROM students
        ORDER BY name
    """)

    students = cursor.fetchall()

    # -----------------------------------------------------
    # GET EXISTING ATTENDANCE
    # -----------------------------------------------------

    attendance_data = {}

    if selected_date:

        cursor.execute("""
            SELECT student_id, status
            FROM attendance
            WHERE date = %s
        """, (selected_date,))

        records = cursor.fetchall()

        for record in records:
            attendance_data[record[0]] = record[1]

    cursor.close()
    db.close()

    return render_template(
        "faculty_attendance.html",
        students=students,
        attendance_data=attendance_data,
        selected_date=selected_date
    )


# =========================================================
# MARKS
# =========================================================

@app.route("/marks")
def marks():

    if "student_id" not in session:
        return redirect("/login")

    db = get_db_connection()
    cursor = db.cursor()

    sql = """
        SELECT subject, marks
        FROM marks
        WHERE student_id = %s
        ORDER BY subject
    """

    cursor.execute(sql, (session["student_id"],))

    marks_records = cursor.fetchall()

    cursor.close()
    db.close()

    return render_template(
        "marks.html",
        marks=marks_records
    )


# =========================================================
# DOCUMENTS
# =========================================================

@app.route("/documents")
def documents():

    if "student_id" not in session:
        return redirect("/login")

    db = get_db_connection()
    cursor = db.cursor()

    sql = """
        SELECT filename, upload_date
        FROM documents
        WHERE student_id = %s
        ORDER BY upload_date DESC
    """

    cursor.execute(sql, (session["student_id"],))

    documents_records = cursor.fetchall()

    cursor.close()
    db.close()

    return render_template(
        "documents.html",
        documents=documents_records
    )


# =========================================================
# UPLOAD DOCUMENT
# =========================================================

@app.route("/upload", methods=["POST"])
def upload():

    if "student_id" not in session:
        return redirect("/login")

    file = request.files.get("document")

    if file and file.filename:

        filename = secure_filename(file.filename)

        file.save(
            os.path.join(
                UPLOAD_FOLDER,
                filename
            )
        )

        db = get_db_connection()
        cursor = db.cursor()

        sql = """
            INSERT INTO documents
            (student_id, filename)
            VALUES (%s, %s)
        """

        cursor.execute(
            sql,
            (
                session["student_id"],
                filename
            )
        )

        db.commit()

        cursor.close()
        db.close()

    return redirect("/documents")


# =========================================================
# FACULTY VIEW STUDENTS
# =========================================================

@app.route("/faculty-students")
def faculty_students():

    # Only faculty can access this page
    if "faculty_id" not in session or "student_id" in session:
        session.pop("student_id", None)
        return redirect("/faculty-login")

    db = get_db_connection()
    cursor = db.cursor()

    cursor.execute("""
        SELECT id, name, email, course
        FROM students
        ORDER BY name
    """)

    students = cursor.fetchall()

    cursor.close()
    db.close()

    return render_template(
        "faculty_students.html",
        students=students
    )


# =========================================================
# FACULTY VIEW ATTENDANCE RECORDS
# =========================================================

@app.route("/faculty-attendance-records")
def faculty_attendance_records():

    # Only faculty can access this page
    if "faculty_id" not in session or "student_id" in session:
        session.pop("student_id", None)
        return redirect("/faculty-login")

    db = get_db_connection()
    cursor = db.cursor()

    cursor.execute("""
        SELECT
            students.name,
            students.email,
            students.course,
            attendance.date,
            attendance.status
        FROM attendance
        JOIN students
        ON attendance.student_id = students.id
        ORDER BY attendance.date DESC, students.name
    """)

    records = cursor.fetchall()

    cursor.close()
    db.close()

    return render_template(
        "faculty_attendance_records.html",
        records=records
    )


# =========================================================
# LOGOUT
# =========================================================

@app.route("/logout")
def logout():

    session.clear()

    return redirect("/login")


# =========================================================
# RUN FLASK
# =========================================================

if __name__ == "__main__":
    app.run(debug=True)