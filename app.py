from flask import Flask, render_template, request, redirect, url_for, session
import mysql.connector
from mysql.connector import IntegrityError
import os
from datetime import datetime, timedelta
from google import genai
from dotenv import load_dotenv


# =========================================================
# LOAD ENVIRONMENT VARIABLES
# =========================================================

load_dotenv()


# =========================================================
# FLASK APPLICATION
# =========================================================

app = Flask(__name__)
app.secret_key = "ems_secret_key"


# =========================================================
# GEMINI CLIENT
# =========================================================

gemini_api_key = os.getenv("GEMINI_API_KEY")

if not gemini_api_key:
    print("WARNING: GEMINI_API_KEY is missing from .env")

client = genai.Client(
    api_key=gemini_api_key
)


# =========================================================
# DATABASE CONNECTION
# =========================================================

def get_db_connection():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST", "localhost"),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME", "employee_management")
    )


# =========================================================
# LOGIN REQUIRED
# =========================================================

def login_required():
    return "user_id" in session


def admin_required():
    return (
        "user_id" in session
        and session.get("role") == "admin"
    )


# =========================================================
# LOGIN
# =========================================================

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        username = request.form["username"]
        password = request.form["password"]

        db = get_db_connection()
        cursor = db.cursor(dictionary=True)

        cursor.execute("""
            SELECT *
            FROM users
            WHERE username=%s AND password=%s
        """, (username, password))

        user = cursor.fetchone()

        cursor.close()
        db.close()

        if user:

            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["role"] = user["role"]
            session["employee_id"] = user["employee_id"]

            if user["role"] == "admin":
                return redirect(url_for("home"))

            return redirect(url_for("user_dashboard"))

        return render_template(
            "login.html",
            error="Invalid username or password"
        )

    return render_template("login.html")


# =========================================================
# LOGOUT
# =========================================================

@app.route("/logout")
def logout():

    session.clear()

    return redirect(url_for("login"))


# =========================================================
# ADMIN DASHBOARD
# =========================================================

@app.route("/")
def home():

    if not login_required():
        return redirect(url_for("login"))

    if session.get("role") != "admin":
        return redirect(url_for("user_dashboard"))

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    # Total employees
    cursor.execute("""
        SELECT COUNT(*) AS total
        FROM employees
    """)
    total_employees = cursor.fetchone()["total"]

    # Present today
    cursor.execute("""
        SELECT COUNT(*) AS total
        FROM attendance
        WHERE attendance_date = CURDATE()
        AND status = 'Present'
    """)
    present_today = cursor.fetchone()["total"]

    # Absent today
    cursor.execute("""
        SELECT COUNT(*) AS total
        FROM attendance
        WHERE attendance_date = CURDATE()
        AND status = 'Absent'
    """)
    absent_today = cursor.fetchone()["total"]

    # Total departments
    cursor.execute("""
        SELECT COUNT(*) AS total
        FROM departments
    """)
    total_departments = cursor.fetchone()["total"]

    # Recent employees
    cursor.execute("""
        SELECT *
        FROM employees
        ORDER BY id DESC
        LIMIT 5
    """)
    recent_employees = cursor.fetchall()

    cursor.close()
    db.close()

    return render_template(
        "index.html",
        total_employees=total_employees,
        present_today=present_today,
        absent_today=absent_today,
        total_departments=total_departments,
        recent_employees=recent_employees
    )


# =========================================================
# USER DASHBOARD
# =========================================================

@app.route("/user_dashboard")
def user_dashboard():

    if not login_required():
        return redirect(url_for("login"))

    if session.get("role") != "user":
        return redirect(url_for("home"))

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    cursor.execute("""
        SELECT COUNT(*) AS total
        FROM employees
    """)
    total_employees = cursor.fetchone()["total"]

    cursor.execute("""
        SELECT COUNT(*) AS total
        FROM departments
    """)
    total_departments = cursor.fetchone()["total"]

    cursor.close()
    db.close()

    return render_template(
        "user_dashboard.html",
        total_employees=total_employees,
        total_departments=total_departments
    )


# =========================================================
# MY PROFILE
# =========================================================

