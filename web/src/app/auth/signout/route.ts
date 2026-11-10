/**
 * Sign out (UX_SPEC §6.1.7). POST only, so a link or a prefetch cannot sign
 * anyone out. No confirmation dialog: it is trivially reversible.
 *
 * An active consultation is NOT abandoned — it stays `active` and resumes on
 * the next sign-in. Nothing here touches the API.
 */
import { NextResponse, type NextRequest } from "next/server";
import { createSupabase } from "@/lib/supabase/server";

export async function POST(request: NextRequest) {
  const supabase = await createSupabase();
  await supabase.auth.signOut();
  // 303 so the browser follows with a GET.
  return NextResponse.redirect(new URL("/?toast=signed-out", request.nextUrl.origin), 303);
}
