import type { Metadata } from "next";
import { NewPasswordForm } from "@/components/auth/ResetForms";

export const metadata: Metadata = { title: "Choose a new password" };

/**
 * S-05 · Set a new password.
 *
 * The spec's route is `/reset/{token}`. With Supabase's PKCE flow the token is
 * exchanged at /auth/callback, which opens a recovery session and sends the
 * person here — so this page needs a session rather than a token in its URL,
 * and the proxy protects it like any other private page. An expired link never
 * reaches it: the callback sends that to /reset?error=expired.
 */
export default function NewPasswordPage() {
  return <NewPasswordForm />;
}
