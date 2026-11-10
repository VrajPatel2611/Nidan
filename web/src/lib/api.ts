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
