// Fails if src/api/schema.ts is not what ../openapi.yaml generates today
// (BUILD_PLAN T-032 criterion 2).
//
// The client is generated from the contract, so a contract that changes
// without regenerating leaves the app type-checking against an API that no
// longer exists — and nothing else would notice. Regenerates with the same CLI
// `npm run gen:api` uses, into a temporary file, and compares.
//
// Also the only strict parse openapi.yaml gets: PyYAML, which the backend's
// tests use, silently keeps the last of two duplicated keys.

import { execFileSync } from "node:child_process";
import { mkdtempSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

const web = fileURLToPath(new URL("..", import.meta.url));
const committed = join(web, "src", "api", "schema.ts");
const dir = mkdtempSync(join(tmpdir(), "nidan-api-"));
const fresh = join(dir, "schema.ts");

try {
  const cli = join(web, "node_modules", "openapi-typescript", "bin", "cli.js");
  execFileSync(process.execPath, [cli, join(web, "..", "openapi.yaml"), "--output", fresh],
    { stdio: ["ignore", "ignore", "inherit"] });

  // Line endings only: git may check the file out as CRLF on Windows.
  const normalise = (path) => readFileSync(path, "utf8").replace(/\r\n/g, "\n");
  if (normalise(committed) !== normalise(fresh)) {
    console.error(
      "src/api/schema.ts is stale: openapi.yaml has changed since it was generated.\n" +
      "Run `npm run gen:api` in web/ and commit the result with the contract change.");
    process.exit(1);
  }
  console.log("src/api/schema.ts matches openapi.yaml.");
} finally {
  rmSync(dir, { recursive: true, force: true });
}
