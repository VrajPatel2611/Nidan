import Link from "next/link";
import s from "@/components/auth/auth.module.css";

/**
 * Placeholder for S-01 · Landing, which is not in T-032. Here so `/` and the
 * signed-out redirect (§6.1.7) land somewhere that says what Nidan is.
 */
export default function Home() {
  return (
    <main className={s.shell}>
      <div className={s.panel} style={{ textAlign: "center" }}>
        <span className={s.brand}>Nidan</span>
        <h1 className={s.title}>Practise clinical reasoning</h1>
        <p className={s.lede}>Interview a patient, examine, order tests and make a diagnosis — then see how you reasoned.</p>
        <p><Link href="/signup">Create an account</Link> · <Link href="/login">Log in</Link></p>
      </div>
    </main>
  );
}
