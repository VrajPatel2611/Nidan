import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { AppHeader } from "@/components/app/AppHeader";
import { ProgressView } from "@/components/app/ProgressView";
import s from "@/components/app/app.module.css";
import { Banner } from "@/components/ui";
import { getProfile, getProgress } from "@/lib/api";
import { buildDashboard } from "@/lib/dashboard";
import { loginRedirect } from "@/lib/redirects";
import { accessToken, currentUser } from "@/lib/supabase/server";

export const metadata: Metadata = { title: "Progress" };

/** S-16 · Progress — computed by the API on read, from the learner's own results. */
export default async function ProgressPage() {
  const token = await accessToken();
  if (!token) redirect(loginRedirect("/progress"));

  const [profile, progress, user] = await Promise.all([getProfile(token), getProgress(token), currentUser()]);
  if (!profile.ok && profile.status === 404) redirect("/welcome");

  const allowance = profile.ok ? buildDashboard({
    tier: profile.data.subscription_tier, remaining: profile.data.sessions_remaining_this_month,
    resetsAt: profile.data.allowance_resets_at, sessions: [], now: new Date(),
  }).allowance : null;

  return (
    <div className={s.page}>
      <AppHeader active="progress" name={profile.ok ? profile.data.display_name : null} email={user?.email} allowance={allowance} />
      <main className={s.main}>
        <h1 className={s.pageTitle}>Progress</h1>
        {progress.ok ? <ProgressView p={progress.data} />
          : <Banner tone="error">We can&apos;t load your progress right now. Please refresh in a moment.</Banner>}
      </main>
    </div>
  );
}
