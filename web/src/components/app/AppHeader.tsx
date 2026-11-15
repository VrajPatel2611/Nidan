import Link from "next/link";
import { Avatar, Button } from "@/components/ui";
import s from "./app.module.css";

/**
 * The signed-in header (UX_SPEC S-08 drawing, §5.1).
 *
 * The free allowance appears here — on the dashboard and other between-case
 * pages — and **never during a consultation** (`PRD` FR-10.2, U2). The
 * consultation screen (T-034) must not render this header with `allowance`.
 */
export function AppHeader({ active, name, email, allowance }: {
  active: "dashboard" | "history" | "progress";
  name?: string | null;
  email?: string | null;
  allowance?: { remaining: number } | null;
}) {
  const links = [
    { key: "dashboard", href: "/dashboard", label: "Dashboard" },
    { key: "history", href: "/history", label: "History" },
    { key: "progress", href: "/progress", label: "Progress" },
  ] as const;
  return (
    <header className={s.header}>
      <Link href="/dashboard" className={s.brand}>Nidan</Link>
      <nav className={s.nav} aria-label="Main">
        {links.map((l) => (
          <Link key={l.key} href={l.href} className={s.navLink} aria-current={active === l.key ? "page" : undefined}>
            {l.label}
          </Link>
        ))}
      </nav>
      <div className={s.right}>
        {allowance && (
          <span className={s.allowance}>
            {allowance.remaining} {allowance.remaining === 1 ? "case" : "cases"} left this month
          </span>
        )}
        <Avatar name={name || email || "?"} />
        <form action="/auth/signout" method="post">
          <Button type="submit" variant="ghost" size="sm">Sign out</Button>
        </form>
      </div>
    </header>
  );
}
