import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import anthropic

from database.db import get_db

CLAUDE_MD_PATH = Path(__file__).parent.parent / "claude.md"


def _to_bold_sans(text: str) -> str:
    """Convert ASCII text to mathematical bold sans-serif Unicode for Upwork plain-text formatting."""
    result = []
    for ch in text:
        if 'A' <= ch <= 'Z':
            result.append(chr(0x1D5D4 + ord(ch) - ord('A')))
        elif 'a' <= ch <= 'z':
            result.append(chr(0x1D5EE + ord(ch) - ord('a')))
        elif '0' <= ch <= '9':
            result.append(chr(0x1D7EC + ord(ch) - ord('0')))
        else:
            result.append(ch)
    return ''.join(result)


PROPOSAL_JSON_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "opening": {
            "type": "string",
            "description": "Strong opening paragraph (40-55 words). Must be confident and direct — state what you can do for them and why this project fits you. NEVER start with 'You mentioned', 'I noticed', 'I saw', or any mirroring phrase. Open with what you bring, not what they said."
        },
        "introduction": {
            "type": "string",
            "description": "One to two sentence introduction tying Virender's experience to this exact job"
        },
        "deliverables": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Bullet list of concrete deliverables tailored to the job requirements"
        },
        "additional_context": {
            "type": "string",
            "description": "Optional 1-2 bridging paragraphs after deliverables — design notes, budget acknowledgement, reliability statement. Empty string if not needed."
        },
        "client_questions_addressed": {
            "type": "string",
            "description": "Direct answers to any client questions from the job post, or empty string if none"
        },
        "cta": {
            "type": "string",
            "description": "Call to action inviting client to message on Upwork, with availability statement"
        },
        "related_projects": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "name": {"type": "string"},
                    "summary": {"type": "string"},
                    "skills": {"type": "string"}
                },
                "required": ["name", "summary", "skills"]
            },
            "description": "2-3 most relevant past projects selected from the projects bank"
        },
        "loom_suggestion": {
            "type": "string",
            "description": "Suggestion for a Loom video if the job is high-value/complex, or empty string"
        }
    },
    "required": [
        "opening", "introduction", "deliverables", "additional_context",
        "client_questions_addressed", "cta", "related_projects", "loom_suggestion"
    ]
}


@dataclass
class ValidationResult:
    is_valid: bool
    errors: list = field(default_factory=list)
    warnings: list = field(default_factory=list)


def _get_user_context(user_id: int) -> dict:
    conn = get_db()
    try:
        user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        if not user:
            raise ValueError(f"User {user_id} not found")
        projects = conn.execute(
            "SELECT * FROM related_projects WHERE user_id = ?", (user_id,)
        ).fetchall()
        return {"user": dict(user), "projects": [dict(p) for p in projects]}
    finally:
        conn.close()


def _build_full_text(proposal_data: dict, user: dict) -> str:
    deliverables_lines = "\n".join(f"* {d}" for d in proposal_data["deliverables"])

    related_lines = []
    for i, proj in enumerate(proposal_data["related_projects"], 1):
        related_lines.append(f"{i}. {_to_bold_sans(proj['name'])}")
        related_lines.append(proj["summary"])
        related_lines.append(f"{_to_bold_sans('Relevant Skills')}: {proj['skills']}")
        if i < len(proposal_data["related_projects"]):
            related_lines.append("")

    parts = [
        "Hi,",
        "",
        proposal_data["opening"],
        "",
        proposal_data["introduction"],
        "",
        "For your project, I can deliver:",
        "",
        deliverables_lines,
        "",
    ]

    if proposal_data.get("additional_context", "").strip():
        parts.extend([proposal_data["additional_context"], ""])

    if proposal_data.get("client_questions_addressed", "").strip():
        parts.extend([proposal_data["client_questions_addressed"], ""])

    parts.extend([
        proposal_data["cta"],
        "",
        user["signature"],
        "",
        "==================",
        _to_bold_sans("RELATED PROJECTS"),
        "==================",
    ])
    parts.extend(related_lines)

    return "\n".join(parts)


