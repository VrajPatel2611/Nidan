"use server";

/**
 * Every auth call, on the server (UX_SPEC §6.1). The browser never holds a
 * Supabase client, so the session lives only in httpOnly cookies (§6.1.3).
 *
 * Copy is the spec's. Two rules shape it: never confirm whether an account
 * exists (S-02 "already registered", S-03 "invalid credentials", S-04), and
 * never make a cancelled OAuth look like a failure.
 */
import { redirect } from "next/navigation";
import { createProfile } from "@/lib/api";
import { env } from "@/lib/env";
import { landingPath, safeNext } from "@/lib/redirects";
import { createSupabase, currentUser } from "@/lib/supabase/server";
import { emailError, normaliseEmail, passwordError } from "@/lib/validation";

export type FormState = {
  fieldErrors?: { email?: string; password?: string; confirm?: string };
  banner?: { tone: "error" | "info" | "success"; text: string };
  /** When a rate-limited form unlocks, as epoch milliseconds (S-03, S-06). */
  retryUntil?: number;
  /** S-04: shown in place of the form after a reset request. */
  sent?: string;
  email?: string;
};

const RATE_LIMIT_S = 15 * 60;
const field = (fd: FormData, name: string) => String(fd.get(name) ?? "");

function callbackUrl(params: Record<string, string | null | undefined>): string {
  const url = new URL("/auth/callback", env.siteUrl());
  for (const [k, v] of Object.entries(params)) if (v) url.searchParams.set(k, v);
  return url.toString();
}

function isRateLimit(err: { status?: number; code?: string }): boolean {
  return err.status === 429 || Boolean(err.code?.startsWith("over_"));
}

// ── S-02 · Signup ─────────────────────────────────────────────────────

export async function signUp(_: FormState, fd: FormData): Promise<FormState> {
  const email = normaliseEmail(field(fd, "email"));
  const password = field(fd, "password");
  const errors = { email: emailError(email) ?? undefined, password: passwordError(password) ?? undefined };
  if (errors.email || errors.password) return { fieldErrors: errors, email };

  const supabase = await createSupabase();
  const { data, error } = await supabase.auth.signUp({
    email, password,
    options: { emailRedirectTo: callbackUrl({ type: "signup", next: safeNext(field(fd, "next")), tz: field(fd, "tz") }) },
  });

  if (error) {
    if (isRateLimit(error)) return { banner: { tone: "error", text: "Too many attempts. Try again in 15 minutes." }, retryUntil: Date.now() + RATE_LIMIT_S * 1000, email };
    if (error.code === "weak_password") {
      return { fieldErrors: { password: "That password is too common — try something less predictable" }, email };
    }
    // "Email already registered" and every other refusal: the same generic
    // outcome, so the form cannot be used to test which addresses have accounts.
    if (error.code !== "user_already_exists") {
      return { banner: { tone: "error", text: "We couldn't create your account. Please try again." }, email };
    }
  }

  if (data?.session) {
    // Email confirmation is off for this project: the session exists now.
    await createProfile(data.session.access_token, {
      anonymous_id: fd.get("anonymous_id") ? field(fd, "anonymous_id") : null,
      timezone: field(fd, "tz") || undefined,
    });
  }
  redirect(`/verify?email=${encodeURIComponent(email)}`);
}

// ── S-03 · Login ──────────────────────────────────────────────────────

