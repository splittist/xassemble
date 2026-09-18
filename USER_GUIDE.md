# xassemble User Guide

This guide is for lawyers, legal assistants, and other colleagues who use or maintain
xassemble. No programming knowledge is required.

xassemble turns answers from a questionnaire into one or more Microsoft Word documents. The
documents are **first drafts**. Always review the legal content, names, dates, defined terms,
cross-references, formatting, and attachments before use.

## 1. Key terms

| Term | Meaning |
| --- | --- |
| **Document set** | One questionnaire and the Word templates connected to it, for example, “NDA Pack”. |
| **Questionnaire** | A Word file containing the questions and the rules for choosing output documents. |
| **Template** | A Word file containing the text and formatting of one output document. It contains placeholders for answers. |
| **Output label** | The internal name connecting an output rule to its template, for example, `nda` or `termination_letter`. |
| **Variable name** | The internal name of an answer, for example, `client_name`. The same name is used in the questionnaire, rules, and templates. |
| **Version** | A saved upload. An uploaded version is not used until it is published. |
| **Current** | The published version that xassemble uses. |

## Part A — Assemble documents

### 2. Sign in and choose a document set

1. Open xassemble in your web browser.
2. Enter your **Username** and **Password**, then select **Sign in**.
3. On the **Document sets** page, find the set you need. Read its description if you are not
   sure which one to use.
4. Select **Assemble**.

A set marked **Setup needed** cannot yet be used. Ask the colleague who maintains that set to
publish its questionnaire and templates.

### 3. Complete the questionnaire

The complete questionnaire appears on one page.

1. Answer each visible question:
   - **Yes/No:** select **Yes** or **No**.
   - **Choice:** select one item from the list.
   - **Short text:** type a short answer, such as a name or date.
   - **Long text:** type one or more paragraphs.
2. Read any smaller explanatory text below the question.
3. If an example is offered, select **Use example** to copy it into the answer. Review and edit
   it; an example is not automatically correct for your matter.
4. Continue until the progress panel shows that all visible questions are answered.

Later questions may appear or disappear when an earlier answer changes. This is normal. An
answer to a question that becomes hidden is not used in the generated documents.

Your answers are held only on the current questionnaire page. They are not saved as a draft. If
you refresh the page, close the tab, sign out, or return to **All document sets**, you may lose
them.

> **Important:** Check the answers yourself before continuing. If visible questions remain blank,
> review the missing-answer list and explicitly select the incomplete-first-draft acknowledgement
> before generation becomes available.

#### Prepare answers with your own LLM

1. Select **Download LLM briefing** on the questionnaire page. The Markdown file contains the
   questions, answer types, options, examples, conditional rules, and an empty JSON answer envelope.
2. Use your organisation's approved LLM with your own resources, procedures, and policies. Give
   it the briefing and appropriate matter material. xassemble does not contact that tool or use
   API keys. The briefing does not contain your existing answers or Word templates.
3. Ask the tool to return the specified `.json` file. It can answer all or only some questions.
   Unsupported answers should be omitted; examples in the briefing are not facts about your matter.
4. Select **Import answers (.json)**. A preview shows additions, unchanged answers, replacements,
   and answers hidden by the selected values. Blank or omitted values never erase existing answers.
5. Select any replacements you want, then **Apply selected answers**. Additions are selected by
   default. **Cancel import** leaves the questionnaire untouched. Editing the questionnaire while
   a preview is open clears its selections so you can review them against the latest answers.
6. Review the imported answers in the questionnaire and complete or edit them. Imported values
   are labelled for review. xassemble evaluates conditional questions itself; currently hidden
   answers are excluded from generated documents.
7. Enter a project code and generate through the normal process.

The file must contain plain JSON, without Markdown fences or surrounding prose. Yes/No values
must be `true` or `false`, choices must match an option exactly, and text answers must be strings.
Files are limited to 1 MiB, with up to 20,000 characters per answer. An invalid file produces an
error without changing your draft; correct the file in your own system and import it again.

If the questionnaire has changed since export or since opening the page, xassemble blocks stale
imports and generation. Keep your draft for reference before leaving, reopen the questionnaire,
and download a new briefing. Do not simply change version metadata in an old answer file.

Answers remain in page memory between requests and are sent to xassemble for validation,
visibility evaluation, and generation. Imported files and answers are not saved as drafts.
xassemble cannot verify which external model produced a file; approval remains your
organisation's responsibility.

