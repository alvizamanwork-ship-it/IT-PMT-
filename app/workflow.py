"""Requirements, stages, actions, history and comments."""
from datetime import date

from . import projects as P
from .db import now
from .perms import LEADS, NotFound, RuleError, ensure_view, log, require, role_of

STAGES = {1: "Requirements", 2: "Analysis", 3: "Dev Review", 4: "Development",
          5: "QA", 6: "Analyst Review", 7: "Acceptance", 8: "Closed"}
CLOSED = 8
PRIORITIES = ["Low", "Normal", "High"]
CREATORS = ("Business Stakeholder", "Project Analyst", "Project Lead")
ANALYST = "Project Analyst"


def get(conn, rid):
    r = conn.execute("SELECT r.*, p.status AS project_status, p.code, p.name AS project_name "
                     "FROM requirements r JOIN projects p ON p.id=r.project_id WHERE r.id=?",
                     (rid,)).fetchone()
    if not r:
        raise NotFound("Requirement not found.")
    return r


def load(conn, user, rid):
    r = get(conn, rid)
    ensure_view(conn, user, r["project_id"])
    return r


def stakeholder_view(conn, user, pid):
    return not user["is_cto"] and role_of(conn, pid, user["id"]) == P.STAKEHOLDER


def create(conn, user, pid, title, description="", due_date="", priority="Normal"):
    p = P.get(conn, pid)
    ensure_view(conn, user, pid)
    title = title.strip()
    if not title:
        raise RuleError("Title is required.")
    if priority not in PRIORITIES:
        raise RuleError("Unknown priority.")
    if due_date:
        try:
            date.fromisoformat(due_date)
        except ValueError:
            raise RuleError("Due date must be YYYY-MM-DD.")
    ok = user["is_cto"] or role_of(conn, pid, user["id"]) in CREATORS
    ov = require(user, ok, "Only Stakeholders, Analysts, Project Leads or the CTO create requirements.")
    ov |= require(user, p["status"] == "Active", f"Project is {p['status']}; no new requirements.")
    t = now()
    rid = conn.execute(
        "INSERT INTO requirements(project_id,title,description,stage,holder_id,due_date,priority,"
        "created_by,entered_stage_at,created_at) VALUES(?,?,?,1,?,?,?,?,?,?)",
        (pid, title, description.strip(), user["id"], due_date or None, priority, user["id"], t, t)
    ).lastrowid
    log(conn, pid, user, "Created requirement", rid, to_user=user["id"], to_stage=1, override=ov)
    return rid


# ---------- actions ----------
def _guard(user, r):
    if r["stage"] == CLOSED:
        raise RuleError("This requirement is Closed.")
    ov = require(user, r["project_status"] == "Active",
                 f"Project is {r['project_status']}; actions are blocked.")
    ov |= require(user, r["holder_id"] == user["id"],
                  "Only the current holder can act on this requirement.")
    return ov


def _member_role(conn, pid, uid):
    role = role_of(conn, pid, uid)
    if not role:
        raise RuleError("Recipient must be a project member.")
    return role


def _need_comment(comment):
    if not (comment or "").strip():
        raise RuleError("A comment is required for this action.")


def _move(conn, user, r, action, to_uid, to_stage, comment, internal, ov, set_prev=True):
    t = now()
    entered = t if to_stage != r["stage"] else r["entered_stage_at"]
    if stakeholder_view(conn, user, r["project_id"]):
        internal = False
    prev_id, prev_stage = (user["id"], r["stage"]) if set_prev else \
        (r["prev_sender_id"], r["prev_sender_stage"])
    conn.execute("UPDATE requirements SET stage=?, holder_id=?, prev_sender_id=?, "
                 "prev_sender_stage=?, entered_stage_at=? WHERE id=?",
                 (to_stage, to_uid, prev_id, prev_stage, entered, r["id"]))
    log(conn, r["project_id"], user, action, r["id"], from_user=r["holder_id"], to_user=to_uid,
        from_stage=r["stage"], to_stage=to_stage, comment=(comment or "").strip(),
        internal=internal, override=ov)
    return {"action": action, "to": to_uid, "comment": (comment or "").strip(),
            "internal": bool(internal), "stage": to_stage, "requirement_id": r["id"]}


def proceed(conn, user, rid, to_uid, comment="", internal=False):
    r = load(conn, user, rid)
    ov = _guard(user, r)
    if r["stage"] >= 7:
        raise RuleError("At Acceptance the Stakeholder uses Accept.")
    role = _member_role(conn, r["project_id"], to_uid)
    if r["stage"] == 5:
        ov |= require(user, role == ANALYST, "After QA the requirement goes to the Project Analyst.")
    return _move(conn, user, r, "Proceed", to_uid, r["stage"] + 1, comment, internal, ov)


