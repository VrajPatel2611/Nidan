import type { Metadata } from "next";
import { RequestResetForm } from "@/components/auth/ResetForms";

export const metadata: Metadata = { title: "Reset your password" };

/** S-04 · Request a reset — public. `?error=expired` comes from an old recovery link. */
export default async function ResetPage({ searchParams }: { searchParams: Promise<{ error?: string }> }) {
  const { error } = await searchParams;
  return <RequestResetForm expired={error === "expired"} />;
}