@app.route("/my_profile")
def my_profile():

    if not login_required():
        return redirect(url_for("login"))

    if session.get("role") != "user":
        return redirect(url_for("home"))

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    cursor.execute("""
        SELECT
            users.username,
            users.role,
            employees.employee_id,
            employees.name,
            employees.email,
            employees.phone,
            employees.department,
            employees.designation,
            employees.joining_date,
            employees.status
        FROM users
        LEFT JOIN employees
            ON users.employee_id = employees.id
        WHERE users.id = %s
    """, (session["user_id"],))

    profile = cursor.fetchone()

    cursor.close()
    db.close()

    if not profile:
        return "Employee profile not found."

    return render_template(
        "my_profile.html",
        profile=profile
    )


# =========================================================
# MY ATTENDANCE
# =========================================================

@app.route("/my_attendance")
def my_attendance():

    if not login_required():
        return redirect(url_for("login"))

    if session.get("role") != "user":
        return redirect(url_for("home"))

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    cursor.execute("""
        SELECT
            attendance.attendance_date,
            attendance.status,
            attendance.check_in,
            attendance.check_out
        FROM attendance
        INNER JOIN employees
            ON attendance.employee_id = employees.id
        INNER JOIN users
            ON users.employee_id = employees.id
        WHERE users.id = %s
        ORDER BY attendance.attendance_date DESC
    """, (session["user_id"],))

    attendance_records = cursor.fetchall()

    cursor.close()
    db.close()

    return render_template(
        "my_attendance.html",
        attendance_records=attendance_records
    )


# =========================================================
# MY DEPARTMENT
# =========================================================

@app.route("/my_department")
def my_department():

    if not login_required():
        return redirect(url_for("login"))

    if session.get("role") != "user":
        return redirect(url_for("home"))

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    cursor.execute("""
        SELECT
            departments.id,
            departments.name,
            departments.code,
            departments.head,
            departments.status
        FROM departments
        INNER JOIN employees
            ON departments.name = employees.department
        INNER JOIN users
            ON users.employee_id = employees.id
        WHERE users.id = %s
    """, (session["user_id"],))

    department = cursor.fetchone()

    cursor.close()
    db.close()

    return render_template(
        "my_department.html",
        department=department
    )


# =========================================================
# EMPLOYEES
# =========================================================

@app.route("/employees")
def employees():

    if not login_required():
        return redirect(url_for("login"))

    if not admin_required():
        return redirect(url_for("user_dashboard"))

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    cursor.execute("""
        SELECT *
        FROM employees
        ORDER BY id DESC
    """)

    employees_list = cursor.fetchall()

    cursor.close()
    db.close()

    return render_template(
        "employees.html",
        employees=employees_list
    )


# =========================================================
# ADD EMPLOYEE + AUTOMATIC USER ACCOUNT
# =========================================================

@app.route("/add_employee", methods=["GET", "POST"])
def add_employee():

    if not login_required():
        return redirect(url_for("login"))

    if not admin_required():
        return redirect(url_for("user_dashboard"))

    if request.method == "POST":

        employee_id = request.form["employee_id"]
        name = request.form["name"]
        email = request.form["email"]
        phone = request.form["phone"]
        department = request.form["department"]
        designation = request.form["designation"]
        joining_date = request.form["joining_date"]
        status = request.form["status"]

        # Automatic username
        first_name = name.strip().split()[0].lower()
        username = first_name

        db = get_db_connection()
        cursor = db.cursor(dictionary=True)

        cursor.execute("""
            SELECT id
            FROM users
            WHERE username=%s
        """, (username,))

        existing_username = cursor.fetchone()

        if existing_username:
            username = (
                first_name
                + employee_id.lower().replace("-", "")
            )

        # Automatic password
        password = employee_id

        try:

            cursor.execute("""
                INSERT INTO employees
                (
                    employee_id,
                    name,
                    email,
                    phone,
                    department,
                    designation,
                    joining_date,
                    status
                )
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
            """, (
                employee_id,
                name,
                email,
                phone,
                department,
                designation,
                joining_date,
                status
            ))

            db.commit()

            employee_database_id = cursor.lastrowid

            cursor.execute("""
                INSERT INTO users
                (
                    username,
                    password,
                    role,
                    employee_id
                )
                VALUES (%s,%s,'user',%s)
            """, (
                username,
                password,
                employee_database_id
            ))

            db.commit()

        except IntegrityError:

            db.rollback()

            cursor.close()
            db.close()

            return render_template(
                "add_employee.html",
                error="Employee ID or username already exists."
            )

        cursor.close()
        db.close()

        return render_template(
            "employee_created.html",
            employee_id=employee_id,
            name=name,
            username=username,
            password=password
        )

    return render_template("add_employee.html")


# =========================================================
# EDIT EMPLOYEE
# =========================================================

