"use server";

/**
 * The consultation's writes (T-034). Each takes the token itself — `/case/*`
 * is public to the proxy (§6.1.4, for the trial), so these must not assume it
 * checked anyone.
 *
 * They return data, never assessment state: the API sends none (CT-1, CT-2),
 * and nothing here adds any.
 */
import { askQuestion, order as orderItem, submitDiagnosis } from "@/lib/api";
import { accessToken } from "@/lib/supabase/server";

export type Refusal = { ok: false; code?: string; status: number; retryAfter?: number };

const signedOut: Refusal = { ok: false, code: "unauthenticated", status: 401 };

export async function ask(sessionId: string, text: string):
  Promise<{ ok: true; reply: string; question: string } | Refusal> {
  const token = await accessToken();
  if (!token) return signedOut;
  const res = await askQuestion(token, sessionId, text);
  if (!res.ok) return { ok: false, code: res.error.code, status: res.status, retryAfter: res.retryAfter };
  return { ok: true, question: res.data.question?.text ?? text, reply: res.data.reply?.text ?? "" };
}

export async function orderOne(sessionId: string, kind: "examinations" | "investigations", key: string):
  Promise<{ ok: true; key: string; label: string; text: string; at: string } | Refusal> {
  const token = await accessToken();
  if (!token) return signedOut;
  const res = await orderItem(token, sessionId, kind, key);
  if (!res.ok) return { ok: false, code: res.error.code, status: res.status };
  return { ok: true, key: res.data.key ?? key, label: res.data.label ?? key,
           text: res.data.result ?? "", at: res.data.at ?? new Date().toISOString() };
}

/** Irreversible. The client keeps one Idempotency-Key per attempt, so a retry is the same conclusion. */
export async function diagnose(sessionId: string, text: string, idempotencyKey: string):
  Promise<{ ok: true } | Refusal> {
  const token = await accessToken();
  if (!token) return signedOut;
  const res = await submitDiagnosis(token, sessionId, text, idempotencyKey);
  if (!res.ok) return { ok: false, code: res.error.code, status: res.status };
  return { ok: true };
}
