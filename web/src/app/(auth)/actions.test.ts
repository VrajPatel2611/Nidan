/**
 * How the auth actions answer each thing Supabase can say (UX_SPEC S-02…S-06).
 *
 * Supabase is mocked: these test the app's decisions — which copy, which
 * redirect — not Supabase. The two rules under test hardest: never confirm
 * whether an account exists, and never let an outage read as a wrong password.
 */
import { UNREACHABLE } from "@/lib/authCopy";
import { logIn, requestReset, signUp } from "./actions";

const auth = {
  signUp: vi.fn(), signInWithPassword: vi.fn(), resetPasswordForEmail: vi.fn(),
};

vi.mock("server-only", () => ({}));
vi.mock("@/lib/supabase/server", () => ({
  createSupabase: async () => ({ auth }),
  currentUser: async () => null,
}));
vi.mock("@/lib/api", () => ({
  createProfile: vi.fn(async () => ({ ok: true, status: 200, data: { onboarded_at: "2026-11-01T00:00:00Z" } })),
}));
// redirect() throws in Next; the test reads where it was going.
vi.mock("next/navigation", () => ({
  redirect: (to: string) => { throw Object.assign(new Error("NEXT_REDIRECT"), { to }); },
}));

async function redirectedTo(run: Promise<unknown>): Promise<string> {
  try { await run; } catch (e) { return (e as { to: string }).to; }
  throw new Error("expected a redirect");
}

function form(fields: Record<string, string>): FormData {
  const fd = new FormData();
  for (const [k, v] of Object.entries(fields)) fd.set(k, v);
  return fd;
}

const creds = form({ email: "Asha@Example.com", password: "tamarind-lamp-41" });
const authError = (status: number, code?: string, name = "AuthApiError") =>
  ({ data: { user: null, session: null }, error: { status, code, name, message: "x" } });

beforeEach(() => vi.clearAllMocks());

describe("log in (S-03)", () => {
  it("never says which of email and password was wrong", async () => {
    auth.signInWithPassword.mockResolvedValue(authError(400, "invalid_credentials"));
    const state = await logIn({}, creds);
    expect(state.banner?.text).toBe("That email or password doesn't match.");
    expect(state.email).toBe("asha@example.com");
  });

  it("does not call an outage a wrong password", async () => {
    auth.signInWithPassword.mockResolvedValue(authError(0, undefined, "AuthRetryableFetchError"));
    expect((await logIn({}, creds)).banner?.text).toBe(UNREACHABLE);
  });

  it.each([500, 502, 503])("treats HTTP %i from Supabase as an outage", async (status) => {
    auth.signInWithPassword.mockResolvedValue(authError(status));
    expect((await logIn({}, creds)).banner?.text).toBe(UNREACHABLE);
  });

  it("locks the form for 15 minutes when rate-limited", async () => {
    auth.signInWithPassword.mockResolvedValue(authError(429, "over_request_rate_limit"));
    const state = await logIn({}, creds);
    expect(state.banner?.text).toBe("Too many attempts. Try again in 15 minutes.");
    expect(state.retryUntil! - Date.now()).toBeGreaterThan(14 * 60 * 1000);
  });

  it("sends an unverified address to S-06", async () => {
    auth.signInWithPassword.mockResolvedValue(authError(400, "email_not_confirmed"));
    expect(await redirectedTo(logIn({}, creds))).toBe("/verify?email=asha%40example.com");
  });

  it("lands per §6.1.5 on success, honouring a safe ?next=", async () => {
    auth.signInWithPassword.mockResolvedValue({
      data: { session: { access_token: "t" }, user: { email_confirmed_at: "2026-11-01" } }, error: null,
    });
    expect(await redirectedTo(logIn({}, form({ ...Object.fromEntries(creds), next: "/history" })))).toBe("/history");
    expect(await redirectedTo(logIn({}, form({ ...Object.fromEntries(creds), next: "https://evil.example" })))).toBe("/dashboard");
  });
});

describe("sign up (S-02)", () => {
  it("treats an already-registered address exactly like a new one", async () => {
    auth.signUp.mockResolvedValue({ data: { user: { identities: [] }, session: null }, error: null });
    const existing = await redirectedTo(signUp({}, creds));
    auth.signUp.mockResolvedValue({ data: { user: { identities: [{}] }, session: null }, error: null });
    const fresh = await redirectedTo(signUp({}, creds));
    expect(existing).toBe(fresh);
    expect(fresh).toBe("/verify?email=asha%40example.com");
  });

  it("refuses a common password before calling Supabase", async () => {
    const state = await signUp({}, form({ email: "a@b.co", password: "password123" }));
    expect(state.fieldErrors?.password).toBe("That password is too common — try something less predictable");
    expect(auth.signUp).not.toHaveBeenCalled();
  });

  it("says when Supabase cannot be reached", async () => {
    auth.signUp.mockResolvedValue(authError(0, undefined, "AuthRetryableFetchError"));
    expect((await signUp({}, creds)).banner?.text).toBe(UNREACHABLE);
  });
});

describe("request a reset (S-04)", () => {
  it("confirms identically whatever Supabase says about the account", async () => {
    auth.resetPasswordForEmail.mockResolvedValue({ data: {}, error: null });
    expect(await requestReset({}, creds)).toEqual({ sent: "asha@example.com" });
    auth.resetPasswordForEmail.mockResolvedValue({ data: null, error: { status: 400, code: "user_not_found", message: "x" } });
    expect(await requestReset({}, creds)).toEqual({ sent: "asha@example.com" });
  });

  it("but does not claim to have sent anything during an outage", async () => {
    auth.resetPasswordForEmail.mockResolvedValue(authError(0, undefined, "AuthRetryableFetchError"));
    expect((await requestReset({}, creds)).banner?.text).toBe(UNREACHABLE);
  });
});
