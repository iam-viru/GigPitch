# Spec: Forgot Password and Reset Password with Email OTP

## Overview
This feature lets a user who has forgotten their password regain access via a 6-digit one-time passcode (OTP) sent to their registered email address. The flow is: enter email → receive OTP by email → enter OTP → set new password. OTPs are stored in the database with a 15-minute expiry and are single-use. Email is sent via Python's built-in `smtplib` (no extra packages) using SMTP credentials stored in environment variables. This is the standard "forgot password" UX that every authenticated app needs before it can be considered production-ready.

## Depends on
- Step 02 — User Login and Registration (users table with `email` and `password_hash` columns must exist)

## Routes
- `GET  /forgot-password`  — render email entry form — public
- `POST /forgot-password`  — validate email, generate OTP, send email, redirect to `/verify-otp` — public
- `GET  /verify-otp`       — render OTP entry form — public
- `POST /verify-otp`       — validate OTP, store `reset_user_id` in session, redirect to `/reset-password` — public
- `GET  /reset-password`   — render new password form (requires `reset_user_id` in session) — public
- `POST /reset-password`   — update password hash, clear OTP + session state, redirect to `/login` — public

## Database changes
Add one new table:

```sql
CREATE TABLE IF NOT EXISTS password_reset_tokens (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL,
    otp         TEXT NOT NULL,
    expires_at  DATETIME NOT NULL,
    used        INTEGER NOT NULL DEFAULT 0,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);
```

New helper functions in `database/db.py`:
- `create_reset_token(user_id, otp, expires_at)` — insert a new token row, return its id
- `get_valid_reset_token(user_id, otp)` — return token row where `used = 0` and `expires_at > now()` and otp matches, else None
- `mark_token_used(token_id)` — set `used = 1`
- `cleanup_expired_tokens()` — delete rows where `expires_at < now()` (call at start of each forgot-password POST to prevent table bloat)

## Templates
- **Create:**
  - `templates/forgot-password.html` — single email field, submit button, link back to login
  - `templates/verify-otp.html` — 6-digit OTP input, hidden email field, resend link, link back to forgot-password
  - `templates/reset-password.html` — new password + confirm password fields
- **Modify:**
  - `templates/login.html` — add "Forgot password?" link pointing to `/forgot-password`

## Files to change
- `app.py` — add 6 new routes; import `send_otp_email` from `utils/email.py`; import new DB helpers
- `database/db.py` — add `password_reset_tokens` table in `init_db()`; add 4 new helper functions
- `templates/login.html` — add "Forgot password?" link

## Files to create
- `utils/__init__.py` — empty package marker
- `utils/email.py` — `send_otp_email(to_email, otp)` using `smtplib` + `email.mime`
- `templates/forgot-password.html`
- `templates/verify-otp.html`
- `templates/reset-password.html`

## New dependencies
No new pip packages. Uses Python stdlib only:
- `smtplib` — SMTP client
- `email.mime.text` / `email.mime.multipart` — email message construction
- `secrets` — `secrets.randbelow(1_000_000)` for cryptographically random 6-digit OTP
- `datetime` — OTP expiry calculation

## Environment variables required
Add these to `.env` (and document in Railway environment settings):
```
MAIL_USERNAME=your-gmail@gmail.com
MAIL_PASSWORD=your-gmail-app-password
MAIL_FROM=your-gmail@gmail.com
```
Gmail requires a 16-character **App Password** (not the account password) — 2FA must be enabled on the Google account first.

## Rules for implementation
- No SQLAlchemy or ORMs — raw SQLite via `sqlite3` only
- Parameterised queries only — no string formatting in SQL
- Passwords hashed with `werkzeug.security.generate_password_hash` / `check_password_hash`
- Use CSS variables — never hardcode hex values in templates or `<style>` blocks
- All templates extend `base.html`
- OTP must be generated with `secrets.randbelow(1_000_000)` zero-padded to 6 digits — never use `random`
- OTP expiry is 15 minutes from generation (`datetime.utcnow() + timedelta(minutes=15)`)
- On `POST /forgot-password`, always flash the same message whether email exists or not: "If that email is registered, you'll receive an OTP shortly." — never reveal whether an email is in the system
- The `/reset-password` GET/POST must check that `session.get("reset_user_id")` exists; if not, redirect to `/forgot-password`
- After a successful password reset, call `session.pop("reset_user_id", None)` to clear the reset state
- SMTP errors must be caught and surfaced as a flash error — never let an unhandled exception reach the user
- `mark_token_used()` must be called immediately after OTP is verified, before redirecting to `/reset-password`

## Definition of done
- [ ] `/forgot-password` page loads for a logged-out user
- [ ] Submitting a registered email on `/forgot-password` sends an OTP email and redirects to `/verify-otp`
- [ ] Submitting an unregistered email shows the same generic flash message (no leak)
- [ ] `/verify-otp` with a correct, non-expired OTP redirects to `/reset-password`
- [ ] `/verify-otp` with a wrong OTP shows an error flash and stays on the form
- [ ] `/verify-otp` with an expired OTP shows an "OTP has expired" flash
- [ ] `/reset-password` visited without a valid session state redirects to `/forgot-password`
- [ ] Submitting mismatched passwords on `/reset-password` shows an error and stays on the form
- [ ] Submitting a valid new password updates the hash in the DB and redirects to `/login` with a success flash
- [ ] After password reset, the old password no longer works; the new password logs in successfully
- [ ] The OTP token is marked as used and cannot be reused for a second reset
- [ ] Login page has a visible "Forgot password?" link
