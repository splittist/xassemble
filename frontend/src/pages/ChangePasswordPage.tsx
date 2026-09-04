import { FormEvent, useState } from "react";
import { ArrowRight, KeyRound } from "lucide-react";
import { Link } from "react-router-dom";

import { api } from "../api";
import type { User } from "../types";

interface Props {
  forced?: boolean;
  onChanged: (user: User) => void;
  onLogout?: () => void;
}

export function ChangePasswordPage({ forced = false, onChanged, onLogout }: Props) {
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const [changed, setChanged] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError("");
    if (newPassword !== confirmation) {
      setError("New passwords do not match");
      return;
    }
    setSaving(true);
    try {
      const user = await api<User>("/auth/change-password", {
        method: "POST",
        body: JSON.stringify({ current_password: currentPassword, new_password: newPassword })
      });
      onChanged(user);
      setCurrentPassword("");
      setNewPassword("");
      setConfirmation("");
      setChanged(true);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not change your password.");
    } finally {
      setSaving(false);
    }
  }

  const form = (
    <form className={forced ? "login-card" : "account-card-form"} onSubmit={submit}>
      <div className="lock-badge"><KeyRound size={20} /></div>
      <p className="eyebrow">Account security</p>
      <h2>{forced ? "Choose a new password" : "Change your password"}</h2>
      <p className="form-intro">{forced ? "Your temporary password must be replaced before you can continue." : "Enter your current password, then choose a new one."}</p>
      <label htmlFor="current-password">Current password</label>
      <input id="current-password" type="password" autoComplete="current-password" value={currentPassword} onChange={(event) => setCurrentPassword(event.target.value)} required />
      <label htmlFor="new-password">New password</label>
      <input id="new-password" type="password" autoComplete="new-password" minLength={12} value={newPassword} onChange={(event) => setNewPassword(event.target.value)} required />
      <p className="field-hint">Use at least 12 characters.</p>
      <label htmlFor="confirm-password">Confirm new password</label>
      <input id="confirm-password" type="password" autoComplete="new-password" minLength={12} value={confirmation} onChange={(event) => setConfirmation(event.target.value)} required />
      {error && <p className="form-error" role="alert">{error}</p>}
      {changed && !forced && <p className="success-banner" role="status">Your password has been changed.</p>}
      <button className="primary-button" disabled={saving}>{saving ? "Changing password…" : "Change password"}<ArrowRight size={17} /></button>
      {forced && <button type="button" className="gate-logout" onClick={onLogout}>Sign out</button>}
    </form>
  );

  if (forced) return <main className="password-gate"><section>{form}</section></main>;
  return <div className="page-frame account-page"><Link className="back-link" to="/">← Document sets</Link>{form}</div>;
}
