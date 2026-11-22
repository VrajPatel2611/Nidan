import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";
import { FeedbackPending } from "@/components/feedback/FeedbackPending";
import { FeedbackView } from "@/components/feedback/FeedbackView";
import s from "@/components/feedback/feedback.module.css";
import { getFeedback, getSession } from "@/lib/api";
import { loginRedirect } from "@/lib/redirects";
import { accessToken } from "@/lib/supabase/server";

export const metadata: Metadata = { title: "Session" };

/**
 * S-15 · Session detail: S-13's layout, read-only, with a "Viewed {date}"
 * header and a link back. The date is the consultation's — the only date the
 * session carries.
 */
export default async function SessionDetail({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const token = await accessToken();
  if (!token) redirect(loginRedirect(`/history/${id}`));

  const [feedback, session] = await Promise.all([getFeedback(token, id), getSession(token, id)]);
  if (!feedback.ok) {
    if (feedback.error.code === "feedback_not_ready") return <FeedbackPending retryAfterMs={1500} />;
    if (feedback.error.code === "session_not_concluded") redirect(`/case/${encodeURIComponent(id)}`);
    redirect("/history");
  }

  const when = session.ok && session.data.started_at
    ? new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "long", year: "numeric" }).format(new Date(session.data.started_at))
    : null;

  return (
    <div className={s.page}>
      <div className={s.main} style={{ paddingBottom: 0 }}>
        <Link href="/history">← Back to history</Link>
        {when && <p className={s.sectionMeta} style={{ margin: "var(--s-2) 0 0" }}>Viewed {when}</p>}
      </div>
      <FeedbackView sessionId={id} f={feedback.data} readOnly />
    </div>
  );
}
