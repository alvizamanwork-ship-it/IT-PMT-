"""Daily digest to the CTO of requirements held longer than STALL_DAYS.

Runs in a background thread at DIGEST_HOUR (server local time). Can also be run
from cron instead: `python -m app.digest` (set DIGEST_ENABLED=0 for the app then).
"""
import logging
import threading
import time
from datetime import datetime, timedelta, timezone

from . import config, db, mailer
from .workflow import STAGES

log = logging.getLogger("pmt.digest")


def stalled(conn):
    days = db.stall_days(conn)
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat(timespec="seconds")
    return days, conn.execute(
        "SELECT r.id, r.title, r.stage, r.entered_stage_at, p.code, u.name AS holder "
        "FROM requirements r JOIN projects p ON p.id=r.project_id "
        "LEFT JOIN users u ON u.id=r.holder_id "
        "WHERE r.stage<8 AND p.status='Active' AND r.entered_stage_at<? "
        "ORDER BY r.entered_stage_at", (cutoff,)).fetchall()


def send_digest(conn):
    days, rows = stalled(conn)
    if not rows:
        return 0
    now = datetime.now(timezone.utc)
    lines = [f"Requirements held longer than {days} days:", ""]
    for r in rows:
        held = (now - db.parse(r["entered_stage_at"])).days
        lines.append(f"- {r['code']} #{r['id']} {r['title']} · stage {r['stage']} {STAGES[r['stage']]}"
                     f" · holder {r['holder'] or 'none'} · {held} days"
                     f" · {config.app_url()}/requirements/{r['id']}")
    for cto in conn.execute("SELECT email FROM users WHERE is_cto=1 AND email<>''").fetchall():
        mailer.send(cto["email"], f"[PMT] Daily digest: {len(rows)} stalled requirement(s)",
                    "\n".join(lines))
    return len(rows)


def run_once():
    conn = db.connect()
    try:
        return send_digest(conn)
    finally:
        conn.close()


def _seconds_until_next():
    now = datetime.now()
    nxt = now.replace(hour=config.digest_hour(), minute=0, second=0, microsecond=0)
    if nxt <= now:
        nxt += timedelta(days=1)
    return (nxt - now).total_seconds()


def _loop():
    while True:
        time.sleep(_seconds_until_next())
        try:
            run_once()
        except Exception:
            log.exception("Digest failed")


def start_scheduler():
    threading.Thread(target=_loop, name="pmt-digest", daemon=True).start()


if __name__ == "__main__":
    db.init()
    print(f"Digest sent for {run_once()} requirement(s).")
