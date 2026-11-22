import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { AppHeader } from "@/components/app/AppHeader";
import { HistoryList } from "@/components/app/HistoryList";
import s from "@/components/app/app.module.css";
import { Banner } from "@/components/ui";
import { getProfile, listSessions } from "@/lib/api";
import { buildDashboard } from "@/lib/dashboard";
import { loginRedirect } from "@/lib/redirects";
import { accessToken, currentUser } from "@/lib/supabase/server";

export const metadata: Metadata = { title: "History" };

/** S-14 · History — 20 a page, by cursor (API_CONTRACT §2.5). */
export default async function HistoryPage({ searchParams }: { searchParams: Promise<{ cursor?: string }> }) {
  const { cursor } = await searchParams;
  const token = await accessToken();
  if (!token) redirect(loginRedirect(cursor ? `/history?cursor=${encodeURIComponent(cursor)}` : "/history"));

  const [profile, page, user] = await Promise.all([getProfile(token), listSessions(token, 20, cursor), currentUser()]);
  if (!profile.ok && profile.status === 404) redirect("/welcome");

  // The header's allowance comes from the same rules as the dashboard's.
  const allowance = profile.ok ? buildDashboard({
    tier: profile.data.subscription_tier, remaining: profile.data.sessions_remaining_this_month,
    resetsAt: profile.data.allowance_resets_at, sessions: [], now: new Date(),
  }).allowance : null;

  // An unreadable cursor is a 422; the first page is the answer to it. Only
  // with a cursor — redirecting a failed first page to itself would loop.
  if (!page.ok && page.status === 422 && cursor) redirect("/history");

  const next = page.ok ? page.data.pagination?.next_cursor : null;
  return (
    <div className={s.page}>
      <AppHeader active="history" name={profile.ok ? profile.data.display_name : null} email={user?.email} allowance={allowance} />
      <main className={s.main}>
        <h1 className={s.pageTitle}>History</h1>
        {!page.ok ? (
          <Banner tone="error">We can&apos;t load your history right now. Please refresh in a moment.</Banner>
        ) : (
          <HistoryList rows={page.data.data ?? []} now={new Date()} timezone={profile.ok ? profile.data.timezone : null}
                       olderHref={next ? `/history?cursor=${encodeURIComponent(next)}` : null}
                       newestHref={cursor ? "/history" : null} />
        )}
      </main>
    </div>
  );
}
