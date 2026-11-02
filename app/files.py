"""Folders on the network share. Only names and paths are stored in the DB."""
import os
import re
import shutil

from . import config
from .db import now
from .perms import NotFound, RuleError, log, require

STAGE_FOLDERS = ["01_Business_Requirements", "02_Analysis", "03_Dev_Review",
                 "04_Development", "05_QA", "06_Acceptance"]
# stage -> folder index (6 Analyst Review shares Analysis; 7 Acceptance and 8 Closed share Acceptance)
STAGE_TO_FOLDER = {1: 0, 2: 1, 3: 2, 4: 3, 5: 4, 6: 1, 7: 5, 8: 5}


def _clean(text, limit):
    text = re.sub(r"[^A-Za-z0-9._ -]+", "_", text or "").strip(" ._")
    return text[:limit] or "file"


def safe_name(filename, limit=80):
    return _clean(os.path.basename((filename or "").replace("\\", "/")), limit)


def make_project_folder(path):
    os.makedirs(path, exist_ok=True)


def make_requirement_folder(conn, rid):
    r = conn.execute("SELECT r.id, r.title, p.folder_path FROM requirements r JOIN projects p "
                     "ON p.id=r.project_id WHERE r.id=?", (rid,)).fetchone()
    path = os.path.join(r["folder_path"], f"{rid}_{_clean(r['title'], 50).replace(' ', '_')}")
    for sub in STAGE_FOLDERS:
        os.makedirs(os.path.join(path, sub), exist_ok=True)
    conn.execute("UPDATE requirements SET folder_path=? WHERE id=?", (path, rid))
    return path


def stage_folder(r):
    return os.path.join(r["folder_path"], STAGE_FOLDERS[STAGE_TO_FOLDER[r["stage"]]])


def _open_unique(folder, name):
    """Create a new file without overwriting: name.ext, name_v2.ext, name_v3.ext ..."""
    base, ext = os.path.splitext(name)
    n = 1
    while True:
        candidate = name if n == 1 else f"{base}_v{n}{ext}"
        path = os.path.join(folder, candidate)
        try:
            return candidate, path, open(path, "xb")
        except FileExistsError:
            n += 1


def upload(conn, user, rid, filename, fileobj):
    from . import workflow as W
    r = W.load(conn, user, rid)
    ov = require(user, r["project_status"] == "Active",
                 f"Project is {r['project_status']}; uploads are blocked.")
    folder = stage_folder(r)
    os.makedirs(folder, exist_ok=True)
    name, path, out = _open_unique(folder, safe_name(filename))
    with out:
        shutil.copyfileobj(fileobj, out)
    conn.execute("INSERT INTO files(requirement_id,stage,name,path,uploaded_by,at) VALUES(?,?,?,?,?,?)",
                 (rid, r["stage"], name, path, user["id"], now()))
    log(conn, r["project_id"], user, f"Uploaded {name}", rid, override=ov)
    return name


def for_requirement(conn, rid):
    return conn.execute("SELECT f.*, u.name AS who FROM files f JOIN users u ON u.id=f.uploaded_by "
                        "WHERE f.requirement_id=? ORDER BY f.stage, f.name", (rid,)).fetchall()


def download(conn, user, fid):
    from . import workflow as W
    f = conn.execute("SELECT * FROM files WHERE id=?", (fid,)).fetchone()
    if not f:
        raise NotFound("File not found.")
    W.load(conn, user, f["requirement_id"])  # permission check
    root = os.path.realpath(config.file_root())
    real = os.path.realpath(f["path"])
    if os.path.commonpath([root, real]) != root:
        raise RuleError("File is outside FILE_ROOT.")
    if not os.path.isfile(real):
        raise NotFound("File is missing from the share.")
    return f["name"], real
