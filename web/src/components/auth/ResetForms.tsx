"use client";

import Link from "next/link";
import { useActionState } from "react";
import { requestReset, resendVerification, setNewPassword, type FormState } from "@/app/(auth)/actions";
import { Banner, Button, TextInput } from "@/components/ui";
import { PasswordField, useCountdown } from "./fields";
import s from "./auth.module.css";

/** S-04 · the same confirmation whether or not the address has an account. */
export function RequestResetForm({ expired }: { expired: boolean }) {
  const [state, action, pending] = useActionState<FormState, FormData>(requestReset, {});

  if (state.sent) {
    return (
      <div className={s.center}>
        <h1 className={s.title}>Check your inbox</h1>
        <p className={s.lede}>
          If an account exists for <strong>{state.sent}</strong>, we&apos;ve sent a reset link.
          It expires in 60 minutes.
        </p>
        <Link href="/login">Back to log in</Link>
      </div>
    );
  }

  return (
    <>
      <h1 className={s.title}>Reset your password</h1>
      <p className={s.lede}>We&apos;ll email you a link to set a new one.</p>
      {expired && <Banner tone="warning">This link has expired. Request a new one below.</Banner>}
      <form action={action} noValidate>
        <TextInput name="email" label="Email" type="email" autoComplete="email" required autoFocus
                   defaultValue={state.email} error={state.fieldErrors?.email} />
        <Button type="submit" block loading={pending} loadingLabel="Sending…">Send reset link</Button>
      </form>
      <p className={s.footer}><Link href="/login">Back to log in</Link></p>
    </>
  );
}

/** S-05 · set a new password. Success signs out every session and returns to login. */
export function NewPasswordForm() {
  const [state, action, pending] = useActionState<FormState, FormData>(setNewPassword, {});
  return (
    <>
      <h1 className={s.title}>Choose a new password</h1>
      {state.banner && (
        <Banner tone={state.banner.tone}>
          {state.banner.text} <Link href="/reset">Request a new one</Link>
        </Banner>
      )}
      <form action={action} noValidate>
        <PasswordField autoComplete="new-password" label="New password" hint="At least 8 characters"
                       error={state.fieldErrors?.password} />
        <PasswordField name="confirm" autoComplete="new-password" label="Confirm new password"
                       error={state.fieldErrors?.confirm} />
        <Button type="submit" block loading={pending} loadingLabel="Updating…">Update password</Button>
      </form>
    </>
  );
}

/** S-06 · Resend is disabled for 60 s after each send; Supabase caps the day. */
export function ResendVerification({ email }: { email: string }) {
  const [state, action, pending] = useActionState<FormState, FormData>(resendVerification, {});
  const wait = useCountdown(state.retryUntil);
  return (
    <form action={action} className={s.actions}>
      <input type="hidden" name="email" value={email} />
      {state.banner && <Banner tone={state.banner.tone}>{state.banner.text}</Banner>}
      <Button type="submit" variant="secondary" loading={pending} disabled={wait > 0}>
        {wait > 0 ? `Resend (${wait}s)` : "Resend"}
      </Button>
    </form>
  );
}
