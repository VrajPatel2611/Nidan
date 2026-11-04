"use client";

import Link from "next/link";
import { useActionState } from "react";
import { logIn, type FormState } from "@/app/(auth)/actions";
import { Banner, Button, TextInput } from "@/components/ui";
import { CarriedFields, PasswordField, formatWait, useCountdown } from "./fields";
import { OAuthButtons } from "./OAuthButtons";
import s from "./auth.module.css";

export function LoginForm({ next, anonymousId, callbackFailed }: {
  next: string | null; anonymousId: string | null; callbackFailed: boolean;
}) {
  const [state, action, pending] = useActionState<FormState, FormData>(logIn, {});
  const wait = useCountdown(state.retryUntil);

  return (
    <>
      <h1 className={s.title}>Log in</h1>
      {next && <p className={s.lede}>Log in to continue</p>}

      {callbackFailed && !state.banner && (
        <Banner tone="error">Sign-in didn&apos;t complete. Please try again.</Banner>
      )}

      <OAuthButtons next={next} />
      <div className={s.divider}>or</div>

      {state.banner && (
        <Banner tone={state.banner.tone}>
          {state.banner.text}{wait > 0 && ` (${formatWait(wait)})`}
        </Banner>
      )}

      <form action={action} noValidate>
        <CarriedFields next={next} anonymousId={anonymousId} />
        <TextInput name="email" label="Email" type="email" autoComplete="email" required autoFocus
                   defaultValue={state.email} error={state.fieldErrors?.email} />
        <PasswordField autoComplete="current-password" error={state.fieldErrors?.password} />
        <Link href="/reset" className={s.forgot}>Forgot password?</Link>
        <Button type="submit" block loading={pending} loadingLabel="Logging in…" disabled={wait > 0}>
          Log in
        </Button>
      </form>

      <p className={s.footer}>New to Nidan? <Link href={next ? `/signup?next=${encodeURIComponent(next)}` : "/signup"}>Create one</Link></p>
    </>
  );
}
