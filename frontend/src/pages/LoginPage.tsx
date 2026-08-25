import { FormEvent, useState } from "react";
import { ArrowRight, FileText, LockKeyhole } from "lucide-react";

import { api } from "../api";
import type { User } from "../types";

export function LoginPage({ onLogin }: { onLogin: (user: User) => void }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault(); setLoading(true); setError("");
    try { onLogin(await api<User>("/auth/login", { method: "POST", body: JSON.stringify({ username, password }) })); }
    catch (caught) { setError(caught instanceof Error ? caught.message : "Unable to sign in."); }
    finally { setLoading(false); }
  }

  return (
    <main className="login-shell">
      <section className="login-story" aria-labelledby="welcome-title">
        <div className="brand-mark"><FileText size={22} strokeWidth={1.7} /> xa</div>
        <div className="story-copy"><p className="eyebrow">Internal legal workspace</p><h1 id="welcome-title">From answers to a strong first draft.</h1><p>Assemble dependable Word documents from questionnaires your legal team can own, update, and roll back with confidence.</p></div>
        <p className="story-note">Private by design · Versioned at every step</p>
      </section>
      <section className="login-panel" aria-labelledby="sign-in-title">
        <form className="login-card" onSubmit={submit}>
          <div className="lock-badge"><LockKeyhole size={20} /></div><p className="eyebrow">Welcome back</p><h2 id="sign-in-title">Sign in to xassemble</h2><p className="form-intro">Use the account provided by your administrator.</p>
          <label htmlFor="username">Username</label><input id="username" autoComplete="username" autoFocus value={username} onChange={(event) => setUsername(event.target.value)} required />
          <label htmlFor="password">Password</label><input id="password" type="password" autoComplete="current-password" value={password} onChange={(event) => setPassword(event.target.value)} required />
          {error && <p className="form-error" role="alert">{error}</p>}
          <button className="primary-button" disabled={loading}>{loading ? "Signing in…" : "Continue"}<ArrowRight size={17} /></button>
        </form><p className="support-note">Need access? Contact your xassemble administrator.</p>
      </section>
    </main>
  );
}