### 4. Generate and access the results

1. Enter a **Project code**, for example, `MAT-2026-014`. It is used in the downloaded filename
   and the generation audit record. Do not use the client name if your organisation's policy
   requires a matter number or another internal reference.
2. Select **Generate documents**.
3. Your browser downloads the result:
   - one output document is downloaded as a `.docx` Word file;
   - two or more output documents are downloaded together as a `.zip` file.
4. If you receive a `.zip` file, open or extract it to access the individual Word files.
5. Open every generated document in Word and review it before use.

If no download is visible, check the browser's **Downloads** list. Your browser or organisation
may ask you to allow downloads from xassemble.

### 5. If generation fails

- Check that a project code was entered.
- Check that all visible questions have an answer.
- If the message says that no published template exists, or that no output document was
  selected, contact the maintainer of the document set and give them the exact error message.
- If the sign-in page appears, your session may have expired. Sign in again. Questionnaire
  answers are not restored after signing in.

## Part B — Create or maintain a document set

Any active xassemble user can create, upload, publish, and roll back document sets. Coordinate
with the document owner before changing a live set.

### 6. Overview

For a new document set, use this order:

1. Create the document set in xassemble.
2. Create the questionnaire as a `.docx` file.
3. Upload, validate, and publish the questionnaire.
4. Create one `.docx` template for each output label.
5. Upload, validate, and publish every template.
6. Run a test assembly and review every possible output.

**Upload** and **Publish** are separate actions. Uploading saves a new version and checks its
structure. It does not change what colleagues use. Publishing makes that version current.

### 7. Create the document set

1. On the **Document sets** page, select **New set**.
2. Enter a clear **Name**, such as `Employment Termination`.
3. Review the generated **URL name**. It may contain lowercase letters, numbers, and single
   hyphens only, for example, `employment-termination`. It must be unique.
4. Add a short **Description** explaining when the set should be used.
5. Select **Create set**.
6. On the new card, select **Manage**.

### 8. Create the questionnaire in Word

Create a normal Word `.docx` file containing two tables. The tables may include introductory
text before or between them. Using the exact headings below is safest.

#### Table 1: questions

The first row must contain these seven headings:

| `variable_name` | `question_text` | `type` | `options` | `example` | `skip_if` | `section` |
| --- | --- | --- | --- | --- | --- | --- |

Add one question per row.

| Column | What to enter |
| --- | --- |
| `variable_name` | A unique internal name. Use letters, numbers, and underscores only; begin with a letter or underscore. Example: `client_name`. Do not use spaces, hyphens, accented letters, or `date`. Names are case-sensitive. |
| `question_text` | The main question shown to the user. To add smaller guidance text, create a second paragraph in the same Word cell. All paragraphs after the first become guidance text. |
| `type` | Exactly one of: `yesno`, `choice`, `text`, or `textarea`. |
| `options` | Required for `choice`; leave blank for other types. Separate choices with a vertical bar (`Employee|Consultant|Director`) or put each choice on a new line. |
| `example` | Optional sample text that the user can copy. Separate multiple examples with a vertical bar or new lines. Examples are supported for `text` and `textarea`, and for `choice` when they exactly match an option. Yes/No questions use the Yes and No buttons instead. |
| `skip_if` | Optional rule that hides this question when the rule is true. It may refer only to questions in earlier rows. Leave blank to always show the question. |
| `section` | Optional heading used to group questions, for example, `Parties` or `Termination details`. Repeat the same value on consecutive rows in the same section. |

Example:

| `variable_name` | `question_text` | `type` | `options` | `example` | `skip_if` | `section` |
| --- | --- | --- | --- | --- | --- | --- |
| `client_name` | What is the client's full legal name? | `text` |  | `Example Holdings AG` |  | `Matter` |
| `termination_type` | What type of termination is required? | `choice` | `Ordinary|Immediate` |  |  | `Termination` |
| `immediate_reason` | State the reason for immediate termination. | `textarea` |  |  | `termination_type != "Immediate"` | `Termination` |
| `include_release` | Should the draft include a release? | `yesno` |  |  |  | `Terms` |

In this example, `immediate_reason` is hidden unless the user selects `Immediate`.

#### Table 2: output documents

The first row must contain these three headings:

| `label` | `include_if` | `filename_pattern` |
| --- | --- | --- |

Add one row for each possible output document.

