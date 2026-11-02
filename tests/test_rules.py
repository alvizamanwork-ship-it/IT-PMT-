import io
import os

import pytest
from fastapi.testclient import TestClient

from app import digest, mailer
from app import files as F
from app import projects as P
from app import workflow as W
from app.main import app
from app.perms import Forbidden, RuleError


def req(w, by="sh"):
    return W.create(w.conn, w.U[by], w.pid, "Login page")


def at(w, rid, stage, holder):
    w.conn.execute("UPDATE requirements SET stage=?, holder_id=? WHERE id=?",
                   (stage, w.U[holder]["id"], rid))


def r_(w, rid):
    return W.get(w.conn, rid)


def overrides(w):
    return w.conn.execute("SELECT COUNT(*) n FROM history WHERE override=1").fetchone()["n"]


def uid(w, n):
    return w.U[n]["id"]


# ---------- projects and members ----------
def test_only_cto_creates_projects(w):
    with pytest.raises(Forbidden):
        P.create(w.conn, w.U["pl"], "Beta", "BET")
    assert os.path.isdir(w.root / "ALP")


def test_member_management(w):
    P.add_member(w.conn, w.U["pl"], w.pid, uid(w, "out"), "Developer")
    P.remove_member(w.conn, w.U["dl"], w.pid, uid(w, "out"))
    with pytest.raises(Forbidden):
        P.add_member(w.conn, w.U["pl"], w.pid, uid(w, "out"), "Business Stakeholder")
    with pytest.raises(Forbidden):
        P.add_member(w.conn, w.U["dev"], w.pid, uid(w, "out"), "QA")
    with pytest.raises(Forbidden):
        P.remove_member(w.conn, w.U["pl"], w.pid, uid(w, "sh"))


def test_cannot_remove_member_holding_requirement(w):
    req(w)
    with pytest.raises(RuleError):
        P.remove_member(w.conn, w.U["cto"], w.pid, uid(w, "sh"))


def test_only_cto_sets_status(w):
    with pytest.raises(Forbidden):
        P.set_status(w.conn, w.U["pl"], w.pid, "On Hold")


def test_close_project_rules(w):
    rid = req(w)
    with pytest.raises(RuleError):
        P.set_status(w.conn, w.U["cto"], w.pid, "Closed", confirm=True)
    at(w, rid, 8, "sh")
    with pytest.raises(RuleError):
        P.set_status(w.conn, w.U["cto"], w.pid, "Closed", confirm=False)
    P.set_status(w.conn, w.U["cto"], w.pid, "Closed", confirm=True)
    assert P.get(w.conn, w.pid)["status"] == "Closed"
    P.set_status(w.conn, w.U["cto"], w.pid, "Active")  # reopen


def test_non_member_cannot_see_project(w):
    rid = req(w)
    with pytest.raises(Forbidden):
        W.load(w.conn, w.U["out"], rid)
    w.conn.commit()
    c = TestClient(app)
    c.post("/login", data={"username": "out", "password": "password1"})
    assert c.get(f"/projects/{w.pid}").status_code == 403
    assert c.get(f"/requirements/{rid}").status_code == 403
    assert "Alpha" not in c.get("/projects").text


# ---------- requirements ----------
def test_creators(w):
    with pytest.raises(Forbidden):
        req(w, "dev")
    with pytest.raises(Forbidden):
        req(w, "qa")
    for who in ("sh", "an", "pl", "cto"):
        r = r_(w, req(w, who))
        assert (r["stage"], r["holder_id"]) == (1, uid(w, who))
    assert sorted(os.listdir(r["folder_path"])) == F.STAGE_FOLDERS


def test_only_holder_acts(w):
    rid = req(w)
    with pytest.raises(Forbidden):
        W.proceed(w.conn, w.U["dev"], rid, uid(w, "an"))


