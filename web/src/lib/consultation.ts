/**
 * The rules of S-10 · Consultation that are worth testing on their own (T-034).
 *
 * Pure — no fetch, no React. The U2 guarantees live here as much as in the
 * view: the menus keep a fixed order, search matches names only, and nothing
 * computes or returns a count to show.
 */

export type MenuItem = { key?: string; label?: string; group?: string; display_order?: number };
export type MenuGroup = { group: string; items: Array<{ key: string; label: string }> };

/**
 * A catalogue as S-10 shows it: grouped, in the catalogue's fixed
 * `display_order`, groups in the order their first item appears. The same
 * for every case (CT-3) — nothing about this case can reorder it.
 */
export function groupMenu(items: MenuItem[]): MenuGroup[] {
  const sorted = items
    .filter((i): i is Required<Pick<MenuItem, "key" | "label">> & MenuItem => Boolean(i.key && i.label))
    .slice()
    .sort((a, b) => (a.display_order ?? 0) - (b.display_order ?? 0));
  const groups = new Map<string, MenuGroup>();
  for (const i of sorted) {
    const name = i.group || "Other";
    if (!groups.has(name)) groups.set(name, { group: name, items: [] });
    groups.get(name)!.items.push({ key: i.key, label: i.label });
  }
  return [...groups.values()];
}

/**
 * Investigation search (S-10, `PRD` FR-6.5): **filters by name only, never
 * ranks by relevance.** A match keeps its place in the fixed order; nothing
 * moves up because it suits the case. Empty groups are dropped.
 */
export function filterMenu(groups: MenuGroup[], query: string): MenuGroup[] {
  const q = query.trim().toLowerCase();
  if (!q) return groups;
  return groups
    .map((g) => ({ group: g.group, items: g.items.filter((i) => i.label.toLowerCase().includes(q)) }))
    .filter((g) => g.items.length > 0);
}

export type Ordered = { kind: "examination" | "investigation"; key: string; label: string; text: string; at: string };

/** What the session already holds, for the Ordered tab — newest first. */
export function orderedFromSession(s: {
  examinations_done?: Array<{ key?: string; label?: string; finding?: string; at?: string }>;
  investigations_done?: Array<{ key?: string; label?: string; result?: string; at?: string }>;
}): Ordered[] {
  const exams: Ordered[] = (s.examinations_done ?? []).map((e) => ({
    kind: "examination", key: e.key ?? "", label: e.label ?? "", text: e.finding ?? "", at: e.at ?? "" }));
  const tests: Ordered[] = (s.investigations_done ?? []).map((t) => ({
    kind: "investigation", key: t.key ?? "", label: t.label ?? "", text: t.result ?? "", at: t.at ?? "" }));
  return [...exams, ...tests].sort((a, b) => b.at.localeCompare(a.at));
}

/**
 * Whether the 40-question cap has already been met, from the transcript the
 * session already carries (Y-19's optional polish). Returns a boolean, never
 * the number: there is no counter to show, at any point (S-10, U2). The 429
 * `question_limit_reached` remains the authority.
 */
export const QUESTION_CAP = 40;
export function capReached(transcript: Array<{ type?: string }>): boolean {
  return transcript.filter((t) => t.type === "question").length >= QUESTION_CAP;
}

export type AskFailure =
  | { state: "reply-error" }                               // 503 — keep the question, offer retry
  | { state: "rate-limited"; retryAfter: number }          // 429 rate_limited — wait, retry by itself
  | { state: "cap" }                                       // 429 question_limit_reached
  | { state: "blocked" }                                   // 422 patient_data_detected — discard
  | { state: "too-long" }                                  // 422 question_too_long
  | { state: "concluded" }                                 // 409 — the diagnosis is in
  | { state: "gone" };                                     // 401/404 — sign in again or leave

/** An API refusal of a question, as the S-10 state that answers it. */
export function askFailure(code: string | undefined, status: number, retryAfter?: number): AskFailure {
  switch (code) {
    case "question_limit_reached": return { state: "cap" };
    case "rate_limited": return { state: "rate-limited", retryAfter: retryAfter ?? 30 };
    case "patient_data_detected": return { state: "blocked" };
    case "question_too_long": return { state: "too-long" };
    case "session_concluded": return { state: "concluded" };
  }
  if (status === 401 || status === 404) return { state: "gone" };
  return { state: "reply-error" };
}

export const MAX_QUESTION = 500;
/** The character counter appears only past 450 (S-10 "Interactions"). */
export const SHOW_COUNTER_FROM = 450;
export const MAX_DIAGNOSIS = 200;