@app.route("/edit_employee/<int:id>", methods=["GET", "POST"])
def edit_employee(id):

    if not login_required():
        return redirect(url_for("login"))

    if not admin_required():
        return redirect(url_for("user_dashboard"))

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    if request.method == "POST":

        employee_id = request.form["employee_id"]
        name = request.form["name"]
        email = request.form["email"]
        phone = request.form["phone"]
        department = request.form["department"]
        designation = request.form["designation"]
        joining_date = request.form["joining_date"]
        status = request.form["status"]

        try:

            cursor.execute("""
                UPDATE employees
                SET
                    employee_id=%s,
                    name=%s,
                    email=%s,
                    phone=%s,
                    department=%s,
                    designation=%s,
                    joining_date=%s,
                    status=%s
                WHERE id=%s
            """, (
                employee_id,
                name,
                email,
                phone,
                department,
                designation,
                joining_date,
                status,
                id
            ))

            db.commit()

        except IntegrityError:

            db.rollback()

            cursor.close()
            db.close()

            return render_template(
                "edit_employee.html",
                employee={
                    "id": id,
                    "employee_id": employee_id,
                    "name": name,
                    "email": email,
                    "phone": phone,
                    "department": department,
                    "designation": designation,
                    "joining_date": joining_date,
                    "status": status
                },
                error="Employee ID already exists."
            )

        cursor.close()
        db.close()

        return redirect(url_for("employees"))

    cursor.execute("""
        SELECT *
        FROM employees
        WHERE id=%s
    """, (id,))

    employee = cursor.fetchone()

    cursor.close()
    db.close()

    if not employee:
        return redirect(url_for("employees"))

    return render_template(
        "edit_employee.html",
        employee=employee
    )


# =========================================================
# DELETE EMPLOYEE
# =========================================================

@app.route("/delete_employee/<int:id>")
def delete_employee(id):

    if not login_required():
        return redirect(url_for("login"))

    if not admin_required():
        return redirect(url_for("user_dashboard"))

    db = get_db_connection()
    cursor = db.cursor()

    try:

        cursor.execute("""
            DELETE FROM attendance
            WHERE employee_id=%s
        """, (id,))

        cursor.execute("""
            DELETE FROM ai_alerts
            WHERE employee_id=%s
        """, (id,))

        cursor.execute("""
            DELETE FROM users
            WHERE employee_id=%s
        """, (id,))

        cursor.execute("""
            DELETE FROM employees
            WHERE id=%s
        """, (id,))

        db.commit()

    except Exception as e:

        db.rollback()

        print(
            "Delete Employee Error:",
            e
        )

    finally:

        cursor.close()
        db.close()

    return redirect(url_for("employees"))


# =========================================================
# ATTENDANCE
# =========================================================

@app.route("/attendance")
def attendance():

    if not login_required():
        return redirect(url_for("login"))

    if not admin_required():
        return redirect(url_for("user_dashboard"))

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    cursor.execute("""
        SELECT
            attendance.id,
            employees.employee_id,
            employees.name,
            employees.department,
            attendance.attendance_date,
            attendance.status,
            attendance.check_in,
            attendance.check_out
        FROM attendance
        INNER JOIN employees
            ON attendance.employee_id = employees.id
        ORDER BY
            attendance.attendance_date DESC,
            attendance.id DESC
    """)

    attendance_records = cursor.fetchall()

    cursor.close()
    db.close()

    return render_template(
        "attendance.html",
        attendance_records=attendance_records
    )


# =========================================================
# MARK ATTENDANCE
# =========================================================

