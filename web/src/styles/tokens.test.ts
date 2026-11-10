/**
 * tokens.css carries UX_SPEC §3.1–3.4 exactly (T-032 criterion 1).
 *
 * Reads the spec itself rather than a copy of it: the CSS blocks in §3.1, §3.3
 * and §3.4 are parsed for `--name: value;` and each must appear in tokens.css
 * with the same value. The typography table (§3.2) is checked row by row.
 * Change the spec, and this fails until the CSS follows.
 */
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

const spec = readFileSync(resolve(__dirname, "../../../docs/spec/UX_SPEC.md"), "utf8");
const css = readFileSync(resolve(__dirname, "tokens.css"), "utf8");

function section(title: string): string {
  const start = spec.indexOf(`## ${title}`);
  if (start < 0) throw new Error(`UX_SPEC has no "## ${title}" section`);
  const next = spec.indexOf("\n## ", start + 1);
  return spec.slice(start, next < 0 ? undefined : next);
}

function declarations(text: string): Map<string, string> {
  const out = new Map<string, string>();
  for (const m of text.matchAll(/(--[a-z0-9-]+)\s*:\s*([^;]+);/gi)) {
    out.set(m[1]!, m[2]!.trim().replace(/\s+/g, " "));
  }
  return out;
}

const cssTokens = declarations(css);

describe.each([
  ["3.1 Colour tokens"],
  ["3.3 Spacing and radius"],
  ["3.4 Elevation"],
])("UX_SPEC §%s", (title) => {
  const specTokens = [...declarations(section(title))];

  it("declares at least one token", () => {
    expect(specTokens.length).toBeGreaterThan(0);
  });

  it.each(specTokens)("%s is %s in tokens.css", (name, value) => {
    expect(cssTokens.get(name)?.toLowerCase()).toBe(value.toLowerCase());
  });
});

describe("UX_SPEC §3.2 Typography", () => {
  const rows = [...section("3.2 Typography").matchAll(
    /\|\s*`(--t-[a-z0-9-]+)`\s*\|\s*(\d+)\s*\/\s*(\d+)\s*\|\s*(\d+)\s*\|/g)];

  it("lists every type token", () => {
    expect(rows.map((r) => r[1])).toEqual([
      "--t-display", "--t-h1", "--t-h2", "--t-h3",
      "--t-body", "--t-body-sm", "--t-caption", "--t-mono",
    ]);
  });

  it.each(rows.map((r) => [r[1]!, r[4]!, r[2]!, r[3]!]))(
    "%s is weight %s, %spx on %spx",
    (name, weight, size, line) => {
      expect(cssTokens.get(name)).toMatch(new RegExp(`^${weight} ${size}px/${line}px `));
    });

  it("uses the monospace stack only for --t-mono", () => {
    for (const [name, value] of cssTokens) {
      if (name.startsWith("--t-")) {
        expect(value.includes("--font-mono")).toBe(name === "--t-mono");
      }
    }
  });
});
