# ADR-0017 · Data residency in the EU (Frankfurt)

| | |
|---|---|
| **Status** | Accepted |
| **Date** | 2026-10-28 |
| **Deciders** | Vraj Patel, Yogesh Bagotia |
| **Supersedes** | — |

## Context

`SECURITY_SPEC` S-4 has carried a ⟨DECIDE⟩ marker since 5 September 2026, and D-7 made it harder rather than easier: a **global English-speaking launch** means UK and EU users from day one.

Three facts constrain the choice.

**GDPR applies because of who the users are, not where the database is.** Article 3(2) binds any controller offering services to people in the Union, wherever the controller or its infrastructure sits. So no region avoids GDPR. The region decides something narrower.

**What the region decides is Chapter V.** Personal data leaving the EEA is a restricted transfer, and lawful only under a transfer mechanism — an adequacy decision, or standard contractual clauses backed by a transfer impact assessment. That is paperwork, periodic review, and a dependency on the destination country's surveillance law. Keeping the data in the EEA removes the obligation rather than satisfying it.

**The obligation is one-directional.** No comparable restriction stops an Indian, Australian or US user's data from sitting in Frankfurt. The asymmetry is the whole decision: one region creates legal work, the other does not, and it is the same database either way.

Against that, latency. One database, one region, and a user base spread across at least three continents — someone is always far away.

`ADR-0001` already placed PostgreSQL on Supabase, and `ADR-0002` placed authentication there too, so this is one project and one jurisdiction for both. A Supabase project cannot be moved between regions; changing this means creating a new project and migrating.

## Decision

**Central EU (Frankfurt), `eu-central-1`.**

One Supabase project holds both the database and GoTrue, created 28 October 2026.

EU users are served from inside the EEA, so Chapter V does not engage for them. UK users rely on the UK's own finding that the EEA offers adequate protection — a transfer in that direction, from a UK data subject to an EU processor, is the well-supported one. Users outside Europe bring no residency constraint of their own.

Latency is accepted as the cost: roughly 120–150 ms from India and 80–100 ms from the US east coast. A consultation is turn-based text, and the LLM call already dominates every response by an order of magnitude, so the round trip is not perceptible where it lands.

## Alternatives considered

| Option | Why rejected |
|---|---|
| **London, `eu-west-2`** | Equivalent for UK users and marginally closer to India. Rejected because it inverts the dependency: EU users' data in the UK relies on the EU's adequacy decision *for* the UK, which is renewable and has been subject to periodic review, whereas the UK's recognition of the EEA is the stabler direction. Choosing the renewable side of a reciprocal pair, for a project that cannot change region later, is the worse of two similar options. |
| **Mumbai, `ap-south-1`** | Best latency for the team and for any India-based pilot cohort, and genuinely tempting while the only users are local. Rejected because it takes on SCCs and a transfer impact assessment as a precondition of the launch D-7 already committed to — legal work that scales with the thing we most want to do. |
| **US East, `us-east-1`** | Supabase's default and its best-tested region. Rejected for the same Chapter V exposure as Mumbai, with none of its latency benefit for us, and with a destination whose surveillance law is the subject of the case history that invalidated two previous adequacy frameworks. |
| **Two regions, routed by user** | Removes the trade-off and introduces a far worse one. Two databases means the assessment engine's `engine_versions` pinning, the golden record and the 16 backfilled pilot sessions all fork, and `ADR-0003`'s single event log stops being single. Not worth it at any plausible scale for this product. |
| **Defer until launch** | The status quo, and the reason this sat open for seven weeks. Rejected because the project had to be created to unblock T-023 regardless, and a region chosen incidentally to unblock a local sign-in is a jurisdiction chosen by accident. |

## Consequences

+ `SECURITY_SPEC` S-4 is closed; the last open ⟨DECIDE⟩ item is settled
+ No Chapter V transfer mechanism, transfer impact assessment or SCC review is needed for EU users
+ The privacy policy (S-7) can state a single, stable processing location
+ Auth and data share one jurisdiction, so there is no second residency question for GoTrue
− Latency of roughly 120–150 ms for users in India, including the team during development
− A later decision to move is a new project and a data migration, not a setting
− UK coverage depends on the UK's recognition of the EEA; if that position ever changed, UK users would need their own mechanism. Worth re-reading at S-7 when the privacy policy is written
− Nothing here addresses *what* is stored, only where. The group-size floor in S-1 and the aggregate-only institutional view remain the decisions that matter more for trust
