"""
bias_detector.py
----------------
Detects three cognitive biases from a completed consultation session.
Called by app.py after user submits diagnosis via POST /conclude.

Three bias types detected:
  1. Anchoring — fixating on the most obvious symptom
  2. Premature closure — concluding before thorough workup
  3. Confirmation bias — only seeking confirming evidence

All detection logic is derived from docs/pseudocode.md Section MODULE 2.
Each detector returns a dict:
  {detected: bool, score: float 0-1, reason: str, evidence: list}
"""

from nidan.domain.assessment.thresholds import PILOT, Thresholds
from nidan.domain.types import BiasResults, Case, DetectorResult, Session


def _rule_fired(*rules: tuple[str, bool]) -> str | None:
    """
    The name of the first rule that fired, or None.

    First rather than all of them: `DATA_MODEL` §8.5 stores a single
    `rule_fired`, and the rules are OR-ed, so the earlier one is the stronger
    claim — A1 measures concentration across every question, where A2 fires on
    breadth alone.
    """
    for name, fired in rules:
        if fired:
            return name
    return None


def detect_all_biases(session: Session, case_config: Case, *,
                      thresholds: Thresholds = PILOT) -> BiasResults:
    """
    Main entry point. Runs all three bias detectors and returns combined
    results. This is the only function app.py calls from this module.

    Args:
        session (dict): Completed session from session_tracker.
        case_config (dict): Case definition from cases.py.

    Returns:
        dict: {
            "anchoring":         {detected, score, rule_fired, reason,
                                  evidence, counters},
            "premature_closure": {detected, score, rule_fired, reason,
                                  evidence, counters},
            "confirmation_bias": {detected, score, rule_fired, reason,
                                  evidence, counters}
        }

    `thresholds` defaults to the pilot values so the detector tests and the
    validation harness need no database. Anything that WRITES a result passes
    the engine version loaded from `engine_versions` (T-016) — see
    `domain/assessment/engine.py`.
    """
    return {
        "anchoring": detect_anchoring(
            session, case_config, thresholds=thresholds),
        "premature_closure": detect_premature_closure(
            session, case_config, thresholds=thresholds),
        "confirmation_bias": detect_confirmation_bias(
            session, case_config, thresholds=thresholds),
    }


def detect_anchoring(session: Session, case_config: Case, *,
                     thresholds: Thresholds = PILOT) -> DetectorResult:
    """
    Checks if user over-focused on the anchor topic without
    exploring alternative explanations.

    Rule A1: More than 60% of questions about anchor topic
             (requires at least 4 total questions to avoid noise)
    Rule A2: Asked 3+ anchor questions but zero alternative questions
             (strong signal even if overall question count is low)

    Args:
        session (dict): Session dict with questions_asked list.
        case_config (dict): Has anchor_keywords and alternative_topics.

    Returns:
        dict: {detected: bool, score: float 0-1, reason: str, evidence: list}
    """
    anchor_keywords = case_config["anchor_keywords"]
    alternative_topics = case_config["alternative_topics"]
    all_questions = session["questions_asked"]
    total_questions = session["question_count"]

    # Count questions containing anchor keywords
    anchor_question_count = 0
    anchor_evidence = []

    for question in all_questions:
        q_lower = question.lower()
        for kw in anchor_keywords:
            if kw in q_lower:
                anchor_question_count += 1
                anchor_evidence.append(question)
                break  # count each question once

    # Count questions containing alternative topic keywords
    alternative_question_count = 0
    for question in all_questions:
        q_lower = question.lower()
        for kw in alternative_topics:
            if kw in q_lower:
                alternative_question_count += 1
                break  # count each question once

    # Rule A1: topic concentration above the configured share
    detected_A1 = False
    score_A1 = 0.0
    if total_questions >= thresholds.anchoring_min_questions:
        concentration = anchor_question_count / total_questions
        if concentration > thresholds.anchoring_concentration:
            detected_A1 = True
            score_A1 = round(concentration, 2)

    # Rule A2: enough anchor questions with zero alternative exploration
    detected_A2 = False
    score_A2 = 0.0
    if (anchor_question_count >= thresholds.anchoring_a2_min_anchor
            and alternative_question_count == 0):
        detected_A2 = True
        score_A2 = thresholds.anchoring_a2_score

    detected = detected_A1 or detected_A2
    score = max(score_A1, score_A2)

    if detected:
        reason = (
            f"{anchor_question_count} of your {total_questions} questions "
            f"focused on {case_config['anchor_topic']} symptoms. "
            f"You asked {alternative_question_count} questions exploring "
            f"alternative causes."
        )
    else:
        reason = "No significant anchoring pattern detected."

    return {
        "detected": detected,
        "score": score,
        # Which of the two OR-ed rules fired, for the threshold-impact preview
        # (DATA_MODEL §8.5). A1 wins the label when both fire, because it is
        # the rule whose score is not flat.
        "rule_fired": _rule_fired(("A1", detected_A1), ("A2", detected_A2)),
        "reason": reason,
        "evidence": anchor_evidence[:3],  # max 3 examples to keep output concise
        # The intermediate values, so a recomputation mismatch can be localised
        # to a counter rather than merely observed as a different score
        # (DATA_MODEL §8.5).
        "counters": {
            "q": total_questions,
            "a": anchor_question_count,
            "m": alternative_question_count,
        },
    }


