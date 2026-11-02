import os
from types import SimpleNamespace

import pytest

os.environ["DIGEST_ENABLED"] = "0"

from app import auth, db  # noqa: E402
from app import projects as P  # noqa: E402

ROLES = [("pl", "Project Lead"), ("dl", "Dev Lead"), ("an", "Project Analyst"),
         ("sh", "Business Stakeholder"), ("dev", "Developer"), ("qa", "QA")]


@pytest.fixture
def w(tmp_path, monkeypatch):
    monkeypatch.setattr(auth, "ITERATIONS", 1000)
    monkeypatch.setenv("PMT_DB", str(tmp_path / "t.db"))
    monkeypatch.setenv("FILE_ROOT", str(tmp_path / "files"))
    monkeypatch.setenv("ADMIN_EMAIL", "cto@example.com")
    monkeypatch.setenv("ADMIN_PASSWORD", "password1")
    db.init()
    conn = db.connect()
    U = {"cto": conn.execute("SELECT * FROM users WHERE id=1").fetchone()}
    for name in [n for n, _ in ROLES] + ["out"]:
        uid = conn.execute("INSERT INTO users(username,name,email,password_hash) VALUES(?,?,?,?)",
                           (name, name.upper(), f"{name}@example.com",
                            auth.hash_password("password1"))).lastrowid
        U[name] = conn.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
    pid = P.create(conn, U["cto"], "Alpha", "ALP")
    for name, role in ROLES:
        P.add_member(conn, U["cto"], pid, U[name]["id"], role)
    conn.commit()
    yield SimpleNamespace(conn=conn, U=U, pid=pid, root=tmp_path / "files")
    conn.close()
