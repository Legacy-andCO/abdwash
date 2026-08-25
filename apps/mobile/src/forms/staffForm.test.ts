import { describe, expect, it } from "vitest";
import type { Profile, Team } from "../lib";
import {
  eligibleTeamsForStaff,
  normalizeStaffPhone,
  normalizeStaffUsername,
  validateAddStaff,
} from "./staffForm";

describe("Add Staff form rules", () => {
  it("normalizes usernames and common UAE phone formats", () => {
    expect(normalizeStaffUsername(" Demo.Employee ")).toBe("demo.employee");
    expect(normalizeStaffPhone("0505555555")).toBe("+971505555555");
    expect(normalizeStaffPhone("050 555 5555")).toBe("+971505555555");
    expect(normalizeStaffPhone("+971505555555")).toBe("+971505555555");
  });

  it("explains every invalid field including a short password", () => {
    expect(
      validateAddStaff({
        name: "A",
        username: "bad username",
        phone: "123",
        password: "123456",
      }),
    ).toEqual({
      name: "Enter at least 2 meaningful characters.",
      username:
        "Use lowercase letters, numbers, dots, underscores or hyphens; start and end with a letter or number.",
      phone: "Enter a valid UAE or international phone number.",
      password: "Password must be at least 8 characters.",
    });
  });

  it("enables a complete valid form, with phone remaining optional", () => {
    expect(
      validateAddStaff({
        name: "Demo Employee",
        username: "demo.employee",
        phone: "",
        password: "temporary-password",
      }),
    ).toEqual({});
  });

  it("offers only teams the selected employee actively belongs to", () => {
    const staff = [
      {
        id: "staff-1",
        teams: [{ id: "team-2", name: "Mobile Team 2" }],
      } as Profile,
    ];
    const teams = [
      { id: "team-1", is_active: true },
      { id: "team-2", is_active: true },
      { id: "team-3", is_active: false },
    ] as Team[];
    expect(eligibleTeamsForStaff("staff-1", staff, teams).map((team) => team.id)).toEqual([
      "team-2",
    ]);
  });
});
