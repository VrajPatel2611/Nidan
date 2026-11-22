import "server-only";
import { redirect } from "next/navigation";
import { getSession, type Session } from "@/lib/api";
import { loginRedirect } from "@/lib/redirects";
import { accessToken } from "@/lib/supabase/server";

/**
 * The session for S-09 and S-10, or a redirect. Signed-in only for now: the
 * API's consultation endpoints all require an account, and the anonymous trial
 * can start a session but not continue it through /v1 (handoff V-10).
 */
export async function loadActiveSession(id: string, here: string): Promise<{ token: string; session: Session }> {
  const token = await accessToken();
  if (!token) redirect(loginRedirect(here));

  const res = await getSession(token, id);
  if (!res.ok) redirect("/dashboard");                 // not theirs, or not there — the same answer
  if (res.data.status === "completed") redirect(`/case/${encodeURIComponent(id)}/feedback`);
  if (res.data.status !== "active") redirect("/dashboard");
  return { token, session: res.data };
}