def _assemble_proposal_dict(user_id: int, job_title: str, job_description: str,
                             client_questions: str, proposal_data: dict, user: dict) -> dict:
    return {
        "user_id": user_id,
        "job_title": job_title,
        "job_description": job_description,
        "client_questions": client_questions,
        "opening": proposal_data["opening"],
        "introduction": proposal_data["introduction"],
        "deliverables": json.dumps(proposal_data["deliverables"]),
        "related_projects": json.dumps(proposal_data["related_projects"]),
        "cta": proposal_data["cta"],
        "client_questions_addressed": proposal_data.get("client_questions_addressed", ""),
        "loom_url": proposal_data.get("loom_suggestion", ""),
        "full_text": _build_full_text(proposal_data, user),
        "status": "draft"
    }


def _call_claude(messages: list, system_prompt: str = "") -> dict:
    client = anthropic.Anthropic()
    kwargs = {
        "model": "claude-sonnet-4-6",
        "max_tokens": 4096,
        "messages": messages,
        "output_config": {
            "format": {
                "type": "json_schema",
                "schema": PROPOSAL_JSON_SCHEMA
            }
        }
    }
    if system_prompt:
        kwargs["system"] = system_prompt
    response = client.messages.create(**kwargs)
    return json.loads(response.content[-1].text)


def build_proposal(user_id: int, job_data: dict) -> dict:
    system_prompt = CLAUDE_MD_PATH.read_text(encoding="utf-8")
    context = _get_user_context(user_id)
    user = context["user"]
    projects = context["projects"]

    projects_text = "\n".join([
        f"- **{p['name']}**: {p['summary']} (Skills: {p['skills']})"
        for p in projects
    ])

    user_message = f"""Generate an Upwork proposal for the following job posting.

**Freelancer Profile:**
- Name: {user['name']}
- Title: {user['title']}
- Rate: {user['rate']}
- Experience: {user['experience']}
- Skills: {user['skills']}
- Upwork: {user['upwork_url']}
- GitHub: {user['github_url']}

**Available Past Projects (pick 2-3 most relevant):**
{projects_text}

**Job Title:** {job_data.get('title', '')}

**Job Description:**
{job_data.get('description', '')}

**Client Questions (if any):**
{job_data.get('client_questions', 'None')}

Return a structured JSON proposal. Select only the 2-3 past projects most relevant to this specific job.

Opening rules (strictly enforced):
- Must be 40-55 words
- Must be confident and direct — lead with what you can deliver and why this fits your expertise
- NEVER start with "You mentioned", "I noticed", "I saw", "I read", or any sentence that mirrors back what the client wrote
- Good example: "Building a responsive admin dashboard with Angular and .NET Core is exactly what I do. I've delivered..."
- Bad example: "You mentioned needing an experienced developer for..." or "I noticed you're looking for..."

Use additional_context for any bridging paragraphs between deliverables and the CTA."""

    proposal_data = _call_claude(
        [{"role": "user", "content": user_message}],
        system_prompt=system_prompt,
    )

    return _assemble_proposal_dict(
        user_id=user_id,
        job_title=job_data.get("title", ""),
        job_description=job_data.get("description", ""),
        client_questions=job_data.get("client_questions", ""),
        proposal_data=proposal_data,
        user=user,
    )


def regenerate_proposal(proposal_id: int) -> dict:
    conn = get_db()
    try:
        row = conn.execute("SELECT * FROM proposals WHERE id = ?", (proposal_id,)).fetchone()
        if not row:
            raise ValueError(f"Proposal {proposal_id} not found")
        existing = dict(row)
    finally:
        conn.close()

    job_data = {
        "title": existing["job_title"],
        "description": existing["job_description"],
        "client_questions": existing.get("client_questions", ""),
    }
    return build_proposal(existing["user_id"], job_data)


