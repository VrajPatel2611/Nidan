/**
 * Configuration, read when it is used rather than at import — so `next build`
 * works without a Supabase project, and a missing value fails as a sentence
 * naming it instead of as `undefined` three layers down.
 */
function required(name: string, value: string | undefined): string {
  if (!value) {
    throw new Error(`${name} is not set. Copy web/.env.example to web/.env.local and fill it in.`);
  }
  return value;
}

export const env = {
  // NEXT_PUBLIC_* must be read as literal property accesses for Next to inline them.
  supabaseUrl: () => required("NEXT_PUBLIC_SUPABASE_URL", process.env.NEXT_PUBLIC_SUPABASE_URL),
  supabaseAnonKey: () => required("NEXT_PUBLIC_SUPABASE_ANON_KEY", process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY),
  siteUrl: () => process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000",
  apiUrl: () => process.env.NIDAN_API_URL ?? "http://localhost:8000/v1",
};
