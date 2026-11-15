"use client";

/**
 * S-07 · Onboarding. Two questions at most (FR-2.6), each skippable (FR-2.7).
 * The year question appears only for roles that have a training year.
 */
import { useActionState, useState } from "react";
import { finishOnboarding, type ActionState } from "@/app/(app)/actions";
import { Banner, Button } from "@/components/ui";
import s from "./onboarding.module.css";

export const ROLES = [
  { value: "medical_student", label: "Medical student" },
  { value: "intern", label: "Intern / F1" },
  { value: "resident", label: "Resident / Registrar" },
  { value: "physician", label: "Physician" },
  { value: "other", label: "Other" },
] as const;

/** Only these have a "year" worth asking about (S-07, step 2). */
export const ROLES_WITH_YEAR = new Set(["medical_student", "intern", "resident"]);

export function Onboarding() {
  const [state, action, pending] = useActionState<ActionState, FormData>(finishOnboarding, {});
  const [role, setRole] = useState<string | null>(null);
  const [step, setStep] = useState<1 | 2>(1);
  const [year, setYear] = useState<string>("");

  const askYear = role !== null && ROLES_WITH_YEAR.has(role);

  return (
    <form action={action} className={s.card}>
      <h1 className={s.title}>Welcome to Nidan</h1>
      <p className={s.lede}>Two quick questions so we can pitch cases at the right level.</p>
      {state.error && <Banner tone="error">{state.error}</Banner>}

      {step === 1 && (
        <fieldset className={s.fieldset}>
          <legend className={s.question}>What best describes you?</legend>
          <div className={s.options}>
            {ROLES.map((r) => (
              <label key={r.value} className={s.option} data-selected={role === r.value || undefined}>
                <input type="radio" name="role" value={r.value} checked={role === r.value}
                       onChange={() => setRole(r.value)} />
                {r.label}
              </label>
            ))}
          </div>
        </fieldset>
      )}

      {step === 2 && (
        <fieldset className={s.fieldset}>
          <input type="hidden" name="role" value={role ?? ""} />
          <legend className={s.question}>What year are you in?</legend>
          <div className={s.years}>
            {["1", "2", "3", "4", "5", "6", "7", "other"].map((y) => (
              <label key={y} className={s.option} data-selected={year === y || undefined}>
                <input type="radio" name="year" value={y === "other" ? "" : y}
                       checked={year === y} onChange={() => setYear(y)} />
                {y === "other" ? "Other" : `Year ${y}`}
              </label>
            ))}
          </div>
        </fieldset>
      )}

      <div className={s.actions}>
        {/* Skipping still ends onboarding. The intent says what is skipped, so
            the server drops it — clearing state here would not reach the form
            data in time. */}
        <Button type="submit" variant="ghost" name="intent" value={step === 1 ? "skip-all" : "skip-year"}
                disabled={pending} formNoValidate>
          Skip
        </Button>
        {step === 1 && askYear ? (
          <Button type="button" onClick={() => setStep(2)}>Next</Button>
        ) : (
          <Button type="submit" name="intent" value="start" loading={pending} loadingLabel="Starting…"
                  disabled={step === 1 && role === null}>
            Start my first case
          </Button>
        )}
      </div>
      <p className={s.step} aria-live="polite">{askYear ? `Step ${step} of 2` : "Step 1 of 1"}</p>
    </form>
  );
}
