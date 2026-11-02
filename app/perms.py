from .db import now

LEADS = ("Project Lead", "Dev Lead")


class Forbidden(Exception):
    pass


class RuleError(Exception):
    pass


class NotFound(Exception):
    pass


def role_of(conn, pid, uid):
    r = conn.execute("SELECT role FROM members WHERE project_id=? AND user_id=?",
                     (pid, uid)).fetchone()
    return r["role"] if r else None


def can_view(conn, user, pid):
    return bool(user["is_cto"]) or role_of(conn, pid, user["id"]) is not None


def ensure_view(conn, user, pid):
    if not can_view(conn, user, pid):
        raise Forbidden("You are not a member of this project.")


def require(user, ok, what):
    """Pass if allowed. The CTO bypasses any rule; returns True when that is an override."""
    if ok:
        return False
    if user["is_cto"]:
        return True
    raise Forbidden(what)


def log(conn, project_id, user, action, requirement_id=None, from_user=None, to_user=None,
        from_stage=None, to_stage=None, comment="", internal=False, override=False):
    if override:
        action += " (CTO override)"
    conn.execute(
        "INSERT INTO history(project_id,requirement_id,user_id,at,action,from_user_id,to_user_id,"
        "from_stage,to_stage,comment,internal,override) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
        (project_id, requirement_id, user["id"], now(), action, from_user, to_user,
         from_stage, to_stage, comment or "", int(bool(internal)), int(bool(override))))