@app.route("/mark_attendance", methods=["POST"])
def mark_attendance():

    if not login_required():
        return redirect(url_for("login"))

    if not admin_required():
        return redirect(url_for("user_dashboard"))

    employee_code = request.form["employee_id"]
    attendance_date = request.form["attendance_date"]
    status = request.form["status"]

    check_in = request.form.get("check_in") or None
    check_out = request.form.get("check_out") or None

    # If not Present, time values should be empty
    if status != "Present":
        check_in = None
        check_out = None

    db = get_db_connection()
    cursor = db.cursor()

    try:

        # Find employee
        cursor.execute("""
            SELECT id
            FROM employees
            WHERE employee_id=%s
        """, (employee_code,))

        employee = cursor.fetchone()

        if not employee:
            return redirect(url_for("attendance"))

        database_employee_id = employee[0]

        # Check existing attendance
        cursor.execute("""
            SELECT id
            FROM attendance
            WHERE employee_id=%s
            AND attendance_date=%s
        """, (
            database_employee_id,
            attendance_date
        ))

        existing = cursor.fetchone()

        if existing:

            # Update
            cursor.execute("""
                UPDATE attendance
                SET
                    status=%s,
                    check_in=%s,
                    check_out=%s
                WHERE id=%s
            """, (
                status,
                check_in,
                check_out,
                existing[0]
            ))

        else:

            # Insert
            cursor.execute("""
                INSERT INTO attendance
                (
                    employee_id,
                    attendance_date,
                    status,
                    check_in,
                    check_out
                )
                VALUES (%s,%s,%s,%s,%s)
            """, (
                database_employee_id,
                attendance_date,
                status,
                check_in,
                check_out
            ))

        db.commit()

    except Exception as e:

        db.rollback()

        print(
            "Mark Attendance Error:",
            e
        )

    finally:

        cursor.close()
        db.close()

    return redirect(url_for("attendance"))


# =========================================================
# DEPARTMENTS
# =========================================================

@app.route("/departments")
def departments():

    if not login_required():
        return redirect(url_for("login"))

    if not admin_required():
        return redirect(url_for("user_dashboard"))

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    cursor.execute("""
        SELECT
            departments.id,
            departments.name,
            departments.code,
            departments.head,
            departments.status,
            COUNT(employees.id) AS employee_count
        FROM departments
        LEFT JOIN employees
            ON departments.name = employees.department
        GROUP BY
            departments.id,
            departments.name,
            departments.code,
            departments.head,
            departments.status
        ORDER BY departments.id DESC
    """)

    departments_list = cursor.fetchall()

    cursor.close()
    db.close()

    return render_template(
        "departments.html",
        departments=departments_list
    )


# =========================================================
# ADD DEPARTMENT
# =========================================================

@app.route("/add_department", methods=["GET", "POST"])
def add_department():

    if not login_required():
        return redirect(url_for("login"))

    if not admin_required():
        return redirect(url_for("user_dashboard"))

    if request.method == "POST":

        name = request.form["name"]
        code = request.form["code"]
        head = request.form["head"]
        status = request.form["status"]

        db = get_db_connection()
        cursor = db.cursor()

        try:

            cursor.execute("""
                INSERT INTO departments
                (
                    name,
                    code,
                    head,
                    status
                )
                VALUES (%s,%s,%s,%s)
            """, (
                name,
                code,
                head,
                status
            ))

            db.commit()

        except IntegrityError:

            db.rollback()

            cursor.close()
            db.close()

            return render_template(
                "add_department.html",
                error="Department code already exists."
            )

        cursor.close()
        db.close()

        return redirect(url_for("departments"))

    return render_template("add_department.html")


# =========================================================
# EDIT DEPARTMENT
# =========================================================

@app.route("/edit_department/<int:id>", methods=["GET", "POST"])
def edit_department(id):

    if not login_required():
        return redirect(url_for("login"))

    if not admin_required():
        return redirect(url_for("user_dashboard"))

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    if request.method == "POST":

        name = request.form["name"]
        code = request.form["code"]
        head = request.form["head"]
        status = request.form["status"]

        try:

            cursor.execute("""
                UPDATE departments
                SET
                    name=%s,
                    code=%s,
                    head=%s,
                    status=%s
                WHERE id=%s
            """, (
                name,
                code,
                head,
                status,
                id
            ))

            db.commit()

        except IntegrityError:

            db.rollback()

            cursor.close()
            db.close()

            return render_template(
                "edit_department.html",
                department={
                    "id": id,
                    "name": name,
                    "code": code,
                    "head": head,
                    "status": status
                },
                error="Department code already exists."
            )

        cursor.close()
        db.close()

        return redirect(url_for("departments"))

    cursor.execute("""
        SELECT *
        FROM departments
        WHERE id=%s
    """, (id,))

    department = cursor.fetchone()

    cursor.close()
    db.close()

    if not department:
        return redirect(url_for("departments"))

    return render_template(
        "edit_department.html",
        department=department
    )


# =========================================================
# DELETE DEPARTMENT
# =========================================================

@app.route("/delete_department/<int:id>")
def delete_department(id):

    if not login_required():
        return redirect(url_for("login"))

    if not admin_required():
        return redirect(url_for("user_dashboard"))

    db = get_db_connection()
    cursor = db.cursor()

    try:

        cursor.execute("""
            DELETE FROM departments
            WHERE id=%s
        """, (id,))

        db.commit()

    except Exception as e:

        db.rollback()

        print(
            "Delete Department Error:",
            e
        )

    finally:

        cursor.close()
        db.close()

    return redirect(url_for("departments"))


