"""All configuration comes from environment variables, read at call time."""
import os


def _env(name, default=None):
    return os.environ.get(name, default)


def db_path():
    return _env("PMT_DB", "pmt.db")


def file_root():
    return _env("FILE_ROOT", "./files")


def stall_days_default():
    return int(_env("STALL_DAYS", "5"))


def secret_key():
    return _env("SECRET_KEY", "change-me")


def secure_cookies():
    return _env("SECURE_COOKIES", "0") == "1"


def app_url():
    return _env("APP_URL", "http://localhost:8000").rstrip("/")


def admin_bootstrap():
    return (_env("ADMIN_USERNAME", "admin"), _env("ADMIN_PASSWORD", "admin"),
            _env("ADMIN_EMAIL", ""), _env("ADMIN_NAME", "CTO"))


def smtp():
    return {
        "host": _env("SMTP_HOST", ""),
        "port": int(_env("SMTP_PORT", "25")),
        "user": _env("SMTP_USER", ""),
        "password": _env("SMTP_PASSWORD", ""),
        "sender": _env("SMTP_FROM", "pmt@localhost"),
        "starttls": _env("SMTP_STARTTLS", "0") == "1",
    }


def digest_hour():
    return int(_env("DIGEST_HOUR", "7"))


def digest_enabled():
    return _env("DIGEST_ENABLED", "1") == "1"
