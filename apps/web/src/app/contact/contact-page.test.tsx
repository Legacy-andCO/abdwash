// @vitest-environment jsdom

import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { I18nProvider } from "@/components/i18n-provider";
import ContactPage from "./page";

vi.mock("@/components/site-header", () => ({ SiteHeader: () => <header /> }));
vi.mock("@/components/site-footer", () => ({ SiteFooter: () => <footer /> }));

describe("customer contact page", () => {
  afterEach(() => {
    cleanup();
    window.localStorage.clear();
  });

  it("links the current email and WhatsApp contact without JavaScript", () => {
    render(<I18nProvider><ContactPage /></I18nProvider>);
    const email = screen.getByRole("link", { name: /contact@trifecta-wash\.com/i });
    const whatsapp = screen.getByRole("link", { name: /WhatsApp.*\+971 56 420 4954/i });
    expect(email.getAttribute("href")).toBe("mailto:contact@trifecta-wash.com");
    expect(whatsapp.getAttribute("href")).toBe("https://wa.me/971564204954");
    expect(whatsapp.getAttribute("target")).toBe("_blank");
    expect(whatsapp.getAttribute("rel")).toContain("noopener");
    expect(document.body.textContent).not.toContain("trifecta-org@outlook.com");
  });

  it("labels WhatsApp naturally in Arabic RTL", async () => {
    window.localStorage.setItem("trifecta-language", "ar");
    render(<I18nProvider><ContactPage /></I18nProvider>);
    await waitFor(() => expect(document.documentElement.dir).toBe("rtl"));
    expect(screen.getByText("واتساب")).toBeTruthy();
  });
});
