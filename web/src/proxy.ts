/**
 * Runs before every page request (UX_SPEC §6.1.4, Next 16's `proxy`).
 *
 *   public route?                         → serve
 *   session valid?                        → serve
 *   expired, but the refresh token works? → refresh, set cookies, serve
 *   no session                            → 302 /login?next={original path}
 *
 * Not the only check: Next runs server actions as POSTs to the page they live
 * on, and a matcher change can drop them out of the proxy's reach silently. So
 * every action and route handler that needs a user asks Supabase again itself.
 */
import { createServerClient } from "@supabase/ssr";
import { NextResponse, type NextRequest } from "next/server";
import { loginRedirect } from "@/lib/redirects";
import { isPublicPath, SIGNED_OUT_ONLY } from "@/lib/routes";
import { sessionCookieOptions } from "@/lib/supabase/cookies";

export async function proxy(request: NextRequest) {
  let response = NextResponse.next({ request });

  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const key = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
  if (!url || !key) {
    // Unconfigured: public pages still render, protected ones say why.
    return isPublicPath(request.nextUrl.pathname)
      ? response
      : new NextResponse("Supabase is not configured: see web/.env.example.", { status: 503 });
  }

  const supabase = createServerClient(url, key, {
    cookieOptions: sessionCookieOptions(),
    cookies: {
      getAll: () => request.cookies.getAll(),
      setAll: (toSet, headers) => {
        for (const { name, value } of toSet) request.cookies.set(name, value);
        response = NextResponse.next({ request });
        for (const { name, value, options } of toSet) {
          response.cookies.set(name, value, { ...options, ...sessionCookieOptions() });
        }
        for (const [k, v] of Object.entries(headers ?? {})) response.headers.set(k, v);
      },
    },
  });

  // getUser() verifies the token with Supabase and refreshes it if it has
  // expired; nothing may run between createServerClient and this call.
  const { data: { user } } = await supabase.auth.getUser();
  const { pathname, search } = request.nextUrl;

  if (!user && !isPublicPath(pathname)) {
    const target = request.nextUrl.clone();
    const [path, query] = loginRedirect(pathname + search).split("?");
    target.pathname = path!;
    target.search = query ? `?${query}` : "";
    return NextResponse.redirect(target);
  }

  if (user && SIGNED_OUT_ONLY.has(pathname)) {
    const target = request.nextUrl.clone();
    target.pathname = "/dashboard";
    target.search = "";
    return NextResponse.redirect(target);
  }

  return response;
}

export const config = {
  // Everything except Next's own assets and files with an extension.
  matcher: ["/((?!_next/static|_next/image|favicon.ico|.*\\.[a-zA-Z0-9]+$).*)"],
};
