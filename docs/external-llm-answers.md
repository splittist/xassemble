# External LLM answers: design and implementation

Status: the initial BYOLLM file-exchange implementation is included in the application.
The sections below retain the original design rationale and acceptance scenarios.
Export, strict import validation, merge preview, review labels, version
checks, and incomplete-generation acknowledgement are implemented. Real-matter evaluation with
the organisation's chosen LLM remains a user-run follow-up.

## Proposal

Let users download a questionnaire briefing, use it with an LLM approved by their
organisation, and upload a structured answer file to prefill the existing questionnaire.
Both complete and partial answers are supported. Users review the import, resolve conflicts,
complete missing answers, and explicitly generate the documents through the existing flow.

This starts an assembly using an existing published document set. It does not create a new
document-set definition, questionnaire, or Word template.

The first slice needs no model integration, API keys, model selection, or new database tables.
The organisation approves the external tool and its permitted use. A file upload cannot prove
which model generated its contents or whether that model was approved. If enforcement of a
model allowlist is required, a managed integration is a separate project.

## Fit with the application before this extension

| Existing behaviour | Implication |
| --- | --- |
| `QuestionnairePage.tsx` stores answers by variable name in React state. | An accepted import can populate the same editable form. |
| `GET /document-sets/{slug}/questionnaire` supplies question text, commentary, types, options, examples, rules, sections, and a version ID. | Most of the export material already exists. |
| `questionnaire_visibility` evaluates rules in question order and gives hidden answers a `null` value in the rendering context. | The server remains responsible for branching; the LLM need not decide which questions to hide. |
| Evaluation and generation accept `dict[str, object]`, without question-specific answer validation. | Add a shared server validator before accepting external data; also use it for evaluation and generation. |
| Evaluation and generation load the current questionnaire at request time. | Bind the draft to a version and reject changes instead of interpreting old answers against a new questionnaire. |
| Generation can proceed with blank visible answers. | Partial import must not be confused with readiness to generate. |
| Answers are transient; the audit log records the user, project code, and questionnaire/template versions. | Import need not persist answer files or claim to audit model provenance. |

Sources: `frontend/src/pages/QuestionnairePage.tsx`, `src/xassemble/app.py`,
`src/xassemble/service.py`, `src/xassemble/database.py`, and `USER_GUIDE.md`.
`PLAN.md` now records answer-key upload as implemented by this extension.

## User journey

1. Open a published document set and select **Prepare answers with your LLM**.
2. Download a UTF-8 Markdown briefing containing all questions, their stable variable names,
   commentary, types, allowed options, sections, and conditional rules. Include an empty answer
   envelope and instructions for returning a JSON file. Clearly label examples as illustrations,
   not facts. Do not include existing answers, templates, or source matter documents by default.
3. Give the briefing and appropriate matter material to the approved external tool. The briefing
   asks the model to answer only from supplied facts, omit uncertain answers, preserve identifiers
   and exact choice values, and return JSON without prose or Markdown fences. Users supply matter
   material to that tool themselves.
4. Back in xassemble, select **Import answers** and choose the returned `.json` file.
5. Validate the entire file, then preview additions, unchanged values, conflicting values,
   unanswered questions, and answers currently hidden by rules. Show current and proposed values
   for conflicts. Nothing changes until **Apply selected answers** is selected.
6. Default to filling unanswered fields. Each conflict requires explicit selection to replace the
   existing value. Omitted, `null`, and whitespace-only imported values never erase an answer.
   Cancel leaves the form untouched. Reimporting the same file is harmless.
7. Mark applied values as imported for review. Re-evaluate visibility from the final merged
   answers. Hidden answers can remain in the draft and become visible later, but the server
   continues to exclude them from rendering while hidden.
8. Review and edit the questionnaire, enter a project code, and select **Generate documents**.
   Show an explicit missing-answer summary when visible answers remain blank; retain the current
   ability to generate an incomplete first draft only after a separate acknowledgement.

The page should describe storage accurately: answers remain in the page's memory between
requests, but are sent to the application server for validation, evaluation, and generation.
Refreshing or leaving the page can lose the draft. The existing text saying they stay in the
browser until generation should be corrected, since evaluation already transmits them.

## Proposed answer contract

Illustrative file for a hypothetical published questionnaire (IDs and keys must come from its
actual exported briefing):

```json
{
  "format": "xassemble.answers.v1",
  "document_set_slug": "nda-pack",
  "questionnaire_version_id": 42,
  "questionnaire_schema_sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "answers": {
    "client_name": "Example AG",
    "urgent": false
  }
}
```

The export supplies the metadata verbatim. The hash is computed on the server from a defined
canonical serialization of the full parsed questionnaire schema, including outputs. It helps
detect accidental use across installations or restored databases where numeric IDs coincide;
it is not a signature or proof of origin. A document-set/version/hash mismatch blocks import.
The example hash above is a placeholder, not a valid export.

| Question type | Accepted non-empty JSON value |
| --- | --- |
| `yesno` | Boolean `true` or `false`; never strings or numbers. |
| `choice` | A string exactly matching one published option. |
| `text`, `textarea` | A string, preserving meaningful whitespace and line breaks. |

