import { describe, expect, it } from "vitest";
import {
  fromApiTime,
  fromIsoDate,
  toApiTime,
  toIsoDate,
} from "./picker-values";

describe("native picker API values", () => {
  it("round-trips a locally selected calendar day without a UTC shift", () => {
    const selected = new Date(2035, 1, 7, 12);
    expect(toIsoDate(selected)).toBe("2035-02-07");
    expect(toIsoDate(fromIsoDate("2035-02-07"))).toBe("2035-02-07");
  });

  it("round-trips native time selections using the API's 24-hour format", () => {
    const selected = new Date(2035, 1, 7, 17, 45);
    expect(toApiTime(selected)).toBe("17:45");
    expect(toApiTime(fromApiTime("17:45:00"))).toBe("17:45");
  });
});
