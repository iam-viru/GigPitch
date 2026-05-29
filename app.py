import os
import secrets
from datetime import datetime, timedelta, timezone
from functools import wraps

from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash, check_password_hash

from database.db import (
    init_db, seed_db, get_user_by_email, create_user,
    create_reset_token, get_valid_reset_token, get_any_token_for_user,
    mark_token_used, cleanup_expired_tokens, update_user_password,
)
from utils.email import send_otp_email
from proposals.proposal_builder import (
    build_proposal, validate_proposal, save_proposal,
    get_proposal, get_all_proposals, get_approved_proposals,
    update_proposal_status, delete_proposal, seed_proposals,
    regenerate_proposal, build_refined_proposal, update_proposal_content,
)

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get("FLASK_ENV") == "production",
    PERMANENT_SESSION_LIFETIME=timedelta(hours=8),
)


@app.after_request
def set_no_cache(response):
    """Prevent browser from caching any HTML page — back button after logout shows nothing."""
    if "text/html" in response.content_type:
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        user = get_user_by_email(email)
        if user and user["password_hash"] and check_password_hash(user["password_hash"], password):
            session.clear()  # prevent session fixation
            session["user_id"] = user["id"]
            return redirect(url_for("index"))

        flash("Invalid email or password.", "danger")
        return render_template("login.html", email=email)

    return render_template("login.html", email="")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        title = request.form.get("title", "").strip()
        rate = request.form.get("rate", "").strip()
        experience = request.form.get("experience", "").strip()
        skills = request.form.get("skills", "").strip()
        upwork_url = request.form.get("upwork_url", "").strip()
        github_url = request.form.get("github_url", "").strip()
        signature = request.form.get("signature", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not all([name, title, rate, experience, skills, upwork_url, github_url, email, password]):
            flash("All fields except signature are required.", "danger")
            return render_template("register.html", form_data=request.form)

        if password != confirm_password:
            flash("Passwords do not match.", "danger")
            return render_template("register.html", form_data=request.form)

        if get_user_by_email(email):
            flash("An account with that email already exists.", "danger")
            return render_template("register.html", form_data=request.form)

        user_id = create_user(
            name, title, rate, experience, skills,
            upwork_url, github_url, signature, email,
            generate_password_hash(password),
        )
        session.clear()  # prevent session fixation
        session["user_id"] = user_id
        return redirect(url_for("index"))

    return render_template("register.html", form_data={})


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if session.get("user_id"):
        return redirect(url_for("index"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        cleanup_expired_tokens()

        user = get_user_by_email(email)
        if user:
            otp = str(secrets.randbelow(1_000_000)).zfill(6)
            expires_at = datetime.now(timezone.utc) + timedelta(minutes=15)
            create_reset_token(user["id"], otp, expires_at)
            try:
                send_otp_email(email, otp)
            except Exception as e:
                flash(f"Could not send email: {e}", "danger")
                return render_template("forgot-password.html")

        session["reset_email"] = email
        flash("If that email is registered, you'll receive an OTP shortly.", "info")
        return redirect(url_for("verify_otp"))

    return render_template("forgot-password.html")


@app.route("/verify-otp", methods=["GET", "POST"])
def verify_otp():
    email = session.get("reset_email")
    if not email:
        return redirect(url_for("forgot_password"))

    if request.method == "POST":
        otp = request.form.get("otp", "").strip()
        user = get_user_by_email(email)

        if user:
            token = get_valid_reset_token(user["id"], otp)
            if token:
                mark_token_used(token["id"])
                session["reset_user_id"] = user["id"]
                session.pop("reset_email", None)
                return redirect(url_for("reset_password"))

            # Give a specific message for expired vs wrong OTP
            stale = get_any_token_for_user(user["id"], otp)
            if stale and stale["used"] == 0:
                flash("OTP has expired. Please request a new one.", "warning")
            else:
                flash("Invalid OTP. Please check the code and try again.", "danger")
        else:
            flash("Invalid OTP. Please check the code and try again.", "danger")

        return render_template("verify-otp.html", email=email)

    return render_template("verify-otp.html", email=email)


@app.route("/reset-password", methods=["GET", "POST"])
def reset_password():
    user_id = session.get("reset_user_id")
    if not user_id:
        return redirect(url_for("forgot_password"))

    if request.method == "POST":
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")

        if len(password) < 8:
            flash("Password must be at least 8 characters.", "danger")
            return render_template("reset-password.html")

        if password != confirm:
            flash("Passwords do not match.", "danger")
            return render_template("reset-password.html")

        update_user_password(user_id, generate_password_hash(password))
        session.pop("reset_user_id", None)
        flash("Password updated. Please log in.", "success")
        return redirect(url_for("login"))

    return render_template("reset-password.html")


@app.route("/")
@login_required
def index():
    user_id = session["user_id"]
    proposals = get_all_proposals(user_id)
    status_filter = request.args.get("status", "")
    if status_filter:
        proposals = [p for p in proposals if p["status"] == status_filter]
    return render_template("index.html", proposals=proposals, status_filter=status_filter)


@app.route("/generate", methods=["GET", "POST"])
@login_required
def generate():
    if request.method == "POST":
        job_title = request.form.get("job_title", "").strip()
        job_description = request.form.get("job_description", "").strip()
        client_questions = request.form.get("client_questions", "").strip()

        if not job_title or not job_description:
            flash("Job title and description are required.", "danger")
            return render_template("generate.html", form_data=request.form)

        user_id = session["user_id"]

        try:
            job_data = {
                "title": job_title,
                "description": job_description,
                "client_questions": client_questions
            }
            proposal = build_proposal(user_id, job_data)
            validation = validate_proposal(proposal)

            proposal_id = save_proposal(user_id, proposal)

            for warning in validation.warnings:
                flash(f"Warning: {warning}", "warning")

            if not validation.is_valid:
                for error in validation.errors:
                    flash(f"Validation: {error}", "warning")

            return redirect(url_for("view_proposal", proposal_id=proposal_id))

        except Exception as e:
            flash(f"Error generating proposal: {str(e)}", "danger")
            return render_template("generate.html", form_data=request.form)

    return render_template("generate.html", form_data={})


@app.route("/proposal/<int:proposal_id>")
@login_required
def view_proposal(proposal_id):
    proposal = get_proposal(proposal_id)
    if not proposal:
        flash("Proposal not found.", "danger")
        return redirect(url_for("index"))
    return render_template("proposal.html", proposal=proposal)


@app.route("/proposal/<int:proposal_id>/approve", methods=["POST"])
@login_required
def approve(proposal_id):
    if update_proposal_status(proposal_id, "approved"):
        flash("Proposal approved and saved to history.", "success")
    else:
        flash("Could not approve proposal.", "danger")
    return redirect(url_for("view_proposal", proposal_id=proposal_id))


@app.route("/proposal/<int:proposal_id>/status", methods=["POST"])
@login_required
def update_status(proposal_id):
    new_status = request.form.get("status", "")
    if update_proposal_status(proposal_id, new_status):
        flash(f"Status updated to '{new_status}'.", "success")
    else:
        flash("Invalid status value.", "danger")
    return redirect(url_for("view_proposal", proposal_id=proposal_id))


@app.route("/history")
@login_required
def history():
    user_id = session["user_id"]
    proposals = get_approved_proposals(user_id)
    return render_template("history.html", proposals=proposals)


@app.route("/proposal/<int:proposal_id>/regenerate", methods=["POST"])
@login_required
def regenerate(proposal_id):
    try:
        new_proposal = regenerate_proposal(proposal_id)
        update_proposal_content(proposal_id, new_proposal)
        flash("Proposal regenerated with fresh content.", "success")
    except Exception as e:
        flash(f"Error regenerating proposal: {str(e)}", "danger")
    return redirect(url_for("view_proposal", proposal_id=proposal_id))


@app.route("/proposal/<int:proposal_id>/refine", methods=["POST"])
@login_required
def refine(proposal_id):
    change_request = request.form.get("change_request", "").strip()
    if not change_request:
        flash("Please describe what you'd like to change.", "warning")
        return redirect(url_for("view_proposal", proposal_id=proposal_id))
    try:
        refined = build_refined_proposal(proposal_id, change_request)
        update_proposal_content(proposal_id, refined)
        flash("Proposal updated with your requested changes.", "success")
    except Exception as e:
        flash(f"Error refining proposal: {str(e)}", "danger")
    return redirect(url_for("view_proposal", proposal_id=proposal_id))


@app.route("/proposal/<int:proposal_id>/delete", methods=["POST"])
@login_required
def delete(proposal_id):
    delete_proposal(proposal_id)
    flash("Proposal deleted.", "success")
    return redirect(url_for("index"))


@app.route("/api/proposal/<int:proposal_id>")
@login_required
def api_proposal(proposal_id):
    proposal = get_proposal(proposal_id)
    if not proposal:
        return jsonify({"error": "Not found"}), 404
    return jsonify(proposal)


if __name__ == "__main__":
    init_db()
    user_id = seed_db()
    seed_proposals()
    print(f"Database initialized. Default user ID: {user_id}")
    app.run(debug=True, host="0.0.0.0", port=5000)
