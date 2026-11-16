// @vitest-environment jsdom
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import React, { StrictMode } from "react";
const mfa = vi.hoisted(() => ({ listFactors: vi.fn(), enroll: vi.fn(), unenroll: vi.fn(), challengeAndVerify: vi.fn(), getAuthenticatorAssuranceLevel: vi.fn() }));
vi.mock("../lib", () => ({ supabase: { auth: { mfa, signOut: vi.fn() } } }));
vi.mock("react-native", () => ({
  Platform: { OS: "web", select: (s: any) => s.default }, StyleSheet: { create: (s: any) => s },
  KeyboardAvoidingView: ({ children }: any) => <div>{children}</div>,
  ScrollView: ({ children }: any) => <div>{children}</div>, View: ({ children }: any) => <div>{children}</div>,
  Text: ({ children, accessibilityRole }: any) => <span role={accessibilityRole}>{children}</span>,
  TextInput: ({ onChangeText, accessibilityLabel, value, onSubmitEditing, inputMode, autoComplete }: any) => <input aria-label={accessibilityLabel} value={value} inputMode={inputMode} autoComplete={autoComplete} onChange={e => onChangeText(e.target.value)} onKeyDown={e => { if (e.key === "Enter") onSubmitEditing(); }} />,
}));
vi.mock("react-native-safe-area-context", () => ({ SafeAreaView: ({ children }: any) => <div>{children}</div> }));
vi.mock("react-native-svg", () => ({ SvgXml: ({ xml }: any) => <div data-testid="qr">{xml}</div> }));
vi.mock("./ui", () => ({ uiStyles: { error: {} }, AppButton: ({ title, onPress, disabled }: any) => <button disabled={disabled} onClick={onPress}>{title}</button> }));
import { PrivilegedMfa } from "./PrivilegedMfa";
const verified = { id: "existing", status: "verified", factor_type: "totp" };
const pending = { id: "unfinished", status: "unverified", factor_type: "totp" };
function mount(done = vi.fn(), strict = false) {
  const ui = <PrivilegedMfa userId="synthetic-user" onVerified={done} />;
  return render(strict ? <StrictMode>{ui}</StrictMode> : ui);
}
function enter(value: string) { fireEvent.change(screen.getByLabelText("Authenticator code"), { target: { value } }); }
beforeEach(() => {
  mfa.listFactors.mockResolvedValue({ data: { totp: [verified], all: [verified] } });
  mfa.enroll.mockResolvedValue({ data: { id: "new-factor", totp: { qr_code: "data:image/svg+xml,%3Csvg%3Etest%3C%2Fsvg%3E" } } });
  mfa.unenroll.mockResolvedValue({});
  mfa.challengeAndVerify.mockResolvedValue({ data: {} });
  mfa.getAuthenticatorAssuranceLevel.mockResolvedValue({ data: { currentLevel: "aal2" } });
});
afterEach(() => { cleanup(); vi.resetAllMocks(); });
it("enrolls once under Strict Mode and waits for provider verification and AAL2", async () => {
  mfa.listFactors.mockResolvedValue({ data: { totp: [], all: [] } });
  const done = vi.fn(); mount(done, true);
  await screen.findByTestId("qr"); expect(mfa.enroll).toHaveBeenCalledOnce();
  expect(screen.getByText("Complete setup").hasAttribute("disabled")).toBe(true);
  enter("123456"); fireEvent.click(screen.getByText("Complete setup"));
  await waitFor(() => expect(done).toHaveBeenCalledOnce());
  expect(mfa.challengeAndVerify).toHaveBeenCalledWith({ factorId: "new-factor", code: "123456" });
});
it("reuses the same verified factor after signing in again, without QR or enrollment", async () => {
  let view = mount(); await screen.findByText(/existing Trifecta/); view.unmount();
  const done = vi.fn(); mount(done); await screen.findByText(/existing Trifecta/);
  expect(screen.queryByTestId("qr")).toBeNull(); expect(mfa.enroll).not.toHaveBeenCalled(); expect(mfa.unenroll).not.toHaveBeenCalled();
  enter("654321"); fireEvent.keyDown(screen.getByLabelText("Authenticator code"), { key: "Enter" });
  await waitFor(() => expect(done).toHaveBeenCalledOnce());
  expect(mfa.challengeAndVerify).toHaveBeenCalledWith({ factorId: "existing", code: "654321" });
});
it.each(["invalid", "expired"])("rejects a provider %s code and allows another attempt", async reason => {
  mfa.challengeAndVerify.mockResolvedValueOnce({ error: new Error(reason) });
  const done = vi.fn(); mount(done); await screen.findByText(/existing Trifecta/);
  enter("123456"); fireEvent.click(screen.getByText("Verify code"));
  await screen.findByRole("alert"); expect(done).not.toHaveBeenCalled(); expect((screen.getByLabelText("Authenticator code") as HTMLInputElement).value).toBe("");
  enter("654321"); fireEvent.click(screen.getByText("Verify code")); await waitFor(() => expect(done).toHaveBeenCalledOnce());
});
it("keeps the gate closed if verification does not promote assurance", async () => {
  mfa.getAuthenticatorAssuranceLevel.mockResolvedValue({ data: { currentLevel: "aal1" } });
  const done = vi.fn(); mount(done); await screen.findByText(/existing Trifecta/);
  enter("123456"); fireEvent.click(screen.getByText("Verify code")); await screen.findByRole("alert"); expect(done).not.toHaveBeenCalled();
});
it("resumes incomplete enrollment and restarts only on explicit request", async () => {
  mfa.listFactors.mockResolvedValue({ data: { totp: [], all: [pending] } });
  mount(); await screen.findByText(/You have an unfinished setup/);
  expect(mfa.enroll).not.toHaveBeenCalled(); expect(mfa.unenroll).not.toHaveBeenCalled();
  fireEvent.click(screen.getByText("Restart unfinished setup")); await screen.findByTestId("qr");
  expect(mfa.unenroll).toHaveBeenCalledWith({ factorId: "unfinished" }); expect(mfa.enroll).toHaveBeenCalledOnce();
});
it("rechecks before restarting and preserves a factor verified in another tab", async () => {
  mfa.listFactors.mockResolvedValueOnce({ data: { totp: [], all: [pending] } });
  mount(); await screen.findByText(/You have an unfinished setup/);
  fireEvent.click(screen.getByText("Restart unfinished setup"));
  await waitFor(() => expect(screen.queryByText("Restart unfinished setup")).toBeNull());
  expect(mfa.unenroll).not.toHaveBeenCalled(); expect(mfa.enroll).not.toHaveBeenCalled();
});
it("handles provider list errors without enrolling or bypassing MFA", async () => {
  mfa.listFactors.mockResolvedValue({ error: new Error("offline") });
  const done = vi.fn(); mount(done); await screen.findByRole("alert"); expect(mfa.enroll).not.toHaveBeenCalled(); expect(done).not.toHaveBeenCalled();
});
it("accepts Arabic digits and paste with spacing using a numeric input", async () => {
  mount(); await screen.findByText(/existing Trifecta/); enter("١٢٣ ٤٥٦");
  const input = screen.getByLabelText("Authenticator code") as HTMLInputElement;
  expect(input.value).toBe("123456"); expect(input.inputMode).toBe("numeric");
});
