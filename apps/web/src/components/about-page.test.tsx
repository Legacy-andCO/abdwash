// @vitest-environment jsdom

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { readFileSync } from "node:fs";
import { AboutPage } from "./about-page";
import { AuthProvider } from "./auth-provider";
import { I18nProvider } from "./i18n-provider";

vi.mock("next/navigation", () => ({
  usePathname: () => "/about",
  useRouter: () => ({ replace: vi.fn() }),
}));

beforeEach(() => {
  window.localStorage.clear();
  document.documentElement.lang = "en";
  document.documentElement.dir = "ltr";
});

afterEach(() => cleanup());

describe("About Trifecta", () => {
  it("renders approved history, founders, audiences, coverage, and working links", () => {
    render(<I18nProvider><AuthProvider client={null}><AboutPage /></AuthProvider></I18nProvider>);
    expect(screen.getByText(/Founded in July 2023/)).toBeTruthy();
    expect(screen.getByText("Abdallah Awad")).toBeTruthy();
    expect(screen.getByText("Faisal Alateibi")).toBeTruthy();
    expect(screen.getByText("Mission")).toBeTruthy();
    expect(screen.getByText("Vision")).toBeTruthy();
    expect(screen.getByText("Individuals · B2C")).toBeTruthy();
    expect(screen.getByText("Businesses · B2B")).toBeTruthy();
    expect(screen.getByText(/currently operates across Abu Dhabi/)).toBeTruthy();
    expect(screen.getAllByRole("link", { name: "About" }).length).toBeGreaterThanOrEqual(2);
    expect(screen.getByRole("link", { name: "Download Company Profile" }).getAttribute("href")).toBe("/company/Trifecta_Car_Washing_Company_Profile.pdf");
    expect(screen.getByRole("link", { name: "Contact Trifecta" }).getAttribute("href")).toBe("/contact?enquiry=corporate");
  });

  it("renders natural Arabic and switches the document to RTL", async () => {
    render(<I18nProvider><AuthProvider client={null}><AboutPage /></AuthProvider></I18nProvider>);
    await userEvent.click(screen.getByRole("button", { name: "العربية" }));
    expect(await screen.findByRole("heading", { name: "عناية احترافية بسيارتك أينما كانت." })).toBeTruthy();
    expect(screen.getByText("رسالتنا")).toBeTruthy();
    expect(screen.getByText("رؤيتنا")).toBeTruthy();
    await waitFor(() => {
      expect(document.documentElement.lang).toBe("ar");
      expect(document.documentElement.dir).toBe("rtl");
    });
  });

  it("keeps profile-only capabilities out of booking catalogue code", () => {
    const bookingSources = [
      "../components/services-preview.tsx",
      "../components/booking-wizard.tsx",
      "../lib/vehicle-types.ts",
    ].map((path) => readFileSync(new URL(path, import.meta.url), "utf8")).join("\n");
    expect(bookingSources).not.toContain("Headlight restoration");
    expect(bookingSources).not.toContain("Steam wash");
  });
});
