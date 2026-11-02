import os

from fastapi import Depends, FastAPI, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from . import auth, config, db
from . import projects as P
from .perms import Forbidden, NotFound, RuleError, can_view, role_of

BASE = os.path.dirname(__file__)
templates = Jinja2Templates(directory=os.path.join(BASE, "templates"))
templates.env.globals["stages"] = {1: "Requirements", 2: "Analysis", 3: "Dev Review", 4: "Development",
                                   5: "QA", 6: "Analyst Review", 7: "Acceptance", 8: "Closed"}


class LoginRequired(Exception):
    pass


def get_conn():
    c = db.connect()
    try:
        yield c
        c.commit()
    finally:
        c.close()


def current_user(request: Request, conn=Depends(get_conn)):
    uid = request.session.get("uid")
    u = conn.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone() if uid else None
    if not u:
        raise LoginRequired()
    return u


def render(request, name, user=None, status_code=200, **ctx):
    return templates.TemplateResponse(request, name, {"user": user, **ctx},
                                      status_code=status_code)


def back(url):
    return RedirectResponse(url, status_code=303)


app = FastAPI(title="PMT")
app.add_middleware(SessionMiddleware, secret_key=config.secret_key(), same_site="lax",
                   https_only=config.secure_cookies())
app.mount("/static", StaticFiles(directory=os.path.join(BASE, "static")), name="static")


@app.on_event("startup")
def _startup():
    db.init()


@app.exception_handler(LoginRequired)
def _login_required(request, exc):
    return back("/login")


@app.exception_handler(Forbidden)
def _forbidden(request, exc):
    return render(request, "error.html", status_code=403, title="Not allowed", message=str(exc))


@app.exception_handler(RuleError)
def _rule(request, exc):
    return render(request, "error.html", status_code=400, title="Cannot do that", message=str(exc))


@app.exception_handler(NotFound)
def _notfound(request, exc):
    return render(request, "error.html", status_code=404, title="Not found", message=str(exc))


# ---------- auth ----------
@app.get("/login")
def login_page(request: Request):
    return render(request, "login.html")


@app.post("/login")
def login(request: Request, username: str = Form(...), password: str = Form(...),
          conn=Depends(get_conn)):
    uid = auth.provider.authenticate(conn, username.strip(), password)
    if not uid:
        return render(request, "login.html", status_code=401, error="Wrong username or password.")
    request.session["uid"] = uid
    return back("/")


@app.post("/logout")
def logout(request: Request):
    request.session.clear()
    return back("/login")


# ---------- projects ----------
@app.get("/projects")
def project_list(request: Request, user=Depends(current_user), conn=Depends(get_conn)):
    return render(request, "projects.html", user, projects=P.visible(conn, user))


@app.get("/projects/{pid}")
def project_page(pid: int, request: Request, user=Depends(current_user), conn=Depends(get_conn)):
    p = P.get(conn, pid)
    if not can_view(conn, user, pid):
        raise Forbidden("You are not a member of this project.")
    history = conn.execute(
        "SELECT h.*, u.name AS who, tu.name AS to_name, fu.name AS from_name FROM history h "
        "JOIN users u ON u.id=h.user_id LEFT JOIN users tu ON tu.id=h.to_user_id "
        "LEFT JOIN users fu ON fu.id=h.from_user_id "
        "WHERE h.project_id=? AND h.requirement_id IS NULL ORDER BY h.id DESC", (pid,)).fetchall()
    ctx = dict(p=p, members=P.members(conn, pid), history=history, roles=P.ROLES,
               statuses=P.STATUSES, my_role=role_of(conn, pid, user["id"]),
               can_manage=P.can_manage_members(conn, user, pid),
               all_users=conn.execute("SELECT id, name, username FROM users ORDER BY name").fetchall())
    ctx.update(project_extra(conn, user, p))
    return render(request, "project.html", user, **ctx)


def project_extra(conn, user, p):
    return {}


@app.post("/projects/{pid}/members")
def member_add(pid: int, user_id: int = Form(...), role: str = Form(...),
               user=Depends(current_user), conn=Depends(get_conn)):
    P.add_member(conn, user, pid, user_id, role)
    return back(f"/projects/{pid}")


@app.post("/projects/{pid}/members/{uid}/remove")
def member_remove(pid: int, uid: int, user=Depends(current_user), conn=Depends(get_conn)):
    P.remove_member(conn, user, pid, uid)
    return back(f"/projects/{pid}")


@app.post("/projects/{pid}/status")
def project_status(pid: int, status: str = Form(...), confirm: str = Form(""),
                   user=Depends(current_user), conn=Depends(get_conn)):
    P.set_status(conn, user, pid, status, confirm == "yes")
    return back(f"/projects/{pid}")


# ---------- admin ----------
def _cto(user):
    if not user["is_cto"]:
        raise Forbidden("Admin is for the CTO only.")


@app.get("/admin")
def admin(request: Request, user=Depends(current_user), conn=Depends(get_conn)):
    _cto(user)
    return render(request, "admin.html", user, stall_days=db.stall_days(conn),
                  users=conn.execute("SELECT * FROM users ORDER BY name").fetchall())


@app.post("/admin/projects")
def admin_project(name: str = Form(...), code: str = Form(...),
                  user=Depends(current_user), conn=Depends(get_conn)):
    pid = P.create(conn, user, name, code)
    return back(f"/projects/{pid}")


@app.post("/admin/users")
def admin_user(username: str = Form(...), name: str = Form(...), email: str = Form(""),
               password: str = Form(...), user=Depends(current_user), conn=Depends(get_conn)):
    _cto(user)
    username = username.strip()
    if not username or not name.strip() or len(password) < 8:
        raise RuleError("Username and name are required; password needs 8+ characters.")
    if conn.execute("SELECT 1 FROM users WHERE username=?", (username,)).fetchone():
        raise RuleError("Username already exists.")
    conn.execute("INSERT INTO users(username,name,email,password_hash) VALUES(?,?,?,?)",
                 (username, name.strip(), email.strip(), auth.hash_password(password)))
    return back("/admin")


@app.post("/admin/settings")
def admin_settings(stall_days: int = Form(...), user=Depends(current_user),
                   conn=Depends(get_conn)):
    _cto(user)
    if stall_days < 1:
        raise RuleError("STALL_DAYS must be at least 1.")
    db.set_setting(conn, "stall_days", stall_days)
    return back("/admin")


# ---------- home ----------
@app.get("/")
def my_queue(request: Request, user=Depends(current_user), conn=Depends(get_conn)):
    return render(request, "queue.html", user, items=[])
