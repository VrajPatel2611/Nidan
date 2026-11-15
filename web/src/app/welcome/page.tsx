import type { Metadata } from "next";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import s from "@/components/auth/auth.module.css";
import { Onboarding } from "@/components/onboarding/Onboarding";
import { Banner } from "@/components/ui";
import { createProfile } from "@/lib/api";
import { loginRedirect } from "@/lib/redirects";
import { accessToken } from "@/lib/supabase/server";

export const metadata: Metadata = { title: "Welcome" };

/**
 * S-07 · Onboarding.
 *
 * Also the retry S-22 relies on: if POST /me failed during sign-in, the
 * session is valid but the profile is missing, and this page tries again —
 * POST /me is idempotent. Someone already onboarded goes to the dashboard.
 */
export default async function Welcome() {
  const token = await accessToken();
  if (!token) redirect(loginRedirect("/welcome"));

  const anonymousId = (await cookies()).get("anonymous_id")?.value ?? null;
  const profile = await createProfile(token, { anonymous_id: anonymousId });
  if (profile.ok && profile.data.onboarded_at) redirect("/dashboard");

  return (
    <main className={s.shell}>
      {profile.ok ? <Onboarding /> : (
        <div className={s.panel}>
          <Banner tone="error">We couldn&apos;t finish setting up your account. Refresh to try again.</Banner>
        </div>
      )}
    </main>
  );
}
