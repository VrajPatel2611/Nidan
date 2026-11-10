/**
 * Where a person lands after authenticating (UX_SPEC §6.1.5).
 *
 * Deterministic, in the spec's priority order. Pure, so it is tested without a
 * browser: getting this wrong is "the most common cause of a disorienting
 * first session".
 */

/**
 * `?next=` if it is a same-origin relative path, otherwise null.
 *
 * Open-redirect protection: an absolute URL, a protocol-relative `//evil.com`,
 * a backslash trick (`/\evil.com`, which some browsers read as `//`), or a
 * control character is discarded rather than followed.
 */
export function safeNext(raw: string | null | undefined): string | null {
  if (!raw) return null;
  let path: string;
  try { path = decodeURIComponent(raw); } catch { return null; }
  if (!path.startsWith("/") || path.startsWith("//") || path.startsWith("/\\")) return null;
  if (/[\u0000-\u001f\\]/.test(path)) return null;
  try {
    const url = new URL(path, "https://nidan.invalid");
    if (url.origin !== "https://nidan.invalid") return null;
    return url.pathname + url.search + url.hash;
  } catch {
    return null;
  }
}

export type LandingFacts = {
  next?: string | null;
  /** False when POST /me failed: the session is valid but there is no profile yet. */
  hasProfile: boolean;
  onboarded: boolean;
  /** `claimed_session_ids` from POST /me — a trial taken before signing up. */
  claimedSessionIds?: string[];
};

export function landingPath(f: LandingFacts): string {
  const next = safeNext(f.next);
  if (next) return next;
  if (!f.hasProfile) return "/welcome";              // /welcome retries POST /me
  if (!f.onboarded) return "/welcome";
  const claimed = f.claimedSessionIds?.[0];
  if (claimed) return `/case/${encodeURIComponent(claimed)}/feedback`;   // show them what they saved
  return "/dashboard";                                // the resume banner lives there
}

/** `/login?next=…` for a protected path, as the proxy redirects (§6.1.4). */
export function loginRedirect(pathWithQuery: string): string {
  return `/login?next=${encodeURIComponent(pathWithQuery)}`;
}
