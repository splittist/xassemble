import { FormEvent, useEffect, useState } from "react";
import { ArrowLeft, CheckCircle2, Download, Files, FileText, RotateCcw, Trash2, Upload, X } from "lucide-react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { api, download } from "../api";
import { ErrorMessage, Loading } from "../components/Feedback";
import type { Version, VersionHistory } from "../types";

type VersionKind = "questionnaire" | "template";

export function ManagePage() {
  const { slug = "" } = useParams();
  const navigate = useNavigate();
  const [history, setHistory] = useState<VersionHistory | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [deleting, setDeleting] = useState(false);

  async function load() {
    try { setHistory(await api<VersionHistory>(`/document-sets/${slug}/versions`)); setError(""); }
    catch (caught) { setError(caught instanceof Error ? caught.message : "Could not load version history."); }
  }
  useEffect(() => { void load(); }, [slug]);

  async function downloadManual(label: string) {
    setBusy(true); setError("");
    try {
      await download(`/document-sets/${slug}/current/templates/${encodeURIComponent(label)}/manual`);
    } catch (caught) { setError(caught instanceof Error ? caught.message : "Could not export a manual template."); }
    finally { setBusy(false); }
  }

  async function upload(kind: VersionKind, form: HTMLFormElement) {
    setBusy(true); setError(""); setNotice("");
    try {
      const endpoint = kind === "questionnaire" ? "questionnaire-versions" : "template-versions";
      const result = await api<{ id: number; version_no: number }>(`/document-sets/${slug}/${endpoint}`, { method: "POST", body: new FormData(form) });
      setNotice(`${kind === "questionnaire" ? "Questionnaire" : "Template"} version ${result.version_no} passed validation and is ready to publish.`);
      form.reset(); await load();
    } catch (caught) { setError(caught instanceof Error ? caught.message : "Upload failed validation."); }
    finally { setBusy(false); }
  }

  async function publish(kind: VersionKind, version: Version) {
    const action = version.is_current ? "republish" : "publish";
    if (!window.confirm(`${action === "publish" ? "Publish" : "Republish"} version ${version.version_no}? This will become the current version.`)) return;
    setBusy(true); setError("");
    try {
      const endpoint = kind === "questionnaire" ? "questionnaire-versions" : "template-versions";
      await api(`/document-sets/${slug}/${endpoint}/${version.id}/publish`, { method: "POST" });
      setNotice(`Version ${version.version_no} is now current.`); await load();
    } catch (caught) { setError(caught instanceof Error ? caught.message : "Could not publish this version."); }
    finally { setBusy(false); }
  }

  async function deleteSet() {
    setBusy(true); setError("");
    try {
      await api(`/document-sets/${slug}`, { method: "DELETE" });
      navigate("/");
    } catch (caught) { setError(caught instanceof Error ? caught.message : "Could not delete this document set."); setDeleting(false); }
    finally { setBusy(false); }
  }

  if (!history && !error) return <div className="page-frame"><Loading label="Loading version history" /></div>;
  const groupedTemplates = groupTemplates(history?.templates ?? []);
  return (
    <div className="page-frame manage-frame">
      <Link className="back-link" to="/"><ArrowLeft size={15} /> All document sets</Link>
      <header className="page-heading"><div><p className="eyebrow">Document set administration</p><h1>{humanize(slug)}</h1><p>Upload validated source files, publish changes, or restore an earlier version.</p></div><button className="button danger" onClick={() => setDeleting(true)}><Trash2 size={16} /> Delete set</button></header>
      {error && <ErrorMessage message={error} />}
      {notice && <div className="success-banner" role="status"><CheckCircle2 size={18} />{notice}</div>}
      <section className="manage-grid">
        <div className="manage-column">
          <SourceHeader icon={<FileText />} title="Questionnaire" description="Questions and output-document rules" downloadUrl={history?.questionnaires.some((version) => version.is_current) ? `/document-sets/${slug}/current/questionnaire` : undefined} />
          <UploadCard kind="questionnaire" busy={busy} onSubmit={(form) => void upload("questionnaire", form)} />
          <VersionList kind="questionnaire" slug={slug} versions={history?.questionnaires ?? []} busy={busy} onPublish={publish} />
        </div>
        <div className="manage-column">
          <SourceHeader icon={<Files />} title="Templates" description="One Word file for each output label" />
          <UploadCard kind="template" busy={busy} onSubmit={(form) => void upload("template", form)} />
          {groupedTemplates.length === 0 ? <div className="no-versions">No template versions uploaded yet.</div> : groupedTemplates.map(([label, versions]) => (
            <div className="template-group" key={label}><div className="template-group-title"><h3>{humanize(label)}</h3>{versions.some((version) => version.is_current) && <><a className="text-link" href={`/document-sets/${slug}/current/templates/${label}`}><Download size={14} /> Current file</a><button className="button quiet small" disabled={busy} onClick={() => void downloadManual(label)} title="Highlighted placeholders and conditional sections, using the current questionnaire"><Download size={14} /> Manual template</button></>}</div><VersionList kind="template" slug={slug} versions={versions} busy={busy} onPublish={publish} /></div>
          ))}
        </div>
      </section>
      {deleting && <DeleteSetDialog slug={slug} busy={busy} onCancel={() => setDeleting(false)} onConfirm={() => void deleteSet()} />}
    </div>
  );
}

