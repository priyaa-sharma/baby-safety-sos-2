import hashlib
import hmac
import os
import re
import secrets
import smtplib
import ssl
import sqlite3
from contextlib import closing
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from urllib.parse import urlencode

AUTH_DB = "users.db"
HASH_ITERATIONS = 310_000
RESET_TOKEN_LIFETIME = timedelta(minutes=30)


def _ensure_schema(connection):
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            email TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            salt BLOB NOT NULL,
            password_hash BLOB NOT NULL
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS password_resets (
            token_hash TEXT PRIMARY KEY,
            email TEXT NOT NULL,
            expires_at TEXT NOT NULL
        )
        """
    )


def _hash_password(password, salt):
    return hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, HASH_ITERATIONS
    )


def create_account(name, email, password, db_path=AUTH_DB):
    name = name.strip()
    email = email.strip().lower()
    if not name:
        return False, "Enter your name."
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        return False, "Enter a valid email address."
    if len(password) < 8:
        return False, "Use a password with at least 8 characters."

    salt = secrets.token_bytes(16)
    password_hash = _hash_password(password, salt)
    with closing(sqlite3.connect(db_path)) as connection:
        with connection:
            _ensure_schema(connection)
            try:
                connection.execute(
                    "INSERT INTO users (email, name, salt, password_hash) VALUES (?, ?, ?, ?)",
                    (email, name, salt, password_hash),
                )
            except sqlite3.IntegrityError:
                return False, "An account with that email already exists."
    return True, "Your account is ready."


def verify_account(email, password, db_path=AUTH_DB):
    email = email.strip().lower()
    with closing(sqlite3.connect(db_path)) as connection:
        with connection:
            _ensure_schema(connection)
            user = connection.execute(
                "SELECT name, salt, password_hash FROM users WHERE email = ?",
                (email,),
            ).fetchone()

    if user is None:
        return None
    name, salt, password_hash = user
    if not hmac.compare_digest(_hash_password(password, salt), password_hash):
        return None
    return {"name": name, "email": email}


def _token_hash(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_password_reset_token(email, db_path=AUTH_DB):
    email = email.strip().lower()
    token = secrets.token_urlsafe(32)
    expires_at = (datetime.now(timezone.utc) + RESET_TOKEN_LIFETIME).isoformat()
    with closing(sqlite3.connect(db_path)) as connection:
        with connection:
            _ensure_schema(connection)
            exists = connection.execute(
                "SELECT 1 FROM users WHERE email = ?", (email,)
            ).fetchone()
            if exists is None:
                return None
            connection.execute("DELETE FROM password_resets WHERE email = ?", (email,))
            connection.execute(
                "INSERT INTO password_resets (token_hash, email, expires_at) VALUES (?, ?, ?)",
                (_token_hash(token), email, expires_at),
            )
    return token


def password_reset_token_valid(token, db_path=AUTH_DB):
    if not token:
        return False
    with closing(sqlite3.connect(db_path)) as connection:
        with connection:
            _ensure_schema(connection)
            row = connection.execute(
                "SELECT expires_at FROM password_resets WHERE token_hash = ?",
                (_token_hash(token),),
            ).fetchone()
    if row is None:
        return False
    return datetime.fromisoformat(row[0]) > datetime.now(timezone.utc)


def discard_password_reset_token(token, db_path=AUTH_DB):
    with closing(sqlite3.connect(db_path)) as connection:
        with connection:
            _ensure_schema(connection)
            connection.execute(
                "DELETE FROM password_resets WHERE token_hash = ?", (_token_hash(token),)
            )


def reset_password(token, password, db_path=AUTH_DB):
    if len(password) < 8:
        return False, "Use a password with at least 8 characters."
    now = datetime.now(timezone.utc)
    with closing(sqlite3.connect(db_path)) as connection:
        with connection:
            _ensure_schema(connection)
            row = connection.execute(
                "SELECT email, expires_at FROM password_resets WHERE token_hash = ?",
                (_token_hash(token),),
            ).fetchone()
            if row is None or datetime.fromisoformat(row[1]) <= now:
                return False, "This reset link has expired or was already used. Request a new one."
            email = row[0]
            salt = secrets.token_bytes(16)
            connection.execute(
                "UPDATE users SET salt = ?, password_hash = ? WHERE email = ?",
                (salt, _hash_password(password, salt), email),
            )
            connection.execute("DELETE FROM password_resets WHERE email = ?", (email,))
    return True, "Your password has been updated."


def send_password_reset_email(email, reset_url):
    required = ("SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASSWORD")
    missing = [key for key in required if not os.getenv(key)]
    if missing:
        raise RuntimeError(
            "Email delivery is not configured. Set " + ", ".join(missing) + " in .env."
        )

    message = EmailMessage()
    message["Subject"] = "Reset your Baby Safety SOS password"
    message["From"] = os.getenv("SMTP_FROM") or os.environ["SMTP_USER"]
    message["To"] = email
    message.set_content(
        "We received a request to reset your Baby Safety SOS password.\n\n"
        "Use this link within 30 minutes to choose a new password:\n"
        f"{reset_url}\n\n"
        "If you did not request this, you can ignore this email."
    )
    with smtplib.SMTP(os.environ["SMTP_HOST"], int(os.environ["SMTP_PORT"]), timeout=20) as server:
        server.starttls(context=ssl.create_default_context())
        server.login(os.environ["SMTP_USER"], os.environ["SMTP_PASSWORD"])
        server.send_message(message)


def build_password_reset_url(base_url, token):
    separator = "&" if "?" in base_url else "?"
    return base_url + separator + urlencode({"reset": token})
