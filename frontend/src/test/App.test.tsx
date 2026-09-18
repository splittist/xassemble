import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, test, vi } from "vitest";

import App from "../App";
import { LoginPage } from "../pages/LoginPage";
import { QuestionnairePage } from "../pages/QuestionnairePage";
import type { Question } from "../types";

function jsonResponse(value: unknown, status = 200) {
  return Promise.resolve(new Response(JSON.stringify(value), { status, headers: { "Content-Type": "application/json" } }));
}

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

function renderQuestionnaire(questions: Question[]) {
  const fetch = vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
    const path = String(input);
    if (path.endsWith("/questionnaire")) return jsonResponse({ version_id: 1, schema_sha256: "hash", questions });
    if (path.endsWith("/evaluate")) return jsonResponse({ visible: questions.map(q => q.variable_name), hidden: [] });
    if (path.endsWith("/answer-import")) return jsonResponse({ questionnaire_version_id: 1, questionnaire_schema_sha256: "hash", answers: { name: "Imported name" } });
    return jsonResponse({ detail: "Test generation response" }, 422);
  });
  render(<MemoryRouter initialEntries={["/sets/letters/assemble"]}>
    <Routes><Route path="/sets/:slug/assemble" element={<QuestionnairePage />} /></Routes>
  </MemoryRouter>);
  return fetch;
}

function question(variable_name: string, type: Question["type"], extra: Partial<Question> = {}): Question {
  return { variable_name, question_text: variable_name, type, options: [], examples: [], commentary: "", skip_if: "", section: "", ...extra };
}

test("example buttons offer only values compatible with the question type", async () => {
  const fetch = renderQuestionnaire([
    question("urgent", "yesno", { examples: ["true", "false"] }),
    question("kind", "choice", { options: ["A", "B"], examples: ["A", "Invalid choice"] }),
    question("name", "text", { examples: ["Example name"] }),
  ]);
  await screen.findByRole("button", { name: "Use example: “A”" });
  expect(screen.queryByRole("button", { name: /Use example: “(?:true|false|Invalid choice)”/ })).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Use example: “A”" }));
  fireEvent.click(screen.getByRole("button", { name: "Use example: “Example name”" }));
  fireEvent.click(screen.getByRole("button", { name: "No" }));
  await waitFor(() => expect(screen.getByRole("button", { name: "Generate documents" })).toBeEnabled());
  const evaluations = fetch.mock.calls.filter(([path]) => String(path).endsWith("/evaluate"));
  expect(JSON.parse(String(evaluations.at(-1)?.[1]?.body)).answers).toEqual({ urgent: false, kind: "A", name: "Example name" });
});

test("incomplete generation requires acknowledgement and edits and imports reset it", async () => {
  const fetch = renderQuestionnaire([question("name", "text"), question("reason", "textarea")]);
  const generate = await screen.findByRole("button", { name: "Generate documents" });
  const acknowledgement = screen.getByRole("checkbox", { name: /Generate an incomplete first draft/ });
  fireEvent.change(screen.getByLabelText("Project code"), { target: { value: "TEST" } });
  expect(generate).toBeDisabled();
  fireEvent.click(generate);
  expect(fetch.mock.calls.some(([path]) => String(path).endsWith("/generate"))).toBe(false);
  fireEvent.click(acknowledgement);
  await waitFor(() => expect(generate).toBeEnabled());
  fireEvent.click(generate);
  await screen.findByText("Test generation response");
  const generation = fetch.mock.calls.find(([path]) => String(path).endsWith("/generate"));
  expect(JSON.parse(String(generation?.[1]?.body))).toEqual({ answers: {}, project_code: "TEST", questionnaire_version_id: 1, questionnaire_schema_sha256: "hash", acknowledge_incomplete: true });

  fireEvent.change(screen.getByRole("textbox", { name: "reason" }), { target: { value: "Manual reason" } });
  expect(acknowledgement).not.toBeChecked();
  expect(generate).toBeDisabled();
  fireEvent.change(screen.getByRole("textbox", { name: "reason" }), { target: { value: "" } });
  fireEvent.click(acknowledgement);
  await waitFor(() => expect(generate).toBeEnabled());
  fireEvent.change(screen.getByLabelText("Import answers (.json)"), { target: { files: [new File(['{}'], "answers.json", { type: "application/json" })] } });
  const apply = await screen.findByRole("button", { name: "Apply selected answers" });
  await waitFor(() => expect(apply).toBeEnabled());
  fireEvent.click(apply);
  expect(screen.getByRole("textbox", { name: "name" })).toHaveValue("Imported name");
  expect(acknowledgement).not.toBeChecked();
  expect(generate).toBeDisabled();
});

