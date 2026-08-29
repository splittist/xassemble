import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, test, vi } from "vitest";

import App from "../App";
import { LoginPage } from "../pages/LoginPage";
import { QuestionnairePage } from "../pages/QuestionnairePage";

function jsonResponse(value: unknown, status = 200) {
  return Promise.resolve(new Response(JSON.stringify(value), { status, headers: { "Content-Type": "application/json" } }));
}

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("authentication", () => {
  test("shows the login screen when there is no session", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() => jsonResponse({ detail: "Authentication required" }, 401));
    render(<App />);
    expect(await screen.findByRole("heading", { name: "Sign in to xassemble" })).toBeInTheDocument();
  });

  test("submits credentials and hands back the user", async () => {
    const onLogin = vi.fn();
    vi.spyOn(globalThis, "fetch").mockImplementation(() => jsonResponse({ id: 1, name: "Jane Smith", username: "jsmith", role: "member", active: true }));
    render(<LoginPage onLogin={onLogin} />);
    fireEvent.change(screen.getByLabelText("Username"), { target: { value: "jsmith" } });
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "a secure password" } });
    fireEvent.click(screen.getByRole("button", { name: /continue/i }));
    await waitFor(() => expect(onLogin).toHaveBeenCalledWith(expect.objectContaining({ username: "jsmith" })));
    expect(globalThis.fetch).toHaveBeenCalledWith("/auth/login", expect.objectContaining({ method: "POST" }));
  });
});

describe("document library", () => {
  test("renders authenticated document sets and their readiness", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const path = String(input);
      if (path === "/auth/me") return jsonResponse({ id: 1, name: "Jane Smith", username: "jsmith", role: "member", active: true });
      if (path === "/document-sets") return jsonResponse([{ id: 2, slug: "nda-pack", name: "NDA Pack", description: "Prepare an NDA", created_at: "2026-08-22", questionnaire_version: 3, current_template_count: 2 }]);
      return jsonResponse({}, 404);
    });
    render(<App />);
    expect(await screen.findByRole("heading", { name: "NDA Pack" })).toBeInTheDocument();
    expect(screen.getByText("Ready")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /^assemble$/i })).toHaveAttribute("href", "/sets/nda-pack/assemble");
  });
});

describe("questionnaire runner", () => {
  test("uses server evaluation to remove skipped questions", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
      const path = String(input);
      if (path.endsWith("/questionnaire")) {
        return jsonResponse({ version_id: 1, questions: [
          { variable_name: "urgent", question_text: "Is this urgent?", type: "yesno", options: [], examples: [], commentary: "", skip_if: "", section: "Matter" },
          { variable_name: "reason", question_text: "Why is it urgent?", type: "textarea", options: [], examples: [], commentary: "", skip_if: "urgent == false", section: "Matter" }
        ] });
      }
      if (path.endsWith("/questionnaire/evaluate")) {
        const body = JSON.parse(String(init?.body)) as { answers: { urgent?: boolean } };
        return jsonResponse(body.answers.urgent === false
          ? { visible: ["urgent"], hidden: ["reason"] }
          : { visible: ["urgent", "reason"], hidden: [] });
      }
      return jsonResponse({}, 404);
    });
    render(
      <MemoryRouter initialEntries={["/sets/nda-pack/assemble"]}>
        <Routes><Route path="/sets/:slug/assemble" element={<QuestionnairePage />} /></Routes>
      </MemoryRouter>
    );
    expect(await screen.findByText("Why is it urgent?")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "No" }));
    await waitFor(() => expect(screen.queryByText("Why is it urgent?")).not.toBeInTheDocument());
    expect(screen.getByText("100%")).toBeInTheDocument();
  });
});