Missing keys, `null`, and whitespace-only strings mean unanswered. `false` is a real answer.
Reject unknown answer keys, unknown envelope fields, nested values, duplicate JSON keys,
non-finite numbers, incorrect types, unsupported formats, and malformed JSON with actionable
field-level errors. Do not guess that "yes" means `true` or silently map labels to variables.
Validate hidden answers too, since later edits may make them visible.

Proposed import limits: 1 MiB file/request size and 20,000 characters per answer. Enforce the
byte limit before parsing on the server and check it in the browser for immediate feedback.
Review these limits against real questionnaires before adopting them for all answer requests.
Reject XML-invalid control characters before Word rendering. Display imported text as plain
text and retain the existing `autoescape=True` rendering behaviour. Answer contents never
become template code, condition expressions, executable instructions, or URLs to fetch.

An empty `answers` object is valid and produces a no-op preview. An invalid file is rejected as
a whole; users can correct it and retry without losing the current form. A partial answer file
is different from an invalid file.

## Proposed implementation

1. Add a small answer-contract module for strict JSON parsing, identity checks, canonical schema
   hashing, and shared question-type validation. Keep visibility rules in the existing service.
2. Add authenticated `GET /document-sets/{slug}/questionnaire/answer-briefing` to download the
   briefing for the current version. Include an expected version from the open page and return
   `409` if it has changed, so export and the visible form cannot silently diverge.
3. Add authenticated `POST /document-sets/{slug}/questionnaire/answer-import` accepting the file
   as multipart data. Return validated candidate answers and identity metadata without writing
   a draft or generating documents. Use `413` for oversize uploads, `422` for invalid files,
   and `409` for version/schema mismatch. Reuse current authentication and password-change rules.
4. Add an import preview component and explicit merge operation on the questionnaire page.
   Recompute conflicts if the form changes while a preview is open. Evaluate visibility using
   the merged answers, not the uploaded subset in isolation. Discard stale async responses when
   the route, draft, or version changes; disable apply while validation is pending.
5. Include the expected questionnaire version and schema hash on evaluation and generation
   requests. The server checks and uses the same loaded questionnaire row for the operation.
   Return `409` on mismatch with guidance to reopen the current questionnaire and prepare a new
   briefing. Keep the user's current draft available for reference; do not silently migrate it.
   Require identity fields consistently and update the existing UI/API tests and API documentation
   together, explicitly documenting the request-contract change.
6. Run the shared value validator on manual answers as well as imports. Keep unanswered values
   allowed, preserving partial evaluation and deliberate incomplete generation. The missing-answer
   acknowledgement should be checked server-side for generation, based on visible questions.
7. Update the user guide with the file workflow, transient draft behaviour, and recovery from
   malformed files. Link this design from the README and document the shipped API contract.

No schema migration is needed for this slice. A future requirement to retain drafts, record
import provenance, or store evidence would change that conclusion. Template selection remains
the current published-template behaviour; template version pinning is a separate decision.

## Acceptance scenarios for a prototype

- Export a real questionnaire, fill its JSON envelope, import it, review, and generate Word
  output containing the accepted answers.
- Import a partial file into an empty form; unanswered questions remain editable and visible
  progress reflects the actual merged answers.
- Import over an existing draft; additions apply, conflicts are preserved by default, explicit
  replacements work, and cancel or validation failure leaves every existing answer unchanged.
- Accept Boolean `false`; reject `"false"`, unknown keys, invalid choices, arrays, objects,
  duplicate keys, oversized files, and unsupported format versions with useful messages.
- Change a branch-driving answer; hidden values do not enter output, and newly visible imported
  answers can be reviewed. Late evaluation responses cannot revert visibility for newer answers.
- Reject the wrong document set, old questionnaire version, or wrong schema hash, including a
  questionnaire published between import and generation. A rollback to the exact original
  version and schema is compatible.
- Generate with missing visible answers only after explicit acknowledgement; server validation
  cannot be bypassed by calling generation directly with invalid types or stale metadata.
- Verify unauthenticated and compulsory-password-change requests cannot export or import.
- Verify multiline, Unicode, and XML-special text survives import and renders correctly; reject
  prohibited control characters without an unhandled rendering error.
- Verify no upload file or answer content is added to persistent storage or application logs.

## Decisions before expanding scope

- **Approval meaning:** assume organisational approval of the external tool. Technical enforcement
  would require controlled execution or trustworthy attestation, which arbitrary files lack.
- **Human review:** propose import preview plus an editable questionnaire, with explicit
  acknowledgement of incomplete generation. Mandatory review of every individual field can be
  added if users need a stronger workflow.
- **Evidence:** defer optional per-answer citations and uncertainty notes until the basic exchange
  works. Such metadata should be shown separately and never accidentally inserted into templates.
- **Persistence:** defer saving/resuming drafts and retaining original import files. These need
  explicit ownership, retention, and access decisions.

Recommended next step: try the implemented file exchange with one
real questionnaire, a complete fact pattern, and an intentionally incomplete fact pattern using
the organisation's chosen approved LLM. Assess file-format reliability, usefulness of the
prefilled answers, and the effort required to review them before adding provider integrations.