| Column | What to enter |
| --- | --- |
| `label` | A unique internal template name, such as `termination_letter`. Use the same naming rules as a variable. The template must later be uploaded with this exact label. |
| `include_if` | Optional rule controlling whether this output is generated. Leave blank to always generate it. This rule may refer to any questionnaire variable. |
| `filename_pattern` | The downloaded filename. It may use `{project_code}`, `{label}`, and `{date}` only. If blank, xassemble uses `{project_code}_{label}_{date}`. The `.docx` ending is added if necessary. |

Example:

| `label` | `include_if` | `filename_pattern` |
| --- | --- | --- |
| `termination_letter` |  | `{project_code}_termination_{date}` |
| `release_agreement` | `include_release == true` | `{project_code}_release_{date}` |

Here, the termination letter is always generated. The release agreement is generated only when
the user answers **Yes** to `include_release`.

The date uses the format `YYYY-MM-DD`. Unsafe filename characters and spaces are replaced when
the file is generated.

### 9. Rules for `skip_if` and `include_if`

These questionnaire rules are intentionally small and are **not** the same as template syntax.

Supported items:

| Purpose | Example |
| --- | --- |
| Yes | `include_release == true` |
| No | `include_release == false` |
| Exact text or choice | `country == "Switzerland"` |
| Different text or choice | `termination_type != "Immediate"` |
| One of several values | `country in ("Switzerland", "France")` |
| Not one of several values | `status not in ("Draft", "Pending")` |
| Both rules true | `urgent == true and approved == true` |
| Either rule true | `urgent == true or claim_value == "High"` |
| Reverse a rule | `not include_release` |
| Group rules | `(urgent == true or claim_value == "High") and approved == true` |
| No answer/value | `manager_name == null` |

Use lowercase `true`, `false`, and `null`. Put text and choice values inside straight quotation
marks. Spelling, capitalisation, and spaces must match the choice exactly.

Do not use calculations, functions, Word formulas, properties such as `client.name`, square
brackets such as `items[0]`, or other Python/Jinja syntax in these columns.

Remember:

- `skip_if` means **hide the question when this rule is true**.
- A hidden question has the value `null`; an earlier answer to it is not used.
- `skip_if` can refer only to variables above it in the questions table.
- `include_if` can refer to questionnaire variables and the reserved `date` variable, but not
  `project_code`.

### 10. Upload and publish the questionnaire

1. Open the set's **Manage** page.
2. Under **Questionnaire**, select the Word file.
3. Optionally enter a short **Version note**, such as `Initial version` or
   `Add release questions`.
4. Select **Validate upload**.
5. If validation fails, read the message, correct the Word file, and upload it again.
6. When the version has passed validation, find it in the version list and select **Publish**.
7. Confirm the action. The version is now marked **Current**.

Uploading creates an immutable version; it does not overwrite an older file. The download icon
beside a version downloads that exact version. The **Current** button downloads the published
questionnaire.

### 11. Create a Word template: `docxtpl` primer

Start with the approved Word document that you want xassemble to produce. Keep its page layout,
styles, headers, footers, tables, and standard text. Replace matter-specific text with the tags
below, then save the file as `.docx`.

#### Insert an answer

Use double curly brackets around the questionnaire variable name:

```text
Dear {{ client_name }},
```

xassemble automatically escapes inserted answers for safe use inside a Word file. Characters
such as `&`, `<`, and `>` are treated as text rather than document markup.

Two additional values are always available:

```text
Matter: {{ project_code }}
Generated: {{ date }}
```

`date` is the generation date in `YYYY-MM-DD` format.

The inserted answer uses the formatting of the tag in Word. Apply one consistent style to the
whole tag. Do not make only part of a tag bold, italic, a hyperlink, or a different font.

#### Include or omit text

For one optional part within a single paragraph, keep all tags in that same Word paragraph and
use:

```text
{% if include_release %}The parties agree to the release below.{% endif %}
```

For one or more complete optional paragraphs, put the opening and closing tags in their own Word
paragraphs:

```text
{%p if include_release %}
Release

The Employee releases the Company from [...].
{%p endif %}
```

The two paragraphs containing `{%p ... %}` are control paragraphs. They are removed from the
generated document. The heading and clause between them appear only when `include_release` is
true.

You can test a choice answer in the same way:

```text
{%p if termination_type == "Immediate" %}
The employment terminates with immediate effect.
{%p else %}
The employment terminates at the end of the notice period.
{%p endif %}
```

