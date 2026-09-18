import { ChangeEvent, FormEvent, useEffect, useMemo, useState } from "react";
import { ArrowLeft, Check, ClipboardPen, Download, Sparkles } from "lucide-react";
import { Link, useParams } from "react-router-dom";

import { api, download } from "../api";
import { AnswerExchange } from "../components/AnswerExchange";
import { ErrorMessage, Loading } from "../components/Feedback";
import type { Question, Questionnaire } from "../types";

type Answers = Record<string, string | boolean | null>;

export function QuestionnairePage() {
  const { slug = "" } = useParams();
  return <QuestionnaireRunner key={slug} slug={slug} />;
}

function QuestionnaireRunner({ slug }: { slug: string }) {
  const [questionnaire, setQuestionnaire] = useState<Questionnaire | null>(null);
  const [answers, setAnswers] = useState<Answers>({});
  const [visible, setVisible] = useState<string[]>([]);
  const [projectCode, setProjectCode] = useState("");
  const [error, setError] = useState("");
  const [generating, setGenerating] = useState(false);
  const [imported, setImported] = useState<string[]>([]);
  const [acknowledge, setAcknowledge] = useState(false);
  const [evaluated, setEvaluated] = useState<Answers | null>(null);

  useEffect(() => {
    let active = true;
    api<Questionnaire>(`/document-sets/${slug}/questionnaire`)
      .then((value) => { if (!active) return; setQuestionnaire(value); setVisible(value.questions.map((question) => question.variable_name)); })
      .catch((caught) => { if (active) setError(caught instanceof Error ? caught.message : "Could not open this questionnaire."); });
    return () => { active = false; };
  }, [slug]);

  useEffect(() => {
    if (!questionnaire) return;
    let active = true;
    const timer = window.setTimeout(() => {
      api<{ visible: string[]; hidden: string[] }>(`/document-sets/${slug}/questionnaire/evaluate`, { method: "POST", body: JSON.stringify({ answers, questionnaire_version_id: questionnaire.version_id, questionnaire_schema_sha256: questionnaire.schema_sha256 }) })
        .then((result) => { if (active) { setVisible(result.visible); setEvaluated(answers); } })
        .catch((caught) => { if (active) setError(caught instanceof Error ? caught.message : "Could not update the questionnaire."); });
    }, 250);
    return () => { active = false; window.clearTimeout(timer); };
  }, [answers, questionnaire, slug]);

  const visibleQuestions = useMemo(() => questionnaire?.questions.filter((question) => visible.includes(question.variable_name)) ?? [], [questionnaire, visible]);
  const answered = visibleQuestions.filter((question) => hasAnswer(answers[question.variable_name])).length;
  const progress = visibleQuestions.length ? Math.round((answered / visibleQuestions.length) * 100) : 0;

  const missing = visibleQuestions.filter(question => !hasAnswer(answers[question.variable_name]));

  function answer(question: Question, value: string | boolean) {
    setAcknowledge(false);
    setImported(current => current.filter(key => key !== question.variable_name));
    setAnswers((current) => ({ ...current, [question.variable_name]: value }));
  }

  async function generate(event: FormEvent) {
    event.preventDefault();
    if (!questionnaire || evaluated !== answers || (missing.length > 0 && !acknowledge)) return;
    setGenerating(true); setError("");
    try { await download(`/document-sets/${slug}/generate`, { method: "POST", body: JSON.stringify({ answers, project_code: projectCode, questionnaire_version_id: questionnaire.version_id, questionnaire_schema_sha256: questionnaire.schema_sha256, acknowledge_incomplete: acknowledge }) }); }
    catch (caught) { setError(caught instanceof Error ? caught.message : "Could not generate the documents."); }
    finally { setGenerating(false); }
  }

  if (error && !questionnaire) return <div className="page-frame"><BackLink /><ErrorMessage message={error} /></div>;
  if (!questionnaire) return <div className="page-frame"><Loading label="Opening questionnaire" /></div>;

  let previousSection = "";
  return (
    <form className="questionnaire-layout" onSubmit={generate}>
      <div className="questionnaire-main">
        <BackLink />
        <header className="page-heading compact"><div><p className="eyebrow">New assembly</p><h1>{humanize(slug)}</h1><p>Complete the visible questions. Answers are held on this page and sent to xassemble for validation and generation. Leaving or refreshing loses your draft.</p></div></header>
        {error && <ErrorMessage message={error} />}
        <AnswerExchange slug={slug} questionnaire={questionnaire} answers={answers} onApply={(value, keys) => { setAnswers(value); setImported(current => [...new Set([...current, ...keys])]); setAcknowledge(false); }} />
        <section className="question-list">
          {visibleQuestions.map((question, index) => {
            const showSection = question.section && question.section !== previousSection;
            previousSection = question.section || previousSection;
            return (
              <div key={question.variable_name}>
                {showSection && <h2 className="section-title"><span>{question.section}</span></h2>}
                <article className="question-card">
                  <div className="question-number">{String(index + 1).padStart(2, "0")}</div>
                  <div className="question-body">
                    <div className="question-label" id={`q-${question.variable_name}-label`}>{question.question_text}</div>
                    {question.commentary && <p className="question-commentary">{question.commentary}</p>}
                    {imported.includes(question.variable_name) && <p className="imported-badge">Imported — review before generation</p>}
                    <QuestionInput question={question} value={answers[question.variable_name]} onChange={(value) => answer(question, value)} />
                    {usableExamples(question).length > 0 && (
                      <div className="example-buttons">
                        {usableExamples(question).map((example, exampleIndex) => (
                          <button key={exampleIndex} type="button" className="example-button" onClick={() => answer(question, example)}><Sparkles size={14} /> Use example: “{example}”</button>
                        ))}
                      </div>
                    )}
                  </div>
                </article>
              </div>
            );
          })}
        </section>
      </div>
      <aside className="generation-panel">
        <div className="progress-copy"><span>Questionnaire progress</span><strong>{progress}%</strong></div>
        <div className="progress-track"><span style={{ width: `${progress}%` }} /></div>
        <p>{answered} of {visibleQuestions.length} visible questions answered</p>
        <hr />
        <label htmlFor="project-code">Project code</label>
        <input id="project-code" value={projectCode} onChange={(event) => setProjectCode(event.target.value)} placeholder="e.g. MAT-2026-014" required />
        <p className="field-help">Used in generated filenames and the audit trail.</p>
        {missing.length > 0 && <div className="missing-answers"><p>Missing answers: {missing.map(question => question.question_text).join("; ")}</p><label><input type="checkbox" checked={acknowledge} onChange={event => setAcknowledge(event.target.checked)} /> Generate an incomplete first draft with these answers missing</label></div>}
        <button className="button primary generate-button" disabled={generating || evaluated !== answers || (missing.length > 0 && !acknowledge)}><Download size={17} /> {generating ? "Generating…" : "Generate documents"}</button>
        <div className="draft-note"><ClipboardPen size={17} /><span><strong>First draft</strong>Review generated documents before use.</span></div>
      </aside>
    </form>
  );
}

