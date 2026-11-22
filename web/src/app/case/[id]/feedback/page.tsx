import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { FeedbackPending } from "@/components/feedback/FeedbackPending";
import { FeedbackView } from "@/components/feedback/FeedbackView";
import s from "@/components/feedback/feedback.module.css";
import { getFeedback } from "@/lib/api";
import { loginRedirect } from "@/lib/redirects";
import { accessToken } from "@/lib/supabase/server";

export const metadata: Metadata = { title: "Your feedback" };

/**
 * S-13 · Feedback, or S-12 while it is still being written. Every number is
 * recomputed by the API from the stored result (ADR-0003); only the tutor's
 * prose is read back.
 */
export default async function FeedbackPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const token = await accessToken();
  if (!token) redirect(loginRedirect(`/case/${id}/feedback`));

  const res = await getFeedback(token, id);
  if (!res.ok) {
    if (res.error.code === "feedback_not_ready") {
      const ms = Number((res.error.details as { retry_after_ms?: number } | undefined)?.retry_after_ms) || 1500;
      return <FeedbackPending retryAfterMs={ms} />;
    }
    if (res.error.code === "session_not_concluded") redirect(`/case/${encodeURIComponent(id)}`);
    redirect("/dashboard");                       // not theirs, or not there — the same answer
  }

  return (
    <div className={s.page}>
      <FeedbackView sessionId={id} f={res.data} />
    </div>
  );
}