For an optional block of table rows, use control rows whose only text is `{%tr if ... %}` and
`{%tr endif %}`. The control rows are removed from the result. Create them as separate rows; do
not put `{%tr if ... %}` and `{%tr endif %}` in the same row.

#### Syntax checklist

- Use spaces inside tags where appropriate: `{{ client_name }}` and `{% if urgent %}`.
- Type normal straight braces and quotation marks. Avoid decorative or “smart” quotation marks
  inside rules.
- Keep each normal `{% ... %}` tag within one Word paragraph and one consistently formatted text
  run. Use `{%p ... %}` when a condition spans complete paragraphs and `{%tr ... %}` when it
  spans table rows.
- Put paragraph and table-row control tags in their own paragraph or row.
- Use questionnaire variable names exactly, including capitalisation.
- A Yes/No answer is a Boolean value. Use `{% if urgent %}`, not
  `{% if urgent == "Yes" %}`.
- A hidden question has the value `none` in a template. Do not print it directly; place dependent
  text inside a suitable condition.
- Repeating groups and loops are outside the supported xassemble workflow. A questionnaire can
  collect only one value per variable.
- Use ordinary Word formatting for generated content. xassemble does not supply images,
  rich-text objects, subdocuments, or custom template filters as answer values.

For more advanced background, see the official
[python-docx-template documentation](https://docxtpl.readthedocs.io/en/stable/). Features shown
there may require application changes and are not necessarily supported by xassemble.

### 12. Upload and publish templates

The questionnaire must be current before you can upload a template.

For every row in the questionnaire's output documents table:

1. Under **Templates** on the **Manage** page, enter the exact **Template label** from that row.
   For example, enter `release_agreement`, not the Word filename or display title.
2. Select the corresponding `.docx` template.
3. Optionally enter a **Version note**.
4. Select **Validate upload**.
5. Correct and re-upload the template if xassemble reports an unknown variable or unreadable
   template.
6. Find the validated version under its template group and select **Publish**.
7. Confirm that the version is marked **Current**.

Repeat these steps until **every possible output label** has a current template. A document set
may appear ready when it has at least one published template, but generation will fail if the
answers select an output whose exact label has no published template.

Validation checks structure and variable names. It does not check legal accuracy, whether every
clause is logically correct, whether a filename pattern contains only supported fields, or
whether all possible output labels have templates.

### 13. Test before colleagues use the set

After publishing:

1. Return to **All document sets** and select **Assemble**.
2. Test the usual answer path.
3. Test each answer that shows or hides a question.
4. Test each answer that includes or excludes an output document.
5. Generate documents for every important combination.
6. Check the downloaded filenames and open every `.docx` file.
7. Search for `{{`, `{%`, blank gaps, the word `None`, and unexpected `True` or `False`.
8. Review wording, numbering, page breaks, tables, headers, footers, and defined terms.

### 14. Update safely and roll back

To update a questionnaire or template, download the current file, edit a copy, upload it with a
clear version note, validate it, test it where possible, and publish it. Keep an untouched local
copy until the new version has been verified.

Some changes need a safe order:

- **Add a variable:** add and publish the questionnaire variable first; then update and publish
  templates that use it.
- **Remove a variable:** first remove it from every current template and publish those template
  versions; then remove it from the questionnaire.
- **Rename a variable:** first add the new variable while keeping the old one; update and publish
  all templates to use the new name; finally remove the old variable. A direct rename can be
  blocked because the current questionnaire and templates must remain compatible.

To restore an older version, open **Manage**, find the older questionnaire or template version,
select **Rollback**, and confirm. Rollback makes that saved version current; it does not delete
newer versions. Test a generation after rollback.

The **Delete set** action is different: it permanently removes the complete document set, all
questionnaire and template versions, and its generation history. It cannot be undone through
xassemble. Use it only when deletion is authorised and a suitable backup exists.

## 15. Quick author checklist

Before publishing a new set, confirm that:

- the set name and description tell colleagues when to use it;
- both questionnaire tables use the required headings;
- every variable and label is unique and follows the naming rules;
- every `skip_if` refers only to earlier questions;
- choice values and rule text match exactly;
- every output label has a template with the exact same label;
  - template answers are inserted as plain text and special characters are escaped automatically;
- each upload was published, not only validated;
- all question paths and output combinations were tested; and
- every generated document was reviewed as a first draft.
