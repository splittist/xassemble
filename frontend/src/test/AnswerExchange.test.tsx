import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import { AnswerExchange } from "../components/AnswerExchange";
import type { Questionnaire } from "../types";

const questionnaire: Questionnaire = { version_id: 1, schema_sha256: "hash", questions: [
  { variable_name: "name", question_text: "Client name", type: "text", options: [], examples: [], commentary: "", skip_if: "", section: "" },
  { variable_name: "urgent", question_text: "Urgent?", type: "yesno", options: [], examples: [], commentary: "", skip_if: "", section: "" }
] };

afterEach(() => { cleanup(); vi.restoreAllMocks(); });

function mockImport(status = 200) {
  vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
    const evaluating = String(input).endsWith("/evaluate");
    if (evaluating) {
      const body = JSON.parse(String(init?.body));
      expect(body.questionnaire_version_id).toBe(1);
      expect(body.questionnaire_schema_sha256).toBe("hash");
    }
    return Promise.resolve(new Response(JSON.stringify(evaluating ? { visible: ["name", "urgent"], hidden: [] }
      : status === 200 ? { answers: { name: "Imported", urgent: false }, questionnaire_version_id: 1, questionnaire_schema_sha256: "hash" }
        : { detail: "urgent: expected a JSON boolean" }), { status: evaluating ? 200 : status }));
  });
}

function chooseFile() {
  fireEvent.change(screen.getByLabelText("Import answers (.json)"), {
    target: { files: [new File(['{}'], "answers.json", { type: "application/json" })] }
  });
}

test("fills gaps including false, preserves conflicts, and allows explicit replacement", async () => {
  mockImport(); const apply = vi.fn();
  render(<AnswerExchange slug="letters" questionnaire={questionnaire} answers={{ name: "Existing" }} onApply={apply} />);
  chooseFile();
  const button = await screen.findByRole("button", { name: "Apply selected answers" });
  await waitFor(() => expect(button).toBeEnabled());
  expect(screen.getByRole("checkbox", { name: /Client name/ })).not.toBeChecked();
  expect(screen.getByRole("checkbox", { name: /Urgent/ })).toBeChecked();
  fireEvent.click(button);
  expect(apply).toHaveBeenCalledWith({ name: "Existing", urgent: false }, ["urgent"]);
  chooseFile();
  fireEvent.click(await screen.findByRole("checkbox", { name: /Client name/ }));
  await waitFor(() => expect(screen.getByRole("button", { name: "Apply selected answers" })).toBeEnabled());
  fireEvent.click(screen.getByRole("button", { name: "Apply selected answers" }));
  expect(apply).toHaveBeenLastCalledWith({ name: "Imported", urgent: false }, expect.arrayContaining(["name", "urgent"]));
});

test("cancel and invalid files never mutate the draft", async () => {
  mockImport(); const apply = vi.fn();
  render(<AnswerExchange slug="letters" questionnaire={questionnaire} answers={{ name: "Existing" }} onApply={apply} />);
  chooseFile();
  fireEvent.click(await screen.findByRole("button", { name: "Cancel import" }));
  expect(apply).not.toHaveBeenCalled();
  mockImport(422); chooseFile();
  expect(await screen.findByRole("alert")).toHaveTextContent("urgent: expected a JSON boolean");
  expect(screen.queryByRole("button", { name: "Apply selected answers" })).not.toBeInTheDocument();
  expect(apply).not.toHaveBeenCalled();
});

test("editing the draft resets prior import selections", async () => {
  mockImport(); const apply = vi.fn();
  const view = render(<AnswerExchange slug="letters" questionnaire={questionnaire} answers={{}} onApply={apply} />);
  chooseFile();
  await waitFor(() => expect(screen.getByRole("button", { name: "Apply selected answers" })).toBeEnabled());
  view.rerender(<AnswerExchange slug="letters" questionnaire={questionnaire} answers={{ name: "New manual answer" }} onApply={apply} />);
  expect(screen.getByRole("checkbox", { name: /Client name/ })).not.toBeChecked();
  expect(screen.getByRole("button", { name: "Apply selected answers" })).toBeDisabled();
});
