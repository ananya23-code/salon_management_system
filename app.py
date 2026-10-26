
import os
from flask import Flask, render_template, request, redirect, url_for, flash
import mysql.connector
from mysql.connector import Error

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "local-development-key")

DB_CONFIG = {
    "host": os.environ.get("DB_HOST", "localhost"),
    "port": int(os.environ.get("DB_PORT", "3306")),
    "user": os.environ.get("DB_USER", "root"),
    "password": os.environ.get("DB_PASSWORD", ""),
    "database": os.environ.get("DB_NAME", "salon_management"),
    "ssl_disabled": False
}


def get_db_connection():
    return mysql.connector.connect(**DB_CONFIG)


def get_dashboard_data():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        counts = {}

        for table, key in [
            ("customers", "customers"),
            ("employees", "employees"),
            ("services", "services"),
            ("appointments", "appointments"),
            ("payments", "payments")
        ]:
            cursor.execute(f"SELECT COUNT(*) AS total FROM {table}")
            counts[key] = cursor.fetchone()["total"]

        cursor.execute("""
            SELECT service_id, service_name, price,
                   duration_minutes, description
            FROM services
            ORDER BY service_name
        """)
        services = cursor.fetchall()

        cursor.execute("""
            SELECT customer_id, full_name, phone
            FROM customers
            ORDER BY full_name
        """)
        customers = cursor.fetchall()

        cursor.execute("""
            SELECT employee_id, full_name, job_role
            FROM employees
            ORDER BY full_name
        """)
        employees = cursor.fetchall()

        return counts, services, customers, employees

    finally:
        cursor.close()
        conn.close()


@app.route("/")
def dashboard():
    search = request.args.get("search", "").strip()
    date_filter = request.args.get("date", "").strip()
    status_filter = request.args.get("status", "").strip()
    service_filter = request.args.get("service_id", "").strip()

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        counts = {}

        for table, key in [
            ("customers", "customers"),
            ("employees", "employees"),
            ("services", "services"),
            ("appointments", "appointments"),
            ("payments", "payments")
        ]:
            cursor.execute(f"SELECT COUNT(*) AS total FROM {table}")
            counts[key] = cursor.fetchone()["total"]

        cursor.execute("""
            SELECT service_id, service_name, price,
                   duration_minutes, description
            FROM services
            ORDER BY service_name
        """)
        services = cursor.fetchall()

        cursor.execute("""
            SELECT customer_id, full_name, phone
            FROM customers
            ORDER BY full_name
        """)
        customers = cursor.fetchall()

        cursor.execute("""
            SELECT employee_id, full_name, job_role
            FROM employees
            ORDER BY full_name
        """)
        employees = cursor.fetchall()

        sql = """
            SELECT
                a.appointment_id,
                a.appointment_date,
                a.appointment_time,
                a.status,
                c.full_name AS customer_name,
                c.phone AS customer_phone,
                e.full_name AS employee_name,
                s.service_name,
                s.price
            FROM appointments a
            JOIN customers c ON a.customer_id = c.customer_id
            JOIN employees e ON a.employee_id = e.employee_id
            JOIN services s ON a.service_id = s.service_id
            WHERE 1 = 1
        """
        params = []

        if search:
            sql += """
                AND (
                    c.full_name LIKE %s
                    OR e.full_name LIKE %s
                    OR s.service_name LIKE %s
                    OR c.phone LIKE %s
                )
            """
            term = f"%{search}%"
            params.extend([term, term, term, term])

        if date_filter:
            sql += " AND a.appointment_date = %s"
            params.append(date_filter)

        if status_filter:
            sql += " AND a.status = %s"
            params.append(status_filter)

        if service_filter.isdigit():
            sql += " AND a.service_id = %s"
            params.append(int(service_filter))

        sql += """
            ORDER BY a.appointment_date DESC,
                     a.appointment_time DESC
            LIMIT 100
        """

        cursor.execute(sql, params)
        appointments = cursor.fetchall()

        return render_template(
            "index.html",
            counts=counts,
            services=services,
            customers=customers,
            employees=employees,
            appointments=appointments,
            search=search,
            date_filter=date_filter,
            status_filter=status_filter,
            service_filter=service_filter
        )

    finally:
        cursor.close()
        conn.close()


@app.route("/add-customer", methods=["POST"])
def add_customer():
    full_name = request.form.get("full_name", "").strip()
    phone = request.form.get("phone", "").strip()
    email = request.form.get("email", "").strip() or None
    gender = request.form.get("gender", "").strip() or None

    if not full_name or not phone:
        flash("Full name and phone number are required.", "error")
        return redirect(url_for("dashboard") + "#customer-form")

    conn = None
    cursor = None

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO customers (full_name, phone, email, gender)
            VALUES (%s, %s, %s, %s)
        """, (full_name, phone, email, gender))

        conn.commit()
        flash("Customer registered successfully!", "success")

    except Error as exc:
        if conn:
            conn.rollback()

        if getattr(exc, "errno", None) == 1062:
            flash(
                "That phone number or email is already registered.",
                "error"
            )
        else:
            app.logger.exception("Could not register customer")
            flash(
                "Could not register customer. Check your database settings.",
                "error"
            )

    finally:
        if cursor:
            cursor.close()
        if conn and conn.is_connected():
            conn.close()

    return redirect(url_for("dashboard") + "#customer-form")


@app.route("/add-appointment", methods=["POST"])
def add_appointment():
    customer_id = request.form.get("customer_id", "").strip()
    employee_id = request.form.get("employee_id", "").strip()
    service_id = request.form.get("service_id", "").strip()
    appointment_date = request.form.get("appointment_date", "").strip()
    appointment_time = request.form.get("appointment_time", "").strip()

    if not all([
        customer_id,
        employee_id,
        service_id,
        appointment_date,
        appointment_time
    ]):
        flash("Please complete every appointment field.", "error")
        return redirect(url_for("dashboard") + "#appointment-form")

    conn = None
    cursor = None

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO appointments
                (customer_id, employee_id, service_id,
                 appointment_date, appointment_time, status)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (
            int(customer_id),
            int(employee_id),
            int(service_id),
            appointment_date,
            appointment_time,
            "Booked"
        ))

        conn.commit()
        flash("Appointment booked successfully!", "success")

    except Error as exc:
        if conn:
            conn.rollback()

        if getattr(exc, "errno", None) == 1062:
            flash(
                "This employee already has an appointment at that date and time.",
                "error"
            )
        else:
            app.logger.exception("Could not book appointment")
            flash(
                "Could not book appointment. Check the selected records and database.",
                "error"
            )

    except ValueError:
        flash(
            "Please select valid customer, employee, and service records.",
            "error"
        )

    finally:
        if cursor:
            cursor.close()
        if conn and conn.is_connected():
            conn.close()

    return redirect(url_for("dashboard") + "#appointment-form")


if __name__ == "__main__":
    app.run(debug=True)
