import { useEffect, useMemo, useRef, useState } from "react";
import { api, download } from "../api";
import type { Answers, Questionnaire } from "../types";

export function AnswerExchange({ slug, questionnaire, answers, onApply }: {
  slug: string; questionnaire: Questionnaire; answers: Answers;
  onApply: (answers: Answers, keys: string[]) => void;
}) {
  const [candidate, setCandidate] = useState<Answers | null>(null);
  const [selected, setSelected] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [visibility, setVisibility] = useState<{ visible: string[]; hidden: string[]; answers: Answers } | null>(null);
  const request = useRef(0);
  const latestAnswers = useRef(answers);
  latestAnswers.current = answers;
  useEffect(() => () => { request.current += 1; }, []);
  // An edit to the draft invalidates any replacement decisions made against its old values.
  useEffect(() => { setSelected([]); }, [answers]);
  const merged = useMemo(() => ({ ...answers, ...Object.fromEntries(
    Object.entries(candidate ?? {}).filter(([key]) => selected.includes(key))
  ) }), [answers, candidate, selected]);
  useEffect(() => {
    if (!candidate) return;
    let active = true;
    setVisibility(null);
    api<{ visible: string[]; hidden: string[] }>(`/document-sets/${slug}/questionnaire/evaluate`, {
      method: "POST", body: JSON.stringify({ answers: merged,
        questionnaire_version_id: questionnaire.version_id,
        questionnaire_schema_sha256: questionnaire.schema_sha256 })
    }).then(value => { if (active) setVisibility({ ...value, answers: merged }); })
      .catch(caught => { if (active) setError(String(caught.message)); });
    return () => { active = false; };
  }, [candidate, merged, questionnaire, slug]);

  async function importFile(file: File) {
    const current = ++request.current;
    setBusy(true); setError(""); setCandidate(null); setVisibility(null);
    try {
      if (file.size > 1024 * 1024) throw new Error("Answer file exceeds the 1 MiB limit.");
      const body = new FormData(); body.append("file", file);
      const value = await api<{ answers: Answers; questionnaire_version_id: number; questionnaire_schema_sha256: string }>(
        `/document-sets/${slug}/questionnaire/answer-import`, { method: "POST", body });
      if (current !== request.current) return;
      if (value.questionnaire_version_id !== questionnaire.version_id || value.questionnaire_schema_sha256 !== questionnaire.schema_sha256)
        throw new Error("This page uses a different questionnaire version. Keep your draft for reference and reopen the questionnaire.");
      setCandidate(value.answers);
      setSelected(Object.keys(value.answers).filter(key => !hasAnswer(latestAnswers.current[key])));
    } catch (caught) { if (current === request.current) setError(caught instanceof Error ? caught.message : "Could not import answers."); }
    finally { if (current === request.current) setBusy(false); }
  }

  return <section className="answer-exchange" aria-label="Bring your own LLM">
    <h2>Bring your own LLM</h2>
    <p>Download the briefing and use your organisation’s approved tool and procedures. Upload its JSON answers here for review. No LLM connection or API keys are needed.</p>
    <button type="button" className="button secondary" onClick={async () => {
      setError("");
      try { await download(`/document-sets/${slug}/questionnaire/answer-briefing?version_id=${questionnaire.version_id}&schema_sha256=${questionnaire.schema_sha256}`); }
      catch (caught) { setError(caught instanceof Error ? caught.message : "Could not download briefing."); }
    }}>Download LLM briefing</button>
    <label className="import-label">Import answers (.json)
      <input type="file" accept=".json,application/json" disabled={busy} onChange={event => {
        const file = event.target.files?.[0]; event.target.value = "";
        if (file) void importFile(file);
      }} />
    </label>
    {busy && <p role="status">Validating answer file…</p>}
    {error && <p role="alert">{error}</p>}
    {candidate && <div className="import-preview">
      <h3>Review imported answers</h3>
      <p>Empty values never erase answers. Existing answers are preserved unless you select a replacement. Hidden answers are retained for later review and excluded from documents while hidden.</p>
      {Object.keys(candidate).length === 0 && <p>No answers to import.</p>}
      {Object.entries(candidate).map(([key, value]) => {
        const existing = answers[key]; const same = existing === value;
        return <div className="import-row" key={key}>
          <label><input type="checkbox" checked={selected.includes(key)} disabled={same}
            onChange={event => setSelected(current => event.target.checked ? [...current, key] : current.filter(item => item !== key))} />
            {questionnaire.questions.find(q => q.variable_name === key)?.question_text} — {same ? "Unchanged" : hasAnswer(existing) ? "Replace existing answer" : "Add answer"}
          </label>
          {hasAnswer(existing) && <p>Current: <span className="answer-value">{display(existing)}</span></p>}
          <p>Imported: <span className="answer-value">{display(value)}</span></p>
          {visibility?.hidden.includes(key) && <p className="field-help">Hidden with the selected answers</p>}
        </div>;
      })}
      {visibility && <p>Unanswered visible questions: {visibility.visible.filter(key => !hasAnswer(merged[key])).map(key => questionnaire.questions.find(q => q.variable_name === key)?.question_text).join("; ") || "None"}</p>}
      <div className="import-actions">
        <button type="button" className="button primary" disabled={!visibility || visibility.answers !== merged || selected.length === 0} onClick={() => {
          onApply(merged, selected); setCandidate(null); setSelected([]);
        }}>Apply selected answers</button>
        <button type="button" className="button secondary" onClick={() => { setCandidate(null); setError(""); }}>Cancel import</button>
      </div>
    </div>}
  </section>;
}

function hasAnswer(value: unknown) { return typeof value === "boolean" || typeof value === "string" && value.trim().length > 0; }
function display(value: unknown) { return value === true ? "Yes" : value === false ? "No" : String(value ?? ""); }
