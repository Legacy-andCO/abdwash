// @vitest-environment jsdom

import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { Session, SupabaseClient } from "@supabase/supabase-js";
import { AuthProvider } from "./auth-provider";
import { AuthenticatedPasswordChange } from "./authenticated-password-change";

vi.mock("next/navigation", () => ({
  usePathname: () => "/account/profile",
  useRouter: () => ({ replace: vi.fn() }),
}));

function session(kind: "customer" | "manager" = "customer") {
  return {
    access_token: `${kind}-access-token`,
    token_type: "bearer",
    expires_in: 3600,
    expires_at: 4_000_000_000,
    refresh_token: `${kind}-refresh-token`,
    user: {
      id: kind,
      email: `${kind}@example.com`,
      app_metadata:
        kind === "manager"
          ? { account_type: "staff", staff_role: "manager" }
          : {},
      user_metadata: {},
      aud: "authenticated",
      created_at: "2026-01-01",
    },
  } as Session;
}

function authClient(initialSession: Session | null) {
  const auth = {
    getSession: vi.fn().mockResolvedValue({
      data: { session: initialSession },
      error: null,
    }),
    onAuthStateChange: vi.fn().mockReturnValue({
      data: { subscription: { unsubscribe: vi.fn() } },
    }),
    updateUser: vi.fn().mockResolvedValue({
      data: { user: initialSession?.user ?? null },
      error: null,
    }),
    reauthenticate: vi.fn().mockResolvedValue({ data: {}, error: null }),
  };
  return { client: { auth } as unknown as SupabaseClient, auth };
}

function renderChangePassword(initialSession: Session | null) {
  const auth = authClient(initialSession);
  render(
    <AuthProvider client={auth.client}>
      <AuthenticatedPasswordChange />
    </AuthProvider>,
  );
  return auth;
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("authenticated password change", () => {
  it("is available to authenticated customers and hidden from visitors", async () => {
    const customer = renderChangePassword(session());
    expect(
      await screen.findByRole("button", { name: "Change password" }),
    ).toBeTruthy();
    expect(customer.auth.getSession).toHaveBeenCalledOnce();
    cleanup();

    renderChangePassword(null);
    await waitFor(() => expect(screen.queryByText("Security")).toBeNull());
    expect(
      screen.queryByRole("button", { name: "Change password" }),
    ).toBeNull();
  });

  it("uses the same Supabase flow for the manager account", async () => {
    const { auth } = renderChangePassword(session("manager"));
    const user = userEvent.setup();
    await user.click(
      await screen.findByRole("button", { name: "Change password" }),
    );
    await user.type(screen.getByLabelText("New password"), "Manager-New-Password!1");
    await user.type(
      screen.getByLabelText("Confirm new password"),
      "Manager-New-Password!1",
    );
    await user.click(screen.getByRole("button", { name: "Update password" }));

    await waitFor(() =>
      expect(auth.updateUser).toHaveBeenCalledWith({
        password: "Manager-New-Password!1",
      }),
    );
    expect(await screen.findByText("Password updated successfully.")).toBeTruthy();
  });

  it("blocks empty and mismatched passwords before calling Supabase", async () => {
    const { auth } = renderChangePassword(session());
    const user = userEvent.setup();
    await user.click(
      await screen.findByRole("button", { name: "Change password" }),
    );
    await user.click(screen.getByRole("button", { name: "Update password" }));
    expect((await screen.findByRole("alert")).textContent).toContain(
      "Enter and confirm your new password",
    );

    await user.type(screen.getByLabelText("New password"), "Password-One!1");
    await user.type(screen.getByLabelText("Confirm new password"), "Password-Two!2");
    await user.click(screen.getByRole("button", { name: "Update password" }));
    expect((await screen.findByRole("alert")).textContent).toContain(
      "Passwords do not match",
    );
    expect(auth.updateUser).not.toHaveBeenCalled();
  });

  it("shows a safe error when Supabase rejects the password", async () => {
    const { auth } = renderChangePassword(session());
    auth.updateUser.mockResolvedValue({
      data: { user: null },
      error: { code: "unexpected_failure", message: "provider stack detail" },
    });
    const user = userEvent.setup();
    await user.click(
      await screen.findByRole("button", { name: "Change password" }),
    );
    await user.type(screen.getByLabelText("New password"), "Customer-New-Password!1");
    await user.type(
      screen.getByLabelText("Confirm new password"),
      "Customer-New-Password!1",
    );
    await user.click(screen.getByRole("button", { name: "Update password" }));

    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toContain("We couldn’t update your password");
    expect(alert.textContent).not.toContain("provider stack detail");
  });

  it("uses Supabase nonce reauthentication when an older session requires it", async () => {
    const { auth } = renderChangePassword(session());
    auth.updateUser
      .mockResolvedValueOnce({
        data: { user: null },
        error: {
          code: "reauthentication_needed",
          message: "Reauthentication needed",
        },
      })
      .mockResolvedValueOnce({ data: { user: session().user }, error: null });
    const user = userEvent.setup();
    await user.click(
      await screen.findByRole("button", { name: "Change password" }),
    );
    await user.type(screen.getByLabelText("New password"), "Customer-New-Password!1");
    await user.type(
      screen.getByLabelText("Confirm new password"),
      "Customer-New-Password!1",
    );
    await user.click(screen.getByRole("button", { name: "Update password" }));

    expect(auth.reauthenticate).toHaveBeenCalledOnce();
    await user.type(await screen.findByLabelText(/^Verification code/), "123456");
    await user.click(screen.getByRole("button", { name: "Update password" }));
    await waitFor(() =>
      expect(auth.updateUser).toHaveBeenLastCalledWith({
        password: "Customer-New-Password!1",
        nonce: "123456",
      }),
    );
  });
});
