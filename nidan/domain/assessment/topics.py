"""
Topic extraction.

Maps a learner's free-text question onto named clinical topic categories by
case-insensitive substring matching against a curated phrase lexicon.

Pure — no I/O, no clock, no randomness. This is the input to history-coverage
scoring and, indirectly, to the premature-closure detector.

Known limitation: lexical matching misses paraphrase. Every error in detector
validation traced here. See ADR-0013 for the embedding upgrade.
"""

# ── Topic keyword lookup table ──────────────────────────────────────
# Maps topic category names to lists of trigger words.
# Category names must match the required_topics lists in cases.py.
# When a user message contains any keyword from a category,
# that topic is marked as covered in the session.
# Matching is case-insensitive substring matching.

TOPIC_KEYWORDS = {
    # ── case_1: GERD / Chest pain ──────────────────────────────────
    "pain_character": [
        "burning", "crushing", "sharp", "dull", "aching",
        "character", "describe", "feel like", "what kind",
        "pressure", "tight", "stabbing", "squeezing",
        "what does it feel", "type of pain",
    ],
    "meal_relationship": [
        "meal", "food", "eating", "after eating", "diet",
        "drink", "spicy", "coffee", "fasting", "empty stomach",
        "before eating", "after food", "when you eat", "trigger food",
    ],
    "radiation": [
        "radiate", "spread", "arm", "jaw", "shoulder",
        "neck", "anywhere else", "go to", "move to",
        "travels", "down the", "into your",
    ],
    "associated_symptoms": [
        "breathless", "nausea", "sweat", "dizzy", "fever",
        "vomit", "other symptoms", "anything else", "weakness",
        "fatigue", "other problems", "shortness of breath",
    ],
    "medications": [
        "medication", "medicine", "drug", "tablet", "pill",
        "taking", "prescribed", "supplements", "painkillers",
        "regular", "daily", "what do you take", "any pills",
    ],
    "family_history": [
        "family", "father", "mother", "parent", "sibling",
        "hereditary", "runs in family", "relative",
        "grandfather", "grandmother", "anyone in family",
    ],
    "duration_pattern": [
        "how long", "when did", "since when", "started",
        "days", "weeks", "months", "constant", "comes and goes",
        "pattern", "how often", "when does it",
    ],
    "relieving_factors": [
        "better", "worse", "relief", "helps", "aggravate",
        "trigger", "lying down", "sitting up", "activity",
        "rest", "position", "makes it", "alleviate",
    ],

    # ── case_6: Hypertension / Headache ───────────────────────────
    # (design CASE 2 in docs/cases_design.md; built 2026-10-29)
    "headache_character": [
        "throbbing", "pressure", "tight", "band", "one side",
        "both sides", "where", "location", "pulsating",
        "pounding", "headache feel like", "describe headache",
    ],
    "timing_pattern": [
        "morning", "night", "evening", "after", "before",
        "always", "sometimes", "pattern", "when", "how long",
        "duration", "time of day", "worse when",
    ],
    "visual_symptoms": [
        "vision", "blurry", "blur", "spots", "floaters",
        "see", "eyes", "visual", "aura", "light",
        "sensitivity to light", "sight", "seeing",
    ],
    "BP_awareness": [
        "blood pressure", "bp", "checked", "measured",
        "monitor", "high pressure", "reading", "hypertension",
        "pressure ever checked", "blood pressure before",
    ],
    "lifestyle": [
        "sleep", "diet", "water", "hydration", "caffeine",
        "coffee", "alcohol", "exercise", "routine", "lifestyle",
        "habits", "work life", "screen",
    ],
    "stress_assessment": [
        "stress", "pressure", "deadline", "event", "recently",
        "changed", "happened", "difficult", "problem",
        "worry", "anxious", "stressful", "trigger the",
    ],

    # ── case_3: UTI/Delirium / Elderly confusion ───────────────────
    "onset_timing": [
        "when", "how long", "started", "sudden", "gradual",
        "yesterday", "this morning", "last week", "always",
        "recent", "how quickly", "onset",
    ],
    "baseline_cognition": [
        "normal", "usual", "before", "last week", "always like this",
        "change", "different", "baseline", "normally", "was he",
        "was she", "used to be", "sharp", "always been",
    ],
    "fever": [
        "fever", "temperature", "hot", "chills", "sweating",
        "warm", "shivering", "unwell", "sick",
        "thermometer", "how hot", "temperature check",
    ],
    "urinary_symptoms": [
        "urinate", "urine", "pee", "toilet", "frequency",
        "burning", "colour", "smell", "waterworks",
        "going more", "going less", "painful urination",
        "wee", "urinary", "passing water",
    ],
    "recent_illness": [
        "recently", "fell", "hospital", "unwell", "sick",
        "illness", "injury", "change", "last few days",
        "any recent", "been ill", "before this",
    ],
    "focal_neuro_signs": [
        "weakness", "arm", "leg", "face", "drooping", "speech",
        "slurred", "one side", "movement", "paralysis",
        "can he move", "arms move", "face look",
        "facial", "limb", "motor",
    ],
    "hydration": [
        "eating", "drinking", "water", "fluid", "appetite",
        "dehydrated", "thirsty", "hungry",
        "drinking enough", "how much water", "oral intake",
    ],

    # ── case_4: Hypothyroidism / Fatigue ──────────────────────────
    "mood_vs_physical": [
        "mood", "sad", "hopeless", "happy", "emotional",
        "how do you feel emotionally", "crying", "enjoying",
        "interests", "depression", "anxious", "mentally",
        "psychologically", "feel inside", "feel down",
        "depressed", "low mood",
    ],
    "weight_change_pattern": [
        "appetite", "more", "less",
        "same", "calories", "changed eating", "portion",
        "hungry", "weight going up", "gaining despite",
        "eating habits", "diet changed",
    ],
    "temperature_tolerance": [
        "cold", "temperature", "always cold", "chilly",
        "layers", "warm", "heating", "hot", "intolerant",
        "feel cold", "cold intolerant", "feel warm",
    ],
    "bowel_habits": [
        "bowel", "constipated", "constipation", "toilet",
        "frequency", "going less", "difficulty", "hard",
        "sluggish", "bowel changed", "stool", "opening bowels",
    ],
    "hair_skin_changes": [
        "hair", "falling out", "hair loss", "skin", "dry",
        "brittle", "nails", "rough", "texture", "changed",
        "hair different", "skin feel", "losing hair",
    ],
    "family_thyroid_history": [
        "family", "thyroid", "mother", "father", "sister",
        "relative", "runs in family", "thyroid condition",
        "underactive", "overactive", "levothyroxine",
        "thyroid tablets", "thyroid history",
    ],
    "menstrual_changes": [
        "period", "menstrual", "cycle", "regular", "heavy",
        "irregular", "missed", "monthly", "flow",
        "spotting", "period changed", "time of month",
    ],
    "energy_time_pattern": [
        "morning", "afternoon", "all day", "worse when",
        "better when", "energy level", "when tired",
        "time of day", "energy", "most tired", "wakes up tired",
    ],

    # ── case_7: Asthma / Wheezing child ───────────────────────────
    # (design CASE 5 in docs/cases_design.md; built 2026-10-29)
    "fever_infection_signs": [
        "fever", "temperature", "runny nose", "sore throat",
        "ear", "tonsils", "sick", "ill", "unwell", "hot",
        "infection sign", "cold symptoms", "snotty", "green",
    ],
    "symptom_timing_pattern": [
        "morning", "night", "evening", "worse when",
        "when bad", "timing", "sleeping", "waking", "pattern",
        "time of day", "night time", "early morning",
    ],
    "exercise_trigger": [
        "exercise", "running", "sport", "pe", "playing",
        "after exercise", "active", "breathless", "exertion",
        "physical", "when he runs", "sport trigger", "gym",
    ],
    "cold_air_trigger": [
        "cold air", "outside", "weather", "cold", "winter",
        "wind", "going out", "temperature changes",
        "cold makes", "outside worse", "outdoors",
    ],
    "duration_recurrence": [
        "before", "first time", "happened before", "previous",
        "recurring", "again", "history of", "ever had",
        "come back", "recurrent", "this before", "in the past",
    ],
    "family_atopy_history": [
        "asthma", "allergy", "eczema", "hay fever",
        "atopy", "family", "inhaler", "allergic family",
        "allergic", "atopic",
    ],
    "school_sport_impact": [
        "school", "missing", "pe", "sport", "activity",
        "playing", "limited", "avoiding", "stopped",
        "cannot", "affected school", "keeping up", "impact",
    ],

    # ── case_2 (PE): travel history + leg/DVT symptoms ────────────
    "travel_history": [
        "flight", "flew", "plane", "airport", "travel", "travelled",
        "holiday", "trip", "abroad", "long journey", "long haul",
        "car journey", "sitting long", "immobile", "immobility",
        "dubai", "recently travel", "bus journey", "train journey",
    ],
    "leg_symptoms": [
        "leg", "calf", "legs", "swelling", "swollen", "dvt",
        "deep vein", "leg pain", "calf pain", "calf swell",
        "leg swell", "clot in leg", "popliteal", "calf ache",
        "leg aching", "tight calf", "leg oedema",
    ],

    # ── case_5 (DKA): polydipsia/polyuria + weight loss ───────────
    "thirst_polyuria": [
        "thirst", "thirsty", "drinking more", "polydipsia",
        "urinating more", "peeing more", "polyuria", "passing more",
        "going toilet more", "drinking lots", "excess thirst",
        "excessive thirst", "drinking water lots", "waking at night",
        "nocturia", "how much water", "frequency urination",
        "using toilet a lot", "drink a lot",
    ],
    "weight_history": [
        "weight", "lost weight", "losing weight", "weight loss",
        "thinner", "clothes", "lost kg", "weight change",
        "lighter", "heavier", "gaining weight", "weight going",
        "noticed weight",
    ],

    # ── case_10: Aortic stenosis / Syncope ────────────────────────
    # The first topics added since migration 017 seeded the original 40.
    # A syncope history is five questions, and which five is not a matter
    # of taste: circumstances, prodrome, recovery, what else happens on
    # exertion, and palpitations. A learner who asks all five cannot call
    # this a simple faint, which is exactly why they are the required set.
    #
    # Seeded by migration 027. Adding a topic here without a migration
    # leaves the database disagreeing with the code, and
    # tests/db/test_seed.py is what says so.
    "syncope_circumstances": [
        "what were you doing", "doing when", "doing at the time",
        "happened when", "where were you", "at the time",
        "before you collapsed", "leading up", "circumstance",
        "standing", "sitting", "lying down", "what brought it on",
    ],
    "prodrome_warning": [
        "warning", "any warning", "before it happened", "beforehand",
        "dizzy", "light headed", "lightheaded", "nausea", "sweaty",
        "clammy", "vision went", "tunnel", "ringing in",
        "feel it coming", "prodrome",
    ],
    "recovery_pattern": [
        "afterwards", "came round", "came to", "recovery", "recovered",
        "confused", "how long were you", "tongue", "bitten",
        "incontinen", "jerking", "shaking", "witness", "anyone see",
        "sleepy after", "back to normal",
    ],
    "exertional_symptoms": [
        "on exertion", "exertion", "walking up", "uphill", "stairs",
        "breathless", "short of breath", "chest tightness",
        "tight chest", "angina", "when you walk", "how far can you",
        "limited by", "stop and rest",
    ],
    "palpitations_rhythm": [
        "palpitation", "racing", "irregular", "skipped", "fluttering",
        "heart rhythm", "pounding heart", "heart racing",
        "aware of your heart", "thumping",
    ],

    # ── case_8: Colorectal cancer / Rectal bleeding ───────────────
    # Seeded by migration 029. `bowel_habits`, `weight_history`,
    # `family_history` and `duration_pattern` are reused unchanged.
    #
    # Note what is NOT here: constipation and straining. They belong to
    # `bowel_habits` already, and they are also the vocabulary of the
    # trap — but asking about them is good history, so they stay a
    # coverage topic and the anchor list uses the words of the
    # CONCLUSION ("piles", "cream", "banding") instead of the question.
    "bleeding_character": [
        "mixed in", "mixed with", "mixed through", "in the stool",
        "on the paper", "colour of the blood", "dark blood", "bright red",
        "how much blood", "clots", "mucus", "what does the blood",
        "separate from",
    ],
    "tenesmus_incomplete": [
        "tenesmus", "incomplete", "not finished", "fully empty",
        "need to go again", "still need to go", "emptied properly",
        "urge to go", "feeling of wanting",
    ],
    "anaemia_symptoms": [
        "tired", "tiredness", "fatigue", "breathless", "pale",
        "short of breath", "dizzy on standing", "palpitations",
        "lacking energy", "anaemia", "anaemic", "iron",
    ],
    "change_from_baseline": [
        "different from", "different to", "same as usual", "like before",
        "changed", "new for you", "worse than usual", "unlike",
        "compared with", "is this the same",
    ],
}


def extract_topics(user_message: str) -> list[str]:
    """
    Scans a user message for keywords matching clinical topic categories.
    Uses the TOPIC_KEYWORDS dictionary.

    Matching is case-insensitive substring matching. A topic is only
    added once per message even if multiple keywords match it.

    Args:
        user_message (str): Raw text from user.

    Returns:
        list: Topic category names found in the message.
              e.g. ["meal_relationship", "medications"]
    """
    message_lower = user_message.lower()
    covered = []

    for topic_name, keywords in TOPIC_KEYWORDS.items():
        for keyword in keywords:
            if keyword in message_lower:
                covered.append(topic_name)
                break   # only add each topic once even if multiple keywords match

    return covered
