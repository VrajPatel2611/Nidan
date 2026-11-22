import "server-only";
import type { components } from "@/api/schema";
import { env } from "@/lib/env";

/**
 * The Nidan API, called from the server with the user's Supabase token.
 *
 * Types come from `src/api/schema.ts`, generated from openapi.yaml — never
 * written by hand here. Called server-side only, so the access token never
 * needs to be readable by browser JavaScript (UX_SPEC §6.1.3).
 */
export type Profile = components["schemas"]["Profile"];
export type ProfileCreate = components["schemas"]["ProfileCreate"];
export type ProfileUpdate = components["schemas"]["ProfileUpdate"];
export type SessionPage = components["schemas"]["SessionPage"];
export type SessionSummary = NonNullable<SessionPage["data"]>[number];
export type Session = components["schemas"]["Session"];
export type Progress = components["schemas"]["Progress"];
export type ApiError = components["schemas"]["Error"];

export type ApiResult<T> =
  | { ok: true; status: number; data: T }
  | { ok: false; status: number; error: ApiError["error"]; retryAfter?: number };

async function call<T>(method: string, path: string, token: string, body?: unknown,
                       headers: Record<string, string> = {}): Promise<ApiResult<T>> {
  let res: Response;
  try {
    res = await fetch(`${env.apiUrl()}${path}`, {
      method,
      headers: {
        Authorization: `Bearer ${token}`,
        Accept: "application/json",
        ...(body === undefined ? {} : { "Content-Type": "application/json" }),
        ...headers,
      },
      body: body === undefined ? undefined : JSON.stringify(body),
      cache: "no-store",
    });
  } catch {
    return { ok: false, status: 0, error: { code: "service_unavailable", message: "The Nidan API could not be reached." } };
  }
  const json = await res.json().catch(() => null);
  if (res.ok) return { ok: true, status: res.status, data: json as T };
  const retry = Number(res.headers.get("Retry-After"));
  return {
    ok: false, status: res.status,
    error: (json as ApiError | null)?.error ?? { code: "internal_error", message: `HTTP ${res.status}` },
    ...(Number.isFinite(retry) && retry > 0 ? { retryAfter: retry } : {}),
  };
}

/**
 * Create or fetch the profile. Idempotent (openapi.yaml: 201 created, 200
 * existed), and the place a trial taken before signup is claimed.
 */
export function createProfile(token: string, body: ProfileCreate) {
  return call<Profile & { claimed_session_ids?: string[] }>("POST", "/me", token, body);
}

export function getProfile(token: string) {
  return call<Profile>("GET", "/me", token);
}

export function updateProfile(token: string, body: ProfileUpdate) {
  return call<Profile>("PATCH", "/me", token, body);
}

/**
 * Newest first, 20 a page, cursor-paginated (API_CONTRACT §2.5 — never an
 * offset). The dashboard reads the first page; S-14 follows `next_cursor`.
 */
export function listSessions(token: string, limit = 20, cursor?: string | null) {
  const q = new URLSearchParams({ limit: String(limit), ...(cursor ? { cursor } : {}) });
  return call<SessionPage>("GET", `/sessions?${q}`, token);
}

/** Trends need three completed sessions; below that the averages are null. */
export function getProgress(token: string) {
  return call<Progress>("GET", "/progress", token);
}

/**
 * Start a consultation. The server chooses the case (`PRD` FR-3) — there is
 * nothing to pass but an optional pre-case confidence.
 */
export function startSession(token: string) {
  return call<Session>("POST", "/sessions", token, {});
}

/** Still counts against the month's allowance (`PRD` FR-3). */
export function abandonSession(token: string, sessionId: string) {
  return call<null>("POST", `/sessions/${encodeURIComponent(sessionId)}/abandon`, token, {});
}

// ── The consultation (T-034) ──────────────────────────────────────────

export type CatalogItem = components["schemas"]["CatalogItem"];
export type PatientReply = components["schemas"]["PatientReply"];
export type OrderResult = components["schemas"]["OrderResult"];

export function getSession(token: string, sessionId: string) {
  return call<Session>("GET", `/sessions/${encodeURIComponent(sessionId)}`, token);
}

/**
 * The two universal menus. Public and the same for every case (CT-3) — no
 * token needed, and cached for the hour the API's Cache-Control allows.
 */
export async function getCatalog(kind: "examinations" | "investigations"): Promise<CatalogItem[] | null> {
  try {
    const res = await fetch(`${env.apiUrl()}/catalog/${kind}`, { next: { revalidate: 3600 } });
    if (!res.ok) return null;
    return ((await res.json()) as { data: CatalogItem[] }).data;
  } catch {
    return null;
  }
}

export function askQuestion(token: string, sessionId: string, text: string) {
  return call<PatientReply>("POST", `/sessions/${encodeURIComponent(sessionId)}/questions`, token, { text });
}

export function order(token: string, sessionId: string, kind: "examinations" | "investigations", key: string) {
  return call<OrderResult>("POST", `/sessions/${encodeURIComponent(sessionId)}/${kind}`, token, { key });
}

/** Irreversible. The Idempotency-Key makes a retried submit one conclusion, not two (§2.8). */
export function submitDiagnosis(token: string, sessionId: string, text: string, idempotencyKey: string) {
  return call<{ session_id?: string; feedback_ready?: boolean }>(
    "POST", `/sessions/${encodeURIComponent(sessionId)}/diagnosis`, token, { text },
    { "Idempotency-Key": idempotencyKey });
}

// ── Feedback (T-036) ──────────────────────────────────────────────────

export type Feedback = components["schemas"]["Feedback"];

/** 404 `feedback_not_ready` means "retry after details.retry_after_ms", not "missing". */
export function getFeedback(token: string, sessionId: string) {
  return call<Feedback>("GET", `/sessions/${encodeURIComponent(sessionId)}/feedback`, token);
}

/** UX-3. A rating of the tutor's prose, stored beside it. */
export function rateFeedback(token: string, sessionId: string, wasHelpful: boolean) {
  return call<null>("POST", `/sessions/${encodeURIComponent(sessionId)}/feedback/rating`, token,
                    { was_helpful: wasHelpful });
}
