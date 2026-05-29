# GigPitch

AI-powered Upwork cover letter generator for freelancers. Paste a job description, get a professional, structured proposal in seconds — formatted exactly how Upwork expects it, with related projects, bold Unicode section headers, and a call to action.

---

## Features

- **AI proposal generation** — Claude (Sonnet) generates a tailored cover letter from the job title, description, and any client questions
- **Structured output** — Proposals follow a proven format: opening → introduction → deliverables → CTA → signature → related projects in bold Unicode
- **Refine with AI** — Ask Claude to change specific parts ("make the opening more confident", "shorten the deliverables") without regenerating the whole thing
- **Regenerate** — Full regeneration from the original job data in one click
- **Quick Tweaks** — One-click chips for common refinements
- **Proposal history** — Track status (draft → ready → submitted → archived → approved)
- **User accounts** — Session-based login, registration, and forgot password via email OTP
- **Copy to clipboard** — One click to copy the full proposal for pasting into Upwork

---

## Tech Stack

- **Backend** — Python / Flask
- **AI** — Anthropic Claude API (`claude-sonnet-4-6`) with structured JSON output
- **Database** — SQLite (via raw parameterized queries)
- **Email** — Gmail SMTP via Python `smtplib`
- **Frontend** — Bootstrap 5.3 + Bootstrap Icons
- **Auth** — Session-based (no external auth library)
- **Deployment** — Railway (gunicorn)

---

## Local Setup

### 1. Clone and install dependencies

```bash
git clone https://github.com/iam-viru/GigPitch.git
cd GigPitch
pip install -r requirements.txt
```

### 2. Configure environment variables

Copy `.env.example` to `.env` and fill in your values:

```bash
cp .env.example .env
```

```env
ANTHROPIC_API_KEY=your_anthropic_api_key_here
SECRET_KEY=change-this-to-a-random-secret-key

# Gmail SMTP — use a 16-char App Password, not your account password
# Enable 2FA first, then generate at: myaccount.google.com/apppasswords
MAIL_USERNAME=your-gmail@gmail.com
MAIL_PASSWORD=your-16-char-app-password
MAIL_FROM=your-gmail@gmail.com
```

### 3. Run

```bash
python app.py
```

App starts at `http://localhost:5000`. The database is created automatically on first run and seeded with a default user.

**Default credentials:**
- Email: `hello.viru.thakur@gmail.com`
- Password: `GigPitch123!`

---

## Project Structure

```
GigPitch/
├── app.py                  # Flask routes and app config
├── database/
│   └── db.py               # SQLite schema, migrations, and query helpers
├── proposals/
│   └── proposal_builder.py # Claude API calls, proposal formatting, refine/regenerate
├── utils/
│   └── email.py            # Gmail SMTP OTP email sender
├── templates/              # Jinja2 HTML templates (Bootstrap)
├── static/                 # Static assets
├── requirements.txt
├── Procfile                # Railway / gunicorn start command
└── .env.example            # Environment variable reference
```

---

## Proposal Format

Generated proposals follow this exact plain-text structure (ready to paste into Upwork):

```
Hi,

[40–55 word opening — confident, specific to the job]

[1–2 sentence introduction]

For your project, I can deliver:

* [deliverable]
* [deliverable]

[optional bridging context]

[call to action]

[signature with Upwork + GitHub links]

==================
𝗥𝗘𝗟𝗔𝗧𝗘𝗗 𝗣𝗥𝗢𝗝𝗘𝗖𝗧𝗦
==================
1. 𝗣𝗿𝗼𝗷𝗲𝗰𝘁 𝗡𝗮𝗺𝗲
Summary of what was built and the outcome.
𝗥𝗲𝗹𝗲𝘃𝗮𝗻𝘁 𝗦𝗸𝗶𝗹𝗹𝘀: skill1, skill2
```

---

## Environment Variables

| Variable | Description |
|---|---|
| `ANTHROPIC_API_KEY` | Anthropic API key for Claude |
| `SECRET_KEY` | Flask session secret (use a long random string in production) |
| `MAIL_USERNAME` | Gmail address used to send OTP emails |
| `MAIL_PASSWORD` | Gmail App Password (16 chars, not your account password) |
| `MAIL_FROM` | From address on OTP emails (usually same as `MAIL_USERNAME`) |
| `FLASK_ENV` | Set to `production` to enable secure cookies |

---

## Deployment (Railway)

The app is configured for Railway with a `Procfile`:

```
web: gunicorn app:app --bind 0.0.0.0:$PORT
```

> **SQLite note:** SQLite data is ephemeral on Railway by default. Attach a Railway Volume mounted at `/app` to persist the database across deployments, or migrate to PostgreSQL for production use.
