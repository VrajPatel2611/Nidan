import s from "@/components/app/app.module.css";
import { Skeleton } from "@/components/ui";

/** S-08 · Loading: skeletons for the hero, the tiles and the list (§5.2). */
export default function Loading() {
  return (
    <div className={s.page} aria-busy="true" aria-label="Loading your dashboard">
      <main className={s.main}>
        <Skeleton variant="text" lines={1} />
        <div style={{ margin: "var(--s-6) 0" }}><Skeleton variant="card" /></div>
        <div className={s.tiles}>
          <Skeleton variant="card" /><Skeleton variant="card" /><Skeleton variant="card" />
        </div>
        <Skeleton variant="list" lines={3} />
      </main>
    </div>
  );
}
