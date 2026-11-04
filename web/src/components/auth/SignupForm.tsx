"use client";

import Link from "next/link";
import { useActionState } from "react";
import { signUp, type FormState } from "@/app/(auth)/actions";
import { Banner, Button, TextInput } from "@/components/ui";
import { CarriedFields, PasswordField, formatWait, useCountdown } from "./fields";
import { OAuthButtons } from "./OAuthButtons";
import s from "./auth.module.css";

export function SignupForm({ next, anonymousId }: { next: string | null; anonymousId: string | null }) {
  const [state, action, pending] = useActionState<FormState, FormData>(signUp, {});
  const wait = useCountdown(state.retryUntil);

  return (
    <>
      <h1 className={s.title}>Create your account</h1>
      <p className={s.lede}>Practise clinical reasoning and track how you improve.</p>

      {anonymousId && <Banner tone="info">Your case result will be saved to your new account.</Banner>}

      <OAuthButtons next={next} />
      <div className={s.divider}>or</div>

      {state.banner && <Banner tone={state.banner.tone}>{state.banner.text}{wait > 0 && ` (${formatWait(wait)})`}</Banner>}

      <form action={action} noValidate>
        <CarriedFields next={next} anonymousId={anonymousId} />
        <TextInput name="email" label="Email" type="email" autoComplete="email" required autoFocus
                   defaultValue={state.email} error={state.fieldErrors?.email} />
        <PasswordField autoComplete="new-password" hint="At least 8 characters"
                       error={state.fieldErrors?.password} />
        <Button type="submit" block loading={pending} loadingLabel="Creating account…" disabled={wait > 0}>
          Create account
        </Button>
      </form>

      <p className={s.fine}>By creating an account you agree to our Terms and Privacy Policy.</p>
      <p className={s.footer}>Already have an account? <Link href={next ? `/login?next=${encodeURIComponent(next)}` : "/login"}>Log in</Link></p>
    </>
  );
}
