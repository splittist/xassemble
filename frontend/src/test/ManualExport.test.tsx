import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, expect, test, vi } from "vitest";

import { ManagePage } from "../pages/ManagePage";

afterEach(() => { cleanup(); vi.restoreAllMocks(); });

test("manual export reports conversion errors without leaving the management page", async () => {
  vi.spyOn(globalThis, "fetch").mockImplementation(input => {
    if (String(input).endsWith("/versions")) return Promise.resolve(new Response(JSON.stringify({
      questionnaires: [{ id: 1, version_no: 1, is_current: true, uploaded_at: "2026-09-17", uploaded_by: "editor" }],
      templates: [{ id: 2, label: "letter", version_no: 1, is_current: true, uploaded_at: "2026-09-17", uploaded_by: "editor" }]
    }), { status: 200 }));
    return Promise.resolve(new Response(JSON.stringify({ detail: "Unsupported manual-export tag: for" }), { status: 422 }));
  });
  render(<MemoryRouter initialEntries={["/sets/letters/manage"]}>
    <Routes><Route path="/sets/:slug/manage" element={<ManagePage />} /></Routes>
  </MemoryRouter>);
  fireEvent.click(await screen.findByRole("button", { name: "Manual template" }));
  expect(await screen.findByText("Unsupported manual-export tag: for")).toBeInTheDocument();
  await waitFor(() => expect(screen.getByRole("button", { name: "Manual template" })).toBeEnabled());
  expect(globalThis.fetch).toHaveBeenCalledWith(
    "/document-sets/letters/current/templates/letter/manual", expect.any(Object)
  );
});
