import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

const source = (path) => readFileSync(new URL(path, import.meta.url), "utf8");

describe("recovery UI contracts", () => {
  it("shows Add Staff validation while keeping invalid submission disabled", () => {
    const team = source("./screens/TeamScreen.tsx");
    const rules = source("./forms/staffForm.ts");
    expect(rules).toContain("Password must be at least 8 characters.");
    expect(team).toContain("disabled={busy || !formValid}");
    expect(team).toContain("Only teams this employee belongs to are shown.");
  });

  it("acknowledges Start Trip before location work and offers no-ETA fallback", () => {
    const jobs = source("./screens/JobsScreen.tsx");
    const flow = source("./location/startTripFlow.ts");
    expect(flow.indexOf('onStage("getting_location")')).toBeLessThan(
      flow.indexOf("acquireTripOrigin(source"),
    );
    expect(jobs).toContain("runStartTripFlow");
    expect(jobs).toContain("Getting location…");
    expect(jobs).toContain("Start without ETA");
  });

  it("renders every authoritative job action without skipping ARRIVED", () => {
    const jobs = source("./screens/JobsScreen.tsx");
    expect(jobs).toContain('job.status === "en_route"');
    expect(jobs).toContain('job.status === "arrived"');
    expect(jobs).toContain('job.status === "in_progress"');
    expect(jobs).toContain('action("arrive")');
    expect(jobs).toContain('action("start")');
    expect(jobs).toContain('action("complete")');
    expect(jobs).toContain('action("cash-payment")');
    expect(jobs).toContain("Confirm arrival");
    expect(jobs).toContain("Complete wash?");
    expect(jobs).toContain("Confirm cash");
  });

  it("offers Navigate and Close after a successful trip", () => {
    const jobs = source("./screens/JobsScreen.tsx");
    expect(jobs).toContain('"Trip started"');
    expect(jobs).toContain('{ text: "Navigate"');
    expect(jobs).toContain('{ text: "Close"');
    expect(jobs).toContain("Customer notification queued.");
  });

  it("ordinary sign-out uses cache-preserving cleanup", () => {
    const app = source("./App.tsx");
    const profile = source("./screens/ProfileScreen.tsx");
    expect(app).toContain("prepareOperationalLogout");
    expect(profile).toContain("prepareOperationalLogout");
    expect(profile).not.toContain("clearOperationalCache");
  });
});
