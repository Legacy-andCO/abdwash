import { describe, expect, it } from "vitest";
import plugin from "../plugins/withAndroidImeInsets.js";

const source = `package com.abdwash.staff

import android.os.Bundle

class MainActivity {
  override fun onCreate(savedInstanceState: Bundle?) {
    super.onCreate(null)
  }
}`;

describe("withAndroidImeInsets", () => {
  it("adds full native IME handling exactly once", () => {
    const once = plugin.addImeInsetsToMainActivity(source, "kt");
    const twice = plugin.addImeInsetsToMainActivity(once, "kt");

    expect(twice).toBe(once);
    expect(once.match(/ABDWASH_IME_INSTALL/g)).toHaveLength(1);
    expect(once.match(/ABDWASH_IME_HANDLER/g)).toHaveLength(1);
    expect(once).toContain("WindowInsetsCompat.Type.ime()");
    expect(once).toContain("SOFT_INPUT_ADJUST_RESIZE");
  });

  it("enforces adjustResize without duplicating activity entries", () => {
    const manifest = {
      manifest: {
        application: [
          { activity: [{ $: { "android:name": ".MainActivity" } }] },
        ],
      },
    };
    const result = plugin.ensureAdjustResize(manifest);
    expect(result.manifest.application[0].activity).toHaveLength(1);
    expect(
      result.manifest.application[0].activity[0].$[
        "android:windowSoftInputMode"
      ],
    ).toBe("adjustResize");
  });
});
