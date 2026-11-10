/**
 * Which paths need a session (UX_SPEC §6.1.4). Everything not listed here is
 * protected — a new page is private until someone decides otherwise, which is
 * the safe way round to forget.
 */
const PUBLIC_EXACT = new Set(["/", "/login", "/signup", "/reset", "/verify", "/auth/callback"]);

// Trial routes are public but session-aware: /case/{id} works with only the
// anonymous trial cookie (§6.1.4). Built in T-034.
const PUBLIC_PREFIXES = ["/case/"];

export function isPublicPath(pathname: string): boolean {
  return PUBLIC_EXACT.has(pathname) || PUBLIC_PREFIXES.some((p) => pathname.startsWith(p));
}

/** Pages a signed-in person has no reason to see; they go to the dashboard. */
export const SIGNED_OUT_ONLY = new Set(["/login", "/signup"]);
