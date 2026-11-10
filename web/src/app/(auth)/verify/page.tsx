import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";
import { ResendVerification } from "@/components/auth/ResetForms";
import s from "@/components/auth/auth.module.css";
import { Banner } from "@/components/ui";
import { currentUser } from "@/lib/supabase/server";
import { normaliseEmail } from "@/lib/validation";

export const metadata: Metadata = { title: "Verify your email" };

/**
 * S-06 · Email verification.
 *
 * Reachable without a session: when the project requires confirmation, signup
 * creates no session until the link is clicked, and the person still needs
 * this page (and its Resend) in the meantime. Already verified → dashboard,
 * silently.
 *
 * Unverified users may complete one case (PRD FR-1.2). That block belongs to
 * the start of a second case — T-033/T-034 — never to this page.
 */
export default async function VerifyPage({ searchParams }: {
  searchParams: Promise<{ email?: string; error?: string }>;
}) {
  const { email: queryEmail, error } = await searchParams;
  const user = await currentUser().catch(() => null);
  if (user?.email_confirmed_at) redirect("/dashboard");

  const email = user?.email ?? (queryEmail ? normaliseEmail(queryEmail) : null);

  return (
    <div className={s.center}>
      <h1 className={s.title}>Verify your email</h1>
      {error === "expired" ? (
        <Banner tone="warning">That link has expired. Send a new one below.</Banner>
      ) : email ? (
        <p className={s.lede}>We sent a link to <strong>{email}</strong>.</p>
      ) : (
        <p className={s.lede}>Check your inbox for the link we sent you.</p>
      )}
      {email && <ResendVerification email={email} />}
      <p className={s.footer}>Wrong address? <Link href="/signup">Change it</Link></p>
    </div>
  );
}