function DeleteSetDialog({ slug, busy, onCancel, onConfirm }: { slug: string; busy: boolean; onCancel: () => void; onConfirm: () => void }) {
  const [confirmation, setConfirmation] = useState("");
  return (
    <div className="dialog-scrim" role="presentation">
      <section className="dialog" role="dialog" aria-modal="true" aria-labelledby="delete-set-title">
        <button className="icon-button dialog-close" aria-label="Close" onClick={onCancel}><X size={20} /></button>
        <p className="eyebrow">Delete document set</p>
        <h2 id="delete-set-title">Are you sure?</h2>
        <p className="dialog-intro">This permanently deletes <strong>{humanize(slug)}</strong>, all of its questionnaire and template versions, and its generation history. This cannot be undone.</p>
        <label htmlFor="delete-confirmation">Type <strong>{slug}</strong> to confirm</label>
        <input id="delete-confirmation" value={confirmation} onChange={(event) => setConfirmation(event.target.value)} autoFocus />
        <div className="dialog-actions">
          <button type="button" className="button quiet" onClick={onCancel}>Cancel</button>
          <button type="button" className="button danger" disabled={busy || confirmation !== slug} onClick={onConfirm}>{busy ? "Deleting…" : "Delete permanently"}</button>
        </div>
      </section>
    </div>
  );
}


function SourceHeader({ icon, title, description, downloadUrl }: { icon: React.ReactNode; title: string; description: string; downloadUrl?: string }) {
  return <header className="source-header"><span>{icon}</span><div><h2>{title}</h2><p>{description}</p></div>{downloadUrl && <a className="button quiet" href={downloadUrl}><Download size={15} /> Current</a>}</header>;
}

function UploadCard({ kind, busy, onSubmit }: { kind: VersionKind; busy: boolean; onSubmit: (form: HTMLFormElement) => void }) {
  function submit(event: FormEvent<HTMLFormElement>) { event.preventDefault(); onSubmit(event.currentTarget); }
  return <form className="upload-card" onSubmit={submit}><div className="upload-card-title"><Upload size={18} /><strong>Upload replacement</strong></div>{kind === "template" && <><label htmlFor="template-label">Template label</label><input id="template-label" name="label" placeholder="e.g. termination_letter" pattern="[A-Za-z_][A-Za-z0-9_]*" required /></>}<label htmlFor={`${kind}-file`}>Word file</label><input id={`${kind}-file`} name="file" type="file" accept=".docx" required /><label htmlFor={`${kind}-note`}>Version note <small>optional</small></label><input id={`${kind}-note`} name="note" placeholder="What changed?" /><button className="button secondary" disabled={busy}><Upload size={15} /> Validate upload</button></form>;
}

function VersionList({ kind, slug, versions, busy, onPublish }: { kind: VersionKind; slug: string; versions: Version[]; busy: boolean; onPublish: (kind: VersionKind, version: Version) => void }) {
  if (versions.length === 0) return <div className="no-versions">No versions uploaded yet.</div>;
  return <div className="version-list">{versions.map((version) => <article className="version-row" key={version.id}><div className="version-badge">v{version.version_no}</div><div className="version-copy"><div><strong>{version.is_current ? "Current version" : version.note || "No version note"}</strong>{version.is_current ? <span className="current-pill">Current</span> : null}</div><p>{version.note && version.is_current ? `${version.note} · ` : ""}{version.uploaded_by} · {formatDate(version.uploaded_at)}</p></div><div className="version-actions"><a className="icon-button" title="Download this version" aria-label={`Download version ${version.version_no}`} href={`/document-sets/${slug}/versions/${kind}/${version.id}`}><Download size={16} /></a>{!version.is_current && <button className="button quiet small" disabled={busy} onClick={() => onPublish(kind, version)}><RotateCcw size={14} /> {versions.some((item) => item.is_current && item.version_no > version.version_no) ? "Rollback" : "Publish"}</button>}</div></article>)}</div>;
}

function groupTemplates(versions: Version[]) { const groups = new Map<string, Version[]>(); for (const version of versions) { const label = version.label ?? "template"; groups.set(label, [...(groups.get(label) ?? []), version]); } return [...groups.entries()]; }
function formatDate(value: string) { return new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(new Date(value)); }
function humanize(value: string) { return value.split(/[-_]/).map((part) => part.charAt(0).toUpperCase() + part.slice(1)).join(" "); }
