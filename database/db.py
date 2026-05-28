import sqlite3
from pathlib import Path

from werkzeug.security import generate_password_hash

DB_PATH = Path(__file__).parent.parent / "proposals.db"


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_db()
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                title TEXT NOT NULL,
                rate TEXT NOT NULL,
                experience TEXT NOT NULL,
                skills TEXT NOT NULL,
                upwork_url TEXT NOT NULL,
                github_url TEXT NOT NULL,
                signature TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS related_projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                summary TEXT NOT NULL,
                skills TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS proposals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                job_title TEXT NOT NULL,
                job_description TEXT NOT NULL,
                client_questions TEXT,
                opening TEXT NOT NULL,
                introduction TEXT NOT NULL,
                deliverables TEXT NOT NULL,
                related_projects TEXT NOT NULL,
                cta TEXT NOT NULL,
                loom_url TEXT,
                full_text TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'draft',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            );
        """)
        conn.commit()

        # Migration: add auth columns to existing databases
        for col in ("email TEXT", "password_hash TEXT"):
            try:
                conn.execute(f"ALTER TABLE users ADD COLUMN {col}")
                conn.commit()
            except Exception:
                pass  # column already exists
    finally:
        conn.close()


def seed_db():
    conn = get_db()
    try:
        existing = conn.execute("SELECT id, email FROM users WHERE name = 'Virender T.'").fetchone()
        if existing:
            if not existing["email"]:
                conn.execute(
                    "UPDATE users SET email = ?, password_hash = ? WHERE id = ? AND email IS NULL",
                    (
                        "hello.viru.thakur@gmail.com",
                        generate_password_hash("GigPitch123!"),
                        existing["id"],
                    ),
                )
                conn.commit()
            return existing["id"]

        cursor = conn.execute("""
            INSERT INTO users (name, title, rate, experience, skills, upwork_url, github_url, signature, email, password_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            "Virender T.",
            "Full-Stack Developer | Angular & C#, .NET Core Expert | Scalable Apps",
            "$15.00/hr",
            "13+ years",
            "Angular 15+, .NET Core, ASP.NET MVC, Web API, C#, SQL Server, Azure, AWS",
            "https://www.upwork.com/freelancers/iamviru?s=1110580755107926016",
            "https://github.com/iam-viru",
            "𝑉𝑖𝑟𝑒𝑛𝑑𝑒𝑟 𝑇. 𝐹𝑢𝑙𝑙-𝑆𝑡𝑎𝑐𝑘 𝐷𝑒𝑣𝑒𝑙𝑜𝑝𝑒𝑟 | 𝐴𝑛𝑔𝑢𝑙𝑎𝑟 & .𝑁𝐸𝑇 𝑆𝑝𝑒𝑐𝑖𝑎𝑙𝑖𝑠𝑡 | 𝑆𝑐𝑎𝑙𝑎𝑏𝑙𝑒 𝑊𝑒𝑏 & 𝐷𝑒𝑠𝑘𝑡𝑜𝑝 𝐴𝑝𝑝𝑠\nhttps://www.upwork.com/freelancers/iamviru?s=1110580755107926016\nGithub: https://github.com/iam-viru",
            "hello.viru.thakur@gmail.com",
            generate_password_hash("GigPitch123!"),
        ))
        user_id = cursor.lastrowid

        projects = [
            (
                user_id,
                "Employee Task Management System (Full-Stack .NET 8 + Angular 19)",
                "Designed and developed a system with secure authentication and real-time operations, aligning with user sign-up and backend update needs.",
                "ASP.NET Core, Angular, API"
            ),
            (
                user_id,
                "SaaS Subscription Billing & Customer Management System",
                "Built a platform with integrated payment processing and role-based access, similar to Stripe checkout and onboarding requirements.",
                ".NET Core, SQL Server, API"
            ),
            (
                user_id,
                "Online Bid System",
                "Developed a system with user management and backend operations, aligning with capturing user information and updating backend systems.",
                "ASP.NET Core, Web API, Microsoft SQL Server"
            ),
        ]
        conn.executemany("""
            INSERT INTO related_projects (user_id, name, summary, skills)
            VALUES (?, ?, ?, ?)
        """, projects)

        conn.commit()
        return user_id
    finally:
        conn.close()


def get_user_by_email(email):
    conn = get_db()
    try:
        return conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    finally:
        conn.close()


def create_user(name, title, rate, experience, skills,
                upwork_url, github_url, signature, email, password_hash):
    conn = get_db()
    try:
        cur = conn.execute("""
            INSERT INTO users (name, title, rate, experience, skills,
                               upwork_url, github_url, signature, email, password_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (name, title, rate, experience, skills,
              upwork_url, github_url, signature, email, password_hash))
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()
