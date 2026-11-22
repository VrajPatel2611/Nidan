/**
 * What S-13 · Feedback shows, from `GET /sessions/{id}/feedback` (T-036).
 *
 * Pure. The API has already turned the detectors into behavioural headings and
 * reasons built from the learner's own actions (`reasoning.py`, CT-4/CT-5);
 * this only lays them out. It never sees `bias_detail` and cannot leak it.
 */
import type { Verdict } from "./dashboard";
import { VERDICTS } from "./dashboard";

export { VERDICTS };

/** `pain_character` → "Pain character" (S-13 §4: sentence case, underscores replaced). */
export function topicLabel(key: string): string {
  const words = key.replace(/_/g, " ").trim().toLowerCase();
  return words.charAt(0).toUpperCase() + words.slice(1);
}

/** "8 questions · 3 examinations · 4 tests · 75% history" — singular where it is one. */
export function summaryParts(s: {
  question_count?: number; examination_count?: number; investigation_count?: number; coverage_pct?: number;
}): string[] {
  const n = (count: number | undefined, one: string, many: string) => `${count ?? 0} ${(count ?? 0) === 1 ? one : many}`;
  return [
    n(s.question_count, "question", "questions"),
    n(s.examination_count, "examination", "examinations"),
    n(s.investigation_count, "test", "tests"),
    `${Math.round(s.coverage_pct ?? 0)}% history`,
  ];
}

export type Row = { label: string; icon: "✓" | "○" | "·" | "⚠"; tone: "green" | "red" | "muted" | "amber" | "faint"; meaning: string };

/**
 * S-13 §5/6's row table. Key done ✓ green, key missed ○ red, relevant or
 * reasonable done · muted, low value ⚠ amber, not needed · faint. The only red
 * in the product is a key item missed — never the reasoning section (U4).
 */
export function scorecardRows(card: Record<string, string[] | undefined> | undefined): Row[] {
  const c = card ?? {};
  const rows = (items: string[] | undefined, icon: Row["icon"], tone: Row["tone"], meaning: string) =>
    (items ?? []).map((label) => ({ label, icon, tone, meaning }));
  return [
    ...rows(c.key_done, "✓", "green", "Key, done"),
    ...rows(c.key_missed, "○", "red", "Key, missed"),
    ...rows(c.relevant_done ?? c.reasonable_done, "·", "muted", "Relevant, done"),
    ...rows(c.low_value_done, "⚠", "amber", "Low value here"),
    ...rows(c.extra_done, "·", "faint", "Not needed here"),
  ];
}

/** "Examination — 2 of 3 key done." Null when the case has no key items (S-13: hide, never "0 of 0"). */
export function scorecardSummary(title: string, card: Record<string, string[] | undefined> | undefined): string | null {
  const done = card?.key_done?.length ?? 0;
  const total = done + (card?.key_missed?.length ?? 0);
  return total === 0 ? null : `${title} — ${done} of ${total} key done.`;
}

export function verdictView(v: string | undefined) {
  return v && v in VERDICTS ? VERDICTS[v as Verdict] : VERDICTS.other;
}