export async function logIn(_: FormState, fd: FormData): Promise<FormState> {
  const email = normaliseEmail(field(fd, "email"));
  const password = field(fd, "password");
  if (emailError(email) || !password) {
    return { fieldErrors: { email: emailError(email) ?? undefined, password: password ? undefined : "Enter your password" }, email };
  }

  const supabase = await createSupabase();
  const { data, error } = await supabase.auth.signInWithPassword({ email, password });
  if (error) {
    if (isRateLimit(error)) return { banner: { tone: "error", text: "Too many attempts. Try again in 15 minutes." }, retryUntil: Date.now() + RATE_LIMIT_S * 1000, email };
    if (error.code === "email_not_confirmed") redirect(`/verify?email=${encodeURIComponent(email)}`);
    // Never say which of the two was wrong (S-03); a deleted account reads the same.
    return { banner: { tone: "error", text: "That email or password doesn't match." }, email };
  }

  const profile = await createProfile(data.session.access_token, {
    anonymous_id: fd.get("anonymous_id") ? field(fd, "anonymous_id") : null,
    timezone: field(fd, "tz") || undefined,
  });
  if (!data.user.email_confirmed_at) redirect(`/verify?email=${encodeURIComponent(email)}`);

  redirect(landingPath({
    next: field(fd, "next"),
    hasProfile: profile.ok,
    onboarded: profile.ok && Boolean(profile.data.onboarded_at),
    claimedSessionIds: profile.ok ? profile.data.claimed_session_ids : undefined,
  }));
}

// ── OAuth (S-02, S-03 → S-22) ─────────────────────────────────────────

export async function signInWithProvider(_: FormState, fd: FormData): Promise<FormState> {
  const provider = field(fd, "provider");
  if (provider !== "google" && provider !== "apple") return {};
  const name = provider === "google" ? "Google" : "Apple";

  const supabase = await createSupabase();
  const { data, error } = await supabase.auth.signInWithOAuth({
    provider,
    options: { redirectTo: callbackUrl({ next: safeNext(field(fd, "next")), tz: field(fd, "tz") }) },
  });
  if (error || !data.url) {
    return { banner: { tone: "error", text: `We couldn't reach ${name}. Try again or use email.` } };
  }
  redirect(data.url);
}

// ── S-04 · Request a reset ────────────────────────────────────────────

export async function requestReset(_: FormState, fd: FormData): Promise<FormState> {
  const email = normaliseEmail(field(fd, "email"));
  if (emailError(email)) return { fieldErrors: { email: emailError(email)! }, email };

  const supabase = await createSupabase();
  // The result is deliberately ignored: the confirmation is the same whether
  // or not the address has an account (S-04).
  await supabase.auth.resetPasswordForEmail(email, { redirectTo: callbackUrl({ type: "recovery" }) });
  return { sent: email };
}

// ── S-05 · Set a new password ─────────────────────────────────────────

export async function setNewPassword(_: FormState, fd: FormData): Promise<FormState> {
  if (!(await currentUser())) {
    return { banner: { tone: "error", text: "This link has expired." } };
  }
  const password = field(fd, "password");
  const confirm = field(fd, "confirm");
  const errors = {
    password: passwordError(password) ?? undefined,
    confirm: password === confirm ? undefined : "Passwords don't match",
  };
  if (errors.password || errors.confirm) return { fieldErrors: errors };

  const supabase = await createSupabase();
  const { error } = await supabase.auth.updateUser({ password });
  if (error) {
    if (error.code === "weak_password" || error.code === "same_password") {
      return { fieldErrors: { password: "That password is too common — try something less predictable" } };
    }
    return { banner: { tone: "error", text: "We couldn't update your password. Please try again." } };
  }
  // Every session, this one included: if the reset was prompted by a
  // compromise, leaving other devices signed in defeats the purpose (S-05).
  await supabase.auth.signOut({ scope: "global" });
  redirect("/login?toast=password-updated");
}

// ── S-06 · Resend verification ────────────────────────────────────────

export async function resendVerification(_: FormState, fd: FormData): Promise<FormState> {
  const email = normaliseEmail(field(fd, "email"));
  if (emailError(email)) return { banner: { tone: "error", text: "Enter a valid email address" } };

  const supabase = await createSupabase();
  const { error } = await supabase.auth.resend({
    type: "signup", email, options: { emailRedirectTo: callbackUrl({ type: "signup" }) },
  });
  if (error && isRateLimit(error)) {
    return { banner: { tone: "error", text: "You've asked for a lot of links today. Try again tomorrow." }, email };
  }
  return { banner: { tone: "success", text: "Sent. Check your inbox." }, retryUntil: Date.now() + 60_000, email };
}
