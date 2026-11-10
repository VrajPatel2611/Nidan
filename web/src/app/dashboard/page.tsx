import type { Metadata } from "next";
import s from "@/components/auth/auth.module.css";
import { Button, Card } from "@/components/ui";
import { currentUser } from "@/lib/supabase/server";

export const metadata: Metadata = { title: "Dashboard" };

/** Placeholder: S-08 · Dashboard is T-033. Protected by the proxy. */
export default async function Dashboard() {
  const user = await currentUser();
  return (
    <main className={s.shell}>
      <Card variant="elevated" className={s.panel}>
        <h1>Dashboard</h1>
        <p>Signed in as {user?.email}. The dashboard arrives in T-033.</p>
        <form action="/auth/signout" method="post">
          <Button type="submit" variant="secondary">Sign out</Button>
        </form>
      </Card>
    </main>
  );
}
