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