def test_proceed(w):
    rid = req(w)
    W.proceed(w.conn, w.U["sh"], rid, uid(w, "an"))
    r = r_(w, rid)
    assert (r["stage"], r["holder_id"], r["prev_sender_id"], r["prev_sender_stage"]) == \
        (2, uid(w, "an"), uid(w, "sh"), 1)
    with pytest.raises(RuleError):
        W.proceed(w.conn, w.U["an"], rid, uid(w, "out"))  # recipient must be a member


def test_feedback_needs_comment_and_keeps_stage(w):
    rid = req(w)
    with pytest.raises(RuleError):
        W.feedback(w.conn, w.U["sh"], rid, uid(w, "an"), " ")
    W.feedback(w.conn, w.U["sh"], rid, uid(w, "an"), "please check")
    r = r_(w, rid)
    assert (r["stage"], r["holder_id"]) == (1, uid(w, "an"))


def test_send_back(w):
    rid = req(w)
    W.proceed(w.conn, w.U["sh"], rid, uid(w, "an"))
    W.proceed(w.conn, w.U["an"], rid, uid(w, "dl"))
    with pytest.raises(RuleError):
        W.send_back(w.conn, w.U["dl"], rid, "")
    W.send_back(w.conn, w.U["dl"], rid, "unclear")
    r = r_(w, rid)
    assert (r["stage"], r["holder_id"], r["prev_sender_id"]) == (2, uid(w, "an"), uid(w, "dl"))


def test_send_back_to_removed_sender_goes_to_analyst(w):
    rid = req(w, "pl")
    W.proceed(w.conn, w.U["pl"], rid, uid(w, "dev"))
    P.remove_member(w.conn, w.U["cto"], w.pid, uid(w, "pl"))
    W.send_back(w.conn, w.U["dev"], rid, "who wrote this?")
    r = r_(w, rid)
    assert (r["stage"], r["holder_id"]) == (1, uid(w, "an"))


def test_after_qa_goes_to_analyst(w):
    rid = req(w)
    at(w, rid, 5, "qa")
    with pytest.raises(Forbidden):
        W.proceed(w.conn, w.U["qa"], rid, uid(w, "dev"))
    W.proceed(w.conn, w.U["qa"], rid, uid(w, "an"))
    W.proceed(w.conn, w.U["an"], rid, uid(w, "sh"))  # analyst picks anyone
    assert r_(w, rid)["stage"] == 7


def test_accept(w):
    rid = req(w)
    at(w, rid, 7, "pl")
    with pytest.raises(Forbidden):
        W.accept(w.conn, w.U["pl"], rid)
    at(w, rid, 7, "sh")
    with pytest.raises(RuleError):
        W.proceed(w.conn, w.U["sh"], rid, uid(w, "an"))
    W.accept(w.conn, w.U["sh"], rid)
    r = r_(w, rid)
    assert (r["stage"], r["holder_id"]) == (8, None)
    with pytest.raises(RuleError):
        W.proceed(w.conn, w.U["cto"], rid, uid(w, "an"))


def test_reassign(w):
    rid = req(w)
    with pytest.raises(Forbidden):
        W.reassign(w.conn, w.U["an"], rid, uid(w, "dev"))
    W.reassign(w.conn, w.U["pl"], rid, uid(w, "dev"))
    W.reassign(w.conn, w.U["dl"], rid, uid(w, "qa"))
    r = r_(w, rid)
    assert (r["stage"], r["holder_id"]) == (1, uid(w, "qa"))


def test_on_hold_blocks_actions_and_queue(w):
    rid = req(w)
    P.set_status(w.conn, w.U["cto"], w.pid, "On Hold")
    with pytest.raises(Forbidden):
        W.proceed(w.conn, w.U["sh"], rid, uid(w, "an"))
    with pytest.raises(Forbidden):
        req(w)
    assert W.queue(w.conn, w.U["sh"]) == []
    P.set_status(w.conn, w.U["cto"], w.pid, "Active")
    assert len(W.queue(w.conn, w.U["sh"])) == 1


