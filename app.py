from flask import Flask, render_template, request, redirect, session, make_response
import sqlite3
import os

app = Flask(__name__)
app.secret_key = "your_secret_key_here"

DB_FILE = "expenses.db"


# -------------------- NO CACHE DECORATOR --------------------
def no_cache(view):
    def no_cache_wrapper(*args, **kwargs):
        response = make_response(view(*args, **kwargs))
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response
    no_cache_wrapper.__name__ = view.__name__
    return no_cache_wrapper


# -------------------- DATABASE SETUP --------------------
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS users(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            email TEXT UNIQUE,
            password TEXT
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS expenses(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount REAL,
            category TEXT,
            date TEXT,
            type TEXT DEFAULT 'expense',
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    """)

    conn.commit()
    conn.close()


# -------------------- HOME / DASHBOARD --------------------
@app.route('/')
@no_cache
def home():
    if 'user_id' not in session:
        return redirect('/login')

    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    c.execute("SELECT name FROM users WHERE id=?", (session['user_id'],))
    row = c.fetchone()
    user_name = row[0] if row else "User"

    c.execute(
        "SELECT amount, category, date FROM expenses WHERE user_id=? ORDER BY date DESC",
        (session['user_id'],)
    )
    expenses = c.fetchall()

    c.execute(
        "SELECT SUM(amount) FROM expenses WHERE user_id=? AND type='income'",
        (session['user_id'],)
    )
    total_income = c.fetchone()[0] or 0

    c.execute(
        "SELECT SUM(amount) FROM expenses WHERE user_id=? AND type='expense'",
        (session['user_id'],)
    )
    total_expense = c.fetchone()[0] or 0

    conn.close()

    return render_template(
        "index.html",
        name=user_name,
        expenses=expenses,
        total_income=total_income,
        total_expense=total_expense
    )


# -------------------- SIGNUP --------------------
@app.route('/signup', methods=['GET', 'POST'])
@no_cache
def signup():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')

        if not (name and email and password):
            return "Please fill all fields", 400

        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        try:
            c.execute(
                "INSERT INTO users (name, email, password) VALUES (?, ?, ?)",
                (name, email, password)
            )
            conn.commit()
        except sqlite3.IntegrityError:
            conn.close()
            return "User with this email already exists", 400

        conn.close()
        return redirect('/login')

    return render_template("signup.html")


# -------------------- LOGIN --------------------
@app.route('/login', methods=['GET', 'POST'])
@no_cache
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute(
            "SELECT * FROM users WHERE email=? AND password=?",
            (email, password)
        )
        user = c.fetchone()
        conn.close()

        if user:
            session['user_id'] = user[0]
            return redirect('/')
        else:
            return "Invalid Credentials", 401

    return render_template("login.html")


# -------------------- LOGOUT --------------------
@app.route('/logout')
@no_cache
def logout():
    session.clear()
    return redirect('/login')


# -------------------- ADD EXPENSE --------------------
@app.route('/add', methods=['GET', 'POST'])
@no_cache
def add_expense():
    if 'user_id' not in session:
        return redirect('/login')

    if request.method == 'POST':
        amount = request.form.get('amount')
        category = request.form.get('category')
        date = request.form.get('date')
        type_value = request.form.get('type')

        if not (amount and category and date):
            return "Please fill all fields", 400

        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute(
            "INSERT INTO expenses (user_id, amount, category, date, type) VALUES (?, ?, ?, ?, ?)",
            (session['user_id'], amount, category, date, type_value)
        )
        conn.commit()
        conn.close()

        return redirect('/')

    return render_template("add_expense.html")


# -------------------- VIEW EXPENSES --------------------
@app.route('/view')
@no_cache
def view_expenses():
    if 'user_id' not in session:
        return redirect('/login')

    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    c.execute("""
        SELECT amount, category, date 
        FROM expenses 
        WHERE user_id=? AND type='expense'
        ORDER BY date DESC
    """, (session['user_id'],))
    expenses = c.fetchall()

    c.execute("""
        SELECT strftime('%Y-%m', date) as month, SUM(amount)
        FROM expenses
        WHERE user_id=? AND type='expense'
        GROUP BY month
        ORDER BY month
    """, (session['user_id'],))
    chart_data = c.fetchall()

    conn.close()

    labels = [row[0] for row in chart_data]
    values = [row[1] for row in chart_data]

    return render_template(
        "view_expenses.html",
        expenses=expenses,
        labels=labels,
        values=values
    )


# -------------------- CHART DATA --------------------
@app.route('/chart-data')
def chart_data():
    if 'user_id' not in session:
        return {}

    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    c.execute("""
        SELECT category, SUM(amount)
        FROM expenses
        WHERE user_id=? AND type='expense'
        GROUP BY category
    """, (session['user_id'],))
    category_data = c.fetchall()

    c.execute("""
        SELECT date, SUM(amount)
        FROM expenses
        WHERE user_id=? AND type='expense'
        GROUP BY date
        ORDER BY date
    """, (session['user_id'],))
    date_data = c.fetchall()

    conn.close()

    return {
        "categories": [c[0] for c in category_data],
        "category_amounts": [c[1] for c in category_data],
        "dates": [d[0] for d in date_data],
        "date_amounts": [d[1] for d in date_data]
    }


# -------------------- ADMIN DASHBOARD --------------------
@app.route('/control-room')
@no_cache
def admin_dashboard():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    c.execute("SELECT COUNT(*) FROM users")
    total_users = c.fetchone()[0]

    c.execute("SELECT name, email FROM users")
    users_list = c.fetchall()

    conn.close()

    return render_template(
        "admin_dashboard.html",
        total_users=total_users,
        users_list=users_list
    )


# -------------------- RUN APP --------------------
if __name__ == "__main__":
    init_db()
    app.run(debug=True)
