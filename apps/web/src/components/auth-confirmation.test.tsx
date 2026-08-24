// @vitest-environment jsdom

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { getSupabaseBrowserClient } from "@/lib/supabase-client";
import { AuthConfirmation } from "./auth-confirmation";

vi.mock("@/lib/supabase-client", () => ({ getSupabaseBrowserClient: vi.fn() }));

afterEach(() => {
  cleanup();
  window.history.replaceState({}, "", "/auth/confirm");
  vi.clearAllMocks();
});

describe("AuthConfirmation", () => {
  it("exchanges the Supabase confirmation code and shows success", async () => {
    const exchangeCodeForSession = vi.fn().mockResolvedValue({ error: null });
    vi.mocked(getSupabaseBrowserClient).mockReturnValue({ auth: { exchangeCodeForSession } } as never);
    window.history.replaceState({}, "", "/auth/confirm?code=confirmation-code");
    render(<AuthConfirmation />);
    expect(await screen.findByText("Email confirmed.")).toBeTruthy();
    expect(exchangeCodeForSession).toHaveBeenCalledWith("confirmation-code");
  });

  it("shows a stable failure state for an expired confirmation link", async () => {
    vi.mocked(getSupabaseBrowserClient).mockReturnValue({ auth: {} } as never);
    window.history.replaceState({}, "", "/auth/confirm?error=access_denied");
    render(<AuthConfirmation />);
    expect(await screen.findByText("We couldn’t confirm that link.")).toBeTruthy();
  });
});