def test_stall_timer_pauses(w):
    rid = req(w)
    w.conn.execute("UPDATE requirements SET entered_stage_at='2026-01-01T00:00:00+00:00'")
    P.set_status(w.conn, w.U["cto"], w.pid, "Cancelled")
    w.conn.execute("UPDATE projects SET paused_at='2026-01-02T00:00:00+00:00'")
    assert digest.stalled(w.conn)[1] == []
    P.set_status(w.conn, w.U["cto"], w.pid, "Active")
    assert r_(w, rid)["entered_stage_at"] > "2026-01-01T00:00:00+00:00"


def test_cto_override_is_logged(w):
    rid = req(w)
    P.set_status(w.conn, w.U["cto"], w.pid, "On Hold")
    W.proceed(w.conn, w.U["cto"], rid, uid(w, "an"))
    assert r_(w, rid)["stage"] == 2
    assert overrides(w) == 1
    W.add_comment(w.conn, w.U["cto"], rid, "fine")  # CTO commenting is not an override
    assert overrides(w) == 1


def test_internal_comments_hidden_from_stakeholder(w):
    rid = req(w)
    W.proceed(w.conn, w.U["sh"], rid, uid(w, "an"))
    W.add_comment(w.conn, w.U["an"], rid, "internal note", internal=True)
    W.add_comment(w.conn, w.U["an"], rid, "shared note")
    W.add_comment(w.conn, w.U["sh"], rid, "stakeholder note", internal=True)
    res = W.feedback(w.conn, w.U["an"], rid, uid(w, "sh"), "secret reason", internal=True)
    mailer.handoff(w.conn, w.U["an"], res)
    assert "secret reason" not in mailer.outbox[-1].get_content()
    r = r_(w, rid)
    texts = [c["text"] for c in W.comments(w.conn, w.U["sh"], r)]
    assert texts == ["shared note", "stakeholder note"]
    assert all("secret" not in h["comment"] for h in W.history(w.conn, w.U["sh"], r))
    assert len(W.comments(w.conn, w.U["dev"], r)) == 3
    assert any("secret" in h["comment"] for h in W.history(w.conn, w.U["dev"], r))


def test_handoff_email_includes_comment(w):
    rid = req(w)
    res = W.feedback(w.conn, w.U["sh"], rid, uid(w, "an"), "see attached")
    mailer.handoff(w.conn, w.U["sh"], res)
    m = mailer.outbox[-1]
    assert m["To"] == "an@example.com" and "see attached" in m.get_content()


# ---------- files ----------
def test_upload_versions_and_download(w):
    rid = req(w)
    names = [F.upload(w.conn, w.U["sh"], rid, "spec.docx", io.BytesIO(b"x")) for _ in range(3)]
    assert names == ["spec.docx", "spec_v2.docx", "spec_v3.docx"]
    f = F.for_requirement(w.conn, rid)[0]
    assert "01_Business_Requirements" in f["path"]
    assert F.download(w.conn, w.U["dev"], f["id"])[0] == f["name"]
    with pytest.raises(Forbidden):
        F.download(w.conn, w.U["out"], f["id"])


# ---------- digest ----------
def test_digest_lists_stalled(w):
    rid = req(w)
    req(w)
    w.conn.execute("UPDATE requirements SET entered_stage_at='2026-01-01T00:00:00+00:00' WHERE id=?",
                   (rid,))
    w.conn.commit()
    assert digest.run_once() == 1
    assert mailer.outbox[-1]["To"] == "cto@example.com"


# ---------- UI settings ----------
def test_user_settings_saved(w):
    c = TestClient(app)
    c.post("/login", data={"username": "dev", "password": "password1"})
    c.post("/settings", data={"theme": "dark", "font": "atkinson", "font_size": 3})
    html = c.get("/").text
    assert 'data-theme="dark"' in html and 'data-font="atkinson"' in html and 'data-size="3"' in html
    assert c.post("/settings", data={"theme": "neon"}).status_code == 400
