import type { CookieOptionsWithName } from "@supabase/ssr";

/**
 * The session cookies, as UX_SPEC §6.1.3 decides them.
 *
 * **httpOnly**, so an XSS bug cannot read the refresh token — which is why no
 * part of this app uses the browser Supabase client: every auth call is a
 * server action, route handler or the proxy. **SameSite=Lax**, not Strict,
 * because Strict drops the cookie on the OAuth callback's cross-site redirect.
 * **Secure** everywhere but plain-http localhost.
 */
export function sessionCookieOptions(): CookieOptionsWithName {
  return {
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    path: "/",
  };
}
