import type { Metadata } from "next";
import { cookies } from "next/headers";
import { SignupForm } from "@/components/auth/SignupForm";
import { safeNext } from "@/lib/redirects";

export const metadata: Metadata = { title: "Create your account" };

/** S-02 · Signup — public. */
export default async function SignupPage({ searchParams }: { searchParams: Promise<{ next?: string }> }) {
  const { next } = await searchParams;
  // Set by the Flask trial routes; its presence means there is a result to claim.
  const anonymousId = (await cookies()).get("anonymous_id")?.value ?? null;
  return <SignupForm next={safeNext(next)} anonymousId={anonymousId} />;
}
