"use client";

import { useActionState } from "react";
import { signInWithProvider, type FormState } from "@/app/(auth)/actions";
import { Banner, Button } from "@/components/ui";
import { CarriedFields } from "./fields";
import s from "./auth.module.css";

/** Google and Apple, above the email form — "most users take it" (S-02). */
export function OAuthButtons({ next }: { next?: string | null }) {
  const [state, action, pending] = useActionState<FormState, FormData>(signInWithProvider, {});
  return (
    <>
      {state.banner && <Banner tone={state.banner.tone}>{state.banner.text}</Banner>}
      <form action={action} className={s.oauth}>
        <CarriedFields next={next} />
        <Button type="submit" variant="secondary" name="provider" value="google" disabled={pending}>
          Google
        </Button>
        <Button type="submit" variant="secondary" name="provider" value="apple" disabled={pending}>
          Apple
        </Button>
      </form>
    </>
  );
}
