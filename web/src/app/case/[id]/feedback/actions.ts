"use server";

import { rateFeedback } from "@/lib/api";
import { accessToken } from "@/lib/supabase/server";

/** UX-3 "Was this helpful?" — checks the user itself; /case/* is public to the proxy. */
export async function rate(sessionId: string, wasHelpful: boolean): Promise<{ ok: boolean }> {
  const token = await accessToken();
  if (!token) return { ok: false };
  const res = await rateFeedback(token, sessionId, wasHelpful);
  return { ok: res.ok };
}
