import { describe, expect, it } from "vitest";
import { parseApiErrorPayload } from "./parseApiError";

describe("FastAPI error parsing", () => {
  it("preserves AbdWash domain errors and request IDs", () => {
    expect(
      parseApiErrorPayload(
        { code: "STAFF_NOT_ON_TEAM", message: "Join the team first.", request_id: "req-1" },
        409,
      ),
    ).toEqual({
      code: "STAFF_NOT_ON_TEAM",
      message: "Join the team first.",
      requestId: "req-1",
    });
  });

  it("turns FastAPI validation arrays into field-level messages", () => {
    const parsed = parseApiErrorPayload(
      {
        detail: [
          {
            loc: ["body", "work_date"],
            msg: "Input should be a valid date",
            type: "date_from_datetime_parsing",
          },
        ],
      },
      422,
    );
    expect(parsed.code).toBe("VALIDATION_ERROR");
    expect(parsed.message).toContain("Work date");
    expect(parsed.message).toContain("valid date");
  });

  it("supports HTTPException detail objects", () => {
    expect(
      parseApiErrorPayload({ detail: { code: "UNAUTHORIZED", message: "No access" } }, 401),
    ).toMatchObject({ code: "UNAUTHORIZED", message: "No access" });
  });
});
