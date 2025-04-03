import base64
from functools import wraps
from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash,
    current_app,
)

auth_bp = Blueprint("auth", __name__)


# A simple decorator to protect routes
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("logged_in"):
            flash("Please log in to access this page.", "warning")
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)

    return decorated_function


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        # Create token: "username:password" then base64 encode it
        token = f"{username}:{password}"
        encoded_token = base64.b64encode(token.encode("utf-8")).decode("utf-8")
        expected_token = current_app.config.get("NEW_EMAG_API_KEY")
        if encoded_token == expected_token:
            session["logged_in"] = True
            flash("Logged in successfully.", "success")
            return redirect(url_for("auth.dashboard"))
        else:
            flash("Invalid credentials. Please try again.", "danger")
    if session.get("logged_in"):
        return redirect(url_for("auth.dashboard"))

    return render_template("login.html")


@auth_bp.route("/logout")
@login_required
def logout():
    session.pop("logged_in", None)
    flash("Logged out successfully.", "success")
    return redirect(url_for("auth.login"))


# A placeholder dashboard route that requires authentication.
@auth_bp.route("/dashboard")
@login_required
def dashboard():
    return render_template("dashboard.html")


# Create an index route (or view) to redirect to the login page
@auth_bp.route("/")
def index():
    return redirect(url_for("auth.dashboard"))
