import { landingPath, loginRedirect, safeNext } from "./redirects";
import { emailError, normaliseEmail, passwordError } from "./validation";

describe("safeNext — open-redirect protection (UX_SPEC §6.1.5)", () => {
  it.each([
    ["/dashboard", "/dashboard"],
    ["/case/abc/feedback?tab=2#x", "/case/abc/feedback?tab=2#x"],
    [encodeURIComponent("/history?page=2"), "/history?page=2"],
  ])("keeps the same-origin path %s", (raw, expected) => expect(safeNext(raw)).toBe(expected));

  it.each([
    "https://evil.example/phish", "//evil.example", "/\\evil.example", "\\\\evil.example",
    "javascript:alert(1)", "dashboard", "/%0d%0aLocation:%20https://evil.example",
    "%2F%2Fevil.example", "", null, undefined,
  ])("discards %j", (raw) => expect(safeNext(raw)).toBeNull());
});

describe("landingPath — UX_SPEC §6.1.5, in priority order", () => {
  const base = { hasProfile: true, onboarded: true };

  it("follows a safe ?next= before anything else", () =>
    expect(landingPath({ ...base, onboarded: false, next: "/history" })).toBe("/history"));
  it("ignores an unsafe ?next=", () =>
    expect(landingPath({ ...base, next: "https://evil.example" })).toBe("/dashboard"));
  it("sends someone with no profile to /welcome, which retries", () =>
    expect(landingPath({ ...base, hasProfile: false })).toBe("/welcome"));
  it("sends someone not yet onboarded to /welcome", () =>
    expect(landingPath({ ...base, onboarded: false, claimedSessionIds: ["s1"] })).toBe("/welcome"));
  it("shows a claimed trial's feedback", () =>
    expect(landingPath({ ...base, claimedSessionIds: ["s 1"] })).toBe("/case/s%201/feedback"));
  it("otherwise, the dashboard", () => expect(landingPath(base)).toBe("/dashboard"));
});

it("loginRedirect carries the original path", () =>
  expect(loginRedirect("/case/1?x=1")).toBe("/login?next=%2Fcase%2F1%3Fx%3D1"));

describe("S-02 field rules, with the spec's copy", () => {
  it("normalises email", () => expect(normaliseEmail("  Asha@Example.COM ")).toBe("asha@example.com"));
  it.each(["asha@example.com", "x7k2@privaterelay.appleid.com"])("accepts %s", (e) =>
    expect(emailError(e)).toBeNull());
  it.each(["asha", "asha@", "@example.com", "asha@example", "a b@example.com"])("refuses %s", (e) =>
    expect(emailError(e)).toBe("Enter a valid email address"));

  it("needs eight characters", () => expect(passwordError("short7!")).toBe("Use at least 8 characters"));
  it("refuses a common password, whatever its case", () =>
    expect(passwordError("Password123")).toBe("That password is too common — try something less predictable"));
  it("accepts an ordinary one", () => expect(passwordError("tamarind-lamp-41")).toBeNull());
});
