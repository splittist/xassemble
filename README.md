# xassemble

A small document-assembly backend for internal legal teams. It turns a Word-authored
questionnaire and one or more `docxtpl` Word templates into generated `.docx` files.

This repository currently implements the backend foundation from `PLAN.md`:

- strict parsing of the two questionnaire tables;
- a deliberately restricted condition language shared by evaluation and generation;
- template/questionnaire variable compatibility checks;
- SQLite-backed document sets and immutable questionnaire/template versions;
- staged uploads, atomic publish and rollback operations;
- reactive questionnaire visibility evaluation;
- Word generation, ZIP output for multiple documents, and generation audit records;
- current and historical source-document downloads;
- per-user Argon2 authentication with signed, expiring session cookies;
- immediate access revocation by deactivating a user;
- a responsive React interface for login, questionnaires, downloads, uploads, publishing, and
  rollback.

The repository includes a non-root container, persistent Compose setup, Caddy TLS proxy, and
verified SQLite backup/restore tooling. See [DEPLOYMENT.md](DEPLOYMENT.md) before production use.

## Run locally

Install [uv](https://docs.astral.sh/uv/), then let it select Python, create `.venv`, and install the
exact versions in `uv.lock`:

```powershell
uv sync
Set-Location frontend
npm ci
npm run build
Set-Location ..
$env:XASSEMBLE_SECRET_KEY = uv run python -c "import secrets; print(secrets.token_urlsafe(48))"
uv run xassemble-user add editor --name "Example Editor"
uv run uvicorn xassemble.app:app --reload
```

The database defaults to `data/xassemble.sqlite3`. Set `XASSEMBLE_DB` to use another location.
The application is available at `http://127.0.0.1:8000/`. The interactive API documentation is
available at `/docs` after login.
The generated secret above is suitable for local development only; production must provide a
stable secret so sessions remain valid across restarts.

Run the checks with:

```powershell
uv run ruff check .
uv run pytest -q
Set-Location frontend
npm run build
npm test
```

Build and exercise the production container on Windows with:

```powershell
.\scripts\container-smoke-test.ps1
```

For frontend development with instant updates, run the API on port 8000 and `npm run dev` from
`frontend` in a second terminal. Vite serves the interface on port 5173 and proxies API requests
to FastAPI. The production build is served directly by FastAPI, including browser refreshes on
questionnaire and management routes.

## Users and sessions

User administration is deliberately local and has no web endpoints. Passwords are prompted for
without echoing or placing them in shell history:

```powershell
uv run xassemble-user list
uv run xassemble-user add jsmith --name "Jane Smith"
uv run xassemble-user reset-password jsmith
uv run xassemble-user deactivate jsmith
uv run xassemble-user activate jsmith
```

`POST /auth/login` accepts `username` and `password`, sets an HttpOnly, SameSite=Lax cookie, and
returns the user's public profile. `POST /auth/logout` clears it and `GET /auth/me` returns the
current profile. Sessions last eight hours by default; configure `XASSEMBLE_SESSION_SECONDS` to
change this. Set `XASSEMBLE_SECURE_COOKIES=true` whenever the app is served behind HTTPS.

Every protected request verifies the cookie signature and expiry, then reloads the user from
SQLite and checks `active`. Deactivation therefore revokes existing sessions immediately. Audit
fields are taken from the authenticated username rather than accepted from request data.

## Database operations

Use the SQLite-aware commands rather than copying a live database file:

```powershell
uv run xassemble-db check
uv run xassemble-db backup backups\xassemble.sqlite3
uv run xassemble-db restore backups\xassemble.sqlite3 --confirm-replace
```

Backup is safe while the application is running. Stop the application before restore. The
commands validate SQLite integrity and the expected xassemble schema. Container-specific backup,
off-host storage, and restore instructions are in [DEPLOYMENT.md](DEPLOYMENT.md).

## Questionnaire document format

The uploaded `.docx` must contain two tables. Header matching is case-insensitive and tolerates
spaces in place of underscores, but all required columns must be present.

Questions table:

| Column | Content |
| --- | --- |
| `variable_name` | A unique identifier such as `client_name` |
| `question_text` | Text shown to the user. Any paragraph after the first is shown as smaller commentary text |
| `type` | `yesno`, `choice`, `text`, or `textarea` |
| `options` | Pipe- or newline-separated values for a choice |
| `example` | Optional sample answer(s), pipe- or newline-separated for multiple choosable examples |
| `skip_if` | Optional condition using earlier questions only |
| `section` | Optional section heading |

Output documents table:

| Column | Content |
| --- | --- |
| `label` | Template slot identifier, such as `termination_letter` |
| `include_if` | Optional condition controlling whether the output is generated |
| `filename_pattern` | Uses `{project_code}`, `{label}`, and/or `{date}` |

Conditions support variable references, strings, `true`, `false`, `null`, `==`, `!=`, `and`,
`or`, `not`, `in`, `not in`, and parentheses. Function calls, attribute access, indexing, and
arithmetic are rejected.

## Publishing workflow

All uploads create non-current versions. A successful upload returns a version ID and validation
summary; publishing is a separate request. Publishing an older version performs a rollback using
the same compatibility validation and atomic pointer change.

Typical API order:

1. `POST /auth/login`
2. `POST /document-sets`
3. `POST /document-sets/{slug}/questionnaire-versions`
4. `POST /document-sets/{slug}/questionnaire-versions/{id}/publish`
5. `POST /document-sets/{slug}/template-versions`
6. `POST /document-sets/{slug}/template-versions/{id}/publish`
7. `GET /document-sets/{slug}/questionnaire`
8. `POST /document-sets/{slug}/questionnaire/evaluate`
9. `POST /document-sets/{slug}/generate`

`GET /document-sets/{slug}/versions` returns version history. Historical downloads use
`GET /document-sets/{slug}/versions/{kind}/{id}`, where `kind` is `questionnaire` or `template`.
The explicit kind is necessary because the plan uses two version tables whose numeric IDs can
overlap.

## Current scope

The planned v1 application and single-container deployment slices are complete. Repeating groups,
answer-key upload, SSO, multiple roles, and rich-text answers remain intentionally out of scope.