def detect_premature_closure(session: Session, case_config: Case, *,
                             thresholds: Thresholds = PILOT) -> DetectorResult:
    """
    Checks if user concluded before conducting a thorough workup.

    Rule P1: Fewer total questions than the minimum threshold
    Rule P2: Covered fewer than 60% of required clinical history topics

    Args:
        session (dict): Session dict with question_count and topics_covered.
        case_config (dict): Has minimum_questions and required_topics.

    Returns:
        dict: {detected: bool, score: float 0-1, reason: str, evidence: list}
              evidence contains list of missed topic names
    """
    minimum_questions = case_config["minimum_questions"]
    required_topics = case_config["required_topics"]
    topics_covered = session["topics_covered"]
    question_count = session["question_count"]

    # Rule P1: too few total questions asked
    detected_P1 = False
    score_P1 = 0.0
    if question_count < minimum_questions:
        detected_P1 = True
        score_P1 = max(
            round(1.0 - (question_count / minimum_questions), 2),
            thresholds.premature_score_floor,
        )

    # Rule P2: too few required topics covered
    topics_hit = [t for t in required_topics if t in topics_covered]
    total_required = len(required_topics)
    coverage_ratio = len(topics_hit) / total_required if total_required > 0 else 1.0

    detected_P2 = False
    score_P2 = 0.0
    if coverage_ratio < thresholds.premature_coverage:
        detected_P2 = True
        score_P2 = round(1.0 - coverage_ratio, 2)

    detected = detected_P1 or detected_P2
    score = max(score_P1, score_P2)

    topics_missed = [t for t in required_topics if t not in topics_covered]
    # Human-readable names for missed topics
    missed_display = [t.replace("_", " ") for t in topics_missed]

    if detected_P1 and detected_P2:
        reason = (
            f"You asked only {question_count} questions "
            f"(minimum recommended: {minimum_questions}) and covered "
            f"{len(topics_hit)} of {total_required} key history areas. "
            f"Areas not explored: {', '.join(missed_display)}."
        )
    elif detected_P1:
        reason = (
            f"You submitted a diagnosis after only {question_count} questions. "
            f"A thorough workup typically requires at least {minimum_questions}."
        )
    elif detected_P2:
        reason = (
            f"You covered {len(topics_hit)} of {total_required} key history "
            f"areas before concluding. "
            f"Areas not explored: {', '.join(missed_display)}."
        )
    else:
        reason = "No premature closure detected — thorough workup completed."

    return {
        "detected": detected,
        "score": score,
        "rule_fired": _rule_fired(("P1", detected_P1), ("P2", detected_P2)),
        "reason": reason,
        "evidence": missed_display,
        "counters": {
            "q": question_count,
            "q_min": minimum_questions,
            "coverage": round(coverage_ratio, 3),
        },
    }


