import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

const source = (path: string) =>
  readFileSync(new URL(path, import.meta.url), "utf8");

describe("saved vehicle booking UI contract", () => {
  it("keeps saved vehicle selection inside each vehicle card", () => {
    const wizard = source("../components/booking-wizard.tsx");
    const vehicleCard = wizard.slice(wizard.indexOf("function VehicleCard"));
    expect(vehicleCard).toContain('className="saved-vehicle-slot"');
    expect(vehicleCard).toContain('type: "apply_saved_vehicle"');
    expect(vehicleCard).toContain("vehicleKey: vehicle.key");
  });

  it("offers manual entry and marks saved vehicles selected elsewhere", () => {
    const wizard = source("../components/booking-wizard.tsx");
    expect(wizard).toContain('t("booking.vehicles.manual")');
    expect(wizard).toContain("disabled={alreadySelected}");
    expect(wizard).toContain('t("booking.vehicles.alreadySelected")');
  });

  it("has compact responsive and RTL-safe styling", () => {
    const css = source("../app/globals.css");
    const savedVehicleStyles = css.slice(css.indexOf(".saved-vehicle-slot"));
    expect(css).toContain(".saved-vehicle-slot");
    expect(css).toContain(".saved-vehicle-summary");
    expect(css).toContain(".form-grid.two");
    expect(savedVehicleStyles.slice(0, 1600)).not.toContain("margin-left");
  });

  it("contains English and Arabic selector translations", () => {
    const translations = source("./i18n.ts");
    expect(translations).toContain(
      '"booking.vehicles.savedSelect": "Use a saved vehicle"',
    );
    expect(translations).toContain(
      '"booking.vehicles.savedSelect": "استخدم مركبة محفوظة"',
    );
  });
});