def build_refined_proposal(proposal_id: int, change_request: str) -> dict:
    conn = get_db()
    try:
        row = conn.execute("SELECT * FROM proposals WHERE id = ?", (proposal_id,)).fetchone()
        if not row:
            raise ValueError(f"Proposal {proposal_id} not found")
        existing = dict(row)
    finally:
        conn.close()

    system_prompt = CLAUDE_MD_PATH.read_text(encoding="utf-8")
    context = _get_user_context(existing["user_id"])
    user = context["user"]

    user_message = f"""You previously generated this Upwork cover letter proposal:

---
{existing["full_text"]}
---

The user wants these specific changes applied:
{change_request}

Apply only the requested changes and return the complete updated proposal in JSON format. Keep all sections that weren't mentioned in the change request exactly as they are."""

    proposal_data = _call_claude(
        [{"role": "user", "content": user_message}],
        system_prompt=system_prompt,
    )

    return _assemble_proposal_dict(
        user_id=existing["user_id"],
        job_title=existing["job_title"],
        job_description=existing["job_description"],
        client_questions=existing.get("client_questions", ""),
        proposal_data=proposal_data,
        user=user,
    )


def update_proposal_content(proposal_id: int, proposal: dict) -> None:
    conn = get_db()
    try:
        conn.execute("""
            UPDATE proposals SET
                opening = ?,
                introduction = ?,
                deliverables = ?,
                related_projects = ?,
                cta = ?,
                loom_url = ?,
                full_text = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (
            proposal.get("opening", ""),
            proposal.get("introduction", ""),
            proposal.get("deliverables", "[]"),
            proposal.get("related_projects", "[]"),
            proposal.get("cta", ""),
            proposal.get("loom_url", ""),
            proposal.get("full_text", ""),
            proposal_id,
        ))
        conn.commit()
    finally:
        conn.close()


def validate_proposal(proposal: dict) -> ValidationResult:
    errors = []
    warnings = []

    opening = proposal.get("opening", "")
    word_count = len(opening.split())
    if word_count < 40:
        errors.append("Opening is too short (minimum 40 words)")
    elif word_count > 55:
        errors.append("Opening is too long (maximum 55 words)")

    if not proposal.get("cta", "").strip():
        errors.append("Call to action is required")

    client_questions = proposal.get("client_questions", "")
    questions_addressed = proposal.get("client_questions_addressed", "")
    if client_questions and client_questions.strip().lower() not in ("none", ""):
        if not questions_addressed or not questions_addressed.strip():
            warnings.append("Client questions detected but not addressed")

    loom_url = proposal.get("loom_url", "")
    if loom_url and loom_url.strip() and loom_url.startswith("http"):
        if "loom.com" not in loom_url:
            warnings.append("Loom URL appears invalid")

    for required in ["opening", "introduction", "deliverables", "cta"]:
        if not proposal.get(required):
            errors.append(f"Missing required field: {required}")

    return ValidationResult(is_valid=len(errors) == 0, errors=errors, warnings=warnings)


def save_proposal(user_id: int, proposal: dict) -> int:
    conn = get_db()
    try:
        existing = conn.execute(
            "SELECT id FROM proposals WHERE user_id = ? AND job_title = ? AND status = 'draft'",
            (user_id, proposal.get("job_title", ""))
        ).fetchone()

        if existing:
            conn.execute("""
                UPDATE proposals SET
                    job_description = ?,
                    client_questions = ?,
                    opening = ?,
                    introduction = ?,
                    deliverables = ?,
                    related_projects = ?,
                    cta = ?,
                    loom_url = ?,
                    full_text = ?,
                    status = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (
                proposal.get("job_description", ""),
                proposal.get("client_questions", ""),
                proposal.get("opening", ""),
                proposal.get("introduction", ""),
                proposal.get("deliverables", "[]"),
                proposal.get("related_projects", "[]"),
                proposal.get("cta", ""),
                proposal.get("loom_url", ""),
                proposal.get("full_text", ""),
                proposal.get("status", "draft"),
                existing["id"]
            ))
            conn.commit()
            return existing["id"]

        cursor = conn.execute("""
            INSERT INTO proposals (
                user_id, job_title, job_description, client_questions,
                opening, introduction, deliverables, related_projects,
                cta, loom_url, full_text, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            user_id,
            proposal.get("job_title", ""),
            proposal.get("job_description", ""),
            proposal.get("client_questions", ""),
            proposal.get("opening", ""),
            proposal.get("introduction", ""),
            proposal.get("deliverables", "[]"),
            proposal.get("related_projects", "[]"),
            proposal.get("cta", ""),
            proposal.get("loom_url", ""),
            proposal.get("full_text", ""),
            proposal.get("status", "draft")
        ))
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def get_proposal(proposal_id: int) -> Optional[dict]:
    conn = get_db()
    try:
        row = conn.execute("SELECT * FROM proposals WHERE id = ?", (proposal_id,)).fetchone()
        if not row:
            return None
        data = dict(row)
        data["deliverables"] = json.loads(data.get("deliverables", "[]"))
        data["related_projects"] = json.loads(data.get("related_projects", "[]"))
        return data
    finally:
        conn.close()


def get_all_proposals(user_id: int) -> list:
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT * FROM proposals WHERE user_id = ? ORDER BY updated_at DESC",
            (user_id,)
        ).fetchall()
        proposals = []
        for row in rows:
            data = dict(row)
            data["deliverables"] = json.loads(data.get("deliverables", "[]"))
            data["related_projects"] = json.loads(data.get("related_projects", "[]"))
            proposals.append(data)
        return proposals
    finally:
        conn.close()


def get_approved_proposals(user_id: int) -> list:
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT * FROM proposals WHERE user_id = ? AND status = 'approved' ORDER BY updated_at DESC",
            (user_id,)
        ).fetchall()
        proposals = []
        for row in rows:
            data = dict(row)
            data["deliverables"] = json.loads(data.get("deliverables", "[]"))
            data["related_projects"] = json.loads(data.get("related_projects", "[]"))
            proposals.append(data)
        return proposals
    finally:
        conn.close()


def update_proposal_status(proposal_id: int, status: str) -> bool:
    valid_statuses = {"draft", "approved", "ready", "submitted", "archived"}
    if status not in valid_statuses:
        return False
    conn = get_db()
    try:
        conn.execute(
            "UPDATE proposals SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (status, proposal_id)
        )
        conn.commit()
        return True
    finally:
        conn.close()


def delete_proposal(proposal_id: int) -> bool:
    conn = get_db()
    try:
        conn.execute("DELETE FROM proposals WHERE id = ?", (proposal_id,))
        conn.commit()
        return True
    finally:
        conn.close()


def seed_proposals():
    conn = get_db()
    try:
        user = conn.execute("SELECT id FROM users WHERE name = 'Virender T.'").fetchone()
        if not user:
            return
        user_id = user["id"]

        existing = conn.execute("SELECT COUNT(*) FROM proposals WHERE user_id = ?", (user_id,)).fetchone()
        if existing[0] > 0:
            return

        samples = [
            {
                "job_title": "Angular + .NET Core Developer for Admin Dashboard",
                "job_description": "Looking for an experienced developer to build a responsive admin dashboard with Angular frontend and .NET Core backend API.",
                "client_questions": "How long will this take? Do you have similar examples?",
                "opening": "Your admin dashboard project is exactly the kind of work I specialize in. Angular and .NET Core together is my primary stack, and I've built several dashboards with real-time data, role-based access, and responsive mobile layouts for clients across finance and workflow automation.",
                "introduction": "I'm a full-stack developer with 13+ years of experience building Angular/.NET Core applications — admin panels, dashboards, and business tools are where I spend most of my time.",
                "deliverables": json.dumps(["Responsive Angular 15+ admin dashboard", ".NET Core Web API backend", "Role-based authentication", "Real-time data updates", "Clean, documented code"]),
                "related_projects": json.dumps([
                    {"name": "Employee Task Management System", "summary": "Full-stack .NET 8 + Angular 19 with real-time operations.", "skills": "ASP.NET Core, Angular, API"},
                    {"name": "SaaS Subscription Billing System", "summary": "Role-based access and payment integration.", "skills": ".NET Core, SQL Server, API"}
                ]),
                "cta": "I'm available to start immediately. Message me on Upwork and we can discuss timeline and requirements in detail.",
                "full_text": "Sample proposal for Angular + .NET Core Dashboard",
                "status": "ready"
            },
            {
                "job_title": "Fix SQL Server Performance Issues",
                "job_description": "Our SQL Server queries are running slow. Need someone to analyze stored procedures and optimize them.",
                "client_questions": "",
                "opening": "Slow SQL Server queries are almost always fixable — missing indexes, inefficient stored procedures, or N+1 query patterns. I've diagnosed and resolved performance bottlenecks in complex SQL Server environments across finance and insurance applications.",
                "introduction": "I'm a full-stack developer with deep SQL Server experience including stored procedures, indexing strategies, and query optimization using execution plans.",
                "deliverables": json.dumps(["Execution plan analysis", "Index optimization", "Stored procedure rewrites", "Before/after performance report"]),
                "related_projects": json.dumps([
                    {"name": "Online Bid System", "summary": "High-traffic backend with SQL Server query optimization.", "skills": "ASP.NET Core, Web API, Microsoft SQL Server"}
                ]),
                "cta": "Happy to look at a sample query or execution plan before we start. Message me on Upwork to discuss.",
                "full_text": "Sample proposal for SQL Server optimization",
                "status": "submitted"
            },
            {
                "job_title": "Build REST API with .NET Core",
                "job_description": "Need a clean, well-documented REST API built with .NET Core for a mobile application.",
                "client_questions": "Can you provide API documentation?",
                "opening": "Building clean, well-documented REST APIs with .NET Core is something I do regularly for mobile and web clients. I follow Clean Architecture principles and always deliver Swagger documentation so your mobile team can integrate without friction.",
                "introduction": "I'm a .NET Core specialist with 13+ years of experience building scalable Web APIs — from simple CRUD endpoints to complex microservices with authentication and event-driven architecture.",
                "deliverables": json.dumps(["RESTful API with .NET Core", "Swagger/OpenAPI documentation", "JWT authentication", "SQL Server database integration", "Clean Architecture structure"]),
                "related_projects": json.dumps([
                    {"name": "SaaS Subscription Billing System", "summary": "Complete API with payment processing and role-based access.", "skills": ".NET Core, SQL Server, API"},
                    {"name": "Employee Task Management System", "summary": "Secure API with real-time operations.", "skills": "ASP.NET Core, Angular, API"}
                ]),
                "cta": "Yes, I always provide full Swagger documentation. Available to start immediately — message me on Upwork.",
                "full_text": "Sample proposal for .NET Core REST API",
                "status": "draft"
            }
        ]

        for s in samples:
            conn.execute("""
                INSERT INTO proposals (
                    user_id, job_title, job_description, client_questions,
                    opening, introduction, deliverables, related_projects,
                    cta, loom_url, full_text, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                user_id,
                s["job_title"], s["job_description"], s["client_questions"],
                s["opening"], s["introduction"], s["deliverables"], s["related_projects"],
                s["cta"], "", s["full_text"], s["status"]
            ))
        conn.commit()
    finally:
        conn.close()
