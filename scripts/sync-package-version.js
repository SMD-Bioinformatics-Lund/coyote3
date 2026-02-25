var fs = require("fs");
var path = require("path");

var repoRoot = path.resolve(__dirname, "..");
var versionPyPath = path.join(repoRoot, "coyote", "__version__.py");
var packageJsonPath = path.join(repoRoot, "package.json");

var versionPy = fs.readFileSync(versionPyPath, "utf8");
var match = versionPy.match(/__version__\s*=\s*"([^"]+)"/);

if (!match) {
  console.error("Could not parse __version__ from coyote/__version__.py");
  process.exit(1);
}

var appVersion = match[1];
var packageJson = JSON.parse(fs.readFileSync(packageJsonPath, "utf8"));

if (packageJson.version !== appVersion) {
  packageJson.version = appVersion;
  fs.writeFileSync(packageJsonPath, JSON.stringify(packageJson, null, 2) + "\n", "utf8");
  console.log("package.json version synced to " + appVersion);
} else {
  console.log("package.json version already " + appVersion);
}
