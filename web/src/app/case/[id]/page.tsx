import type { Metadata } from "next";
import { Consultation, type Turn } from "@/components/consultation/Consultation";
import { getCatalog } from "@/lib/api";
import { capReached, groupMenu, orderedFromSession } from "@/lib/consultation";
import { relativeDay } from "@/lib/dashboard";
import { loadActiveSession } from "./load";

export const metadata: Metadata = { title: "Consultation" };

/**
 * S-10 · Consultation. The session is replayed by the API from its event log
 * (ADR-0003), so a refresh, a resume and a first visit are the same request.
 * No top navigation, and no allowance — the header is not rendered here (U2).
 */
export default async function ConsultationPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const [{ session }, examinations, investigations] = await Promise.all([
    loadActiveSession(id, `/case/${id}`), getCatalog("examinations"), getCatalog("investigations"),
  ]);

  const transcript = session.transcript ?? [];
  const turns: Turn[] = [
    ...(session.case?.opening_line ? [{ id: "opening", who: "patient" as const, text: session.case.opening_line }] : []),
    ...transcript.map((t, i) => ({
      id: `t${t.seq ?? i}`, who: t.type === "question" ? "doctor" as const : "patient" as const, text: t.text ?? "",
    })),
  ];
  const ordered = orderedFromSession(session);
  const resumed = transcript.length > 0 || ordered.length > 0;

  return (
    <Consultation
      sessionId={id}
      patient={session.case?.patient ?? {}}
      turns={turns}
      ordered={ordered}
      examinations={groupMenu(examinations ?? [])}
      investigations={groupMenu(investigations ?? [])}
      resumedFrom={resumed ? relativeDay(session.last_activity_at ?? session.started_at ?? new Date().toISOString(), new Date()) : null}
      capReached={capReached(transcript)}
    />
  );
}
