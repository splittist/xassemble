import { FormEvent, useEffect, useState } from "react";
import { ArrowRight, FilePlus2, Files, Plus, Settings2, X } from "lucide-react";
import { Link } from "react-router-dom";

import { api } from "../api";
import { ErrorMessage, Loading } from "../components/Feedback";
import type { DocumentSet } from "../types";

export function DashboardPage() {
  const [sets, setSets] = useState<DocumentSet[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [creating, setCreating] = useState(false);
  async function load() {
    try { setSets(await api<DocumentSet[]>("/document-sets")); setError(""); }
    catch (caught) { setError(caught instanceof Error ? caught.message : "Could not load document sets."); }
    finally { setLoading(false); }
  }
  useEffect(() => { void load(); }, []);
  return (
    <div className="page-frame">
      <header className="page-heading"><div><p className="eyebrow">Document library</p><h1>Document sets</h1><p>Choose a workflow to assemble a new first draft.</p></div><button className="button secondary" onClick={() => setCreating(true)}><Plus size={17} /> New set</button></header>
      {error && <ErrorMessage message={error} />}
      {loading ? <Loading label="Loading document sets" /> : sets.length === 0 ? (
        <section className="empty-state"><span><FilePlus2 size={28} /></span><h2>Create your first document set</h2><p>Start with a named workspace, then publish its questionnaire and Word templates.</p><button className="button primary" onClick={() => setCreating(true)}><Plus size={17} /> New document set</button></section>
      ) : <section className="set-grid" aria-label="Available document sets">{sets.map((set) => <DocumentSetCard key={set.id} documentSet={set} />)}</section>}
      {creating && <CreateSetDialog onClose={() => setCreating(false)} onCreated={() => { setCreating(false); void load(); }} />}
    </div>
  );
}

function DocumentSetCard({ documentSet }: { documentSet: DocumentSet }) {
  const ready = documentSet.questionnaire_version !== null && documentSet.current_template_count > 0;
  return (
    <article className="set-card"><div className="set-card-icon"><Files size={23} strokeWidth={1.65} /></div><div className="set-card-copy"><span className={`status-dot ${ready ? "ready" : "setup"}`}>{ready ? "Ready" : "Setup needed"}</span><h2>{documentSet.name}</h2><p>{documentSet.description || "No description has been added yet."}</p><div className="set-meta"><span>Questionnaire {documentSet.questionnaire_version ? `v${documentSet.questionnaire_version}` : "not published"}</span><span>{documentSet.current_template_count} template{documentSet.current_template_count === 1 ? "" : "s"}</span></div></div><div className="card-actions"><Link className={`button primary ${ready ? "" : "disabled"}`} aria-disabled={!ready} tabIndex={ready ? 0 : -1} to={ready ? `/sets/${documentSet.slug}/assemble` : "#"}>Assemble <ArrowRight size={16} /></Link><Link className="button quiet" to={`/sets/${documentSet.slug}/manage`}><Settings2 size={16} /> Manage</Link></div></article>
  );
}

function CreateSetDialog({ onClose, onCreated }: { onClose: () => void; onCreated: () => void }) {
  const [name, setName] = useState(""); const [slug, setSlug] = useState(""); const [description, setDescription] = useState(""); const [error, setError] = useState(""); const [saving, setSaving] = useState(false);
  function changeName(value: string) { setName(value); setSlug(value.toLowerCase().trim().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "")); }
  async function submit(event: FormEvent) { event.preventDefault(); setSaving(true); setError(""); try { await api<DocumentSet>("/document-sets", { method: "POST", body: JSON.stringify({ name, slug, description }) }); onCreated(); } catch (caught) { setError(caught instanceof Error ? caught.message : "Could not create the set."); } finally { setSaving(false); } }
  return (
    <div className="dialog-scrim" role="presentation"><section className="dialog" role="dialog" aria-modal="true" aria-labelledby="new-set-title"><button className="icon-button dialog-close" aria-label="Close" onClick={onClose}><X size={20} /></button><p className="eyebrow">New workspace</p><h2 id="new-set-title">Create a document set</h2><p className="dialog-intro">Give colleagues a clear name and a short description of when to use it.</p><form onSubmit={submit}><label htmlFor="set-name">Name</label><input id="set-name" autoFocus value={name} onChange={(event) => changeName(event.target.value)} required /><label htmlFor="set-slug">URL name</label><input id="set-slug" value={slug} onChange={(event) => setSlug(event.target.value)} pattern="[a-z0-9]+(?:-[a-z0-9]+)*" required /><label htmlFor="set-description">Description</label><textarea id="set-description" rows={3} value={description} onChange={(event) => setDescription(event.target.value)} />{error && <ErrorMessage message={error} />}<div className="dialog-actions"><button type="button" className="button quiet" onClick={onClose}>Cancel</button><button className="button primary" disabled={saving}>{saving ? "Creating…" : "Create set"}</button></div></form></section></div>
  );
}
