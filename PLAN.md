# Document Assembly Application — Specification

## 1. Purpose

Replace Docassemble for the in-house legal team. A user completes a
questionnaire and receives one or more Word documents (docxtpl-rendered)
reflecting their answers. Output is an internal first draft for further
editing, not an execution-ready document. This is an internal tool with a
deliberately small, "good enough and freeze it" scope — not a product.

Key goals driving the design:
- Non-technical legal colleagues can update questionnaires and templates
  themselves, without a developer, and without redeploying the app.
- Mistakes are cheap to undo (instant rollback), because publishing errors
  are inevitable in a self-service editing model.
- Runs on a single cheap VM. No SSO. Minimal moving parts.

---

## 2. Architecture

- **Backend**: Python + FastAPI (required — docxtpl is Python-only)
- **Frontend**: TypeScript + Tailwind, built with Vite; Vitest for tests
- **Storage**: single SQLite database — holds all persistent state,
  including the docx files themselves as blobs (see §4 for rationale)
- **Deployment**: one Docker container running the FastAPI app (serving
  the built frontend as static files), behind a reverse proxy (nginx or
  Caddy) for TLS termination only — **not** for auth
- **No message queue, no object storage, no separate database server.**
  Backups = copy the SQLite file.

---

## 3. Core Concept: Document Sets

A **Document Set** bundles one questionnaire with the output templates it
drives (e.g. "Employment Termination," "NDA Pack"). This is the unit of
versioning, publishing, and rollback. The home page lists document sets;
selecting one launches its questionnaire.

Within a document set:
- The **questionnaire** (a single Word file) defines the questions *and*
  the output-document control table (which templates to render, under
  what condition, with what filename pattern). These stay together
  because the control table's conditions reference questionnaire
  variables — they're conceptually one artifact.
- Each **template** (a separate Word file, one per output document) is
  versioned independently of the questionnaire and of other templates.

Editing the questionnaire doesn't require touching templates, and vice
versa. What keeps them from silently drifting apart is validation at
publish time (§6), not tight coupling.

---

## 4. Data Model (SQLite)

