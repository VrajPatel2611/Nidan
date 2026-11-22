/**
 * S-16 · Progress, as text and geometry (T-037). Pure.
 *
 * The copy rule that matters: **decline is stated as plainly and as
 * neutrally as improvement** (S-16, U1). Every sentence here has the same
 * shape whichever way the number moved — no "worse", no warning, no colour
 * difference in the view. Facts, not judgement.
 */

export const MIN_SESSIONS = 3;   // `MIN_SESSIONS_FOR_TRENDS`; the API's has_sufficient_data agrees
export const WINDOW = 10;

export type Trend = {
  id?: string; label?: string;
  last10_rate?: number | null; prev10_rate?: number | null;
  direction?: "improving" | "stable" | "declining" | null;
};

/** How many of the cases in a window a rate represents. */
function count(rate: number, inWindow: number): number {
  return Math.round(rate * inWindow);
}

/**
 * "Diagnostic focus flagged in 2 of your last 10 cases, down from 5."
 * The windows are the last ten completed cases and the ten before them, so
 * with twelve completed the second window holds two.
 */
export function patternSentence(t: Trend, completed: number): string {
  const label = t.label ?? "This pattern";
  const last = Math.min(WINDOW, completed);
  const prev = Math.min(WINDOW, Math.max(0, completed - WINDOW));
  if (t.last10_rate == null) return `${label}: not enough cases yet.`;

  const now = count(t.last10_rate, last);
  const head = `${label} flagged in ${now} of your last ${last} ${last === 1 ? "case" : "cases"}`;
  if (t.prev10_rate == null || prev === 0) return `${head}.`;

  const before = count(t.prev10_rate, prev);
  if (before === now || t.direction === "stable") return `${head}, about the same as the ${prev} before.`;
  return `${head}, ${now < before ? "down" : "up"} from ${before}.`;
}

/** "2 of 3 completed" for the empty state. */
export function untilTrends(completed: number): string {
  return `${Math.min(completed, MIN_SESSIONS)} of ${MIN_SESSIONS} completed`;
}

export type Point = { x: number; y: number; pct: number };

/**
 * The coverage line: the last ten points, scaled into a width × height box
 * with 0–100 % on the y axis, plus where the mean line sits.
 */
export function coverageChart(series: Array<{ coverage_pct?: number }>, width: number, height: number, pad = 8):
  { points: Point[]; meanY: number | null; mean: number | null } {
  const last = series.slice(-WINDOW).map((p) => Math.max(0, Math.min(100, p.coverage_pct ?? 0)));
  if (last.length === 0) return { points: [], meanY: null, mean: null };
  const y = (pct: number) => pad + (1 - pct / 100) * (height - 2 * pad);
  const step = last.length === 1 ? 0 : (width - 2 * pad) / (last.length - 1);
  const mean = last.reduce((a, b) => a + b, 0) / last.length;
  return {
    points: last.map((pct, i) => ({ x: last.length === 1 ? width / 2 : pad + i * step, y: y(pct), pct })),
    meanY: y(mean),
    mean: Math.round(mean),
  };
}

/** The four verdicts as stacked-bar segments, in S-13's order, skipping empty ones. */
export function verdictSegments(dist: Record<string, number | undefined> | undefined) {
  const order = ["correct", "partial", "anchored", "other"] as const;
  const total = order.reduce((n, v) => n + (dist?.[v] ?? 0), 0);
  return order
    .map((v) => ({ verdict: v, count: dist?.[v] ?? 0, share: total ? (dist?.[v] ?? 0) / total : 0 }))
    .filter((s) => s.count > 0);
}
