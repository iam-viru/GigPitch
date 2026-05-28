import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


def send_otp_email(to_email, otp):
    username = os.environ.get("MAIL_USERNAME")
    password = os.environ.get("MAIL_PASSWORD")
    mail_from = os.environ.get("MAIL_FROM", username)

    if not username or not password:
        raise RuntimeError("MAIL_USERNAME and MAIL_PASSWORD must be set in environment variables.")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Your GigPitch password reset code"
    msg["From"] = mail_from
    msg["To"] = to_email

    plain = (
        f"Your one-time code is: {otp}\n\n"
        "It expires in 15 minutes. Do not share it with anyone.\n\n"
        "If you did not request a password reset, you can safely ignore this email."
    )
    html = f"""
    <div style="font-family:sans-serif;max-width:480px;margin:auto">
      <h2 style="color:#14a800">GigPitch Password Reset</h2>
      <p>Use the code below to reset your password. It expires in <strong>15 minutes</strong>.</p>
      <div style="font-size:2rem;font-weight:700;letter-spacing:0.3em;padding:1rem;
                  background:#f8f9fa;border-radius:8px;text-align:center">{otp}</div>
      <p style="color:#6c757d;font-size:0.85rem;margin-top:1rem">
        If you didn't request this, ignore this email — your password won't change.
      </p>
    </div>
    """

    msg.attach(MIMEText(plain, "plain"))
    msg.attach(MIMEText(html, "html"))

    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.ehlo()
        server.starttls()
        server.login(username, password)
        server.sendmail(mail_from, to_email, msg.as_string())
