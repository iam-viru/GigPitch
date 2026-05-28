import os
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from dotenv import load_dotenv

from database.db import init_db, seed_db
from proposals.proposal_builder import (
    build_proposal, validate_proposal, save_proposal,
    get_proposal, get_all_proposals, get_approved_proposals,
    update_proposal_status, delete_proposal, seed_proposals
)

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")

DEFAULT_USER_ID = 1


def get_default_user_id():
    from database.db import get_db
    conn = get_db()
    try:
        user = conn.execute("SELECT id FROM users LIMIT 1").fetchone()
        return user["id"] if user else None
    finally:
        conn.close()


@app.route("/")
def index():
    user_id = get_default_user_id()
    proposals = get_all_proposals(user_id) if user_id else []
    status_filter = request.args.get("status", "")
    if status_filter:
        proposals = [p for p in proposals if p["status"] == status_filter]
    return render_template("index.html", proposals=proposals, status_filter=status_filter)


@app.route("/generate", methods=["GET", "POST"])
def generate():
    if request.method == "POST":
        job_title = request.form.get("job_title", "").strip()
        job_description = request.form.get("job_description", "").strip()
        client_questions = request.form.get("client_questions", "").strip()

        if not job_title or not job_description:
            flash("Job title and description are required.", "danger")
            return render_template("generate.html", form_data=request.form)

        user_id = get_default_user_id()
        if not user_id:
            flash("No user profile found. Please set up your profile.", "danger")
            return render_template("generate.html", form_data=request.form)

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
def view_proposal(proposal_id):
    proposal = get_proposal(proposal_id)
    if not proposal:
        flash("Proposal not found.", "danger")
        return redirect(url_for("index"))
    return render_template("proposal.html", proposal=proposal)


@app.route("/proposal/<int:proposal_id>/approve", methods=["POST"])
def approve(proposal_id):
    if update_proposal_status(proposal_id, "approved"):
        flash("Proposal approved and saved to history.", "success")
    else:
        flash("Could not approve proposal.", "danger")
    return redirect(url_for("view_proposal", proposal_id=proposal_id))


@app.route("/proposal/<int:proposal_id>/status", methods=["POST"])
def update_status(proposal_id):
    new_status = request.form.get("status", "")
    if update_proposal_status(proposal_id, new_status):
        flash(f"Status updated to '{new_status}'.", "success")
    else:
        flash("Invalid status value.", "danger")
    return redirect(url_for("view_proposal", proposal_id=proposal_id))


@app.route("/history")
def history():
    user_id = get_default_user_id()
    proposals = get_approved_proposals(user_id) if user_id else []
    return render_template("history.html", proposals=proposals)


@app.route("/proposal/<int:proposal_id>/delete", methods=["POST"])
def delete(proposal_id):
    delete_proposal(proposal_id)
    flash("Proposal deleted.", "success")
    return redirect(url_for("index"))


@app.route("/api/proposal/<int:proposal_id>")
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
