// @vitest-environment jsdom

import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { BookingPolicyAcceptance } from "./booking-policy-acceptance";
import { ComplaintForm } from "./complaint-form";
import { I18nProvider } from "./i18n-provider";
import { SiteFooter } from "./site-footer";
import { createComplaint } from "@/lib/api";
import { policySlugs, policyTitles } from "@/lib/policies";

vi.mock("@/lib/api", () => ({ createComplaint: vi.fn(), ApiError: Error }));

afterEach(() => {
  cleanup();
  localStorage.clear();
  vi.resetAllMocks();
});

it.each(["en", "ar"] as const)("links all six policies in the %s footer", async (language) => {
  localStorage.setItem("trifecta-language", language);
  render(<I18nProvider><SiteFooter /></I18nProvider>);
  for (const slug of policySlugs) {
    expect((await screen.findByRole("link", { name: policyTitles[slug][language] })).getAttribute("href")).toBe(`/${slug}`);
  }
  expect(document.documentElement.dir).toBe(language === "ar" ? "rtl" : "ltr");
});

it("renders an unchecked required booking control with three linked policies", () => {
  const onChange = vi.fn();
  render(<BookingPolicyAcceptance checked={false} disabled={false} onChange={onChange} />);
  const checkbox = screen.getByRole<HTMLInputElement>("checkbox");
  expect(checkbox.checked).toBe(false);
  expect(checkbox.required).toBe(true);
  expect(screen.getAllByRole("link").map((link) => link.getAttribute("href"))).toEqual([
    "/terms-and-conditions", "/cancellation-and-refund-policy", "/privacy-policy",
  ]);
  fireEvent.click(checkbox);
  expect(onChange).toHaveBeenCalledWith(true);
});

it("requires contact details and shows a reference only after intake succeeds", async () => {
  vi.mocked(createComplaint).mockRejectedValueOnce(new Error("network"))
    .mockResolvedValueOnce({ reference: "TC-TEST" });
  render(<ComplaintForm />);
  fireEvent.change(screen.getByLabelText("Full name"), { target: { value: "Sample Customer" } });
  fireEvent.change(screen.getByLabelText("Complaint category"), { target: { value: "service" } });
  fireEvent.change(screen.getByLabelText("Describe what happened"), { target: { value: "The service was incomplete." } });
  fireEvent.click(screen.getByRole("checkbox"));
  fireEvent.click(screen.getByRole("button", { name: "Submit complaint" }));
  expect(screen.getByRole("alert").textContent).toContain("Enter an email address or telephone number.");
  expect(createComplaint).not.toHaveBeenCalled();
  fireEvent.change(screen.getByLabelText("Telephone"), { target: { value: "050 123 4567" } });
  fireEvent.click(screen.getByRole("button", { name: "Submit complaint" }));
  await waitFor(() => expect(screen.getByRole("alert").textContent).toContain("could not confirm receipt"));
  expect(screen.queryByRole("status")).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "Submit complaint" }));
  expect(within(await screen.findByRole("status")).getByText("TC-TEST")).toBeTruthy();
  const [first, second] = vi.mocked(createComplaint).mock.calls;
  expect(JSON.parse(first[0])).toMatchObject({ phone: "+971501234567", privacy_acknowledged: true });
  expect(second).toEqual(first);
});
