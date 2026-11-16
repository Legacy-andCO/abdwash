import { describe, expect, it } from "vitest";
import plugin from "../plugins/withSecurityDefaults.js";

describe("Android release security", () => {
  it("keeps debug usable and makes release signing explicit across repeated prebuilds", () => {
    const original = "android { signingConfigs { debug {} } buildTypes { debug { signingConfig signingConfigs.debug } release { signingConfig signingConfigs.debug } } }";
    const result = plugin.hardenGradle(original);
    expect(result).toContain("debug { signingConfig signingConfigs.debug }");
    expect(result).toContain("release { signingConfig signingConfigs.release }");
    expect(result).toContain("TRIFECTA_RELEASE_STORE_FILE");
    expect(result).toContain("debug signing is forbidden for release builds.");
    expect(plugin.hardenGradle(result)).toBe(result);
  });
});
