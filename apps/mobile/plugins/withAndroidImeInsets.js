const {
  AndroidConfig,
  withAndroidManifest,
  withMainActivity,
} = require("expo/config-plugins");

const IMPORT_MARKER = "// TRIFECTA_IME_IMPORTS";
const METHOD_MARKER = "// TRIFECTA_IME_HANDLER";
const CALL_MARKER = "// TRIFECTA_IME_INSTALL";

const kotlinImports = `${IMPORT_MARKER}
import android.view.View
import android.view.WindowManager
import androidx.core.view.ViewCompat
import androidx.core.view.WindowInsetsCompat`;

const kotlinMethod = `
  ${METHOD_MARKER}
  /**
   * Edge-to-edge windows are not resized reliably by adjustResize on every Android version.
   * Apply the complete IME obstruction to the activity content root so React Native lays out
   * against the genuinely usable viewport. Insets continue to descendants for safe-area use.
   */
  private fun installTrifectaImeInsets() {
    window.setSoftInputMode(WindowManager.LayoutParams.SOFT_INPUT_ADJUST_RESIZE)
    val content = findViewById<View>(android.R.id.content)
    val initialLeft = content.paddingLeft
    val initialTop = content.paddingTop
    val initialRight = content.paddingRight
    val initialBottom = content.paddingBottom
    ViewCompat.setOnApplyWindowInsetsListener(content) { view, insets ->
      val imeVisible = insets.isVisible(WindowInsetsCompat.Type.ime())
      val imeBottom = insets.getInsets(WindowInsetsCompat.Type.ime()).bottom
      view.setPadding(
        initialLeft,
        initialTop,
        initialRight,
        initialBottom + if (imeVisible) imeBottom else 0,
      )
      insets
    }
    ViewCompat.requestApplyInsets(content)
  }
`;

function ensureAdjustResize(androidManifest) {
  const mainActivity =
    AndroidConfig.Manifest.getMainActivityOrThrow(androidManifest);
  mainActivity.$["android:windowSoftInputMode"] = "adjustResize";
  return androidManifest;
}

function addImeInsetsToMainActivity(source, language) {
  if (language !== "kt") {
    throw new Error(
      "withAndroidImeInsets currently requires Expo's Kotlin MainActivity.",
    );
  }
  let next = source;
  if (!next.includes(IMPORT_MARKER)) {
    const packageLine = next.match(/^package .+$/m)?.[0];
    if (!packageLine)
      throw new Error("Unable to locate the Android MainActivity package.");
    next = next.replace(packageLine, `${packageLine}\n\n${kotlinImports}`);
  }
  if (!next.includes(CALL_MARKER)) {
    next = next.replace(
      /super\.onCreate\(null\)/,
      `super.onCreate(null)\n    ${CALL_MARKER}\n    installTrifectaImeInsets()`,
    );
  }
  if (!next.includes(METHOD_MARKER)) {
    const classEnd = next.lastIndexOf("}");
    if (classEnd < 0)
      throw new Error("Unable to locate the Android MainActivity class body.");
    next = `${next.slice(0, classEnd)}${kotlinMethod}${next.slice(classEnd)}`;
  }
  return next;
}

const withAndroidImeInsets = (config) => {
  config = withAndroidManifest(config, (result) => {
    result.modResults = ensureAdjustResize(result.modResults);
    return result;
  });
  config = withMainActivity(config, (result) => {
    result.modResults.contents = addImeInsetsToMainActivity(
      result.modResults.contents,
      result.modResults.language,
    );
    return result;
  });
  return config;
};

module.exports = withAndroidImeInsets;
module.exports.addImeInsetsToMainActivity = addImeInsetsToMainActivity;
module.exports.ensureAdjustResize = ensureAdjustResize;
