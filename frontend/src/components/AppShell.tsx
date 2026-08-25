import { FileStack, LogOut, Menu, UserRound, X } from "lucide-react";
import { ReactNode, useState } from "react";
import { Link, NavLink } from "react-router-dom";

import type { User } from "../types";

interface Props { children: ReactNode; user: User; onLogout: () => void; }

export function AppShell({ children, user, onLogout }: Props) {
  const [menuOpen, setMenuOpen] = useState(false);
  return (
    <div className="app-shell">
      <header className="mobile-header">
        <Link to="/" className="wordmark"><FileStack size={20} /> xassemble</Link>
        <button className="icon-button" aria-label="Open navigation" onClick={() => setMenuOpen(true)}><Menu size={21} /></button>
      </header>
      {menuOpen && <button className="menu-scrim" aria-label="Close navigation" onClick={() => setMenuOpen(false)} />}
      <aside className={`sidebar ${menuOpen ? "sidebar-open" : ""}`}>
        <div className="sidebar-top">
          <Link to="/" className="wordmark"><FileStack size={22} /> xassemble</Link>
          <button className="icon-button sidebar-close" aria-label="Close navigation" onClick={() => setMenuOpen(false)}><X size={20} /></button>
        </div>
        <nav aria-label="Main navigation"><NavLink to="/" end onClick={() => setMenuOpen(false)}><FileStack size={18} /> Document sets</NavLink></nav>
        <div className="account-card">
          <span className="avatar"><UserRound size={17} /></span>
          <span><strong>{user.name}</strong><small>@{user.username}</small></span>
          <button className="icon-button" aria-label="Sign out" title="Sign out" onClick={onLogout}><LogOut size={17} /></button>
        </div>
      </aside>
      <main className="workspace">{children}</main>
    </div>
  );
}
