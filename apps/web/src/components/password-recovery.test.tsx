// @vitest-environment jsdom

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { AuthChangeEvent, Session, SupabaseClient } from "@supabase/supabase-js";
import { AuthProvider } from "./auth-provider";
import { ForgotPasswordForm } from "./forgot-password-form";
import { LoginForm } from "./login-form";
import { ResetPasswordForm } from "./reset-password-form";

const replace = vi.fn();
vi.mock("next/navigation", () => ({
  usePathname: () => "/login",
  useRouter: () => ({ replace }),
  useSearchParams: () => new URLSearchParams(),
}));

function recoverySession() {
  return {
    access_token: "recovery-access-token",
    token_type: "bearer",
    expires_in: 3600,
    expires_at: 4_000_000_000,
    refresh_token: "recovery-refresh-token",
    user: { id: "customer", app_metadata: {}, user_metadata: {}, aud: "authenticated", created_at: "2026-01-01" },
  } as Session;
}

function authClient(initialSession: Session | null = null) {
  let listener: ((event: AuthChangeEvent, session: Session | null) => void) | null = null;
  const auth = {
    getSession: vi.fn().mockResolvedValue({ data: { session: initialSession }, error: null }),
    onAuthStateChange: vi.fn().mockImplementation((callback) => {
      listener = callback;
      return { data: { subscription: { unsubscribe: vi.fn() } } };
    }),
    signInWithPassword: vi.fn(),
    signUp: vi.fn(),
    resetPasswordForEmail: vi.fn().mockResolvedValue({ data: {}, error: null }),
    updateUser: vi.fn().mockResolvedValue({ data: { user: initialSession?.user }, error: null }),
    signOut: vi.fn().mockResolvedValue({ error: null }),
  };
  return {
    client: { auth } as unknown as SupabaseClient,
    auth,
    emit: (event: AuthChangeEvent, session: Session | null) => listener?.(event, session),
  };
}

beforeEach(() => {
  window.history.replaceState({}, "", "/login");
  window.sessionStorage.clear();
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("customer password recovery", () => {
  it("shows the Forgot password link only in login mode", async () => {
    const { client } = authClient();
    render(<AuthProvider client={client}><LoginForm /></AuthProvider>);
    const link = screen.getByRole("link", { name: "Forgot password?" });
    expect(link.getAttribute("href")).toBe("/forgot-password");
    await userEvent.click(screen.getByRole("button", { name: /create account/i }));
    expect(screen.queryByRole("link", { name: "Forgot password?" })).toBeNull();
  });

  it("validates email before requesting a reset", async () => {
    const { client, auth } = authClient();
    render(<AuthProvider client={client}><ForgotPasswordForm /></AuthProvider>);
    await userEvent.type(screen.getByLabelText("Email address"), "not-an-email");
    await userEvent.click(screen.getByRole("button", { name: "Send reset link" }));
    expect((await screen.findByRole("alert")).textContent).toContain("Enter a valid email address.");
    expect(auth.resetPasswordForEmail).not.toHaveBeenCalled();
  });

  it("uses the trusted reset redirect, blocks double-submit, and shows generic success", async () => {
    const { client, auth } = authClient();
    let complete: ((value: { data: object; error: null }) => void) | undefined;
    auth.resetPasswordForEmail.mockReturnValue(new Promise((resolve) => { complete = resolve; }));
    render(<AuthProvider client={client}><ForgotPasswordForm /></AuthProvider>);
    const user = userEvent.setup();
    await user.type(screen.getByLabelText("Email address"), "customer@example.com");
    await user.click(screen.getByRole("button", { name: "Send reset link" }));
    expect((screen.getByRole("button", { name: /Sending reset link/ }) as HTMLButtonElement).disabled).toBe(true);
    await user.click(screen.getByRole("button", { name: /Sending reset link/ }));
    expect(auth.resetPasswordForEmail).toHaveBeenCalledOnce();
    expect(auth.resetPasswordForEmail).toHaveBeenCalledWith("customer@example.com", {
      redirectTo: "http://localhost:3000/auth/reset-password",
    });
    complete?.({ data: {}, error: null });
    expect(await screen.findByText(/If an account exists for this email address/)).toBeTruthy();
    expect(screen.queryByText(/user not found/i)).toBeNull();
  });

  it("shows a safe recoverable provider error", async () => {
    const { client, auth } = authClient();
    auth.resetPasswordForEmail.mockResolvedValue({ data: null, error: { message: "SMTP provider detail" } });
    render(<AuthProvider client={client}><ForgotPasswordForm /></AuthProvider>);
    await userEvent.type(screen.getByLabelText("Email address"), "customer@example.com");
    await userEvent.click(screen.getByRole("button", { name: "Send reset link" }));
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toContain("We couldn’t send the reset link right now");
    expect(alert.textContent).not.toContain("SMTP provider detail");
  });

  it("accepts the PASSWORD_RECOVERY event and updates the password", async () => {
    const { client, auth, emit } = authClient();
    render(<AuthProvider client={client}><ResetPasswordForm /></AuthProvider>);
    await waitFor(() => expect(auth.getSession).toHaveBeenCalledOnce());
    emit("PASSWORD_RECOVERY", recoverySession());
    expect(await screen.findByRole("heading", { name: "Create a new password" })).toBeTruthy();
    const user = userEvent.setup();
    await user.type(screen.getByLabelText("New password"), "new-secure-password");
    await user.type(screen.getByLabelText("Confirm new password"), "new-secure-password");
    await user.click(screen.getByRole("button", { name: "Update password" }));
    await waitFor(() => expect(auth.updateUser).toHaveBeenCalledWith({ password: "new-secure-password" }));
    expect(auth.signOut).toHaveBeenCalledWith({ scope: "local" });
    expect(replace).toHaveBeenCalledWith("/login?passwordReset=success");
    expect(document.body.textContent).not.toContain("recovery-access-token");
  });

  it("enforces the signup-length policy and matching confirmation", async () => {
    window.history.replaceState({}, "", "/auth/reset-password#type=recovery");
    const { client, auth } = authClient(recoverySession());
    render(<AuthProvider client={client}><ResetPasswordForm /></AuthProvider>);
    const user = userEvent.setup();
    await user.type(await screen.findByLabelText("New password"), "short");
    await user.type(screen.getByLabelText("Confirm new password"), "short");
    await user.click(screen.getByRole("button", { name: "Update password" }));
    expect((await screen.findByRole("alert")).textContent).toContain("at least 6 characters");
    await user.clear(screen.getByLabelText("New password"));
    await user.clear(screen.getByLabelText("Confirm new password"));
    await user.type(screen.getByLabelText("New password"), "password-one");
    await user.type(screen.getByLabelText("Confirm new password"), "password-two");
    await user.click(screen.getByRole("button", { name: "Update password" }));
    expect((await screen.findByRole("alert")).textContent).toContain("Passwords do not match");
    expect(auth.updateUser).not.toHaveBeenCalled();
  });

  it("fails safely when the recovery session is missing", async () => {
    const { client } = authClient();
    render(<AuthProvider client={client}><ResetPasswordForm /></AuthProvider>);
    expect(await screen.findByText("This reset link is invalid or has expired.")).toBeTruthy();
    expect(screen.getByRole("link", { name: "Request a new reset link" }).getAttribute("href")).toBe("/forgot-password");
  });
});
