var fs = require("fs");
var path = require("path");

var repoRoot = path.resolve(__dirname, "..");
var versionPyPath = path.join(repoRoot, "api", "version.py");

var versionPy = fs.readFileSync(versionPyPath, "utf8");
var match = versionPy.match(/__version__\s*=\s*"([^"]+)"/);

if (!match) {
  console.error("Could not parse __version__ from api/version.py");
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