# =========================================================
# AI TOOL 1 - GET TODAY'S ATTENDANCE
# =========================================================

def get_today_attendance(employee_id: int) -> dict:

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    try:

        cursor.execute("""
            SELECT
                employees.id AS database_employee_id,
                employees.employee_id,
                employees.name,
                employees.email,
                employees.department,
                employees.designation,
                attendance.attendance_date,
                attendance.status,
                attendance.check_in,
                attendance.check_out
            FROM employees
            LEFT JOIN attendance
                ON employees.id = attendance.employee_id
                AND attendance.attendance_date = CURDATE()
            WHERE employees.id = %s
        """, (employee_id,))

        result = cursor.fetchone()

    finally:

        cursor.close()
        db.close()

    if not result:

        return {
            "found": False,
            "message": "Employee not found."
        }

    check_in = result.get("check_in")
    check_out = result.get("check_out")

    working_minutes = None

    # -----------------------------------------------------
    # CALCULATE WORKING TIME
    # -----------------------------------------------------

    if check_in is not None and check_out is not None:

        try:

            check_in_time = datetime.strptime(
                str(check_in),
                "%H:%M:%S"
            )

            check_out_time = datetime.strptime(
                str(check_out),
                "%H:%M:%S"
            )

            # Handle overnight shift
            if check_out_time < check_in_time:
                check_out_time += timedelta(days=1)

            difference = (
                check_out_time -
                check_in_time
            )

            working_minutes = int(
                difference.total_seconds() / 60
            )

        except Exception as e:

            print(
                "Working Time Calculation Error:",
                e
            )

    # Convert DB date/time values into strings
    for key, value in result.items():

        if value is not None:
            result[key] = str(value)

    result["working_minutes"] = working_minutes

    if working_minutes is not None:

        hours = working_minutes // 60
        minutes = working_minutes % 60

        result["working_time"] = (
            f"{hours} hours {minutes} minutes"
        )

    else:

        result["working_time"] = None

    return {
        "found": True,
        "attendance": result
    }


# =========================================================
# AI TOOL 2 - SAVE ATTENDANCE ALERT
# =========================================================

def save_ai_alert(
    employee_id: int,
    message: str,
    alert_type: str
) -> dict:

    db = get_db_connection()
    cursor = db.cursor()

    try:

        # Prevent duplicate same-day alert
        cursor.execute("""
            SELECT id
            FROM ai_alerts
            WHERE employee_id=%s
            AND alert_type=%s
            AND DATE(created_at)=CURDATE()
            LIMIT 1
        """, (
            employee_id,
            alert_type
        ))

        existing = cursor.fetchone()

        if existing:

            return {
                "success": True,
                "message": "Today's alert already exists."
            }

        cursor.execute("""
            INSERT INTO ai_alerts
            (
                employee_id,
                alert_type,
                message
            )
            VALUES (%s,%s,%s)
        """, (
            employee_id,
            alert_type,
            message
        ))

        db.commit()

    except Exception:

        db.rollback()
        raise

    finally:

        cursor.close()
        db.close()

    return {
        "success": True,
        "message": "Attendance alert saved successfully."
    }


# =========================================================
# GEMINI ATTENDANCE AGENT
# =========================================================

