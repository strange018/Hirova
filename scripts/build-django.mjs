// Builds the frontend for the Django server in core/: Django serves index.html for every page (core/urls.py) and the
// built files under /static/ (whitenoise), and the API lives on the same site under /api.
//
//   npm run build:django
//
// Writes core/templates/index.html and core/static/ (assets, models, 3D files). Commit both — the server doesn't build
// the frontend itself.
import { execSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";

const root = path.resolve(import.meta.dirname, "..");
const dist = path.join(root, "dist");
const templates = path.join(root, "core", "templates");
const staticDir = path.join(root, "core", "static");

execSync("npx vite build --base /static/", {
  cwd: root,
  stdio: "inherit",
  // Same-site API: the browser calls /api on whatever address the app is served from.
  env: { ...process.env, VITE_API_URL: "/api" },
});

// Old hashed bundles would otherwise pile up.
fs.rmSync(path.join(staticDir, "assets"), { recursive: true, force: true });
for (const entry of fs.readdirSync(dist)) {
  if (entry === "index.html") continue;
  fs.cpSync(path.join(dist, entry), path.join(staticDir, entry), { recursive: true });
}
fs.mkdirSync(templates, { recursive: true });
// Leftovers of an earlier manual copy of the bundle into templates/.
for (const entry of fs.readdirSync(templates)) {
  if (/^index-.*\.(js|css)$/.test(entry)) fs.rmSync(path.join(templates, entry));
}
fs.copyFileSync(path.join(dist, "index.html"), path.join(templates, "index.html"));
console.log("Django frontend written to core/templates/index.html and core/static/.");
