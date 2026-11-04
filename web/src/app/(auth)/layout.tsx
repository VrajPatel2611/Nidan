import Link from "next/link";
import type { ReactNode } from "react";
import s from "@/components/auth/auth.module.css";

export default function AuthLayout({ children }: { children: ReactNode }) {
  return (
    <main className={s.shell}>
      <div className={s.panel}>
        <Link href="/" className={s.brand}>Nidan</Link>
        {children}
      </div>
    </main>
  );
}
