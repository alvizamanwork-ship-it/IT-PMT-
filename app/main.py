import os

from fastapi import Depends, FastAPI, File, Form, Request, UploadFile
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from . import auth, config, db, mailer
from . import files as F
from . import projects as P
from . import workflow as W
from .perms import Forbidden, NotFound, RuleError, can_view, role_of

BASE = os.path.dirname(__file__)
templates = Jinja2Templates(directory=os.path.join(BASE, "templates"))
templates.env.globals.update(stages=W.STAGES, priorities=W.PRIORITIES)


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
    if config.digest_enabled():
        from .digest import start_scheduler
        start_scheduler()


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
    history = conn.execute(W.HISTORY_SQL + "WHERE h.project_id=? AND h.requirement_id IS NULL ORDER BY h.id DESC", (pid,)).fetchall()
    ctx = dict(p=p, members=P.members(conn, pid), history=history, roles=P.ROLES,
               statuses=P.STATUSES, my_role=role_of(conn, pid, user["id"]),
               can_manage=P.can_manage_members(conn, user, pid),
               all_users=conn.execute("SELECT id, name, username FROM users ORDER BY name").fetchall())
    ctx.update(project_extra(conn, user, p))
    return render(request, "project.html", user, **ctx)


def project_extra(conn, user, p):
    can_create = bool(user["is_cto"]) or role_of(conn, p["id"], user["id"]) in W.CREATORS
    return dict(requirements=W.for_project(conn, p["id"]), can_create=can_create)


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
    return render(request, "queue.html", user, items=W.queue(conn, user))


# ---------- requirements ----------
@app.post("/projects/{pid}/requirements")
def req_create(pid: int, title: str = Form(...), description: str = Form(""),
               due_date: str = Form(""), priority: str = Form("Normal"),
               user=Depends(current_user), conn=Depends(get_conn)):
    rid = W.create(conn, user, pid, title, description, due_date, priority)
    return back(f"/requirements/{rid}")


@app.get("/requirements/{rid}")
def req_page(rid: int, request: Request, user=Depends(current_user), conn=Depends(get_conn)):
    r = W.load(conn, user, rid)
    pid = r["project_id"]
    my_role = role_of(conn, pid, user["id"])
    names = {u["id"]: u["name"] for u in conn.execute("SELECT id, name FROM users").fetchall()}
    ctx = dict(r=r, my_role=my_role, members=P.members(conn, pid), names=names,
               history=W.history(conn, user, r), comments=W.comments(conn, user, r),
               stakeholder=W.stakeholder_view(conn, user, pid),
               can_act=r["stage"] < W.CLOSED and (r["holder_id"] == user["id"] or bool(user["is_cto"])),
               can_reassign=r["stage"] < W.CLOSED and (my_role in ("Project Lead", "Dev Lead")
                                                       or bool(user["is_cto"])))
    ctx.update(req_extra(conn, user, r))
    return render(request, "requirement.html", user, **ctx)


def req_extra(conn, user, r):
    return dict(files=F.for_requirement(conn, r["id"]))


@app.post("/requirements/{rid}/files")
def req_upload(rid: int, file: UploadFile = File(...), user=Depends(current_user),
               conn=Depends(get_conn)):
    if not file.filename:
        raise RuleError("Choose a file to upload.")
    F.upload(conn, user, rid, file.filename, file.file)
    return back(f"/requirements/{rid}#files")


@app.get("/files/{fid}")
def file_download(fid: int, user=Depends(current_user), conn=Depends(get_conn)):
    name, path = F.download(conn, user, fid)
    return FileResponse(path, filename=name)


@app.post("/requirements/{rid}/action")
def req_action(rid: int, action: str = Form(...), to_user: int = Form(0), comment: str = Form(""),
               internal: str = Form(""), user=Depends(current_user), conn=Depends(get_conn)):
    internal = internal == "yes"
    if action == "proceed":
        res = W.proceed(conn, user, rid, to_user, comment, internal)
    elif action == "feedback":
        res = W.feedback(conn, user, rid, to_user, comment, internal)
    elif action == "back":
        res = W.send_back(conn, user, rid, comment, internal)
    elif action == "accept":
        res = W.accept(conn, user, rid, comment)
    else:
        raise RuleError("Unknown action.")
    mailer.handoff(conn, user, res)
    return back(f"/requirements/{rid}")


@app.post("/requirements/{rid}/reassign")
def req_reassign(rid: int, to_user: int = Form(...), comment: str = Form(""),
                 user=Depends(current_user), conn=Depends(get_conn)):
    mailer.handoff(conn, user, W.reassign(conn, user, rid, to_user, comment))
    return back(f"/requirements/{rid}")


@app.post("/requirements/{rid}/comments")
def req_comment(rid: int, text: str = Form(...), internal: str = Form(""),
                user=Depends(current_user), conn=Depends(get_conn)):
    W.add_comment(conn, user, rid, text, internal == "yes")
    return back(f"/requirements/{rid}#comments")
