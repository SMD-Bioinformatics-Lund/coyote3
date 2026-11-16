// SPDX-FileCopyrightText: 2026 Ram Nanduri
// SPDX-License-Identifier: GPL-3.0-only

var fs = require("fs");
var path = require("path");

var repoRoot = path.resolve(__dirname, "../..");
var releasePath = path.join(repoRoot, "release.toml");

var release = fs.readFileSync(releasePath, "utf8");
var match = release.match(/^application_version\s*=\s*"([^"]+)"/m);

if (!match) {
  console.error("Could not parse application_version from release.toml");
  process.exit(1);
}

var appVersion = match[1];

// Sync targets: root package.json and frontend/package.json
var targets = [
  path.join(repoRoot, "package.json"),
  path.join(repoRoot, "frontend", "package.json"),
];

targets.forEach(function (packageJsonPath) {
  var rel = path.relative(repoRoot, packageJsonPath);
  var packageJson = JSON.parse(fs.readFileSync(packageJsonPath, "utf8"));

  if (packageJson.version !== appVersion) {
    packageJson.version = appVersion;
    fs.writeFileSync(packageJsonPath, JSON.stringify(packageJson, null, 2) + "\n", "utf8");
    console.log(rel + " version synced to " + appVersion);
  } else {
    console.log(rel + " version already " + appVersion);
  }
});

// Package the application label separately from the independently versioned server.
var identityPath = path.join(repoRoot, "api/src/coyote_api/config/application_release.toml");
var identity = "# Generated from release.toml by npm run sync:version.\n" +
  'application_version = "' + appVersion + '"\n';
if (!fs.existsSync(identityPath) || fs.readFileSync(identityPath, "utf8") !== identity) {
  fs.writeFileSync(identityPath, identity, "utf8");
  console.log("API application identity synced to " + appVersion);
}
