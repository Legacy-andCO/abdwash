// @vitest-environment jsdom

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { Session, SupabaseClient } from "@supabase/supabase-js";
import { AuthProvider } from "./auth-provider";
import { LoginForm } from "./login-form";
import { SiteHeader } from "./site-header";

const replace = vi.fn();
const profileResource = vi.hoisted(() => ({
  cachedCustomerProfile: vi.fn(),
  loadCustomerProfile: vi.fn(),
}));
vi.mock("@/lib/customer-profile-resource", () => profileResource);
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
    signInWithOtp: vi.fn().mockResolvedValue({ data: {}, error: null }),
    verifyOtp: vi.fn().mockResolvedValue({ data: { session: session() }, error: null }),
    signInWithPassword: vi.fn().mockResolvedValue({ data: { session: session(), user: session().user }, error: null }),
    signUp: vi.fn().mockResolvedValue({ data: { session: null, user: session().user }, error: null }),
    signOut: vi.fn().mockResolvedValue({ error: null }),
  };
  return { client: { auth } as unknown as SupabaseClient, auth };
}

beforeEach(() => {
  profileResource.cachedCustomerProfile.mockReturnValue(null);
  profileResource.loadCustomerProfile.mockResolvedValue({
    authenticated_email: "customer@example.com",
    profile: null,
    addresses: [],
    vehicles: [],
  });
});

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
    await user.click(screen.getByRole("button", { name: "Use password instead" }));
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
    await user.click(screen.getByRole("button", { name: "Use password instead" }));
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

  it("uses one passwordless flow for new and returning email addresses", async () => {
    const { client, auth } = authClient();
    render(<AuthProvider client={client}><LoginForm /></AuthProvider>);
    const user = userEvent.setup();
    await user.type(screen.getByLabelText("Email address"), "noor@example.com");
    expect(screen.queryByLabelText("Password")).toBeNull();
    await user.click(screen.getByRole("button", { name: "Email me a sign-in link" }));
    await waitFor(() => expect(auth.signInWithOtp).toHaveBeenCalledWith({
      email: "noor@example.com",
      options: {
        emailRedirectTo: "http://localhost:3000/auth/confirm?returnTo=%2Fbook",
      },
    }));
    expect(await screen.findByRole("heading", { name: "Check your email" })).toBeTruthy();
    expect(screen.getByText("We sent a sign-in email to:")).toBeTruthy();
    expect(screen.getByText("noor@example.com")).toBeTruthy();
    expect(screen.getByText("Open the email on this device and follow the sign-in link.")).toBeTruthy();
    expect(screen.getByText("Accessing your email from another device?")).toBeTruthy();
    expect(screen.getByText(/use the OTP code below to sign in on this device/i)).toBeTruthy();
    expect(screen.queryByText(/account exists/i)).toBeNull();
  });

  it("verifies a pasted six-digit code on the original device", async () => {
    const { client, auth } = authClient();
    render(<AuthProvider client={client}><LoginForm /></AuthProvider>);
    const user = userEvent.setup();
    await user.type(screen.getByLabelText("Email address"), "noor@example.com");
    await user.click(screen.getByRole("button", { name: "Email me a sign-in link" }));
    await screen.findByRole("heading", { name: "Check your email" });
    const code = screen.getByLabelText("6-digit code");
    await user.click(code);
    await user.paste(" 12a3456 ");
    expect((code as HTMLInputElement).value).toBe("123456");
    await user.clear(code);
    await user.paste("12-34-56");
    expect((code as HTMLInputElement).value).toBe("123456");
    await user.clear(code);
    await user.paste("123456789");
    expect((code as HTMLInputElement).value).toBe("123456");
    await user.click(screen.getByRole("button", { name: "Verify code" }));
    await waitFor(() => expect(auth.verifyOtp).toHaveBeenCalledWith({
      email: "noor@example.com",
      token: "123456",
      type: "email",
    }));
    expect(replace).toHaveBeenCalledWith("/book");
  });

  it("maps invalid and expired OTPs to safe customer messages", async () => {
    const { client, auth } = authClient();
    auth.verifyOtp
      .mockResolvedValueOnce({ data: { session: null }, error: { message: "Token is invalid" } })
      .mockResolvedValueOnce({ data: { session: null }, error: { message: "Token has expired" } });
    render(<AuthProvider client={client}><LoginForm /></AuthProvider>);
    const user = userEvent.setup();
    await user.type(screen.getByLabelText("Email address"), "noor@example.com");
    await user.click(screen.getByRole("button", { name: "Email me a sign-in link" }));
    await user.type(await screen.findByLabelText("6-digit code"), "123456");
    await user.click(screen.getByRole("button", { name: "Verify code" }));
    expect(await screen.findByText("The code is incorrect. Please try again.")).toBeTruthy();
    await user.click(screen.getByLabelText("6-digit code"));
    await user.click(screen.getByRole("button", { name: "Verify code" }));
    expect(await screen.findByText("This code has expired. Request a new one.")).toBeTruthy();
  });

  it("prefers the saved customer profile first name over auth metadata", async () => {
    profileResource.loadCustomerProfile.mockResolvedValue({
      authenticated_email: "customer@example.com",
      profile: { id: "profile", first_name: "Ahmad", surname: "Ali", email: "customer@example.com", phone: "+971501234567" },
      addresses: [],
      vehicles: [],
    });
    const { client } = authClient(session("Metadata Name"));
    render(<AuthProvider client={client}><SiteHeader /></AuthProvider>);
    expect(await screen.findByText("Hi, Ahmad")).toBeTruthy();
    expect(screen.queryByText("Hi, Metadata Name")).toBeNull();
  });

  it("uses a cached profile name immediately and falls back to Account without a name", async () => {
    profileResource.cachedCustomerProfile.mockReturnValue({
      authenticated_email: "customer@example.com",
      profile: { id: "profile", first_name: "Aisha", surname: "Ali", email: "customer@example.com", phone: "+971501234567" },
      addresses: [],
      vehicles: [],
    });
    const cachedClient = authClient(session("")).client;
    const view = render(<AuthProvider client={cachedClient}><SiteHeader /></AuthProvider>);
    expect(await screen.findByText("Hi, Aisha")).toBeTruthy();
    view.unmount();

    profileResource.cachedCustomerProfile.mockReturnValue(null);
    const fallbackClient = authClient(session("")).client;
    render(<AuthProvider client={fallbackClient}><SiteHeader /></AuthProvider>);
    expect(await screen.findByText("Account")).toBeTruthy();
  });

  it("keeps Magic Link primary while exposing password sign-up from password login", async () => {
    const { client, auth } = authClient();
    render(<AuthProvider client={client}><LoginForm /></AuthProvider>);
    expect(screen.getByRole("button", { name: "Email me a sign-in link" })).toBeTruthy();
    await userEvent.click(screen.getByRole("button", { name: "Use password instead" }));
    await userEvent.click(screen.getByRole("button", { name: "Sign up with password" }));
    await userEvent.type(screen.getByLabelText("Email address"), "new@example.com");
    await userEvent.type(screen.getByLabelText("Password"), "secure-password");
    await userEvent.type(screen.getByLabelText("Confirm password"), "secure-password");
    await userEvent.click(screen.getByRole("button", { name: "Sign up" }));
    await waitFor(() => expect(auth.signUp).toHaveBeenCalledWith({
      email: "new@example.com",
      password: "secure-password",
      options: {
        emailRedirectTo: "http://localhost:3000/auth/confirm?returnTo=%2Fbook",
      },
    }));
    expect(await screen.findByRole("heading", { name: "Confirm your email" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Use another email" })).toBeTruthy();
  });

  it("rejects an unsafe external return path", async () => {
    const { client, auth } = authClient();
    render(<AuthProvider client={client}><LoginForm /></AuthProvider>);
    await userEvent.type(screen.getByLabelText("Email address"), "safe@example.com");
    await userEvent.click(screen.getByRole("button", { name: "Email me a sign-in link" }));
    await waitFor(() => expect(auth.signInWithOtp).toHaveBeenCalled());
    expect(auth.signInWithOtp.mock.calls[0][0].options.emailRedirectTo).not.toContain("http%3A");
  });
});
