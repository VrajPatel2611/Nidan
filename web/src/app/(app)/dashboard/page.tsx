import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { AppHeader } from "@/components/app/AppHeader";
import { DashboardView } from "@/components/app/DashboardView";
import s from "@/components/app/app.module.css";
import { Banner } from "@/components/ui";
import { getProfile, getProgress, listSessions } from "@/lib/api";
import { buildDashboard } from "@/lib/dashboard";
import { loginRedirect } from "@/lib/redirects";
import { accessToken, currentUser } from "@/lib/supabase/server";

export const metadata: Metadata = { title: "Dashboard" };

/**
 * S-08 · Dashboard (T-033). Three reads in parallel, one pure function
 * (`buildDashboard`) decides the state, and the view renders it.
 */
export default async function DashboardPage() {
  const token = await accessToken();
  if (!token) redirect(loginRedirect("/dashboard"));

  const [profile, sessions, progress, user] = await Promise.all([
    getProfile(token), listSessions(token), getProgress(token), currentUser(),
  ]);

  // No profile yet: sign-in could not create one. /welcome retries.
  if (!profile.ok && profile.status === 404) redirect("/welcome");

  if (!profile.ok || !sessions.ok) {
    return (
      <div className={s.page}>
        <AppHeader active="dashboard" email={user?.email} />
        <main className={s.main}>
          <Banner tone="error">We can&apos;t load your dashboard right now. Please refresh in a moment.</Banner>
        </main>
      </div>
    );
  }

  const d = buildDashboard({
    displayName: profile.data.display_name,
    timezone: profile.data.timezone,
    tier: profile.data.subscription_tier,
    remaining: profile.data.sessions_remaining_this_month,
    resetsAt: profile.data.allowance_resets_at,
    sessions: sessions.data.items ?? [],
    progress: progress.ok ? progress.data : null,
    now: new Date(),
  });

  return (
    <div className={s.page}>
      <AppHeader active="dashboard" name={profile.data.display_name} email={user?.email} allowance={d.allowance} />
      <main className={s.main}>
        <DashboardView d={d} />
      </main>
    </div>
  );
}
