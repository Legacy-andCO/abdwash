// @vitest-environment jsdom
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { beforeEach, describe, expect, it } from "vitest";
import { CustomerStatus } from "./customer-status";
import { I18nProvider, LanguageSwitcher, useI18n } from "./i18n-provider";
import { contactErrors, emptyVehicle, vehicleErrors } from "@/lib/booking-state";
import { LANGUAGE_STORAGE_KEY, translate } from "@/lib/i18n";
import { ApiError } from "@/lib/api";
import { localizedCustomerError } from "@/lib/customer-error";
import type { Location } from "@/lib/types";

function StateProbe() {
  const { t } = useI18n();
  const [plate, setPlate] = useState("");
  return <><LanguageSwitcher /><label>{t("booking.vehicles.plateRequired")}<input aria-label="plate" value={plate} onChange={(event) => setPlate(event.target.value)} /></label></>;
}

describe("customer website localization", () => {
  beforeEach(() => {
    window.localStorage.clear();
    document.documentElement.lang = "en";
    document.documentElement.dir = "ltr";
  });

  it("renders English and Arabic without exposing translation keys", () => {
    expect(translate("en", "common.continue")).toBe("Continue");
    expect(translate("ar", "common.continue")).toBe("متابعة");
    expect(translate("ar", "common.continue")).not.toContain("common.continue");
  });

  it("persists Arabic, sets RTL, restores English LTR, and preserves booking input", async () => {
    const user = userEvent.setup();
    render(<I18nProvider><StateProbe /></I18nProvider>);
    await user.type(screen.getByLabelText("plate"), "ABC 123");
    await user.click(screen.getByRole("button", { name: "العربية" }));
    await waitFor(() => expect(document.documentElement.dir).toBe("rtl"));
    expect(document.documentElement.lang).toBe("ar");
    expect(window.localStorage.getItem(LANGUAGE_STORAGE_KEY)).toBe("ar");
    expect((screen.getByLabelText("plate") as HTMLInputElement).value).toBe("ABC 123");
    await user.click(screen.getByRole("button", { name: "EN" }));
    await waitFor(() => expect(document.documentElement.dir).toBe("ltr"));
    expect(document.documentElement.lang).toBe("en");
  });

  it("restores a persisted Arabic choice", async () => {
    window.localStorage.setItem(LANGUAGE_STORAGE_KEY, "ar");
    render(<I18nProvider><StateProbe /></I18nProvider>);
    await waitFor(() => expect(document.documentElement.dir).toBe("rtl"));
    expect(screen.getByText("رقم اللوحة (مطلوب)")).toBeTruthy();
    expect(window.localStorage.getItem(LANGUAGE_STORAGE_KEY)).toBe("ar");
  });

  it("localizes required plate and location-notes validation", () => {
    const location: Location = { written_address: "Abu Dhabi", location_url: "https://maps.google.com/maps?q=x", latitude: null, longitude: null, instructions: "" };
    const t = (key: Parameters<typeof translate>[1]) => translate("ar", key);
    expect(contactErrors({ first_name: "A", surname: "B", email: "a@b.com", phone: "+971501234567", phone_country: "AE" }, location, t).instructions).toBe("تفاصيل الموقع مطلوبة.");
    const vehicle = { ...emptyVehicle("service"), make: "Toyota", model: "Camry", vehicle_type: "sedan", plate_number: "" };
    expect(vehicleErrors([vehicle], t)[`${vehicle.key}.plate_number`]).toBe("رقم لوحة المركبة مطلوب.");
  });

  it("localizes customer job statuses", async () => {
    window.localStorage.setItem(LANGUAGE_STORAGE_KEY, "ar");
    render(<I18nProvider><CustomerStatus status={{ key: "en_route", label: "Driver on the way", stage: 2, job_status: "en_route" }} /></I18nProvider>);
    await waitFor(() => expect(screen.getAllByText("السائق في الطريق").length).toBeGreaterThan(0));
  });

  it("does not expose English network errors in Arabic", () => {
    const t = (key: Parameters<typeof translate>[1]) => translate("ar", key);
    const error = new ApiError("NETWORK_ERROR", "English network message", 0);
    expect(localizedCustomerError(error, "ar", t)).toBe("تعذر الوصول إلى ترايفكتا. تحقق من اتصالك وحاول مرة أخرى.");
  });

  it("localizes real-capacity scheduling conflicts in Arabic", () => {
    const t = (key: Parameters<typeof translate>[1]) => translate("ar", key);
    const error = new ApiError(
      "NO_TEAM_CAPACITY",
      "This time is no longer available.",
      409,
    );
    expect(localizedCustomerError(error, "ar", t)).toBe(
      "هذا الموعد لم يعد متاحاً. اختر موعداً آخر.",
    );
  });
});
