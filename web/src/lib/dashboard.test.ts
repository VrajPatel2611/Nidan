/**
 * S-08's states and copy rules (T-033), as data.
 */
import { VERDICTS, buildDashboard, greeting, relativeDay, streakDays, type DashboardInput } from "./dashboard";

const NOW = new Date("2026-11-15T13:30:00Z");                 // 19:00 in Kolkata
const base: DashboardInput = {
  displayName: "Aarav Mehta", timezone: "Asia/Kolkata", tier: "free",
  remaining: 2, resetsAt: "2026-11-30T18:30:00Z", sessions: [], progress: null, now: NOW,
};
const done = (id: string, iso: string, verdict = "correct") =>
  ({ id, case_title: `Case ${id}`, started_at: iso, status: "completed", diagnosis_verdict: verdict });

describe("the four states (S-08)", () => {
  it("empty: no sessions — stat tiles hidden", () => {
    const d = buildDashboard(base);
    expect(d.hero).toBe("empty");
    expect(d.stats).toBeNull();
    expect(d.active).toBeNull();
  });

  it("normal: tiles shown, recent sessions listed", () => {
    const d = buildDashboard({ ...base, sessions: [done("a", "2026-11-14T10:00:00Z")],
      progress: { sessions_completed: 1, mean_coverage_last10: null } });
    expect(d.hero).toBe("normal");
    expect(d.stats).toEqual({ completed: 1, streakDays: 1, coveragePct: null });
    expect(d.recent.map((r) => r.caseTitle)).toEqual(["Case a"]);
  });

  it("limit reached: free with nothing left, and when it resets", () => {
    const d = buildDashboard({ ...base, remaining: 0, sessions: [done("a", "2026-11-14T10:00:00Z")] });
    expect(d.hero).toBe("limit");
    expect(d.allowance).toEqual({ remaining: 0, resetsOn: "1 December" });   // midnight IST
  });

  it("unfinished session: a banner, alongside whichever hero applies", () => {
    const d = buildDashboard({ ...base, remaining: 0, sessions: [
      { id: "live", case_title: "Chest pain, 48M", started_at: "2026-11-15T12:00:00Z", status: "active" },
      done("a", "2026-11-14T10:00:00Z"),
    ] });
    expect(d.active).toEqual({ id: "live", caseTitle: "Chest pain, 48M", startedAt: "today" });
    expect(d.hero).toBe("limit");
    expect(d.recent.map((r) => r.id)).toEqual(["a"]);            // not listed twice
  });

  it("Pro has no allowance to show and never reaches the limit", () => {
    const d = buildDashboard({ ...base, tier: "pro", remaining: null, sessions: [done("a", "2026-11-14T10:00:00Z")] });
    expect(d.allowance).toBeNull();
    expect(d.hero).toBe("normal");
  });
});

describe("copy rules", () => {
  it.each([
    ["2026-11-15T01:00:00Z", "Good morning, Aarav"],             // 06:30 IST
    ["2026-11-15T08:00:00Z", "Good afternoon, Aarav"],           // 13:30 IST
    ["2026-11-15T13:30:00Z", "Good evening, Aarav"],             // 19:00 IST
  ])("greets by the learner's local time at %s", (iso, expected) =>
    expect(greeting(new Date(iso), "Asia/Kolkata", "Aarav Mehta")).toBe(expected));

  it("greets without a name when there is none, and survives an unknown zone", () => {
    expect(greeting(NOW, "Not/AZone", null)).toBe("Good afternoon");
  });

  it("never puts the word 'anchored' on screen (PRD P1)", () => {
    const d = buildDashboard({ ...base, sessions: [done("a", "2026-11-14T10:00:00Z", "anchored")] });
    expect(d.recent[0]!.verdict).toEqual({ label: "Worth reconsidering", icon: "↯", tone: "amber" });
    const everyLabel = Object.values(VERDICTS).map((v) => v.label.toLowerCase()).join(" ");
    for (const banned of ["anchor", "bias", "premature", "wrong", "failed"]) {
      expect(everyLabel).not.toContain(banned);
    }
  });
});

describe("streak", () => {
  const tz = "Asia/Kolkata";
  it("counts consecutive local days back from today", () =>
    expect(streakDays(["2026-11-15T05:00:00Z", "2026-11-14T05:00:00Z", "2026-11-13T05:00:00Z"], NOW, tz)).toBe(3));
  it("is not broken by today still being in progress", () =>
    expect(streakDays(["2026-11-14T05:00:00Z", "2026-11-13T05:00:00Z"], NOW, tz)).toBe(2));
  it("stops at a gap", () =>
    expect(streakDays(["2026-11-15T05:00:00Z", "2026-11-13T05:00:00Z"], NOW, tz)).toBe(1));
  it("uses the learner's calendar, not UTC's", () =>
    // 20:00 UTC on the 14th is 01:30 on the 15th in Kolkata: two sessions, one local day.
    expect(streakDays(["2026-11-14T20:00:00Z", "2026-11-15T05:00:00Z"], NOW, tz)).toBe(1));
  it("is zero with nothing recent", () => expect(streakDays(["2026-11-01T05:00:00Z"], NOW, tz)).toBe(0));
});

it.each([
  ["2026-11-15T03:00:00Z", "today"], ["2026-11-14T03:00:00Z", "yesterday"],
  ["2026-11-12T03:00:00Z", "3 days ago"], ["2026-11-01T03:00:00Z", "1 Nov"],
])("relativeDay %s → %s", (iso, expected) => expect(relativeDay(iso, NOW, "Asia/Kolkata")).toBe(expected));
