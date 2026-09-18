# Manual template export

On a document set's **Manage** page, choose **Manual template** beside a published
template. This downloads a Word copy made from the current published template and
questionnaire. No answers are needed. The filename records both version numbers.
The original source documents are unchanged.

The manual copy contains:

- Yellow highlighted placeholders such as `[the name of the owner entity]`.
  Labels use the question's first paragraph, removing a leading `What is ` and the
  final question mark. Repeated variables use the same label.
- Shaded conditional text, including every alternative, with `[Include C1]` and
  `[End C1]` boundary markers. A rule key is appended on a new page. Colours repeat;
  the numbers identify the rules. Nested text uses the innermost condition's colour.
- A whole-document inclusion instruction when the questionnaire makes that output
  optional.

Fill in placeholders, select the appropriate clauses, and remove the markers,
highlighting, shading and instruction sheet before using the completed document.

## Try local files without uploading them

```powershell
uv run xassemble-manual --questionnaire path/to/questions.docx --template path/to/letter.docx --label letter --output path/to/letter-manual.docx
```

You can also use `uv run python -m xassemble.manual` with the same arguments.
`--label` must match an output in the questionnaire; it defaults to the template's
filename without `.docx`. The destination folder must already exist. The exporter
refuses to overwrite either source file. Keep private source files and trial
exports outside the repository.

## First-pass scope

The exporter handles `if`, `elif`, `else`, and `endif`, including docxtpl paragraph,
run and table tags and whitespace-control variants. It preserves both alternatives
instead of evaluating them. It handles tags split across Word runs, tables,
headers, footers and note paragraphs while retaining the source package's styles,
relationships, images and numbering definitions.

`upper`, `lower`, and `title` become explicit formatting instructions beside the
question label. Other field expressions become highlighted
`[Calculate / review manually: ...]` placeholders. Complex condition expressions
retain their source rule with a review instruction. No template expression executes
during export.

Loops, assignments, macros, includes and other control tags are not supported.
Unknown variables, broken conditional boundaries and tags crossing paragraph
boundaries produce an error rather than a partial download. This is a manual aid,
not a reversible conversion: questionnaire validation, examples, commentary and
question skip rules are not reproduced. Expect longer documents and changed page
breaks because placeholders and editing instructions occupy space.

The authenticated API endpoint is
`GET /document-sets/{slug}/current/templates/{label}/manual`.
