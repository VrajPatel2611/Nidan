import Link from "next/link";
import s from "./consultation.module.css";

/** UX_SPEC §4.1 — below 768 px, S-09 and S-10 refuse rather than degrade. */
export function SmallScreen() {
  return (
    <div className={s.small} role="note">
      <div>
        <h1>Best on a larger screen</h1>
        <p>A consultation needs room for the patient, your questions, and the test panel side by side.
          Open Nidan on a tablet or computer to start a case.</p>
        <p><em>You can still review your past feedback and progress here.</em></p>
        <Link href="/progress">View my progress</Link>
      </div>
    </div>
  );
}
