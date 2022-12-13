import os
from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.security import check_password_hash, generate_password_hash
import datetime

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""

    user_id = session["user_id"]
    transactions_db = db.execute("SELECT symbol, SUM(shares) AS shares FROM transactions WHERE user_id = ? GROUP BY symbol", user_id)

    cash_db = db.execute("SELECT cash FROM users WHERE id = ?", user_id)
    cash = cash_db[0]["cash"]

    symbol_db = db.execute("SELECT symbol FROM transactions WHERE user_id = ? GROUP BY symbol", user_id)

    total = cash
    for a in range(len(symbol_db)):
        transactions_db[a]["price"] = lookup(symbol_db[a]["symbol"].upper())["price"]
        transactions_db[a]["total"] = transactions_db[a]["shares"] * transactions_db[a]["price"]

        total += transactions_db[a]["total"]


    return render_template("index.html", template = transactions_db, cash = cash, total = total)




@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "GET":
        return render_template("buy.html")

    else:
        symbol = request.form.get("symbol")
        quantity = request.form.get("shares")

        if not symbol:
            return apology("Input Symbol")

        stock = lookup(symbol.upper())
        if stock == None:
            return apology("Stock Does Not Exist")

        if quantity.isnumeric() == False:
            return apology("Must Give An Interger")

        quantity = int(quantity)

        if quantity < 0:
            return apology("Must Give Positive Interger")



        purchase_price = stock["price"] * quantity

        user_id = session["user_id"]

        user_cash = db.execute("SELECT cash FROM users WHERE id = :id", id = user_id)

        if purchase_price > user_cash[0]["cash"]:
            return apology("Not Enough Cash")

        update_cash = user_cash[0]["cash"] - purchase_price
        db.execute("UPDATE users SET cash = ? WHERE id =?", update_cash, user_id)

        date = datetime.datetime.now()

        db.execute("INSERT INTO transactions (user_id, symbol, shares, price, time) VALUES(?,?,?,?,?)", user_id, stock["symbol"], quantity, stock["price"], date)


        flash("Stocks have been bought!")
        return redirect("/")




@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    user_id = session["user_id"]
    history_db = db.execute("SELECT * FROM transactions WHERE user_id =?", user_id)
    return render_template("history.html", template = history_db)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method == "GET":
        return render_template("quote.html")

    else:

        symbol = request.form.get("symbol")

        if not symbol:
            return apology("Must Give Symbol")

        stock = lookup(symbol.upper())

        if stock == None:
            return apology("Stock Does Not Exist")

        return render_template("quoted.html", name = stock["name"], price = stock["price"], symbol = stock["symbol"])



@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "GET":
        return render_template("register.html")

    else:
        username = request.form.get("username")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")

        if not username:
            return apology("Must give username")

        if not password:
            return apology("Must give password")

        if not confirmation:
            return apology("Must give confirmation")

        if password != confirmation:
            return apology("Passwords do not match")

        hash = generate_password_hash(password)
        try:
            new_user = db.execute("INSERT INTO users (username, hash) VALUES(?, ?)", username, hash)

        except:
            return apology("Username Already Exists")

        session["user_id"] = new_user

        return redirect("/")



@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    if request.method == "GET":
        user_id = session["user_id"]
        portfolio_dbs = db.execute("SELECT symbol FROM transactions WHERE user_id = ? GROUP BY symbol HAVING sum(shares) > 0", user_id)
        portfolio_db =[]
        for row in portfolio_dbs:
            portfolio_db.append(row["symbol"])
        return render_template("sell.html", portfolio =  portfolio_db)


    else:
            symbol = request.form.get("symbol")
            quantity = request.form.get("shares")
            stock = lookup(symbol.upper())

            quantity = int(quantity)

            if quantity < 0:
                return apology("Must Give Positive Interger")


            purchase_price = stock["price"] * quantity

            shares_db = db.execute("SELECT shares FROM transactions WHERE symbol =?", stock["symbol"])
            if shares_db[0]["shares"] < quantity:
                return apology("Not enough Stocks")

            user_id = session["user_id"]

            user_cash = db.execute("SELECT cash FROM users WHERE id = :id", id = user_id)

            update_cash = user_cash[0]["cash"] + purchase_price
            db.execute("UPDATE users SET cash = ? WHERE id =?", update_cash, user_id)

            date = datetime.datetime.now()

            db.execute("INSERT INTO transactions (user_id, symbol, shares, price, time) VALUES(?,?,?,?,?)", user_id, stock["symbol"], -abs(quantity), stock["price"], date)

            flash("Stocks have been Sold!")
            return redirect("/")