describe("authentication", () => {
  test("shows the login screen when there is no session", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() => jsonResponse({ detail: "Authentication required" }, 401));
    render(<App />);
    expect(await screen.findByRole("heading", { name: "Sign in to xassemble" })).toBeInTheDocument();
  });

  test("submits credentials and hands back the user", async () => {
    const onLogin = vi.fn();
    vi.spyOn(globalThis, "fetch").mockImplementation(() => jsonResponse({ id: 1, name: "Jane Smith", username: "jsmith", role: "member", active: true, must_change_password: false }));
    render(<LoginPage onLogin={onLogin} />);
    fireEvent.change(screen.getByLabelText("Username"), { target: { value: "jsmith" } });
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "a secure password" } });
    fireEvent.click(screen.getByRole("button", { name: /continue/i }));
    await waitFor(() => expect(onLogin).toHaveBeenCalledWith(expect.objectContaining({ username: "jsmith" })));
    expect(globalThis.fetch).toHaveBeenCalledWith("/auth/login", expect.objectContaining({ method: "POST" }));
  });

  test("requires a temporary password to be changed before opening the app", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
      const path = String(input);
      if (path === "/auth/me") return jsonResponse({ id: 1, name: "Jane Smith", username: "jsmith", role: "member", active: true, must_change_password: true });
      if (path === "/auth/change-password" && init?.method === "POST") return jsonResponse({ id: 1, name: "Jane Smith", username: "jsmith", role: "member", active: true, must_change_password: false });
      if (path === "/document-sets") return jsonResponse([]);
      return jsonResponse({}, 404);
    });
    render(<App />);
    expect(await screen.findByRole("heading", { name: "Choose a new password" })).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Current password"), { target: { value: "temporary password" } });
    fireEvent.change(screen.getByLabelText("New password"), { target: { value: "a different secure password" } });
    fireEvent.change(screen.getByLabelText("Confirm new password"), { target: { value: "a different secure password" } });
    fireEvent.click(screen.getByRole("button", { name: /change password/i }));
    expect(await screen.findByRole("heading", { name: "Create your first document set" })).toBeInTheDocument();
  });

  test("shows user administration only to administrators", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const path = String(input);
      if (path === "/auth/me") return jsonResponse({ id: 1, name: "Admin", username: "admin", role: "admin", active: true, must_change_password: false });
      if (path === "/document-sets") return jsonResponse([]);
      return jsonResponse({}, 404);
    });
    render(<App />);
    expect(await screen.findByRole("link", { name: "Users" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Change password" })).toBeInTheDocument();
  });
});

describe("document library", () => {
  test("renders authenticated document sets and their readiness", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const path = String(input);
      if (path === "/auth/me") return jsonResponse({ id: 1, name: "Jane Smith", username: "jsmith", role: "member", active: true, must_change_password: false });
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
        return jsonResponse({ version_id: 1, schema_sha256: "hash", questions: [
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

test("late evaluation responses cannot restore questions hidden by newer answers", async () => {
  let finishOld: ((response: Response) => void) | undefined;
  vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
    if (String(input).endsWith("/questionnaire")) return jsonResponse({ version_id: 1, schema_sha256: "hash", questions: [
      { variable_name: "urgent", question_text: "Urgent?", type: "yesno", options: [], examples: [], commentary: "", skip_if: "", section: "" },
      { variable_name: "reason", question_text: "Reason?", type: "text", options: [], examples: [], commentary: "", skip_if: "urgent == false", section: "" }
    ] });
    const body = JSON.parse(String(init?.body));
    if (body.answers.urgent === false) return jsonResponse({ visible: ["urgent"], hidden: ["reason"] });
    return new Promise<Response>(resolve => { finishOld = resolve; });
  });
  render(<MemoryRouter initialEntries={["/sets/letters/assemble"]}>
    <Routes><Route path="/sets/:slug/assemble" element={<QuestionnairePage />} /></Routes>
  </MemoryRouter>);
  await screen.findByText("Reason?");
  await waitFor(() => expect(finishOld).toBeDefined());
  fireEvent.click(screen.getByRole("button", { name: "No" }));
  await waitFor(() => expect(screen.queryByText("Reason?")).not.toBeInTheDocument());
  await act(async () => { finishOld!(new Response(JSON.stringify({ visible: ["urgent", "reason"], hidden: [] }))); });
  expect(screen.queryByText("Reason?")).not.toBeInTheDocument();
  expect(screen.getByText("100%")).toBeInTheDocument();
});
