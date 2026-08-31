// @vitest-environment jsdom

import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { AuthConfirmation } from "./auth-confirmation";
import { I18nProvider } from "./i18n-provider";

const replace = vi.fn();
const getSession = vi.fn();
const exchangeCodeForSession = vi.fn();

vi.mock("next/navigation", () => ({ useRouter: () => ({ replace }) }));
vi.mock("@/lib/supabase-client", () => ({
  getSupabaseBrowserClient: () => ({
    auth: { getSession, exchangeCodeForSession },
  }),
}));

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  window.history.replaceState({}, "", "/");
});

describe("magic-link confirmation", () => {
  it("accepts the existing implicit session and returns to a safe requested route", async () => {
    window.history.replaceState({}, "", "/auth/confirm?returnTo=%2Fbook%3Fservice%3D123#access_token=redacted");
    getSession.mockResolvedValue({ data: { session: { user: { id: "customer" } } }, error: null });
    render(<I18nProvider><AuthConfirmation /></I18nProvider>);
    await waitFor(() => expect(replace).toHaveBeenCalledWith("/book?service=123"));
    expect(await screen.findByRole("heading", { name: "Email confirmed." })).toBeTruthy();
    expect(document.body.textContent).not.toContain("redacted");
  });

  it("rejects an external return path and falls back to account", async () => {
    window.history.replaceState({}, "", "/auth/confirm?returnTo=https%3A%2F%2Fevil.example");
    getSession.mockResolvedValue({ data: { session: { user: { id: "customer" } } }, error: null });
    render(<I18nProvider><AuthConfirmation /></I18nProvider>);
    await waitFor(() => expect(replace).toHaveBeenCalledWith("/account"));
  });

  it("fails safely for an expired provider link", async () => {
    window.history.replaceState({}, "", "/auth/confirm?error=access_denied");
    render(<I18nProvider><AuthConfirmation /></I18nProvider>);
    expect(await screen.findByRole("heading", { name: "We couldn’t confirm that link." })).toBeTruthy();
    expect(replace).not.toHaveBeenCalled();
  });
});