def clue_keywords(clue: list[str] | tuple[str, ...] | str) -> list[str]:
    """
    The keyword list a contradictory clue is matched by.

    Shared with tests/test_case_invariants.py so that invariant C-4 is checked
    against the same terms the detector actually matches on. If this logic and
    the invariant test ever disagree, C-4 stops protecting anything — which is
    the failure mode that produced the bug it exists to prevent.

    A curated list is used as-is. A legacy free-text clue is split into words
    longer than 4 characters, which is what made the old clues collide with the
    anchor vocabulary in the first place.
    """
    if isinstance(clue, (list, tuple)):
        return [k.lower() for k in clue]
    return [w for w in clue.lower().split() if len(w) > 4]


def detect_confirmation_bias(session: Session, case_config: Case, *,
                             thresholds: Thresholds = PILOT) -> DetectorResult:
    """
    Checks if user only sought confirming evidence for their
    initial assumption and never explored contradictory information.

    Rule C1: Submitted an anchor diagnosis AND explored 0 contradictory clues
    Rule C2: Explored fewer than 25% of contradictory clues overall
             (regardless of diagnosis, if at least 5 questions asked)

    Contradictory clue detection uses significant words (length > 4)
    extracted from each clue description string in case_config.

    Args:
        session (dict): Session dict with questions_asked and diagnosis_submitted.
        case_config (dict): Has contradictory_clues and anchor_keywords.

    Returns:
        dict: {detected: bool, score: float 0-1, reason: str, evidence: list}
    """
    contradictory_clues = case_config["contradictory_clues"]
    anchor_keywords = case_config["anchor_keywords"]
    all_questions = session["questions_asked"]
    diagnosis = session.get("diagnosis_submitted") or ""
    total_clues = len(contradictory_clues)

    # Count how many contradictory clue topics the user asked about.
    #
    # Each clue is a list of SPECIFIC disconfirming keyword phrases — terms
    # unique to the evidence that argues AGAINST the trap diagnosis, curated to
    # NOT overlap with the anchor vocabulary. (A legacy string clue is still
    # accepted and split into words > 4 chars for backwards compatibility.)
    # A clue counts as explored if any of its keywords is a substring of any
    # question the student asked.
    clues_explored = 0
    for clue in contradictory_clues:
        keywords = clue_keywords(clue)

        clue_found = False
        for question in all_questions:
            q_lower = question.lower()
            for kw in keywords:
                if kw in q_lower:
                    clues_explored += 1
                    clue_found = True
                    break
            if clue_found:
                break  # count each clue once

    # Rule C1: diagnosed anchor topic but never explored any contradictory clues
    detected_C1 = False
    score_C1 = 0.0
    diagnosis_matches_anchor = False

    if diagnosis:
        d_lower = diagnosis.lower()
        for kw in anchor_keywords:
            if kw in d_lower:
                diagnosis_matches_anchor = True
                break

    if diagnosis_matches_anchor and clues_explored == 0:
        detected_C1 = True
        score_C1 = thresholds.confirmation_c1_score

    # Rule C2: less than 25% of contradictory clues explored
    detected_C2 = False
    score_C2 = 0.0
    if total_clues > 0:
        exploration_ratio = clues_explored / total_clues
        if (exploration_ratio < thresholds.confirmation_clue_ratio
                and len(all_questions) >= thresholds.confirmation_min_questions):
            detected_C2 = True
            score_C2 = round(1.0 - exploration_ratio, 2)

    detected = detected_C1 or detected_C2
    score = max(score_C1, score_C2)

    if detected:
        reason = (
            f"You explored {clues_explored} of {total_clues} key pieces of "
            f"information that could have challenged your initial assumption. "
            f"Confirmation bias occurs when we seek only evidence that supports "
            f"our first instinct."
        )
    else:
        reason = "No significant confirmation bias detected."

    return {
        "detected": detected,
        "score": score,
        "rule_fired": _rule_fired(("C1", detected_C1), ("C2", detected_C2)),
        "reason": reason,
        "evidence": [
            f"Only {clues_explored}/{total_clues} contradictory areas explored"
        ],
        "counters": {"k": clues_explored, "K": total_clues},
    }
