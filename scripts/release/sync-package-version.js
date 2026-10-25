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
