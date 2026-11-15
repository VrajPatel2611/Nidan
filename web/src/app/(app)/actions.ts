"use server";

/**
 * Onboarding, starting a case and abandoning one (T-033). Every action takes
 * the token itself rather than trusting the proxy — Next runs server actions
 * as POSTs to their page, and a matcher change can drop them out of its reach.
 */
import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";
import { abandonSession, startSession, updateProfile, type ProfileUpdate } from "@/lib/api";
import { loginRedirect } from "@/lib/redirects";
import { accessToken } from "@/lib/supabase/server";

export type ActionState = { error?: string };

const ROLES = new Set(["medical_student", "intern", "resident", "physician", "other"]);

async function tokenOrLogin(back: string): Promise<string> {
  const token = await accessToken();
  if (!token) redirect(loginRedirect(back));
  return token;
}

/**
 * Start a consultation, then go to its preview (S-09). The server picks the
 * case. Each refusal the dashboard can explain becomes a sentence.
 */
async function startAndGo(token: string): Promise<ActionState> {
  const res = await startSession(token);
  if (res.ok) redirect(`/case/${encodeURIComponent(res.data.session_id ?? "")}/preview`);
  switch (res.error.code) {
    case "monthly_limit_reached":
      revalidatePath("/dashboard");
      return { error: "You've used this month's free cases." };
    case "session_already_active":
      revalidatePath("/dashboard");
      return { error: "You already have a consultation in progress — resume or abandon it first." };
    case "no_cases_available":
      return { error: "There are no cases available right now. Please try again later." };
    default:
      return { error: "We couldn't start a case. Please try again." };
  }
}

/**
 * S-07. Answered or skipped, it ends onboarding (`PRD` FR-2.7: skipping never
 * blocks), so `onboarded: true` goes with every submit. "Start my first case"
 * then does exactly that; if it cannot, the dashboard explains why.
 */
export async function finishOnboarding(_: ActionState, fd: FormData): Promise<ActionState> {
  const token = await tokenOrLogin("/welcome");

  const intent = String(fd.get("intent") ?? "");
  const body: ProfileUpdate = { onboarded: true };
  const role = String(fd.get("role") ?? "");
  if (intent !== "skip-all" && ROLES.has(role)) {
    body.professional_role = role as NonNullable<ProfileUpdate["professional_role"]>;
  }
  const year = Number(fd.get("year"));
  if (intent === "start" && Number.isInteger(year) && year >= 1 && year <= 7) body.year_of_training = year;

  const saved = await updateProfile(token, body);
  if (!saved.ok) return { error: "We couldn't save that. Please try again." };

  if (intent === "start") {
    const started = await startAndGo(token);
    if (started.error) redirect("/dashboard");
  }
  redirect("/dashboard");
}

export async function startCase(): Promise<ActionState> {
  return startAndGo(await tokenOrLogin("/dashboard"));
}

/** Confirmed in a modal first (UX_SPEC §5.5): it still uses up the case. */
export async function abandonCase(_: ActionState, fd: FormData): Promise<ActionState> {
  const token = await tokenOrLogin("/dashboard");
  const id = String(fd.get("session_id") ?? "");
  if (!id) return { error: "Nothing to abandon." };
  const res = await abandonSession(token, id);
  if (!res.ok && res.status !== 404) return { error: "We couldn't abandon that consultation. Please try again." };
  revalidatePath("/dashboard");
  return {};
}
