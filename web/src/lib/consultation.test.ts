import { QUESTION_CAP, askFailure, capReached, filterMenu, groupMenu, orderedFromSession } from "./consultation";

const menu = [
  { key: "fbc", label: "Full blood count", group: "Haematology", display_order: 2 },
  { key: "ecg", label: "ECG (12-lead)", group: "Cardiology", display_order: 1 },
  { key: "ferritin", label: "Ferritin", group: "Haematology", display_order: 3 },
  { key: "troponin_0h", label: "High-sensitivity Troponin (0 h)", group: "Cardiology", display_order: 4 },
];

describe("menus (S-10, CT-3)", () => {
  it("groups in the catalogue's fixed order", () => {
    expect(groupMenu(menu)).toEqual([
      { group: "Cardiology", items: [{ key: "ecg", label: "ECG (12-lead)" }, { key: "troponin_0h", label: "High-sensitivity Troponin (0 h)" }] },
      { group: "Haematology", items: [{ key: "fbc", label: "Full blood count" }, { key: "ferritin", label: "Ferritin" }] },
    ]);
  });

  it("searches names only and never reorders (FR-6.5)", () => {
    const g = groupMenu(menu);
    // Groups keep their place in the full catalogue: Cardiology stays first
    // although its only match comes later in display order than Haematology's.
    expect(filterMenu(g, "  T ").map((x) => [x.group, x.items.map((i) => i.key)])).toEqual([
      ["Cardiology", ["troponin_0h"]], ["Haematology", ["fbc", "ferritin"]]]);
    expect(filterMenu(g, "rit").flatMap((x) => x.items.map((i) => i.key))).toEqual(["ferritin"]);
    // a group name or a key is not a name: "haem" matches nothing, nor does "fbc"
    expect(filterMenu(g, "haem")).toEqual([]);
    expect(filterMenu(g, "fbc")).toEqual([]);
    expect(filterMenu(g, "")).toBe(g);
  });
});

it("lists what was done newest first, whatever its kind", () => {
  const ordered = orderedFromSession({
    examinations_done: [{ key: "vitals", label: "Vital signs", finding: "HR 76", at: "2026-11-22T10:00:00Z" }],
    investigations_done: [{ key: "ecg", label: "ECG", result: "Normal", at: "2026-11-22T10:05:00Z" }],
  });
  expect(ordered.map((o) => [o.kind, o.key, o.text])).toEqual([
    ["investigation", "ecg", "Normal"], ["examination", "vitals", "HR 76"]]);
});

describe("the cap is a refusal, not a gauge (API-6, U2)", () => {
  const q = (n: number) => Array.from({ length: n }, () => ({ type: "question" }));
  it("is met at 40 questions, not 40 events", () => {
    expect(capReached([...q(39), ...Array(20).fill({ type: "patient_reply" })])).toBe(false);
    expect(capReached(q(QUESTION_CAP))).toBe(true);
  });
  it("answers yes or no, never a number", () => expect(typeof capReached(q(3))).toBe("boolean"));
});

describe("question refusals map to S-10's states", () => {
  it.each([
    ["question_limit_reached", 429, undefined, { state: "cap" }],
    ["rate_limited", 429, 300, { state: "rate-limited", retryAfter: 300 }],
    ["patient_data_detected", 422, undefined, { state: "blocked" }],
    ["question_too_long", 422, undefined, { state: "too-long" }],
    ["session_concluded", 409, undefined, { state: "concluded" }],
    ["patient_unavailable", 503, undefined, { state: "reply-error" }],
    ["service_unavailable", 0, undefined, { state: "reply-error" }],
    ["unauthenticated", 401, undefined, { state: "gone" }],
  ])("%s (%i)", (code, status, retry, expected) => expect(askFailure(code, status, retry)).toEqual(expected));
});
