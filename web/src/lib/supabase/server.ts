import "server-only";
import { createServerClient } from "@supabase/ssr";
import { cookies } from "next/headers";
import { env } from "@/lib/env";
import { sessionCookieOptions } from "./cookies";

/**
 * A Supabase client for server components, server actions and route handlers.
 * One per request — the library's cache headers are only sent on a client's
 * first cookie write.
 */
export async function createSupabase() {
  const store = await cookies();
  return createServerClient(env.supabaseUrl(), env.supabaseAnonKey(), {
    cookieOptions: sessionCookieOptions(),
    cookies: {
      getAll: () => store.getAll(),
      setAll: (toSet) => {
        try {
          for (const { name, value, options } of toSet) {
            store.set(name, value, { ...options, ...sessionCookieOptions() });
          }
        } catch {
          // A server component cannot set cookies. The proxy refreshes the
          // session on every request, so the write it would have made is
          // already done.
        }
      },
    },
  });
}

/** The signed-in user, verified with Supabase — never trusted from the cookie alone. */
export async function currentUser() {
  const supabase = await createSupabase();
  const { data } = await supabase.auth.getUser();
  return data.user;
}

/** The access token to send to the Nidan API as a Bearer token, or null. */
export async function accessToken(): Promise<string | null> {
  const supabase = await createSupabase();
  // getUser() first: it verifies the token with Supabase. getSession() alone
  // only reads the cookie.
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) return null;
  const { data: { session } } = await supabase.auth.getSession();
  return session?.access_token ?? null;
}
