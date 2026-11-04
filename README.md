# IDLC Streams — lightweight project management for the IT team

(Earlier name: PMT. The FastAPI app below still uses the old name.)

## Clickable demo (latest design)

`demo/index.html` is a browser-only mock-up of the latest agreed design, for approval. Open it in any browser; no server needed. It opens with sample data (the IT team and five dummy projects); data stays in that browser and "Reset sample data" restores it. It reflects these design changes, which are **not yet in the FastAPI app below**:

- Project codes are generated from the name (e.g. "Help Desk Portal" → HDP-001); the CTO joins every project as Project Head.
- Team members are added as User + Role dropdown rows. One person can hold several roles in a project ("+ Add role"); single roles can be removed from the Members list. Only the CTO can remove a Project Lead or Dev Lead.
- Projects and requirements have an optional "Start from" date (must be on or before the deadline / due date). The Dev Lead can create requirements.
- Projects have a priority (Low, Normal, High) and an optional deadline, set by the CTO at creation. The CTO, Project Lead and Dev Lead can add or change them on the project page; changes are logged in Project history, and a past deadline on an Active project shows "Overdue".
- Stages: Analysis, Analysis Feedback, Development, Development Feedback, QA, QA Feedback, Approval (plus Closed). The holder picks the stage and the user on every Send; a comment is required for Feedback stages; only the Stakeholder closes from Approval.
- A requirement can be sent to several people at once ("+ Add person"). All of them get it in their queue and any of them can work on it; when one of them sends it on, it leaves all their queues.
- A requirement is visible only to its current holder. Only the Project Head (CTO), Project Lead and Dev Lead see every requirement in a project and who holds it; the Dev Lead can view others' requirements but not act on them. Only these three can add or remove project members.
- Inside their project the Project Lead has the CTO's powers: add or remove any member including Stakeholders, open and act on any requirement (logged as a Project Lead override), and change project status. Creating projects and Admin stay CTO-only.
- Creating and working on a requirement happens in one card: Title (set by the creator, read-only for others), Uploaded files, Description, Comments, Stage + User, Send.
- No stall threshold or daily digest.
- On Hold & Cancelled page (Project Head only): paused projects with since-date, dates and open requirement counts; they leave the Head's Projects list.
- Workload counters for the Project Head, Project Lead and Dev Lead: a Workload table on the project page (open requirements per member, in this project and across all active projects), a Team workload table on the Head's Projects page, and "· N open" next to each name when picking people for a project, adding members or sending.
- Projects need an end date when created; with no start date, the creation day is used. "New project" lives on the Projects page with a shortcut in My Queue (CTO).
- Clicking a project opens a project card with two tabs. Primary: requirements, workload, members, project status. Overview: Summary, Description, Analysis, Project cost, priority and start date, a Timeline table (List, Requirement, Start date, End date 1, End date 2, … and Days deviated), end date extension requests, and project history.
- Overview approval: only the Project Analyst or Business Stakeholder fills in the overview fields and sends them for approval; the Project Head or Project Lead approves or declines (with a note). Once approved the overview is read-only; only the Project Analyst can request a change, which needs a new approval.
- Date change requests (start or end date, for the project or a requirement) need a reason and must be accepted by the Project Lead or the Project Head. The Head, Project Lead, Dev Lead and the requirement's assignees can ask; the Project Lead's and Head's own requests apply at once. The Timeline is a numbered list (1. Whole project, 2. first requirement, …) showing Start date, Start date 2 – reason, End date, End date 2 – reason, and days deviated.
- Downloads (on claude.ai): the Overview tab offers an Overview report (.html: overview, timeline, extension requests, history) and the Timeline (.csv). In this repo copy, opened as a plain file, the download buttons stay hidden.
- The CTO's My Queue shows only requirements sent to him for approval. Everything else (other people's requirements, feedback requests, date changes, overview approvals) is in each project's card.
- Approval stage: a requirement can only be sent to Approval to the Project Lead or Dev Lead (or the Project Head). Everyone can send approval requests to the Project Lead or Dev Lead; only the Project Lead, Dev Lead or Business Stakeholder can send one to the Project Head, who receives requirements only as approval requests. Any approver closes it with Approve and close.
- Request feedback: the person a requirement is assigned to asks for feedback with a reason. Only the Project Head, Project Lead or Dev Lead can accept (choosing the Feedback stage and who gives feedback) or decline. Pending requests show in their My Queue and in the project card. Regular members can no longer send straight to a Feedback stage.
- The main menu is a fixed left sidebar (a row of links on phone-width screens); every page starts at the same left edge beside it.
- Projects have a type: Vendor (no Developers), Internal, or Integration (no Project Analysts). Project codes come from the type: VND-001, INT-002, ITG-003.
- Requirements get codes from their project code, e.g. HDP-001-R01. The top-bar search finds projects (by code or name) and requirements (by code or title) that the person is allowed to open.
- Side menu order: My Queue, Notifications, Reminders, Projects, On Hold & Cancelled (Head), Sent Requests, Archive, Admin (Head), How To. How To is a short text manual for the essential tasks.
- Reminders (everyone, private): a month calendar with reminders (date, optional time and note), a day panel to add and tick off reminders, an overdue/next-14-days list, and personal notes (optionally tagged with a project). The menu badge counts today's and overdue reminders.
- Sign-in page with username and password, and password reset by email: a 6-digit code (valid 15 minutes) is emailed through the mail integration. Demo sign-ins: the sample people use password `demo`; the system admin is `admin` / `admin` and only has the Admin page. Only the system admin has Admin; the Project Head (CTO) does not. Sign out is in the Settings menu; the demo strip keeps a Quick switch for trying other people.
- Folder share (Admin): set the internal server share link (e.g. `\\server\share\IDLC_Streams`) and service account. Uploads are saved as share \ project code \ requirement code \ stage folder \ file. The app only adds files: it never deletes or overwrites (same names become _v2, _v3). Give the service account create/write rights but not delete.
- Uploaded files and links on a requirement have a Remove button for the person who added them and for the Project Head, Project Lead or Dev Lead (not on Closed requirements). Removing a file only hides it from the requirement; it stays on the folder share. Removals are logged in history.
- Change password: Settings → Change password opens a card (current, new, repeat). "Forgot password?" emails a reset code to use in the same card, or says to contact the system admin when email is off or the account has no email.
- Usernames are made automatically from the full name (first name, then first.last, then a number). Each user has a CIF (ID number), which must be unique.
- User import integration: Admin → Users → Import users fetches Name, Username, CIF and Email from an HR / core-system integration; a blank or taken username is made from the name, and people whose CIF already exists are skipped.
- "Added to project": when someone adds you to a project (or gives you another role), a notice appears in My Queue below your tasks, with Open project and Acknowledge buttons (also shown inside the project card). It stays until you press Acknowledge; the My Queue menu item shows the count.
- My Queue starts with Urgent deadlines: your requirements due within 2 days or already overdue.
- My Queue also shows Reminders today (today's and overdue, including ones others sent you) with a quick add box.
- Reminders and Notes page: send a reminder to someone else (it shows in their My Queue on that day, and you can track or cancel it under Reminders you sent). Notes show as tiles in My Notes with All / By me / From others filters, and Send a copy gives anyone their own copy.
- The top bar shows a 12-hour clock and the date beside the logo.
- How To: a full manual in collapsible panels (Expand all / Collapse all): start here, how a project runs (a diagram showing work can move forward, back or skip stages; no fixed pipeline), role hierarchy, access control, a "who can do what" permissions table by role, daily pages, projects, requirements, dates and overview, files, account, reminders and Admin.
- Requirement and project cards open wide (landscape).
- Appearance: Light mode is the default; font size is a 5-step slider with live preview. Page and section headings have a line under them.
- Choosing members (New project team step and Add member): type part of a name or username and pick from the suggestion list (arrow keys and Enter work).
- Start or request a project: the Project Head and people the system admin allows press New project (a non-Head starter joins as Project Lead). Everyone else presses Request project (name, type, priority, dates, why); the Project Head approves it (the New project form opens pre-filled) or declines it with a reason. Requests are tracked in Sent Requests and can be withdrawn while waiting.
- Access control (Admin): make any person a SuperUser (the Project Head's privileges in every project; the Project Head is always one), turn project requests from staff on (default) or off, and allow chosen people to start projects.
- Admin (system admin only): users (with temporary password and "Email reset code"), Mail integration (SMTP server, port, security, credentials, From address, test email), Integrations with other sites (directory sign-in, single sign-on, webhook, REST API, file storage; turn on/off, test, remove), roles, stages and the email log. In the demo nothing is contacted or sent, and passwords use a simple demo hash kept in the browser; the real app uses PBKDF2 hashes on the server.
- Sent Requests for everyone: every requirement the person sent, with status (Waiting with …, Moved on, Unsent). Unsend returns it to the sender at the previous stage, as long as the recipient has not sent it on and the project is Active; recipients are notified.
- Notifications for everyone: the last 24 hours of activity, e.g. "NAJ (Project Head) assigned you requirement “Task 1” · Development". Regular members see only what is about them (assignments, being added or removed, comments on what they hold); the Head, Project Lead and Dev Lead see all activity in their projects. A badge counts new items until the page is opened.
- Archive for everyone: closed projects they belong to and closed requirements in open projects. The CTO sees everything; the Project Lead and Dev Lead see every requirement in their projects; everyone else sees only requirements they created, acted on or were assigned. Searchable; archived requirements open read-only. Closed projects leave the Projects list.
- The CTO can add new role names and new stage names in Admin. New stages go before Closed, can be marked as Feedback (comment required) and get their own folder.
- Text boxes, comments, file rows and emails are inverted panels with a brushed-metal rim: dark in Light mode, bright in Dark mode. All colour pairs meet WCAG AA.
- Under the files, a requirement can hold repository and reference links (URL plus optional label). Repository hosts (GitHub, GitLab, Bitbucket, Azure DevOps) are tagged REPO; links open in a new tab.
- Files are added as dummy files (a typed name only, no real file) so the flow can be tried without uploads.
- iOS-style look: translucent top bar, large titles, grouped rounded cards, pill buttons, iOS switches, a segmented Light/Dark control, a red accent colour and outlined cards. Dark mode (true black, white text) is the default; Light mode uses an IBM-style beige with dark text. Fonts: Century Gothic (default; Questrial is used where Century Gothic is not installed), Poppins, Atkinson Hyperlegible, Merriweather. Settings also have an accent colour choice (Red, Blue, Green, Purple; each checked for contrast in both themes) and a Brightness slider (5 levels, level 3 is normal), saved per person. The selected side-menu tab is outlined in the accent colour.


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
