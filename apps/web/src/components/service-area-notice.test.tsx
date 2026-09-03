// @vitest-environment jsdom

import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it } from "vitest";
import { I18nProvider, LanguageSwitcher } from "./i18n-provider";
import { ServiceAreaNotice } from "./service-area-notice";

afterEach(() => {
  cleanup();
  window.localStorage.clear();
  document.documentElement.lang = "en";
  document.documentElement.dir = "ltr";
});

describe("service area notice", () => {
  it("explains the Mawaqif restriction and permitted private-parking locations", () => {
    render(<I18nProvider><ServiceAreaNotice /></I18nProvider>);
    expect(screen.getByText("Important service area notice")).toBeTruthy();
    expect(screen.getByText(/cannot wash vehicles in Mawaqif areas/)).toBeTruthy();
    expect(screen.getByText("Private villas")).toBeTruthy();
    expect(screen.getByText(/Facility Management grants access/)).toBeTruthy();
  });

  it("keeps the complete location guidance in the compact payment variant", () => {
    render(<I18nProvider><ServiceAreaNotice compact /></I18nProvider>);
    expect(screen.getByText("Private villas")).toBeTruthy();
    expect(screen.getByText("Compounds")).toBeTruthy();
    expect(screen.getByText(/Facility Management grants access/)).toBeTruthy();
  });

  it("renders the supplied Arabic translation in RTL", async () => {
    render(<I18nProvider><LanguageSwitcher /><ServiceAreaNotice /></I18nProvider>);
    await userEvent.click(screen.getByRole("button", { name: "العربية" }));
    await waitFor(() => expect(document.documentElement.dir).toBe("rtl"));
    expect(screen.getByText("تنبيه مهم بشأن نطاق الخدمة")).toBeTruthy();
    expect(screen.getByText(/مواقف \(Mawaqif\)/)).toBeTruthy();
  });
});
