# PMT — lightweight project management for the IT team

FastAPI + SQLite + Jinja templates. Files live on a mounted network share; only names and paths are stored in the DB.

## Run

```bash
pip install -r requirements.txt
FILE_ROOT=/mnt/share/pmt SECRET_KEY=... uvicorn app.main:app --host 0.0.0.0 --port 8000
```

First start creates a CTO account from `ADMIN_USERNAME` / `ADMIN_PASSWORD` (default `admin` / `admin` — change it). The CTO adds users in Admin.

## Configuration (env vars)

| Var | Default | Purpose |
|---|---|---|
| `PMT_DB` | `pmt.db` | SQLite file path |
| `FILE_ROOT` | `./files` | Mounted network share root |
| `STALL_DAYS` | `5` | Default stall threshold (CTO can override in Admin; stored in DB) |
| `SECRET_KEY` | `change-me` | Session cookie signing key |
| `SECURE_COOKIES` | `0` | Set `1` behind HTTPS |
| `APP_URL` | `http://localhost:8000` | Base URL used in email links |
| `ADMIN_USERNAME` / `ADMIN_PASSWORD` / `ADMIN_EMAIL` / `ADMIN_NAME` | `admin` / `admin` / empty / `CTO` | Bootstrap CTO account (only if no users exist) |

## Defaults and decisions

- **Auth**: local accounts, PBKDF2-SHA256 hashed passwords, signed session cookie. `app/auth.py` has an `AuthProvider` interface; replace `provider` with a directory (LDAP/AD) implementation later.
- **User accounts**: created by the CTO in Admin (needed so people can log in). No self-signup, no password reset UI.
- **One role per user per project.**
- **Removing a member** is blocked while they hold open requirements (reassign first). Stakeholders can only be added/removed by the CTO.
- **CTO overrides**: whenever the CTO does something the normal rules would block (acting when not the holder, acting on an On Hold/Cancelled project, etc.), the history entry is marked "(CTO override)" and flagged in the DB.
- **Project status**: the CTO can set any status. Leaving Active for On Hold/Cancelled pauses the stall timer; returning to Active shifts each open requirement's entered-stage time by the paused duration. Closing needs all requirements Closed plus a confirmation tick (not bypassable).
- **CSRF**: relies on `SameSite=Lax` session cookies (internal tool).
- **New requirement**: starts at stage 1 Requirements, held by its creator.
- **Proceed** is not offered at stage 7; the Stakeholder uses **Accept** to move to Closed. Proceed from stage 5 QA must go to a Project Analyst ("after QA the Analyst chooses the next person").
- **Send Back** goes to the previous sender at the stage they held when they sent it; the sender becomes the new previous sender. If that person is no longer a member, it goes to the first Project Analyst.
- **Reassign** (Project Lead, Dev Lead, CTO) changes the holder without changing the stage or previous sender.
- **Comments**: shared by default; tick "Internal" to hide from Stakeholders. Stakeholders' own comments are always shared. Internal action comments are blanked in the history Stakeholders see.
- **My Queue** is sorted by priority (High first), then due date.
- **Folders**: `FILE_ROOT/<CODE>/<id>_<Title>/` with the six stage folders. Stage mapping for uploads: 1→01, 2→02, 3→03, 4→04, 5→05, 6 Analyst Review→02_Analysis, 7 Acceptance and 8 Closed→06_Acceptance. File and folder names are sanitised. Any project member can upload while the project is Active.
