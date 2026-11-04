import type { Metadata } from "next";
import { cookies } from "next/headers";
import s from "@/components/auth/auth.module.css";
import { Banner, Card } from "@/components/ui";
import { createProfile } from "@/lib/api";
import { accessToken } from "@/lib/supabase/server";

export const metadata: Metadata = { title: "Welcome" };

/**
 * Placeholder: S-07 · Onboarding is T-033. What T-032 needs from it is the
 * retry S-22 relies on: if POST /me failed during sign-in, the session is valid
 * but the profile is missing, and this page tries again. It is idempotent.
 */
export default async function Welcome() {
  const token = await accessToken();
  const anonymousId = (await cookies()).get("anonymous_id")?.value ?? null;
  const profile = token ? await createProfile(token, { anonymous_id: anonymousId }) : null;

  return (
    <main className={s.shell}>
      <Card variant="elevated" className={s.panel}>
        <h1>Welcome to Nidan</h1>
        {profile && !profile.ok ? (
          <Banner tone="error">We couldn&apos;t finish setting up your account. Refresh to try again.</Banner>
        ) : (
          <p>Onboarding arrives in T-033.</p>
        )}
      </Card>
    </main>
  );
}
