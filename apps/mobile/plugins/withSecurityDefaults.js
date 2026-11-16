const { withAndroidManifest, withAppBuildGradle } = require("expo/config-plugins");

const signing = `
        release {
            def releaseFile = System.getenv('TRIFECTA_RELEASE_STORE_FILE')
            if (releaseFile) {
                storeFile file(releaseFile)
                storePassword System.getenv('TRIFECTA_RELEASE_STORE_PASSWORD')
                keyAlias System.getenv('TRIFECTA_RELEASE_KEY_ALIAS')
                keyPassword System.getenv('TRIFECTA_RELEASE_KEY_PASSWORD')
            }
        }`;
const gate = `
// TRIFECTA_RELEASE_SIGNING_GATE
tasks.configureEach { task ->
    if (task.name == 'preReleaseBuild') {
        task.doFirst {
            def required = ['TRIFECTA_RELEASE_STORE_FILE', 'TRIFECTA_RELEASE_STORE_PASSWORD', 'TRIFECTA_RELEASE_KEY_ALIAS', 'TRIFECTA_RELEASE_KEY_PASSWORD']
            if (required.any { !System.getenv(it) }) {
                throw new GradleException('Release signing credentials must be configured; debug signing is forbidden for release builds.')
            }
        }
    }
}
`;

function hardenGradle(source) {
  if (!source.includes("TRIFECTA_RELEASE_STORE_FILE")) {
    source = source.replace("signingConfigs {", `signingConfigs {${signing}`);
  }
  source = source.replace(/(buildTypes\s*\{[\s\S]*?release\s*\{[\s\S]*?)signingConfig signingConfigs\.debug/, "$1signingConfig signingConfigs.release");
  if (!source.includes("debug signing is forbidden for release builds.")) source += gate;
  return source;
}

function withSecurityDefaults(config) {
  config = withAndroidManifest(config, (result) => {
    const application = result.modResults.manifest.application[0].$;
    application["android:allowBackup"] = "false";
    application["android:usesCleartextTraffic"] = "false";
    return result;
  });
  return withAppBuildGradle(config, (result) => {
    result.modResults.contents = hardenGradle(result.modResults.contents);
    return result;
  });
}

module.exports = withSecurityDefaults;
module.exports.hardenGradle = hardenGradle;