def run_attendance_agent(employee_id: int) -> str:

    # =====================================================
    # STEP 1: GET ATTENDANCE FROM MYSQL
    # =====================================================

    attendance_data = get_today_attendance(employee_id)

    if not attendance_data.get("found"):
        return "Employee record was not found."

    attendance = attendance_data.get("attendance")

    if not attendance:
        return "Today's attendance has not been recorded yet."

    employee_name = attendance.get(
        "name",
        "Employee"
    )

    status = attendance.get("status")
    check_in = attendance.get("check_in")
    check_out = attendance.get("check_out")
    working_minutes = attendance.get("working_minutes")
    working_time = attendance.get("working_time")

    # =====================================================
    # STEP 2: PREPARE ATTENDANCE INFORMATION
    # =====================================================

    attendance_text = f"""
Employee Name: {employee_name}
Employee ID: {attendance.get("employee_id")}
Date: {attendance.get("attendance_date")}
Status: {status}
Check-in: {check_in}
Check-out: {check_out}
Working Time: {working_time}
Required Working Time: 8 hours
"""

    # =====================================================
    # STEP 3: ASK GEMINI FOR FINAL RESPONSE
    # =====================================================

    prompt = f"""
You are an AI Attendance Assistant.

Analyze the attendance information below.

{attendance_text}

Rules:

1. Never invent information.
2. Required working time is 8 hours.
3. If today's attendance is not recorded, say so.
4. If status is Absent, explain that the employee is absent.
5. If status is Present but checkout is missing, explain that checkout is missing.
6. If check-in and check-out exist and working time is below 8 hours,
   calculate the exact shortage in hours and minutes.
7. If working time is 8 hours or more,
   congratulate the employee.
8. Keep the final response professional and short.
9. Use the real employee name.
10. Do not mention internal database details.
11. IMPORTANT: Never show total minutes, required minutes,
    or shortage minutes.
12. Only use hours and minutes in the final response.

Example:
"Hello Ahsan Imran,

On 2026-08-31, you worked 4 hours and 43 minutes.
As the required working time is 8 hours, you have a
shortage of 3 hours and 17 minutes."

Return ONLY the final message for the employee.
"""

    try:

        response = client.interactions.create(
            model="gemini-3.6-flash",
            input=prompt
        )

        message = response.output_text

        if not message:
            message = "Attendance analysis completed."

        # =================================================
        # STEP 4: SAVE ALERT IN DATABASE
        # =================================================

        if status == "Absent":

            save_ai_alert(
                employee_id=employee_id,
                message=message,
                alert_type="Absence"
            )

        elif (
            status == "Present"
            and not check_out
        ):

            save_ai_alert(
                employee_id=employee_id,
                message=message,
                alert_type="Missing Checkout"
            )

        elif (
            status == "Present"
            and working_minutes is not None
            and working_minutes < 480
        ):

            save_ai_alert(
                employee_id=employee_id,
                message=message,
                alert_type="Short Working Hours"
            )

        return message

    except Exception as e:

        print(
            "Gemini Attendance Agent Error:",
            e
        )

        raise


# =========================================================
# AI ATTENDANCE PAGE
# =========================================================

@app.route("/ai_attendance")
def ai_attendance():

    if not login_required():
        return redirect(url_for("login"))

    if session.get("role") != "user":
        return redirect(url_for("home"))

    employee_id = session.get("employee_id")

    if not employee_id:
        return (
            "Employee account is not linked "
            "to an employee record."
        )

    try:

        # Run AI analysis
        result = run_attendance_agent(
            int(employee_id)
        )

        # =================================================
        # GET ATTENDANCE FOR ALERT
        # =================================================

        attendance_data = get_today_attendance(
            int(employee_id)
        )

        alert_message = None
        alert_type = None

        if attendance_data.get("found"):

            attendance = attendance_data.get("attendance")

            if attendance:

                status = attendance.get("status")

                working_minutes = attendance.get(
                    "working_minutes"
                )

                check_out = attendance.get("check_out")

                # -----------------------------------------
                # ABSENT ALERT
                # -----------------------------------------

                if status == "Absent":

                    alert_type = "danger"

                    alert_message = (
                        "You are marked absent today."
                    )

                # -----------------------------------------
                # MISSING CHECKOUT ALERT
                # -----------------------------------------

                elif (
                    status == "Present"
                    and not check_out
                ):

                    alert_type = "warning"

                    alert_message = (
                        "Your check-out time has "
                        "not been recorded yet."
                    )

                # -----------------------------------------
                # SHORT WORKING HOURS ALERT
                # -----------------------------------------

                elif (
                    status == "Present"
                    and working_minutes is not None
                    and working_minutes < 480
                ):

                    shortage = 480 - working_minutes

                    shortage_hours = shortage // 60
                    shortage_minutes = shortage % 60

                    alert_type = "warning"

                    alert_message = (
                        "Your working hours are incomplete. "
                        f"You are short by "
                        f"{shortage_hours} hours "
                        f"and {shortage_minutes} minutes today."
                    )

        return render_template(
            "ai_attendance.html",
            result=result,
            alert_message=alert_message,
            alert_type=alert_type
        )

    except Exception as e:

        print(
            "AI Attendance Agent Error:",
            e
        )

        return render_template(
            "ai_attendance.html",
            result=(
                "The AI Attendance Agent could not "
                "process your attendance right now. "
                "Please try again."
            ),
            alert_message=None,
            alert_type=None
        )


# =========================================================
# RUN APPLICATION
# =========================================================

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)