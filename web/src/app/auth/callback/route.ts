/**
 * S-22 · OAuth callback — and the landing point for every Supabase email link
 * (verification, password recovery), which arrive the same way: `?code=`.
 *
 * Exchange the code, create or fetch the profile, redirect. **Every path ends
 * in a redirect** — a user must never be left on this screen (UX_SPEC §6.5).
 */
import { NextResponse, type NextRequest } from "next/server";
import { createProfile } from "@/lib/api";
import { landingPath, safeNext } from "@/lib/redirects";
import { createSupabase } from "@/lib/supabase/server";

export async function GET(request: NextRequest) {
  const params = request.nextUrl.searchParams;
  const to = (path: string) => NextResponse.redirect(new URL(path, request.nextUrl.origin));

  if (params.get("error") === "access_denied") return to("/login?toast=signin-cancelled");

  const code = params.get("code");
  if (!code) return to("/login?error=callback");

  // Set by the actions that send email links, so an expired link can be
  // answered on the screen it belongs to (S-05, S-06).
  const type = params.get("type");

  const supabase = await createSupabase();
  const { data, error } = await supabase.auth.exchangeCodeForSession(code);
  if (error || !data.session) {
    if (type === "recovery") return to("/reset?error=expired");
    if (type === "signup") return to("/verify?error=expired");
    return to("/login?error=callback");
  }

  const next = safeNext(params.get("next"));
  // A recovery link goes straight to "set a new password"; nothing else applies.
  if (type === "recovery") return to("/reset/new");

  const anonymousId = request.cookies.get("anonymous_id")?.value || null;
  const profile = await createProfile(data.session.access_token, {
    anonymous_id: anonymousId,
    timezone: params.get("tz") || undefined,
  });

  // A failed POST /me leaves a valid session and no profile; /welcome retries.
  const landing = landingPath({
    next,
    hasProfile: profile.ok,
    onboarded: profile.ok && Boolean(profile.data.onboarded_at),
    claimedSessionIds: profile.ok ? profile.data.claimed_session_ids : undefined,
  });
  // S-06 "Verified": a toast, then the usual landing.
  if (type !== "signup") return to(landing);
  return to(`${landing}${landing.includes("?") ? "&" : "?"}toast=email-verified`);
}
