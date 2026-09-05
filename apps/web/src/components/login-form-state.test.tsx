// @vitest-environment jsdom

import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { I18nProvider } from "./i18n-provider";
import { LoginForm } from "./login-form";

const requestMagicLink = vi.fn().mockResolvedValue(undefined);
const replace = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace }),
  useSearchParams: () => new URLSearchParams("passwordReset=success"),
}));
vi.mock("./auth-provider", () => ({
  useAuth: () => ({
    login: vi.fn(),
    requestMagicLink,
    verifyEmailOtp: vi.fn(),
    signUp: vi.fn(),
    available: true,
  }),
}));

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("authentication state presentation", () => {
  it("consumes password-reset query state and never shows it with Magic Link sent", async () => {
    render(<I18nProvider><LoginForm /></I18nProvider>);
    expect(screen.getByText("Password updated.")).toBeTruthy();
    await waitFor(() => expect(replace).toHaveBeenCalledWith("/login"));
    await userEvent.type(screen.getByLabelText("Email address"), "customer@example.com");
    await userEvent.click(screen.getByRole("button", { name: "Email me a sign-in link" }));
    expect(await screen.findByRole("heading", { name: "Check your email" })).toBeTruthy();
    expect(screen.queryByText("Password updated.")).toBeNull();
  });

  it("supports use-another-email and a cooldown after sending", async () => {
    render(<I18nProvider><LoginForm /></I18nProvider>);
    await userEvent.type(screen.getByLabelText("Email address"), "customer@example.com");
    await userEvent.click(screen.getByRole("button", { name: "Email me a sign-in link" }));
    const resend = await screen.findByRole("button", { name: "Resend in 60s" });
    expect((resend as HTMLButtonElement).disabled).toBe(true);
    await userEvent.click(screen.getByRole("button", { name: "Use another email" }));
    expect(screen.getByRole("button", { name: "Email me a sign-in link" })).toBeTruthy();
    expect((screen.getByLabelText("Email address") as HTMLInputElement).value).toBe("");
  });
});