function QuestionInput({ question, value, onChange }: { question: Question; value: string | boolean | null | undefined; onChange: (value: string | boolean) => void }) {
  const id = `q-${question.variable_name}`;
  if (question.type === "yesno") return (
    <div className="yesno-group" id={id} role="group" aria-labelledby={`${id}-label`}>
      <button type="button" className={value === true ? "selected" : ""} onClick={() => onChange(true)}>{value === true && <Check size={16} />} Yes</button>
      <button type="button" className={value === false ? "selected" : ""} onClick={() => onChange(false)}>{value === false && <Check size={16} />} No</button>
    </div>
  );
  if (question.type === "choice") return (
    <select id={id} aria-labelledby={`${id}-label`} value={typeof value === "string" ? value : ""} onChange={(event) => onChange(event.target.value)}><option value="">Select an option</option>{question.options.map((option) => <option key={option}>{option}</option>)}</select>
  );
  if (question.type === "textarea") return <textarea id={id} aria-labelledby={`${id}-label`} rows={5} value={typeof value === "string" ? value : ""} onChange={(event: ChangeEvent<HTMLTextAreaElement>) => onChange(event.target.value)} />;
  return <input id={id} aria-labelledby={`${id}-label`} value={typeof value === "string" ? value : ""} onChange={(event) => onChange(event.target.value)} />;
}

function BackLink() { return <Link className="back-link" to="/"><ArrowLeft size={15} /> All document sets</Link>; }
function usableExamples(question: Question) {
  if (question.type === "yesno") return [];
  return question.examples.filter(example => question.type !== "choice" || question.options.includes(example));
}
function hasAnswer(value: unknown) { return value === true || value === false || (typeof value === "string" && value.trim().length > 0); }
function humanize(value: string) { return value.split("-").map((part) => part.charAt(0).toUpperCase() + part.slice(1)).join(" "); }
