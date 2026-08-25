import { useEffect, useState } from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";

import { api } from "./api";
import { AppShell } from "./components/AppShell";
import { Loading } from "./components/Feedback";
import { DashboardPage } from "./pages/DashboardPage";
import { LoginPage } from "./pages/LoginPage";
import { ManagePage } from "./pages/ManagePage";
import { QuestionnairePage } from "./pages/QuestionnairePage";
import type { User } from "./types";

export default function App() {
  const [user, setUser] = useState<User | null | undefined>(undefined);

  useEffect(() => {
    api<User>("/auth/me").then(setUser).catch(() => setUser(null));
    const unauthorized = () => setUser(null);
    window.addEventListener("xassemble:unauthorized", unauthorized);
    return () => window.removeEventListener("xassemble:unauthorized", unauthorized);
  }, []);

  async function logout() {
    await api<void>("/auth/logout", { method: "POST" });
    setUser(null);
  }

  if (user === undefined) return <div className="app-loading"><Loading label="Opening workspace" /></div>;
  if (!user) return <LoginPage onLogin={setUser} />;

  return (
    <BrowserRouter>
      <AppShell user={user} onLogout={() => void logout()}>
        <Routes>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/sets/:slug/assemble" element={<QuestionnairePage />} />
          <Route path="/sets/:slug/manage" element={<ManagePage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AppShell>
    </BrowserRouter>
  );
}
