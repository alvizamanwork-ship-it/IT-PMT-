# PMT — lightweight project management for the IT team

## Clickable demo (latest design)

`demo/index.html` is a browser-only mock-up of the latest agreed design, for approval. Open it in any browser; no server needed. It starts empty (users only), and data stays in that browser. It reflects these design changes, which are **not yet in the FastAPI app below**:

- Project codes are generated from the name (e.g. "Help Desk Portal" → HDP-001); the CTO joins every project as Project Head.
- Team members are added as User + Role dropdown rows. One person can hold several roles in a project ("+ Add role"); single roles can be removed from the Members list. Only the CTO can remove a Project Lead or Dev Lead.
- Projects have a priority (Low, Normal, High) and an optional deadline, set by the CTO at creation. The CTO, Project Lead and Dev Lead can add or change them on the project page; changes are logged in Project history, and a past deadline on an Active project shows "Overdue".
- Stages: Analysis, Analysis Feedback, Development, Development Feedback, QA, QA Feedback, Approval (plus Closed). The holder picks the stage and the user on every Send; a comment is required for Feedback stages; only the Stakeholder closes from Approval.
- A requirement is visible only to its current holder. The CTO (all projects) and the Project Lead (their own project) see all requirements and holders.
- Inside their project the Project Lead has the CTO's powers: add or remove any member including Stakeholders, open and act on any requirement (logged as a Project Lead override), and change project status. Creating projects and Admin stay CTO-only.
- Creating and working on a requirement happens in one card: Title (set by the creator, read-only for others), Uploaded files, Description, Comments, Stage + User, Send.
- No stall threshold or daily digest.
- The CTO can add new role names and new stage names in Admin. New stages go before Closed, can be marked as Feedback (comment required) and get their own folder.
- Text boxes, comments, file rows and emails are inverted panels with a brushed-metal rim: dark in Light mode, bright in Dark mode. All colour pairs meet WCAG AA.
- Files are added as dummy files (a typed name only, no real file) so the flow can be tried without uploads.
- iOS-style look: translucent sticky nav bar, large titles, grouped rounded cards, pill buttons, iOS switches, a segmented Light/Dark control, and the iOS system font by default. Dark mode (true black, white text) is the default; Light mode uses a beige background with dark text. Stages, priorities and comment types use high-contrast colour chips.


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
| `SMTP_HOST` / `SMTP_PORT` / `SMTP_USER` / `SMTP_PASSWORD` / `SMTP_FROM` / `SMTP_STARTTLS` | empty / `25` / empty / empty / `pmt@localhost` / `0` | Email. With no `SMTP_HOST`, emails are only logged |
| `DIGEST_HOUR` | `7` | Hour (server local time) the daily digest runs |
| `DIGEST_ENABLED` | `1` | Set `0` to disable the in-app scheduler (e.g. to use cron with `python -m app.digest`) |
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
- **Handoff email** goes to the new holder after Proceed, Send with Feedback, Send Back and Reassign. Accept has no recipient, so no email. Internal comments are left out when the recipient is a Stakeholder. Email failures are logged and never block the action.
- **Daily digest**: in-app background thread at `DIGEST_HOUR`; emails every CTO with an email address the requirements in Active projects whose time in the current stage exceeds STALL_DAYS. No email when nothing is stalled.
- **UI**: per-user Appearance / Font / Font size are saved to the account from the top-bar menu and applied with CSS variables (`app/static/style.css`); everything is sized in `rem`, so spacing and buttons scale with font size. Fonts load from Google Fonts with system fallbacks. Colour pairs checked for 4.5:1 in both themes.

## Tests

```bash
python -m pytest -q
```

Covers the action rules, permissions, CTO overrides, internal comments, uploads, digest and UI settings.
