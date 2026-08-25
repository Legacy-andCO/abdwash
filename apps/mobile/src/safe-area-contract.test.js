import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

describe("native safe-area contract", () => {
  it("mounts one provider and consumes top and bottom edges in the shell", () => {
    const app = readFileSync(new URL("./App.tsx", import.meta.url), "utf8");
    const shell = readFileSync(
      new URL("./navigation/OperationsShell.tsx", import.meta.url),
      "utf8",
    );
    expect(app).toContain("<SafeAreaProvider");
    expect(shell).toContain('["top", "bottom", "left", "right"]');
    expect(shell).toContain('from "react-native-safe-area-context"');
  });
});
