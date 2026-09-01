import { describe, expect, it } from "vitest";
import { localizeServiceDescription } from "./i18n";

describe("Arabic catalogue presentation", () => {
  it.each([
    [
      "Once weekly. Monthly package; online entitlement activation is not yet available.",
      "زيارة واحدة أسبوعياً ضمن باقة شهرية؛ تفعيل الاستحقاق عبر الإنترنت غير متاح حالياً.",
    ],
    [
      "A complete interior reset for upholstery, leather and difficult stains.",
      "تجديد داخلي متكامل للمفروشات والجلد وإزالة البقع الصعبة.",
    ],
    [
      "Exterior polishing, wax and paint enhancement.",
      "تلميع الهيكل الخارجي مع طبقة شمع وتحسين طلاء المركبة.",
    ],
  ])("localizes %s", (description, expected) => {
    expect(
      localizeServiceDescription(
        "ar",
        description,
        "services.defaultDescription",
      ),
    ).toBe(expected);
  });

  it("leaves the canonical English catalogue copy unchanged", () => {
    const description = "Exterior polishing, wax and paint enhancement.";
    expect(
      localizeServiceDescription(
        "en",
        description,
        "services.defaultDescription",
      ),
    ).toBe(description);
  });
});
