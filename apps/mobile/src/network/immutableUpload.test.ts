import { expect, it } from "vitest";
import { alreadyUploaded } from "./immutableUpload";

it("allows an immutable upload retry to finalize an existing object, and rejects other errors", () => {
  expect(alreadyUploaded({ statusCode: "409" })).toBe(true);
  expect(alreadyUploaded({ statusCode: 409 })).toBe(true);
  expect(alreadyUploaded({ statusCode: "403" })).toBe(false);
  expect(alreadyUploaded({ message: "resource already exists" })).toBe(false);
  expect(alreadyUploaded(null)).toBe(false);
});