def feedback(conn, user, rid, to_uid, comment, internal=False):
    r = load(conn, user, rid)
    ov = _guard(user, r)
    _need_comment(comment)
    _member_role(conn, r["project_id"], to_uid)
    return _move(conn, user, r, "Send with Feedback", to_uid, r["stage"], comment, internal, ov)


def send_back(conn, user, rid, comment, internal=False):
    r = load(conn, user, rid)
    ov = _guard(user, r)
    _need_comment(comment)
    if not r["prev_sender_id"]:
        raise RuleError("There is no previous sender to send this back to.")
    to, stage = r["prev_sender_id"], r["prev_sender_stage"]
    if not role_of(conn, r["project_id"], to):
        a = conn.execute("SELECT user_id FROM members WHERE project_id=? AND role=? "
                         "ORDER BY user_id LIMIT 1", (r["project_id"], ANALYST)).fetchone()
        if not a:
            raise RuleError("The previous sender was removed and the project has no Analyst.")
        to = a["user_id"]
    return _move(conn, user, r, "Send Back", to, stage, comment, internal, ov)


def accept(conn, user, rid, comment=""):
    r = load(conn, user, rid)
    ov = _guard(user, r)
    ok = r["stage"] == 7 and role_of(conn, r["project_id"], user["id"]) == P.STAKEHOLDER
    ov |= require(user, ok, "Only the Business Stakeholder can accept, at the Acceptance stage.")
    return _move(conn, user, r, "Accept", None, CLOSED, comment, False, ov)


def reassign(conn, user, rid, to_uid, comment=""):
    r = load(conn, user, rid)
    if r["stage"] == CLOSED:
        raise RuleError("This requirement is Closed.")
    ov = require(user, r["project_status"] == "Active",
                 f"Project is {r['project_status']}; actions are blocked.")
    ov |= require(user, role_of(conn, r["project_id"], user["id"]) in LEADS,
                  "Only the Project Lead or Dev Lead can reassign.")
    _member_role(conn, r["project_id"], to_uid)
    return _move(conn, user, r, "Reassign", to_uid, r["stage"], comment, False, ov, set_prev=False)


# ---------- comments / reads ----------
def add_comment(conn, user, rid, text, internal=False):
    r = load(conn, user, rid)
    text = (text or "").strip()
    if not text:
        raise RuleError("Comment text is required.")
    if stakeholder_view(conn, user, r["project_id"]):
        internal = False
    conn.execute("INSERT INTO comments(requirement_id,user_id,at,text,internal) VALUES(?,?,?,?,?)",
                 (rid, user["id"], now(), text, int(bool(internal))))


def comments(conn, user, r):
    rows = conn.execute("SELECT c.*, u.name AS who FROM comments c JOIN users u ON u.id=c.user_id "
                        "WHERE c.requirement_id=? ORDER BY c.id", (r["id"],)).fetchall()
    if stakeholder_view(conn, user, r["project_id"]):
        rows = [c for c in rows if not c["internal"]]
    return rows


HISTORY_SQL = ("SELECT h.*, u.name AS who, tu.name AS to_name, fu.name AS from_name FROM history h "
               "JOIN users u ON u.id=h.user_id LEFT JOIN users tu ON tu.id=h.to_user_id "
               "LEFT JOIN users fu ON fu.id=h.from_user_id ")


def history(conn, user, r):
    rows = conn.execute(HISTORY_SQL + "WHERE h.requirement_id=? ORDER BY h.id DESC",
                        (r["id"],)).fetchall()
    if stakeholder_view(conn, user, r["project_id"]):
        for h in rows:
            if h["internal"]:
                h["comment"] = ""
    return rows


PRIORITY_ORDER = "CASE r.priority WHEN 'High' THEN 0 WHEN 'Normal' THEN 1 ELSE 2 END"


def queue(conn, user):
    return conn.execute(
        "SELECT r.*, p.code FROM requirements r JOIN projects p ON p.id=r.project_id "
        "WHERE r.holder_id=? AND r.stage<8 AND p.status='Active' "
        f"ORDER BY {PRIORITY_ORDER}, r.due_date IS NULL, r.due_date, r.id", (user["id"],)).fetchall()


def for_project(conn, pid):
    return conn.execute(
        "SELECT r.*, u.name AS holder_name FROM requirements r LEFT JOIN users u ON u.id=r.holder_id "
        f"WHERE r.project_id=? ORDER BY r.stage=8, {PRIORITY_ORDER}, r.id", (pid,)).fetchall()
