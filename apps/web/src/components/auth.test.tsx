// @vitest-environment jsdom

import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { Session, SupabaseClient } from "@supabase/supabase-js";
import { AuthProvider } from "./auth-provider";
import { LoginForm } from "./login-form";
import { SiteHeader } from "./site-header";

const replace = vi.fn();
vi.mock("next/navigation", () => ({
  usePathname: () => "/book",
  useRouter: () => ({ replace }),
  useSearchParams: () => new URLSearchParams("returnTo=%2Fbook"),
}));

function session(firstName = "Ahmad") {
  return {
    access_token: "access-token",
    token_type: "bearer",
    expires_in: 3600,
    expires_at: 4_000_000_000,
    refresh_token: "refresh-token",
    user: { id: "customer", app_metadata: {}, user_metadata: { first_name: firstName }, aud: "authenticated", created_at: "2026-01-01" },
  } as Session;
}

function authClient(initialSession: Session | null = null) {
  const auth = {
    getSession: vi.fn().mockResolvedValue({ data: { session: initialSession }, error: null }),
    onAuthStateChange: vi.fn().mockReturnValue({ data: { subscription: { unsubscribe: vi.fn() } } }),
    signInWithPassword: vi.fn().mockResolvedValue({ data: { session: session(), user: session().user }, error: null }),
    signUp: vi.fn().mockResolvedValue({ data: { session: null, user: session().user }, error: null }),
    signOut: vi.fn().mockResolvedValue({ error: null }),
  };
  return { client: { auth } as unknown as SupabaseClient, auth };
}

afterEach(() => { cleanup(); vi.clearAllMocks(); });

describe("customer authentication", () => {
  it("shows Log in in the logged-out header", async () => {
    const { client } = authClient();
    render(<AuthProvider client={client}><SiteHeader /></AuthProvider>);
    expect((await screen.findByRole("link", { name: "Log in" })).getAttribute("href")).toBe("/login?returnTo=%2Fbook");
  });

  it("restores an existing Supabase session after mount", async () => {
    const { client, auth } = authClient(session("Aisha"));
    render(<AuthProvider client={client}><SiteHeader /></AuthProvider>);
    expect(await screen.findByText("Hi, Aisha")).toBeTruthy();
    expect(auth.getSession).toHaveBeenCalledOnce();
  });

  it("submits login through Supabase and returns to the originating page", async () => {
    const { client, auth } = authClient();
    render(<AuthProvider client={client}><LoginForm /></AuthProvider>);
    const user = userEvent.setup();
    await user.type(screen.getByLabelText("Email address"), "ahmad@example.com");
    await user.type(screen.getByLabelText("Password"), "correct-password");
    await user.click(screen.getByRole("button", { name: "Log in" }));
    await waitFor(() => expect(auth.signInWithPassword).toHaveBeenCalledWith({ email: "ahmad@example.com", password: "correct-password" }));
    expect(replace).toHaveBeenCalledWith("/book");
  });

  it("shows a useful invalid-credentials error", async () => {
    const { client, auth } = authClient();
    auth.signInWithPassword.mockResolvedValue({ data: { session: null, user: null }, error: { message: "Invalid login credentials" } });
    render(<AuthProvider client={client}><LoginForm /></AuthProvider>);
    const user = userEvent.setup();
    await user.type(screen.getByLabelText("Email address"), "bad@example.com");
    await user.type(screen.getByLabelText("Password"), "wrong-password");
    await user.click(screen.getByRole("button", { name: "Log in" }));
    expect((await screen.findByRole("alert")).textContent?.toLowerCase()).toContain("email or password is incorrect");
  });

  it("logs out locally and updates the header immediately", async () => {
    const { client, auth } = authClient(session());
    render(<AuthProvider client={client}><SiteHeader /></AuthProvider>);
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "Log out" }));
    await waitFor(() => expect(screen.getByRole("link", { name: "Log in" })).toBeTruthy());
    expect(auth.signOut).toHaveBeenCalledWith({ scope: "local" });
  });

  it("sends safe name metadata and handles email-confirmation sign-up", async () => {
    const { client, auth } = authClient();
    render(<AuthProvider client={client}><LoginForm /></AuthProvider>);
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: /create account/i }));
    await user.type(screen.getByLabelText("First name"), "Noor");
    await user.type(screen.getByLabelText("Surname"), "Ali");
    await user.type(screen.getByLabelText("Email address"), "noor@example.com");
    await user.type(screen.getByLabelText("Password"), "strong-password");
    await user.type(screen.getByLabelText("Confirm password"), "strong-password");
    await user.click(screen.getByRole("button", { name: "Create account" }));
    await waitFor(() => expect(auth.signUp).toHaveBeenCalledWith({ email: "noor@example.com", password: "strong-password", options: { data: { first_name: "Noor", surname: "Ali" } } }));
    expect(await screen.findByText(/check your email/i)).toBeTruthy();
  });
});
