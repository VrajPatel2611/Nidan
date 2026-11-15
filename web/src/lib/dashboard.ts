/**
 * What S-08 · Dashboard shows, computed from the API's answers (T-033).
 *
 * Pure — no fetch, no clock, no React — so every state in UX_SPEC S-08's table
 * is a test case rather than something to click through.
 */

export type Verdict = "correct" | "partial" | "anchored" | "other";

/**
 * S-13's verdict labels. `anchored` is a machine value and must never reach
 * the screen (`PRD` P1, U4): it reads "Worth reconsidering", in amber, never
 * "Wrong" or "You anchored".
 */
export const VERDICTS: Record<Verdict, { label: string; icon: string; tone: "green" | "neutral" | "amber" }> = {
  correct:  { label: "Correct diagnosis",   icon: "✓", tone: "green" },
  partial:  { label: "On the right track",  icon: "◑", tone: "neutral" },
  anchored: { label: "Worth reconsidering", icon: "↯", tone: "amber" },
  other:    { label: "Not quite",           icon: "?", tone: "neutral" },
};

export type DashboardInput = {
  displayName?: string | null;
  timezone?: string | null;
  tier?: string | null;
  /** Free tier only; null or absent for Pro (unlimited). */
  remaining?: number | null;
  resetsAt?: string | null;
  sessions: Array<{ id?: string; case_title?: string; started_at?: string; status?: string; diagnosis_verdict?: string }>;
  progress?: { sessions_completed?: number; mean_coverage_last10?: number | null } | null;
  now: Date;
};

export type Dashboard = {
  greeting: string;
  /** S-08 states. `unfinished` is a banner, so it combines with any of these. */
  hero: "empty" | "normal" | "limit";
  active: { id: string; caseTitle: string; startedAt: string } | null;
  /** Shown in the header for the free tier only, and never in a consultation (U2). */
  allowance: { remaining: number; resetsOn: string | null } | null;
  /** Hidden in the empty state. Coverage is null below three sessions. */
  stats: { completed: number; streakDays: number; coveragePct: number | null } | null;
  recent: Array<{ id: string; caseTitle: string; when: string; verdict: (typeof VERDICTS)[Verdict] | null; status: string }>;
};

/** The hour of `now` in `timezone`, falling back to UTC for an unknown zone. */
function hourIn(now: Date, timezone?: string | null): number {
  try {
    return Number(new Intl.DateTimeFormat("en-GB", { hour: "numeric", hourCycle: "h23", timeZone: timezone || "UTC" }).format(now));
  } catch {
    return now.getUTCHours();
  }
}

/** `YYYY-MM-DD` of an instant in `timezone` — a calendar day, for streaks. */
export function dayIn(instant: Date, timezone?: string | null): string {
  try {
    return new Intl.DateTimeFormat("en-CA", { timeZone: timezone || "UTC" }).format(instant);
  } catch {
    return instant.toISOString().slice(0, 10);
  }
}

export function greeting(now: Date, timezone?: string | null, name?: string | null): string {
  const h = hourIn(now, timezone);
  const part = h < 12 ? "Good morning" : h < 18 ? "Good afternoon" : "Good evening";
  const first = name?.trim().split(/\s+/)[0];
  return first ? `${part}, ${first}` : part;
}

/**
 * Consecutive calendar days, in the learner's timezone, with a completed
 * session — counting back from today, or from yesterday if today has none yet
 * (a streak is not broken by the day still being in progress). Stated
 * factually; S-08 forbids any urgency about it (U1).
 */
export function streakDays(dates: string[], now: Date, timezone?: string | null): number {
  const days = new Set(dates.map((d) => dayIn(new Date(d), timezone)));
  const cursor = new Date(now);
  if (!days.has(dayIn(cursor, timezone))) cursor.setUTCDate(cursor.getUTCDate() - 1);
  let streak = 0;
  while (days.has(dayIn(cursor, timezone))) {
    streak += 1;
    cursor.setUTCDate(cursor.getUTCDate() - 1);
  }
  return streak;
}

/** "today", "yesterday", "3 days ago", then a date — S-14's relative dates. */
export function relativeDay(iso: string, now: Date, timezone?: string | null): string {
  const then = new Date(iso);
  const a = Date.parse(dayIn(then, timezone));
  const b = Date.parse(dayIn(now, timezone));
  const days = Math.round((b - a) / 86_400_000);
  if (days <= 0) return "today";
  if (days === 1) return "yesterday";
  if (days < 7) return `${days} days ago`;
  return new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short", timeZone: timezone || "UTC" }).format(then);
}

export function formatResetDate(iso: string, timezone?: string | null): string {
  return new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "long", timeZone: timezone || "UTC" }).format(new Date(iso));
}

export function buildDashboard(input: DashboardInput): Dashboard {
  const { sessions, now, timezone } = input;
  const completed = sessions.filter((s) => s.status === "completed");
  const activeRow = sessions.find((s) => s.status === "active" && s.id);
  const isFree = input.tier !== "pro" && typeof input.remaining === "number";

  const hero: Dashboard["hero"] =
    isFree && input.remaining! <= 0 ? "limit"
      : completed.length === 0 && (input.progress?.sessions_completed ?? 0) === 0 ? "empty"
        : "normal";

  const coverage = input.progress?.mean_coverage_last10;
  return {
    greeting: greeting(now, timezone, input.displayName),
    hero,
    active: activeRow
      ? { id: activeRow.id!, caseTitle: activeRow.case_title || "a case", startedAt: relativeDay(activeRow.started_at ?? now.toISOString(), now, timezone) }
      : null,
    allowance: isFree
      ? { remaining: Math.max(0, input.remaining!), resetsOn: input.resetsAt ? formatResetDate(input.resetsAt, timezone) : null }
      : null,
    stats: hero === "empty" ? null : {
      completed: input.progress?.sessions_completed ?? completed.length,
      streakDays: streakDays(completed.flatMap((s) => (s.started_at ? [s.started_at] : [])), now, timezone),
      // Already a percentage: the average of session_results.coverage_pct.
      coveragePct: coverage == null ? null : Math.round(coverage),
    },
    recent: sessions
      .filter((s) => s.status !== "active" && s.id)
      .slice(0, 5)
      .map((s) => ({
        id: s.id!,
        caseTitle: s.case_title || "Case",
        when: s.started_at ? relativeDay(s.started_at, now, timezone) : "",
        verdict: s.diagnosis_verdict && s.diagnosis_verdict in VERDICTS ? VERDICTS[s.diagnosis_verdict as Verdict] : null,
        status: s.status ?? "",
      })),
  };
}
