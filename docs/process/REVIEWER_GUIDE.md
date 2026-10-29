# Nidan — guide for clinical reviewers

Thank you for agreeing to do this. This explains what Nidan is, what we are
asking you to judge, and the one thing about these cases that is easy to
mistake for a mistake.

It should take about ten minutes to read, and it is worth reading before the
first case rather than during it.

---

## What Nidan is

Nidan is a practice tool for medical students and early trainees. The learner
takes a history from a simulated patient by typing questions, orders
examinations and investigations, and commits to a diagnosis.

What makes it different from other virtual patients is what happens next. The
feedback is not mainly about whether the diagnosis was right. It is about **how
the learner got there** — whether they settled on an answer early and then
looked only for support, whether they left whole parts of the history unasked,
whether they ordered the test that would have changed their mind.

In a pilot with sixteen students, history coverage rose from 45 % to 80 %. That
study had no control group, so we cannot claim the tool caused it — but it is
why the project continued.

## What we are asking you to judge

A case must be approved by a clinician before any learner can see it. Nothing
publishes without that, and the block is in the database rather than in
anyone's good intentions.

You are the person deciding whether this case is safe and sound to teach from.
You are not being asked to proofread it, to rewrite it, or to agree with how
the software works.

---

## The one thing to know first: the trap is deliberate

**Every Nidan case is built around a plausible wrong answer.**

A man of 48 arrives with three days of chest pain. There is a path that leads
to a cardiac diagnosis, and it is a reasonable path — his age, the site, his
anxiety. There is also a burning quality, a clear relationship to meals, and
daily ibuprofen for back pain, and a learner who asks about those finds reflux.

The cardiac path is not an error in the case. **It is the case.** The whole
point is to give a learner somewhere wrong to go, so the feedback has something
true to say about how they reasoned.

This matters because of one of the four things you will score. Reading the case
cold, a sensible clinician sees the misleading path and marks the case down for
being misleading. That is the single most likely way for this review to go
wrong, and it would block a case that is working exactly as designed.

What you are judging is not whether the case misleads. It is whether it
misleads **fairly** — whether a careful learner who asks the right questions
can find their way out.

---

## Reviewing a case

Sign in and you will see **Clinical review** with the cases assigned to you.
Open one.

The case opens in **Playtest**, with the review form beside it. Playtest is the
learner's screen: you can talk to the patient exactly as a student would, order
examinations and investigations, and see what comes back. Nothing you do there
affects any learner, and you can start again as often as you like.

**Please actually play it, at least twice.**

1. **Once properly** — take the history you would take. Can you reach the right
   diagnosis? How much did you have to ask to get there?
2. **Once down the wrong path** — pursue the tempting diagnosis deliberately.
   Does the patient stay consistent? Do the investigations you would order come
   back with sensible results? Is there a point at which an honest learner would
   realise, or does the case let them stay wrong with no way out?

The second run is the one that finds the real problems. Reading the content
alone will not show you that the patient contradicts herself on the fourth
question, or that the one investigation that settles it was never included.

Twenty minutes or so a case is about right. If it is taking much longer than
that, say so in the comments — that is a finding, not a failing.

---

## The four questions you are scoring

Each is 1 to 5.

### Clinical plausibility

*Could this patient walk into a clinic?*

The history, the examination findings and the results should hang together as
one real person. Watch for the pattern that reads like a textbook paragraph
rather than a presentation, and for values that are abnormal in a way nothing
else in the case accounts for.

- **5** — you have seen this patient
- **below 4** — something is off in a way that would mislead a learner about how the condition actually presents

### Internal consistency

*Does the case contradict itself?*

The patient should answer the same question the same way however it is asked,
and the examination and results should match the history. This is where a
second playthrough earns its keep: the patient is voiced by a language model
working from a written brief, and a thin brief shows up as drift under
questioning.

- **5** — nothing contradicts anything, including under awkward questioning
- **below 4** — a learner who asked twice would get two different answers

### Trap validity

*Is the wrong path fair?*

Not "is there a wrong path" — there always is, deliberately. The question is
whether the correct answer is genuinely reachable:

- The misleading path should be one a competent learner could reasonably take
- The evidence that points the right way must be **findable by asking**, not
  only revealed by luck
- The investigation that settles it must be available and reasonable to order
- No pure trickery: the patient should not conceal something a real patient
  would volunteer

- **5** — tempting, and fair; you found your way out by asking the right things
- **below 4** — you could not get out, or the way out depended on knowing in advance

### Solvability from the information given

*Could a good student in years 3 to 5 reach the diagnosis?*

The audience is clinical-phase students and early trainees. The case should be
hard, not obscure. A diagnosis needing subspecialty knowledge, or one that
cannot be reached without a test the case does not offer, is not solvable here
however good the medicine is.

- **5** — a well-prepared student would get there by asking well
- **below 4** — too hard, too obscure, or missing something needed

---

## The rule that will stop you

**A case cannot be approved with any dimension below 4.** The Approve button
switches off and tells you which one is short.

This is not a suggestion the software is making. A 3 means something is wrong
enough to mention, and a case with something wrong enough to mention should not
be the one a student learns from. If you find yourself wanting to approve a
case with a 3, the right move is **Request changes**, say what it is in a
sentence, and approve the next version.

---

## The three verdicts

| | When |
|---|---|
| **Approve** | Sound and safe to teach from. All four at 4 or 5 |
| **Request changes** | Fixable. Something specific is wrong and you can name it. **Needs a comment** |
| **Reject** | Not fixable by editing — wrong teaching point, unsafe, or the trap cannot be made fair. **Needs a comment** |

Request changes is the normal outcome for a first version, and it is not a
criticism of anyone. These cases are written to be corrected by you; that is
the whole arrangement.

**Comments are read by a person who will act on them.** "Internal consistency
3 — she says the pain is worse at night when asked about timing, but better at
night when asked about sleep" is worth more than three paragraphs of general
impressions.

---

## Please don't fix it yourself

You cannot edit a case, and that is deliberate rather than an oversight — the
account you have been given has no permission to write content at all.

A reviewer who edits a case is no longer reviewing it. Nobody independent has
then looked at the version that goes live, and the record would say the case
was approved by the person who wrote the thing being approved.

So: say what is wrong, and it will come back to you corrected.

---

## Small practical things

- **Units are SI, with Commonwealth conventions**, and every value carries its
  interpretation and reference range. If a value appears without one and you
  had to look it up, that is worth a comment.
- **Signing in lasts about an hour.** If the site stops responding and starts
  showing "not found", you have been signed out. Sign in again.
- **Every refusal looks identical** — a plain "not found" page. It is not
  telling you nothing by accident; the console deliberately gives no clue that
  it exists to anyone without an account. If you see it where you expect a
  page, say so rather than trying to diagnose it.
- **You may review a case someone on the team wrote.** You will see a note
  saying so. It is not a problem — just worth knowing.
- **Nothing you do in Playtest reaches a learner.** Experiment freely.

---

## What happens next

An approved case becomes publishable. Ten reviewed cases is what we need before
launch; five exist and five are being written.

If something about this process is awkward, tell us — it was designed around a
guess at what you would want, and you are the first two people to use it.
