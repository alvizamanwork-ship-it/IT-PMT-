"""SMTP email. With no SMTP_HOST set, messages are only logged (and kept in `outbox`)."""
import logging
import smtplib
from email.message import EmailMessage

from . import config
from .perms import role_of

log = logging.getLogger("pmt.mail")
outbox = []  # last messages, for inspection when SMTP is not configured


def send(to, subject, body):
    if not to:
        return
    cfg = config.smtp()
    msg = EmailMessage()
    msg["From"], msg["To"], msg["Subject"] = cfg["sender"], to, subject
    msg.set_content(body)
    outbox.append(msg)
    del outbox[:-100]
    if not cfg["host"]:
        log.info("Email (SMTP not configured) to %s: %s", to, subject)
        return
    try:
        with smtplib.SMTP(cfg["host"], cfg["port"], timeout=15) as s:
            if cfg["starttls"]:
                s.starttls()
            if cfg["user"]:
                s.login(cfg["user"], cfg["password"])
            s.send_message(msg)
    except Exception:  # an email failure must never break the action
        log.exception("Email to %s failed", to)


def handoff(conn, actor, result):
    """Email the new holder after an action."""
    from .workflow import STAGES, get
    if not result.get("to"):
        return
    u = conn.execute("SELECT name, email FROM users WHERE id=?", (result["to"],)).fetchone()
    if not u or not u["email"]:
        return
    r = get(conn, result["requirement_id"])
    hide = result["internal"] and role_of(conn, r["project_id"], result["to"]) == "Business Stakeholder"
    lines = [f"{actor['name']} sent you a requirement ({result['action']}).", "",
             f"Project: {r['code']} · {r['project_name']}",
             f"Requirement: #{r['id']} {r['title']}",
             f"Stage: {r['stage']} {STAGES[r['stage']]}",
             f"Priority: {r['priority']}" + (f" · Due: {r['due_date']}" if r["due_date"] else "")]
    if result["comment"] and not hide:
        lines += ["", "Comment:", result["comment"]]
    lines += ["", f"{config.app_url()}/requirements/{r['id']}"]
    send(u["email"], f"[PMT {r['code']}] #{r['id']} {r['title']}: {result['action']}", "\n".join(lines))