Docx files are stored as blobs directly in SQLite rather than on disk.
At the expected scale (single documents in the 100KB–2MB range even with
embedded logos, low hundreds of versions over the tool's lifetime) this
stays far below where SQLite blob storage becomes a concern, and it buys
atomicity: a version's file and its metadata commit together, so there's
no possibility of a DB row pointing at a missing file or an orphaned file
with no corresponding row. A file + DB pointer split was considered and
rejected for exactly this reason.

```sql
users
  id, name, username, password_hash, role, active, created_at

document_sets
  id, slug, name, description, created_at

questionnaire_versions
  id, document_set_id, version_no, docx_blob, parsed_schema_json,
  is_current, uploaded_by, uploaded_at, note

template_versions
  id, document_set_id, label, version_no, docx_blob,
  is_current, uploaded_by, uploaded_at, note

generation_log
  id, document_set_id, questionnaire_version_id, template_version_ids,
  project_code, generated_by, generated_at
```

Notes:
- `label` on `template_versions` identifies the template *slot* (e.g.
  `termination_letter`) across its version history — multiple rows share
  a label, only one per label is `is_current`.
- `parsed_schema_json` caches the parsed questionnaire structure so it
  isn't re-parsed from the docx on every request.
- Publishing = a transaction that unsets the old `is_current` row and
  sets the new one. Rollback is the same operation, pointed at an older
  version id. Both are atomic single-table updates.
- `generation_log` is a lightweight audit trail: given a generated
  document, you can trace exactly which questionnaire/template versions
  produced it.
- Suggested library: SQLModel (typed, integrates naturally with FastAPI's
  Pydantic models). Plain `sqlite3` + a hand-written `schema.sql` is a
  reasonable simpler alternative given the small number of tables.

---

## 5. Authentication & Authorization

- Per-user accounts (`users` table), not a shared credential.
- Passwords hashed with argon2.
- Login issues a signed session cookie (user id + expiry) via
  `itsdangerous` — no server-side session store needed.
- **Every request re-checks `active` against the DB.** Revoking access is
  flipping one boolean; it takes effect on the person's next request,
  with no token blocklist or expiry wait involved.
- **Single flat role** — any active user can fill out questionnaires,
  generate documents, upload/publish document set updates, and view/roll
  back version history. No admin/editor split for v1.
- Admin sets/resets passwords directly; no self-service reset flow, no
  SMTP dependency.
- No SSO.

---

## 6. Publish Workflow

Uploading is a deliberate action via a web form — not a watched folder —
so that a validation gate sits between "edited" and "live."

1. User goes to a document set's admin page, uploads a replacement
   questionnaire or template docx, and types their name + an optional
   note.
2. The system parses the upload and runs a **cross-check**:
   - Questionnaire upload: every variable referenced by the *current*
     output-table conditions and by *current* templates must still be
     defined.
   - Template upload: every Jinja2 variable referenced in the template
     must exist in the *current* questionnaire's variable set.
   - This reuses the variable cross-check logic already designed for the
     standalone docxtpl-linter tool — same check, now running as a
     publish gate instead of (or in addition to) an offline script.
3. **Any mismatch hard-blocks the upload.** The editor sees exactly which
   variable(s) don't resolve; nothing changes; they fix and re-upload.
4. Clean validation → a summary is shown (e.g. "+2 questions, 1 variable
   removed, template X now referenced") → an explicit **Publish** button
   flips the `is_current` pointer.
5. Version history for the document set lists every version (uploader
   name, note, timestamp) with a one-click **Rollback**, which is the
   same pointer-flip operation aimed at an older version.

What this catches: variable-name drift between questionnaire and
templates. What it doesn't catch: substantively wrong content that's
still logically valid (wrong wording, wrong example, wrong logic) —
that's what rollback is for.

---

## 7. Questionnaire Format (Word Table)

Authored as a Word document containing two tables:

**Table 1 — Questions**

| Column | Purpose |
|---|---|
| `variable_name` | valid Jinja2 identifier |
| `question_text` | shown to the user |
| `type` | `yesno` \| `choice` \| `text` \| `textarea` |
| `options` | for `choice`, pipe- or newline-separated |
| `example` | sample answer, shown as cut-paste-and-edit content |
| `skip_if` | condition referencing earlier variables (§8) |
| `section` | optional grouping/heading |

**Table 2 — Output Documents**

| Column | Purpose |
|---|---|
| `label` | matches a `template_versions.label` |
| `include_if` | condition (§8) — omit for "always include" |
| `filename_pattern` | e.g. `{project_code}_{label}_{date}` |

`project_code` and `date` are reserved variables: `date` auto-populates,
`project_code` is entered by the user as one of the questions (or a
fixed field outside the question table — implementer's choice).

Parsing uses `python-docx`; no rich text handling is needed (plain text
per cell only).

---

## 8. Condition Language

A restricted DSL — not full Jinja2 — used identically for `skip_if` and
`include_if`:

- Variable references, string/bool literals
- Operators: `==`, `!=`, `and`, `or`, `not`, `in`
- Parentheses for grouping
- No arithmetic, no function calls

Implement via `simpleeval` (or equivalent safe-eval), evaluated with the
current answers dict as the namespace. This is deliberately smaller than
docxtpl's own Jinja2 templates (which retain full conditional/loop
capability) — the questionnaire-level DSL only needs to answer
"show/hide" and "include/exclude" questions, not render content.

**This same evaluator is the single source of truth** — see §9. There is
no client-side reimplementation of condition logic.

---

## 9. Questionnaire Runtime (Single Reactive Page)

The whole questionnaire renders as one page; visibility of individual
questions updates as the user answers, driven by the server (not
duplicated client-side logic):

- `GET /document-sets/{slug}/questionnaire` — current questionnaire's
  full question list (id, text, type, options, example)
- `POST /document-sets/{slug}/questionnaire/evaluate` — send current
  answers, receive updated visible/hidden question list (called on each
  answer change, debounced client-side)
- `POST /document-sets/{slug}/generate` — send final answers + project
  code; server evaluates each output document's `include_if`, renders
  applicable docxtpl templates, zips if more than one, returns the
  download; writes a `generation_log` row

---

## 10. Document Generation

- Render via docxtpl (Jinja2 + docx-specific markup for paragraphs/
  tables), using the current template version(s) for the document set.
- Required template capabilities: variable substitution, conditional
  inclusion, light conjunction (`if var1 and var2`). Repeating sections/
  loops are explicitly **out of scope for v1** (see §12).
- Filenames built from each output row's `filename_pattern`, with
  `project_code` and `date` reserved.
- Multiple output documents → zipped into a single download.

---

## 11. Downloads

Any logged-in user (flat role — no special permission needed) can
download:

- `GET /document-sets/{slug}/current/questionnaire` — current
  questionnaire docx
- `GET /document-sets/{slug}/current/templates/{label}` — current
  template docx
- `GET /document-sets/{slug}/versions/{version_id}` — any historical
  version (questionnaire or template), by id

This is one download mechanism, not several — it doubles as the blob
inspection/export tool needed because the docx files live in SQLite
rather than on disk (there's no filesystem copy to eyeball directly).

---

## 12. Explicitly Out of Scope for v1

- Repeating/looped sections (multiple parties, multiple assets, etc.) —
  a real docxtpl capability, deferred; will need both a questionnaire
  table extension (something like a "repeat group") and an answer-data
  model extension when it's tackled.
- Answer-key upload to pre-fill answers.
- SSO / external identity provider.
- Role split beyond the single flat role (could be added later by
  introducing an `is_admin`-style flag without restructuring the rest of
  the schema).
- Rich text in questionnaire answers or example content.

---

## 13. Suggested Build Order

1. Questionnaire parser (docx tables → schema) + the variable
   cross-check validator (shared logic with the docxtpl-linter design) —
   highest risk, everything else depends on getting this right.
2. SQLite schema + document set / version / publish / rollback endpoints.
3. Condition evaluator (`simpleeval`-based) + the `evaluate` endpoint.
4. docxtpl generation + filename/zip logic.
5. Auth (users, sessions, login).
6. Frontend: questionnaire runner (single reactive page), document set
   list, admin upload/publish screen, version history.
7. Deployment: Dockerfile, reverse proxy config, backup process for the
   SQLite file.