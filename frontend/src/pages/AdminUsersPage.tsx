import { FormEvent, useEffect, useState } from "react";
import { KeyRound, Plus, ShieldCheck, UserCheck, UserX, X } from "lucide-react";

import { api } from "../api";
import { ErrorMessage, Loading } from "../components/Feedback";
import type { ManagedUser, User } from "../types";

export function AdminUsersPage({ currentUser }: { currentUser: User }) {
  const [users, setUsers] = useState<ManagedUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [creating, setCreating] = useState(false);
  const [resetting, setResetting] = useState<ManagedUser | null>(null);

  async function load() {
    try { setUsers(await api<ManagedUser[]>("/admin/users")); setError(""); }
    catch (caught) { setError(caught instanceof Error ? caught.message : "Could not load users."); }
    finally { setLoading(false); }
  }
  useEffect(() => { void load(); }, []);

  async function update(user: ManagedUser, changes: Partial<Pick<ManagedUser, "role" | "active">>) {
    setError("");
    try {
      await api<ManagedUser>(`/admin/users/${user.id}`, {
        method: "PUT",
        body: JSON.stringify({ name: user.name, role: changes.role ?? user.role, active: changes.active ?? user.active })
      });
      await load();
    } catch (caught) { setError(caught instanceof Error ? caught.message : "Could not update the user."); }
  }

  return (
    <div className="page-frame users-frame">
      <header className="page-heading"><div><p className="eyebrow">Administration</p><h1>Users</h1><p>Create accounts, control access, and issue temporary passwords.</p></div><button className="button secondary" onClick={() => setCreating(true)}><Plus size={17} /> New user</button></header>
      {error && <ErrorMessage message={error} />}
      {loading ? <Loading label="Loading users" /> : <section className="user-list" aria-label="User accounts">
        {users.map((user) => <article className="user-row" key={user.id}>
          <span className={`user-status ${user.active ? "active" : ""}`}>{user.active ? <UserCheck size={19} /> : <UserX size={19} />}</span>
          <div className="user-copy"><strong>{user.name}</strong><span>@{user.username}</span>{user.must_change_password && <small>Must change password</small>}</div>
          <label><span>Role</span><select aria-label={`Role for ${user.username}`} value={user.role} onChange={(event) => void update(user, { role: event.target.value as User["role"] })}><option value="member">Member</option><option value="admin">Administrator</option></select></label>
          <div className="user-actions">
            <button className="button quiet small" disabled={user.id === currentUser.id} onClick={() => setResetting(user)}><KeyRound size={14} /> Reset password</button>
            <button className={`button small ${user.active ? "danger" : "secondary"}`} onClick={() => void update(user, { active: !user.active })}>{user.active ? "Deactivate" : "Activate"}</button>
          </div>
        </article>)}
      </section>}
      {creating && <CreateUserDialog onClose={() => setCreating(false)} onCreated={() => { setCreating(false); void load(); }} />}
      {resetting && <ResetPasswordDialog user={resetting} onClose={() => setResetting(null)} onReset={() => { setResetting(null); void load(); }} />}
    </div>
  );
}

function CreateUserDialog({ onClose, onCreated }: { onClose: () => void; onCreated: () => void }) {
  const [name, setName] = useState(""); const [username, setUsername] = useState(""); const [password, setPassword] = useState(""); const [confirmation, setConfirmation] = useState(""); const [role, setRole] = useState<User["role"]>("member"); const [error, setError] = useState(""); const [saving, setSaving] = useState(false);
  async function submit(event: FormEvent) { event.preventDefault(); setError(""); if (password !== confirmation) { setError("Temporary passwords do not match"); return; } setSaving(true); try { await api<ManagedUser>("/admin/users", { method: "POST", body: JSON.stringify({ name, username, temporary_password: password, role }) }); onCreated(); } catch (caught) { setError(caught instanceof Error ? caught.message : "Could not create the user."); } finally { setSaving(false); } }
  return <div className="dialog-scrim"><section className="dialog" role="dialog" aria-modal="true" aria-labelledby="create-user-title"><button className="icon-button dialog-close" aria-label="Close" onClick={onClose}><X size={20} /></button><ShieldCheck size={24} className="dialog-icon" /><p className="eyebrow">New account</p><h2 id="create-user-title">Create a user</h2><p className="dialog-intro">They will have to replace this temporary password when they first sign in.</p><form onSubmit={submit}><label htmlFor="user-name">Name</label><input id="user-name" value={name} onChange={(event) => setName(event.target.value)} required autoFocus /><label htmlFor="user-username">Username</label><input id="user-username" value={username} onChange={(event) => setUsername(event.target.value)} required /><label htmlFor="user-password">Temporary password</label><input id="user-password" type="password" autoComplete="new-password" minLength={12} value={password} onChange={(event) => setPassword(event.target.value)} required /><label htmlFor="user-password-confirmation">Confirm temporary password</label><input id="user-password-confirmation" type="password" autoComplete="new-password" minLength={12} value={confirmation} onChange={(event) => setConfirmation(event.target.value)} required /><label htmlFor="user-role">Role</label><select id="user-role" value={role} onChange={(event) => setRole(event.target.value as User["role"])}><option value="member">Member</option><option value="admin">Administrator</option></select>{error && <ErrorMessage message={error} />}<div className="dialog-actions"><button type="button" className="button quiet" onClick={onClose}>Cancel</button><button className="button primary" disabled={saving}>{saving ? "Creating…" : "Create user"}</button></div></form></section></div>;
}

function ResetPasswordDialog({ user, onClose, onReset }: { user: ManagedUser; onClose: () => void; onReset: () => void }) {
  const [password, setPassword] = useState(""); const [confirmation, setConfirmation] = useState(""); const [error, setError] = useState(""); const [saving, setSaving] = useState(false);
  async function submit(event: FormEvent) { event.preventDefault(); setError(""); if (password !== confirmation) { setError("Temporary passwords do not match"); return; } setSaving(true); try { await api<void>(`/admin/users/${user.id}/reset-password`, { method: "POST", body: JSON.stringify({ temporary_password: password }) }); onReset(); } catch (caught) { setError(caught instanceof Error ? caught.message : "Could not reset the password."); } finally { setSaving(false); } }
  return <div className="dialog-scrim"><section className="dialog" role="dialog" aria-modal="true" aria-labelledby="reset-title"><button className="icon-button dialog-close" aria-label="Close" onClick={onClose}><X size={20} /></button><p className="eyebrow">Account security</p><h2 id="reset-title">Reset {user.name}'s password</h2><p className="dialog-intro">Their sessions will end immediately, and they must replace this password at their next login.</p><form onSubmit={submit}><label htmlFor="reset-password">Temporary password</label><input id="reset-password" type="password" autoComplete="new-password" minLength={12} value={password} onChange={(event) => setPassword(event.target.value)} required autoFocus /><label htmlFor="reset-password-confirmation">Confirm temporary password</label><input id="reset-password-confirmation" type="password" autoComplete="new-password" minLength={12} value={confirmation} onChange={(event) => setConfirmation(event.target.value)} required />{error && <ErrorMessage message={error} />}<div className="dialog-actions"><button type="button" className="button quiet" onClick={onClose}>Cancel</button><button className="button primary" disabled={saving}>{saving ? "Resetting…" : "Reset password"}</button></div></form></section></div>;
}
