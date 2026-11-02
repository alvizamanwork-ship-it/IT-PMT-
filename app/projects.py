import os
import re
from datetime import timedelta

from . import config
from .db import now, parse
from .perms import LEADS, Forbidden, NotFound, RuleError, log, role_of

ROLES = ["Project Lead", "Dev Lead", "Project Analyst", "Business Stakeholder", "Developer", "QA"]
STATUSES = ["Active", "On Hold", "Cancelled", "Closed"]
PAUSED = ("On Hold", "Cancelled")
STAKEHOLDER = "Business Stakeholder"


def get(conn, pid):
    p = conn.execute("SELECT * FROM projects WHERE id=?", (pid,)).fetchone()
    if not p:
        raise NotFound("Project not found.")
    return p


def visible(conn, user):
    if user["is_cto"]:
        return conn.execute("SELECT p.*, m.role FROM projects p LEFT JOIN members m "
                            "ON m.project_id=p.id AND m.user_id=? ORDER BY p.name",
                            (user["id"],)).fetchall()
    return conn.execute("SELECT p.*, m.role FROM projects p JOIN members m ON m.project_id=p.id "
                        "WHERE m.user_id=? ORDER BY p.name", (user["id"],)).fetchall()


def members(conn, pid):
    return conn.execute("SELECT u.id, u.name, u.email, m.role FROM members m JOIN users u "
                        "ON u.id=m.user_id WHERE m.project_id=? ORDER BY u.name", (pid,)).fetchall()


def can_manage_members(conn, user, pid):
    return bool(user["is_cto"]) or role_of(conn, pid, user["id"]) in LEADS


def create(conn, user, name, code):
    if not user["is_cto"]:
        raise Forbidden("Only the CTO creates projects.")
    name, code = name.strip(), code.strip().upper()
    if not name or not re.fullmatch(r"[A-Z0-9_-]{1,20}", code):
        raise RuleError("Name is required; code must be 1-20 letters, digits, - or _.")
    if conn.execute("SELECT 1 FROM projects WHERE code=?", (code,)).fetchone():
        raise RuleError("A project with this code already exists.")
    folder = os.path.join(config.file_root(), code)
    pid = conn.execute("INSERT INTO projects(name,code,folder_path,created_at) VALUES(?,?,?,?)",
                       (name, code, folder, now())).lastrowid
    from .files import make_project_folder
    make_project_folder(folder)
    log(conn, pid, user, "Project created")
    return pid


def _member_rule(conn, user, pid, role):
    if role == STAKEHOLDER:
        if not user["is_cto"]:
            raise Forbidden("Only the CTO manages Business Stakeholders.")
    elif not can_manage_members(conn, user, pid):
        raise Forbidden("Only the CTO, Project Lead or Dev Lead manage members.")


def add_member(conn, user, pid, uid, role):
    get(conn, pid)
    if role not in ROLES:
        raise RuleError("Unknown role.")
    _member_rule(conn, user, pid, role)
    if not conn.execute("SELECT 1 FROM users WHERE id=?", (uid,)).fetchone():
        raise RuleError("Unknown user.")
    if role_of(conn, pid, uid):
        raise RuleError("User is already a member.")
    conn.execute("INSERT INTO members(project_id,user_id,role) VALUES(?,?,?)", (pid, uid, role))
    log(conn, pid, user, f"Added member as {role}", to_user=uid)


def remove_member(conn, user, pid, uid):
    role = role_of(conn, pid, uid)
    if not role:
        raise RuleError("User is not a member.")
    _member_rule(conn, user, pid, role)
    if conn.execute("SELECT 1 FROM requirements WHERE project_id=? AND holder_id=? AND stage<8",
                    (pid, uid)).fetchone():
        raise RuleError("This member holds open requirements. Reassign them first.")
    conn.execute("DELETE FROM members WHERE project_id=? AND user_id=?", (pid, uid))
    log(conn, pid, user, f"Removed member ({role})", from_user=uid)


def set_status(conn, user, pid, status, confirm=False):
    if not user["is_cto"]:
        raise Forbidden("Only the CTO changes project status.")
    p = get(conn, pid)
    if status not in STATUSES:
        raise RuleError("Unknown status.")
    if status == p["status"]:
        return
    if status == "Closed":
        if conn.execute("SELECT 1 FROM requirements WHERE project_id=? AND stage<8",
                        (pid,)).fetchone():
            raise RuleError("All requirements must be Closed before the project can close.")
        if not confirm:
            raise RuleError("Tick the confirmation box to close the project.")
    t = now()
    paused_at = p["paused_at"]
    if status in PAUSED and p["status"] not in PAUSED:
        paused_at = t
    elif status not in PAUSED and p["status"] in PAUSED:
        # Resume the stall timer: shift entered-stage times by the paused duration.
        delta = parse(t) - parse(p["paused_at"]) if p["paused_at"] else timedelta(0)
        for r in conn.execute("SELECT id, entered_stage_at FROM requirements "
                              "WHERE project_id=? AND stage<8", (pid,)).fetchall():
            new = (parse(r["entered_stage_at"]) + delta).isoformat(timespec="seconds")
            conn.execute("UPDATE requirements SET entered_stage_at=? WHERE id=?", (new, r["id"]))
        paused_at = None
    conn.execute("UPDATE projects SET status=?, paused_at=? WHERE id=?", (status, paused_at, pid))
    log(conn, pid, user, f"Status changed: {p['status']} to {status}")
