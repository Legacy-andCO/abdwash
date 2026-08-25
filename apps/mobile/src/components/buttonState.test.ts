import { describe, expect, it } from "vitest";
import { buttonInteractionState } from "./buttonState";

describe("AppButton interaction state", () => {
  it("does not show a spinner for a validation-disabled button", () => {
    expect(buttonInteractionState(true, false)).toEqual({
      disabled: true,
      busy: false,
      showSpinner: false,
    });
  });

  it("shows a spinner only while a real operation is loading", () => {
    expect(buttonInteractionState(false, true)).toEqual({
      disabled: true,
      busy: true,
      showSpinner: true,
    });
  });
});
