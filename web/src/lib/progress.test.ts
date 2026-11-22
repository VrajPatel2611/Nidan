import { coverageChart, patternSentence, untilTrends, verdictSegments } from "./progress";

const focus = (last: number | null, prev: number | null, direction: "improving" | "stable" | "declining" | null = null) =>
  ({ id: "diagnostic_focus", label: "Diagnostic focus", last10_rate: last, prev10_rate: prev, direction });

describe("pattern sentences (S-16 copy rules)", () => {
  it("states improvement plainly — the spec's own example", () =>
    expect(patternSentence(focus(0.2, 0.5, "improving"), 20))
      .toBe("Diagnostic focus flagged in 2 of your last 10 cases, down from 5."));

  it("states decline in exactly the same shape — no alarm, no judgement", () => {
    const s = patternSentence(focus(0.5, 0.2, "declining"), 20);
    expect(s).toBe("Diagnostic focus flagged in 5 of your last 10 cases, up from 2.");
    expect(s).not.toMatch(/worse|declin|warning|careful|!/i);
  });

  it("says when it is about the same", () =>
    expect(patternSentence(focus(0.3, 0.32, "stable"), 20))
      .toBe("Diagnostic focus flagged in 3 of your last 10 cases, about the same as the 10 before."));

  it("uses the real window sizes when there are fewer than twenty", () => {
    // 12 completed: the earlier window holds 2 cases, both flagged.
    expect(patternSentence(focus(0.5, 1, "declining"), 12)).toBe("Diagnostic focus flagged in 5 of your last 10 cases, up from 2.");
    expect(patternSentence(focus(1 / 3, null), 3)).toBe("Diagnostic focus flagged in 1 of your last 3 cases.");
  });

  it("does not invent a comparison with nothing to compare", () =>
    expect(patternSentence(focus(null, null), 2)).toBe("Diagnostic focus: not enough cases yet."));
});

it("the empty state counts towards three", () => {
  expect(untilTrends(2)).toBe("2 of 3 completed");
  expect(untilTrends(0)).toBe("0 of 3 completed");
});

describe("coverage chart", () => {
  it("plots the last ten only, 0–100 % top to bottom, with the mean", () => {
    const series = Array.from({ length: 12 }, (_, i) => ({ coverage_pct: i < 2 ? 0 : 50 }));
    const c = coverageChart(series, 200, 100, 0);
    expect(c.points).toHaveLength(10);
    expect(c.points.every((p) => p.y === 50)).toBe(true);    // the two zeros fell out of the window
    expect(c.mean).toBe(50);
    expect(c.points[0]!.x).toBe(0);
    expect(c.points[9]!.x).toBe(200);
  });

  it("clamps out-of-range values and copes with one point or none", () => {
    expect(coverageChart([{ coverage_pct: 140 }], 100, 100, 0).points[0]).toEqual({ x: 50, y: 0, pct: 100 });
    expect(coverageChart([], 100, 100)).toEqual({ points: [], meanY: null, mean: null });
  });
});

it("verdict segments keep S-13's order and drop empty ones", () => {
  expect(verdictSegments({ correct: 3, partial: 0, anchored: 1, other: 0 }))
    .toEqual([{ verdict: "correct", count: 3, share: 0.75 }, { verdict: "anchored", count: 1, share: 0.25 }]);
});
