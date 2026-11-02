import sqlite3
from datetime import datetime, timezone

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS users(
  id INTEGER PRIMARY KEY, username TEXT UNIQUE NOT NULL, name TEXT NOT NULL,
  email TEXT NOT NULL DEFAULT '', password_hash TEXT, is_cto INTEGER NOT NULL DEFAULT 0,
  theme TEXT NOT NULL DEFAULT 'light', font TEXT NOT NULL DEFAULT 'poppins',
  font_size INTEGER NOT NULL DEFAULT 2);
CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS projects(
  id INTEGER PRIMARY KEY, name TEXT NOT NULL, code TEXT UNIQUE NOT NULL,
  status TEXT NOT NULL DEFAULT 'Active', folder_path TEXT NOT NULL,
  paused_at TEXT, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS members(
  project_id INTEGER NOT NULL REFERENCES projects(id),
  user_id INTEGER NOT NULL REFERENCES users(id), role TEXT NOT NULL,
  PRIMARY KEY(project_id, user_id));
CREATE TABLE IF NOT EXISTS requirements(
  id INTEGER PRIMARY KEY, project_id INTEGER NOT NULL REFERENCES projects(id),
  title TEXT NOT NULL, description TEXT NOT NULL DEFAULT '',
  stage INTEGER NOT NULL DEFAULT 1, holder_id INTEGER REFERENCES users(id),
  prev_sender_id INTEGER REFERENCES users(id), prev_sender_stage INTEGER,
  due_date TEXT, priority TEXT NOT NULL DEFAULT 'Normal',
  folder_path TEXT NOT NULL DEFAULT '', created_by INTEGER NOT NULL REFERENCES users(id),
  entered_stage_at TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS history(
  id INTEGER PRIMARY KEY, project_id INTEGER NOT NULL REFERENCES projects(id),
  requirement_id INTEGER REFERENCES requirements(id),
  user_id INTEGER NOT NULL REFERENCES users(id), at TEXT NOT NULL, action TEXT NOT NULL,
  from_user_id INTEGER, to_user_id INTEGER, from_stage INTEGER, to_stage INTEGER,
  comment TEXT NOT NULL DEFAULT '', internal INTEGER NOT NULL DEFAULT 0,
  override INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS comments(
  id INTEGER PRIMARY KEY, requirement_id INTEGER NOT NULL REFERENCES requirements(id),
  user_id INTEGER NOT NULL REFERENCES users(id), at TEXT NOT NULL, text TEXT NOT NULL,
  internal INTEGER NOT NULL DEFAULT 1);
CREATE TABLE IF NOT EXISTS files(
  id INTEGER PRIMARY KEY, requirement_id INTEGER NOT NULL REFERENCES requirements(id),
  stage INTEGER NOT NULL, name TEXT NOT NULL, path TEXT NOT NULL,
  uploaded_by INTEGER NOT NULL REFERENCES users(id), at TEXT NOT NULL);
"""


def _dict_row(cur, row):
    return {d[0]: row[i] for i, d in enumerate(cur.description)}


def connect():
    c = sqlite3.connect(config.db_path())
    c.row_factory = _dict_row
    c.execute("PRAGMA foreign_keys=ON")
    return c


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def parse(ts):
    return datetime.fromisoformat(ts)


def get_setting(conn, key, default):
    r = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return r["value"] if r else default


def set_setting(conn, key, value):
    conn.execute("INSERT INTO settings(key,value) VALUES(?,?) "
                 "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, str(value)))


def stall_days(conn):
    return int(get_setting(conn, "stall_days", config.stall_days_default()))


def init():
    from .auth import hash_password
    c = connect()
    c.executescript(SCHEMA)
    if not c.execute("SELECT 1 FROM users LIMIT 1").fetchone():
        username, password, email, name = config.admin_bootstrap()
        c.execute("INSERT INTO users(username,name,email,password_hash,is_cto) VALUES(?,?,?,?,1)",
                  (username, name, email, hash_password(password)))
    c.commit()
    c.close()
