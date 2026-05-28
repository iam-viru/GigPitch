# Spec: User Login and Registration

## Overview
This feature adds proper user authentication to GigPitch. Currently the app hard-codes a default user (`get_default_user_id()` returns the first row in `users`). Step 02 replaces that with a real session-based login/registration flow so that Virender — or any user — must sign in before accessing the dashboard, generating proposals, or viewing history. All protected routes redirect unauthenticated visitors to `/login`.

## Depends on
- Step 01 — initial project setup (app.py, database/db.py, base.html, and seeded user data already in place)

## Routes
- `GET  /login`    — render login form — public
- `POST /login`    — authenticate user, set session, redirect to `/` — public
- `GET  /register` — render registration form — public
- `POST /register` — create new user, set session, redirect to `/` — public
- `POST /logout`   — clear session, redirect to `/login` — logged-in

## Database changes
Add two columns to the existing `users` table:

| Column          | Type         | Constraints          |
|-----------------|--------------|----------------------|
| `email`         | TEXT         | UNIQUE, NOT NULL     |
| `password_hash` | TEXT         | NOT NULL             |

Migration strategy (in `init_db()`):
- `CREATE TABLE IF NOT EXISTS` keeps the full new schema for fresh installs.
- For existing databases, use `ALTER TABLE users ADD COLUMN` guarded by a try/except to add `email` and `password_hash` if they are missing.

`seed_db()` must also set `email = 'hello.viru.thakur@gmail.com'` and a hashed default password for the seeded user, using `UPDATE` if the row already exists without credentials.

New helper functions in `database/db.py`:
- `get_user_by_email(email)` — returns the user row or None
- `create_user(name, title, rate, experience, skills, upwork_url, github_url, signature, email, password_hash)` — inserts and returns new user id

## Templates
- **Create:**
  - `templates/login.html` — login form (email + password fields, link to register)
  - `templates/register.html` — registration form (all profile fields + email + password)
- **Modify:**
  - `templates/base.html` — replace hardcoded hex values with CSS variables; add Login/Logout nav link that shows conditionally based on `session.user_id`

## Files to change
- `app.py` — add `/login`, `/register`, `/logout` routes; add `login_required` decorator; replace all `get_default_user_id()` calls with `session['user_id']`; remove `DEFAULT_USER_ID` constant
- `database/db.py` — update `CREATE TABLE users` to include `email` and `password_hash`; add migration in `init_db()`; update `seed_db()`; add `get_user_by_email()` and `create_user()`
- `templates/base.html` — CSS variables, conditional auth nav

## Files to create
- `templates/login.html`
- `templates/register.html`

## New dependencies
No new dependencies. `werkzeug.security` (`generate_password_hash`, `check_password_hash`) ships with Flask. Flask's built-in `session` handles the session cookie.

## Rules for implementation
- No SQLAlchemy or ORMs — raw SQLite via `sqlite3` only
- Parameterised queries only — no string formatting in SQL
- Passwords hashed with `werkzeug.security.generate_password_hash` / `check_password_hash`
- Use CSS variables — never hardcode hex values in templates or `<style>` blocks
- All templates extend `base.html`
- Use Flask's built-in `session` dict — do NOT add flask-login or any auth extension
- `login_required` must be a plain Python decorator defined in `app.py`, not a third-party library
- Registration must validate that email is not already taken before inserting
- On failed login, show a generic flash message — do not reveal whether email or password was wrong

## Definition of done
- [ ] Visiting `/` while logged out redirects to `/login`
- [ ] Visiting `/generate` while logged out redirects to `/login`
- [ ] Visiting `/history` while logged out redirects to `/login`
- [ ] `/register` form creates a new user, logs them in, and redirects to `/`
- [ ] Attempting to register with a duplicate email shows a flash error and stays on `/register`
- [ ] `/login` with correct credentials sets the session and redirects to `/`
- [ ] `/login` with wrong password shows a generic error flash and stays on `/login`
- [ ] Logged-in navbar shows a "Logout" link; logged-out navbar shows "Login"
- [ ] `POST /logout` clears the session and redirects to `/login`
- [ ] The seeded user (`hello.viru.thakur@gmail.com`) can log in after `init_db()` + `seed_db()` run
- [ ] All existing proposal routes still work correctly for a logged-in user
