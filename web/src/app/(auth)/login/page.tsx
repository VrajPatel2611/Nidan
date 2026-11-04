import type { Metadata } from "next";
import { cookies } from "next/headers";
import { LoginForm } from "@/components/auth/LoginForm";
import { safeNext } from "@/lib/redirects";

export const metadata: Metadata = { title: "Log in" };

/** S-03 · Login — public. `?error=callback` is S-22's "Code exchange failed". */
export default async function LoginPage({ searchParams }: {
  searchParams: Promise<{ next?: string; error?: string }>;
}) {
  const { next, error } = await searchParams;
  const anonymousId = (await cookies()).get("anonymous_id")?.value ?? null;
  return <LoginForm next={safeNext(next)} anonymousId={anonymousId} callbackFailed={error === "callback"} />;
}
