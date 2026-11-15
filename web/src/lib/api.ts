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
export type SessionSummary = NonNullable<SessionPage["items"]>[number];
export type Session = components["schemas"]["Session"];
export type Progress = components["schemas"]["Progress"];
export type ApiError = components["schemas"]["Error"];

export type ApiResult<T> =
  | { ok: true; status: number; data: T }
  | { ok: false; status: number; error: ApiError["error"] };

async function call<T>(method: string, path: string, token: string, body?: unknown): Promise<ApiResult<T>> {
  let res: Response;
  try {
    res = await fetch(`${env.apiUrl()}${path}`, {
      method,
      headers: {
        Authorization: `Bearer ${token}`,
        Accept: "application/json",
        ...(body === undefined ? {} : { "Content-Type": "application/json" }),
      },
      body: body === undefined ? undefined : JSON.stringify(body),
      cache: "no-store",
    });
  } catch {
    return { ok: false, status: 0, error: { code: "service_unavailable", message: "The Nidan API could not be reached." } };
  }
  const json = await res.json().catch(() => null);
  if (res.ok) return { ok: true, status: res.status, data: json as T };
  return {
    ok: false, status: res.status,
    error: (json as ApiError | null)?.error ?? { code: "internal_error", message: `HTTP ${res.status}` },
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

/** Newest first (`openapi.yaml` GET /sessions). The dashboard reads one page. */
export function listSessions(token: string, limit = 20) {
  return call<SessionPage>("GET", `/sessions?limit=${limit}`, token);
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
