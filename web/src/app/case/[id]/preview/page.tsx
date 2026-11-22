import type { Metadata } from "next";
import { SmallScreen } from "@/components/consultation/SmallScreen";
import s from "@/components/consultation/preview.module.css";
import { Button } from "@/components/ui";
import { loadActiveSession } from "../load";

export const metadata: Metadata = { title: "Your patient" };

/**
 * S-09 · Case preview. Sets the scene and lets the learner commit
 * deliberately. Everything here comes from `case_view.py`'s presentation,
 * which carries no diagnosis, trap, key tests or required topics (FR-3.4, CT-1).
 */
export default async function Preview({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const { session } = await loadActiveSession(id, `/case/${id}/preview`);
  const patient = session.case?.patient ?? {};

  return (
    <>
      <SmallScreen />
      <main className={s.page}>
        <div className={s.body}>
          <p className={s.label}>Your patient</p>
          <h1 className={s.name}>{[patient.name, patient.age].filter(Boolean).join(", ")}</h1>
          {session.is_repeat && (
            <p className={s.repeat}>You have seen this case before. Treat it as practice.</p>
          )}
          <hr className={s.rule} />
          {patient.intro && <p className={s.intro}>{patient.intro}</p>}
          <hr className={s.rule} />
          <p>Take a history, examine {patient.sex === "female" ? "her" : patient.sex === "male" ? "him" : "them"},
            order whatever investigations you think are appropriate, then give your diagnosis.</p>
          <p>There&apos;s no time limit.</p>
          <div className={s.action}>
            <Button size="lg" href={`/case/${encodeURIComponent(id)}`}>Begin consultation</Button>
          </div>
        </div>
      </main>
    </>
  );
}
