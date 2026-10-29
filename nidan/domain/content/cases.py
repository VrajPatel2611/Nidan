"""
cases.py
--------
Defines all 9 clinical case configurations for the virtual patient
simulator. Each case contains the patient persona, Gemini system
prompt, correct diagnosis, and bias detection configuration.

This file is the Python translation of docs/cases_design.md.
Never change this file without first updating cases_design.md.

Evaluators: medical students — system prompts tuned accordingly.

Case list:
  case_1: Ramesh Kumar, 48M — Chest pain — GERD vs Cardiac (labs exclude ACS)
  case_2: Kavya Menon,  29F — SOB + chest pain — PE vs Chest infection (CTPA req'd)
  case_3: Gopal Mehta,  74M — Acute confusion — UTI/delirium vs Stroke/Dementia
  case_4: Meera Patel,  35F — Fatigue — Hypothyroidism vs Depression (TFTs req'd)
  case_5: Aisha Khan,   21F — Vomiting + abdo pain — DKA vs Gastroenteritis
  case_6: Priya Sharma, 28F — Headache — Hypertension vs stress/tension
          (examination-required: the diagnosis is on the blood pressure cuff)
  case_7: Arjun Shah,   10M — Cough and wheeze — Asthma vs chest infection
          (two voices: the child and his mother Sunita)
  case_8: Naveen Reddy, 58M — Rectal bleeding — Colorectal cancer vs piles
          (the anchor is TRUE: he has haemorrhoids, and they are not the cause)
  case_10: Harbans Singh, 68M — Collapse — Aortic stenosis vs a simple faint
          (id 9 is reserved for the case still to be written;
           the number names the content, not the order it was authored)
"""

from nidan.domain.types import Case, CaseSummary

CASES = {

    # ──────────────────────────────────────────────────────────────────
    # CASE 1: Ramesh Kumar — Chest pain — GERD vs Cardiac
    # ──────────────────────────────────────────────────────────────────
    "case_1": {
        "id": "case_1",
        "title": "The Chest Pain Trap",
        "patient_intro": (
            "A 48-year-old male accountant named Ramesh Kumar visits the clinic "
            "complaining of chest pain that has been present for the past 3 days. "
            "He appears mildly anxious but is not in acute distress."
        ),
        "opening_line": (
            "I have been having this pain in my chest for about 3 days now. "
            "It started after a work dinner and has not really gone away. "
            "I am a bit worried about what it might be."
        ),
        "system_prompt": (
            "You are playing Ramesh Kumar, a 48-year-old male accountant presenting "
            "with chest pain for 3 days. Speak naturally, without medical jargon. "
            "Keep responses to 2-4 sentences. You are mildly worried.\n\n"
            "CRITICAL RULE: Only reveal information when DIRECTLY asked. "
            "Do not volunteer clinical details not asked about.\n\n"
            "YOUR HISTORY — reveal ONLY when asked:\n"
            "- Pain character: BURNING sensation in mid-chest, sometimes felt in the "
            "throat. Not crushing or squeezing. Describe as 'burning' ONLY if asked "
            "what the pain feels like.\n"
            "- Meal relationship: Definitely worse after meals, especially spicy food "
            "and coffee (2-3 cups/day). Mention ONLY if asked about food or eating.\n"
            "- Medications: Takes ibuprofen 400mg EVERY DAY for chronic lower back "
            "pain. Disclose ONLY if asked about medications, tablets, or what you take.\n"
            "- Radiation: Pain does NOT go to arm or jaw. Say so ONLY if asked where "
            "it spreads or radiates.\n"
            "- Associated symptoms: NO shortness of breath, NO sweating, NO nausea. "
            "Share ONLY if specifically asked.\n"
            "- Postural triggers: Lying down after eating makes it worse; sitting up "
            "helps slightly. Share ONLY if asked about triggers or position.\n"
            "- Antacids: Tried an antacid once out of curiosity and it helped "
            "temporarily. Share ONLY if asked about remedies tried.\n"
            "- Family history: Father had type 2 diabetes, NO heart attacks in the "
            "family. Share ONLY if asked about family history.\n"
            "- Duration/onset: 3 days. Started the evening after a work dinner with "
            "spicy Indian food.\n"
            "- Severity: 4-5 out of 10. Uncomfortable but manageable.\n"
            "- Previous: Occasional brief burning after spicy meals, always resolved "
            "within an hour. This episode has lasted 3 days.\n\n"
            "PERSONALITY: Cooperative, slightly anxious, gives concise direct answers. "
            "Does not use medical terminology. Occasionally mentions being very busy "
            "at work."
        ),
        "correct_diagnosis": (
            "GERD (Gastroesophageal Reflux Disease) — specifically NSAID-induced GERD"
        ),
        "anchor_topic": "cardiac / heart disease",
        "anchor_keywords": [
            # NOT bare "heart" — it is a substring of "heartburn", which is a
            # contradictory clue, and the detectors match by substring. The
            # specific phrases below carry the same cardiac intent without
            # matching a learner who is correctly chasing reflux (invariant
            # C-4, DATA_MODEL §8.1).
            "heart problem", "heart disease", "heart condition", "my heart",
            "heart failure",
            # NOT "mi" — it is a substring of "exaMIne", "voMIting" and
            # "abdoMInal", so ordinary questions counted as cardiac fixation.
            # "myocardial" and "heart attack" carry the same intent safely.
            "cardiac", "myocardial", "infarction", "angina",
            "ecg", "ekg", "electrocardiogram", "troponin", "cholesterol",
            "coronary", "arteri", "palpitation", "heart attack", "stent",
            "bypass", "cardiologist", "cardiac enzyme", "stress test",
            "arrhythmia", "tachycardia", "bradycardia", "irregular heartbeat",
            "ischaemia", "ischemia", "aorta", "pericarditis", "aed",
            "defibrillator", "chest tightness"
        ],
        "alternative_topics": [
            # NOT "gi" — substring of "allerGIes", "beGIn", "reGIon".
            # "gastro" and "gastrointestinal" cover it.
            "reflux", "gastro", "gastrointestinal", "stomach",
            "oesophagus", "esophagus", "food", "meal", "eating", "diet",
            "spicy", "ibuprofen", "nsaid", "anti-inflammatory", "painkiller",
            "acid", "antacid", "heartburn", "burning", "after eating",
            "lying down", "coffee", "alcohol", "digestive", "indigestion",
            "bloating", "regurgitation", "throat", "swallowing", "peptic"
        ],
        "required_topics": [
            "pain_character",
            "meal_relationship",
            "radiation",
            "associated_symptoms",
            "medications",
            "family_history",
            "duration_pattern",
            "relieving_factors",
        ],
        "minimum_questions": 7,
        # Curated disconfirming keyword sets (arguing AGAINST cardiac / for GERD).
        # Each inner list is one line of enquiry; terms are specific to the
        # reflux story and deliberately do NOT overlap the cardiac anchor.
        "contradictory_clues": [
            ["burning", "heartburn"],
            ["after meal", "after eating", "meals", "spicy", "coffee", "greasy", "fatty"],
            ["ibuprofen", "nsaid", "anti-inflammatory", "painkiller", "naproxen", "diclofenac"],
            ["antacid", "gaviscon", "omeprazole", "proton pump", "ppi", "ranitidine"],
            ["lying down", "lie down", "recline", "bending", "stoop", "sitting up"],
            ["regurgitation", "acid reflux", "sour taste", "indigestion", "waterbrash", "belch"],
        ],
    },

    # ──────────────────────────────────────────────────────────────────
    # CASE 2: Kavya Menon — Breathless & Chest Pain — PE vs Chest Infection
    # Lab-required: D-dimer + CTPA mandatory for diagnosis
    # ──────────────────────────────────────────────────────────────────
    "case_2": {
        "id": "case_2",
        "title": "Breathless and Worried",
        "patient_intro": (
            "Kavya Menon, a 29-year-old marketing executive, walks into A&E "
            "breathing faster than normal. She has had 2 days of worsening "
            "shortness of breath and a right-sided chest pain that is sharply "
            "worse when she takes a deep breath or coughs. She looks anxious."
        ),
        "opening_line": (
            "I have been struggling to catch my breath for about 2 days now and "
            "there is a sharp pain on the right side of my chest — it is really "
            "bad when I breathe in deeply. I thought I caught something on the "
            "flight back from Dubai last week but it is getting worse, not better."
        ),
        "system_prompt": (
            "You are playing Kavya Menon, a 29-year-old marketing executive. "
            "You are visibly short of breath, anxious, and in pain. "
            "Keep responses to 2-4 sentences. You are frightened.\n\n"
            "CRITICAL RULE: Only reveal information when DIRECTLY asked. "
            "Do not volunteer clinical details.\n\n"
            "YOUR HISTORY — reveal ONLY when asked:\n"
            "- Pain: SHARP, PLEURITIC right-sided chest pain, dramatically "
            "WORSE on deep breathing or coughing. Unlike anything before.\n"
            "- Breathlessness: Progressive over 2 days, now SOB even walking "
            "slowly. Was perfectly fine before this.\n"
            "- Haemoptysis: Small amount of BLOOD-TINGED SPUTUM once this "
            "morning. Share ONLY if asked about blood in sputum or coughing up blood.\n"
            "- Flight: Flew back from an 11-HOUR FLIGHT from Dubai 5 days ago. "
            "Sat in a window seat the entire flight, barely moved. Share ONLY if "
            "asked about travel, flights, or recent journeys.\n"
            "- OCP: Has been on the COMBINED ORAL CONTRACEPTIVE PILL (Microgynon) "
            "for 2 years. Share ONLY if asked about medications or the pill.\n"
            "- Calf: Right calf has been ACHING and LOOKS SLIGHTLY SWOLLEN for "
            "3 days. She thought she just pulled a muscle. Share ONLY if asked "
            "about leg pain, calf, or swelling.\n"
            "- No fever, no productive sputum, no sick contacts, no sore throat.\n"
            "- Previous VTE: None. No family history of blood clots she is aware of.\n"
            "- Smoking: Non-smoker. Alcohol socially. BMI normal.\n"
            "- Immobility: The 11-hour flight was the longest she had sat still in "
            "years. No other recent periods of immobility.\n\n"
            "PERSONALITY: Frightened, cooperative, tends to catastrophise slightly. "
            "Does not know anything about blood clots or DVT."
        ),
        "correct_diagnosis": (
            "Pulmonary embolism (PE) / venous thromboembolism (VTE)"
        ),
        "anchor_topic": "chest infection / pneumonia / URTI",
        "anchor_keywords": [
            "infection", "pneumonia", "antibiotic", "chest infection", "viral",
            "cold", "flu", "bronchitis", "bacteria", "sputum", "productive",
            "upper respiratory", "throat infection", "tamiflu", "oseltamivir",
            "caught something", "plane germs", "amoxicillin",
            "cough syrup", "nebuliser", "steam inhalation", "gp", "sick",
        ],
        "alternative_topics": [
            "dvt", "deep vein", "clot", "embolism", "pulmonary embolism", "ctpa",
            "anticoagulant", "d-dimer", "heparin", "warfarin", "rivaroxaban",
            "wells", "thrombosis", "ocp", "pill", "contraceptive", "flight",
            "flew", "travel", "immobile", "immobility", "calf", "leg swelling",
            "leg pain", "virchow", "pleuritic", "haemoptysis", "risk factor",
            "clotting", "coagulation", "thrombophilia",
        ],
        "required_topics": [
            "pain_character",
            "associated_symptoms",
            "medications",
            "travel_history",
            "leg_symptoms",
            "family_history",
            "duration_pattern",
            "relieving_factors",
        ],
        "minimum_questions": 8,
        # Curated disconfirming keyword sets (arguing AGAINST infection / for PE).
        # Specific to venous thromboembolism; no overlap with the infection anchor.
        "contradictory_clues": [
            ["pleuritic"],
            ["haemoptysis", "coughing up blood", "cough up blood", "blood-stained",
             "blood streaked", "blood-tinged", "blood in your phlegm"],
            ["calf", "leg swelling", "leg pain", "swollen leg", "leg is swollen", "leg swollen"],
            ["contraceptive", "the pill", "ocp", "oestrogen", "estrogen", "microgynon"],
            ["flight", "flew", "long haul", "long-haul", "long journey", "immobile",
             "immobility", "aeroplane", "airplane", "long flight"],
            ["dvt", "deep vein", "clot", "thrombosis", "embolism", "d-dimer",
             "wells score", "anticoagul"],
        ],
    },

    # ──────────────────────────────────────────────────────────────────
    # CASE 3: Gopal Mehta — Confusion — UTI vs Stroke/Dementia
    # ──────────────────────────────────────────────────────────────────
    "case_3": {
        "id": "case_3",
        "title": "The Confused Elderly Man",
        "patient_intro": (
            "A 74-year-old retired school teacher named Gopal Mehta is brought to "
            "the clinic by his daughter Anita. She says he has been confused and "
            "acting differently since yesterday. He is present and can speak but "
            "is not his usual self. You may address questions to either Gopal or Anita."
        ),
        "opening_line": (
            "[Anita speaking] I am very worried about my father. He has not been "
            "himself since yesterday evening. He was perfectly fine in the morning "
            "— reading his newspaper as usual — but by the evening he was not "
            "making sense. This is completely unlike him."
        ),
        "system_prompt": (
            "You are playing TWO characters in this consultation.\n\n"
            "CHARACTER 1 — GOPAL MEHTA: A 74-year-old retired school teacher who is "
            "confused and not his usual self. He speaks slowly, sometimes trails off, "
            "gives brief vague answers. He is oriented to place but his thoughts are "
            "muddled. He is NOT in pain. He answers with 1-2 sentences maximum.\n\n"
            "CHARACTER 2 — ANITA: Gopal's daughter, approximately 45 years old. "
            "She is the primary historian. Calm, concerned, observant. She gives "
            "clear concise answers. She does NOT use medical terminology.\n\n"
            "DEFAULT: Respond as ANITA unless the user directly addresses Gopal, "
            "'the patient', or 'the elderly man'.\n\n"
            "CRITICAL RULE: Only reveal information when DIRECTLY asked. "
            "Do not volunteer clinical details.\n\n"
            "ANITA'S HISTORY — reveal ONLY when asked:\n"
            "- Onset: SUDDEN, yesterday afternoon. He was COMPLETELY NORMAL "
            "yesterday morning. If asked when it started: 'Yesterday afternoon. He "
            "was fine in the morning, he was reading his newspaper.'\n"
            "- Baseline: Completely normal 3 days ago — sharp, doing crosswords, "
            "reading. This is ACUTE, not gradual. If asked if he was always like "
            "this: 'Absolutely not. He was perfectly normal 3 days ago.'\n"
            "- Fever: He has a LOW-GRADE FEVER of 37.8 degrees C. Anita checked. "
            "Share ONLY if asked about fever or temperature.\n"
            "- Urinary symptoms: He has been going to the toilet MORE FREQUENTLY "
            "than usual and mentioned it was UNCOMFORTABLE. Anita did not connect "
            "this to the confusion. Share ONLY if asked about urination or toilet.\n"
            "- Medications: Aspirin 75mg and amlodipine for blood pressure daily. "
            "No new medications. Share if asked.\n"
            "- Recent events: No falls, no hospital visits, no recent illness.\n"
            "- Focal neurology: Both arms and legs move fine. Face looks symmetrical. "
            "Speech is slow but NOT slurred. If asked about focal signs: 'His arms "
            "and legs are fine, his face looks normal, his speech is slow but clear.'\n"
            "- Headache/neck stiffness: None reported.\n"
            "- Hydration: He has barely drunk any water for 2 days — says he is not "
            "thirsty. Share ONLY if asked about fluid intake or hydration.\n\n"
            "GOPAL (when directly addressed):\n"
            "'I am... not feeling very well. A bit confused.' (how he feels)\n"
            "'I am at the... clinic. Anita brought me.' (where he is)\n"
            "'It is a little... uncomfortable when I go.' (urination — only if asked)\n"
            "Gopal's answers are brief and sometimes he trails off mid-sentence."
        ),
        "correct_diagnosis": (
            "Urinary Tract Infection (UTI) causing acute confusional state "
            "(delirium secondary to UTI in an elderly patient)"
        ),
        "anchor_topic": "stroke / dementia / neurological cause",
        "anchor_keywords": [
            "dementia", "alzheimer", "stroke", "brain", "ct scan",
            "neurologist", "tia", "mini-stroke", "memory loss",
            "brain scan", "mri head", "psychiatric", "cognitive decline",
            "neuro", "neurological", "brain bleed", "haemorrhage",
            "blood clot", "brain tumor", "transient ischaemic", "focal",
            "space occupying", "encephalopathy", "subdural"
        ],
        "alternative_topics": [
            "urine", "urinary", "pee", "frequency", "burning urine",
            "colour of urine", "smell of urine", "fever", "temperature",
            "infection", "uti", "antibiotic", "waterworks", "toilet",
            "passing water", "painful urination", "incontinence",
            "cloudy urine", "going more often", "sepsis"
        ],
        "required_topics": [
            "onset_timing",
            "baseline_cognition",
            "fever",
            "urinary_symptoms",
            "medications",
            "recent_illness",
            "focal_neuro_signs",
            "hydration",
        ],
        "minimum_questions": 8,
        # Curated disconfirming keyword sets (arguing AGAINST stroke/dementia,
        # for UTI-delirium). Specific to infection/acute-onset; no anchor overlap.
        "contradictory_clues": [
            ["urine", "urinary", "passing water", "waterworks", "toilet", "dysuria",
             "wee", "weeing", "pee", "peeing"],
            ["fever", "temperature", "pyrexia", "feverish"],
            ["sudden", "abrupt", "yesterday", "overnight", "acute onset", "acutely"],
            ["baseline", "usual self", "normal before", "before this", "himself", "his usual"],
            ["dehydrat", "drinking", "fluid intake", "not drinking", "how much water"],
            ["uti", "urine infection", "urinary tract", "urinalysis", "urine dip",
             "urine sample", "sepsis"],
        ],
    },

    # ──────────────────────────────────────────────────────────────────
    # CASE 4: Meera Patel — Fatigue — Hypothyroidism vs Depression
    # ──────────────────────────────────────────────────────────────────
    "case_4": {
        "id": "case_4",
        "title": "The Tired Teacher",
        "patient_intro": (
            "A 35-year-old primary school teacher named Meera Patel visits the "
            "clinic. She has been feeling very tired for the past 3 months and "
            "has noticed she is putting on weight despite no change in her eating "
            "habits. She is concerned and wants to find out what is wrong."
        ),
        "opening_line": (
            "I have been so tired for about 3 months now and I just cannot shake "
            "it. The strange thing is I have been putting on weight even though I "
            "am not eating any more than usual — if anything I am eating a little "
            "less."
        ),
        "system_prompt": (
            "You are playing Meera Patel, a 35-year-old primary school teacher "
            "with progressive fatigue and unexplained weight gain for 3 months. "
            "Speak naturally. Keep responses to 2-4 sentences.\n\n"
            "CRITICAL RULE: Only reveal information when DIRECTLY asked. "
            "Do not volunteer clinical details.\n\n"
            "YOUR HISTORY — reveal ONLY when asked:\n"
            "- Mood: Your MOOD IS FINE. You are NOT depressed. You still enjoy "
            "your job and your students. You are not sad, not hopeless, still "
            "doing things you enjoy. If asked about mood or depression: 'No, my "
            "mood is actually fine. I still enjoy things. I am just physically "
            "exhausted and slow.'\n"
            "- Weight: Going UP despite eating LESS than before. If asked about "
            "diet or weight: 'I am actually eating less than before but the weight "
            "is still going up. It does not make sense to me.'\n"
            "- Cold intolerance: ALWAYS COLD — wearing extra layers when colleagues "
            "are comfortable, even in warm weather, even in summer. If asked about "
            "feeling cold or temperature: 'Yes, I am always cold. My colleagues "
            "think it is warm and I am sitting there in a cardigan.'\n"
            "- Hair: FALLING OUT more than usual — noticeable on brush and shower "
            "drain. If asked about hair: 'Yes, I have been losing more hair than "
            "usual. I see it every morning on my brush.'\n"
            "- Bowel habits: CONSTIPATED for past 2 months — new for her. If asked "
            "about bowel habits: 'I have been a bit constipated for about 2 months. "
            "That is new for me.'\n"
            "- Family history: MOTHER takes levothyroxine for underactive thyroid. "
            "If asked about family history or thyroid: 'My mother has an underactive "
            "thyroid. She has been on tablets for years.'\n"
            "- Menstrual: PERIODS HEAVIER over past 2 months. If asked: 'They have "
            "become much heavier recently, yes.'\n"
            "- Thinking: Feels MENTALLY SLOW — has to re-read things, making small "
            "errors at work. If asked about concentration: 'I feel mentally slow. "
            "I have to read things twice and I have been making silly errors at "
            "work which is not like me at all.'\n"
            "- Energy: Tired ALL DAY. Wakes up exhausted despite adequate sleep.\n"
            "- Duration: 3 months of gradually worsening symptoms.\n\n"
            "PERSONALITY: Thoughtful, engaged with her job, slightly puzzled by "
            "her symptoms, not anxious. Describes symptoms precisely when asked."
        ),
        "correct_diagnosis": (
            "Primary hypothyroidism (likely autoimmune — Hashimoto's thyroiditis)"
        ),
        "anchor_topic": "depression / burnout / lifestyle issues",
        "anchor_keywords": [
            "depression", "anxiety", "stress", "mental health", "counselling",
            "therapy", "mood disorder", "sadness", "emotional", "sleep hygiene",
            "exercise", "calories", "weight loss program", "lifestyle",
            "burnout", "motivation", "psychiatrist", "psychologist", "cbt",
            "antidepressant", "ssri", "sad", "hopeless", "helpless",
            "work stress", "teacher stress", "emotional eating", "gym",
            "workout", "physical activity", "insomnia"
        ],
        "alternative_topics": [
            "thyroid", "cold", "temperature", "hair", "constipation", "skin",
            "dry skin", "bowel", "period", "menstrual", "family thyroid",
            "metabolism", "swelling neck", "hoarse voice", "goitre", "t4",
            "tsh", "hormone", "thyroid test", "always cold", "intolerant",
            "brittle nails", "puffy face", "hair loss", "thinning hair",
            "levothyroxine", "underactive"
        ],
        "required_topics": [
            "mood_vs_physical",
            "weight_change_pattern",
            "temperature_tolerance",
            "bowel_habits",
            "hair_skin_changes",
            "family_thyroid_history",
            "menstrual_changes",
            "energy_time_pattern",
        ],
        "minimum_questions": 8,
        # Curated disconfirming keyword sets (arguing AGAINST depression, for
        # hypothyroidism). Specific to thyroid physical features; no anchor overlap.
        "contradictory_clues": [
            ["cold", "chilly", "cold intolerance", "layers", "cardigan", "shiver", "feel the cold"],
            ["hair loss", "losing hair", "hair falling", "thinning hair", "hair thinning", "brittle nail"],
            ["constipat", "bowel"],
            ["thyroid", "levothyroxine", "underactive", "goitre", "hoarse", "neck swelling", "puffy face"],
            ["weight gain", "putting on weight", "gaining weight", "gained weight", "eating less", "weight going up"],
            ["heavier period", "periods heavier", "menorrhagia", "menstrual", "heavier bleed", "heavier flow"],
        ],
    },

    # ──────────────────────────────────────────────────────────────────
    # CASE 5: Aisha Khan — Vomiting & Abdo Pain — DKA vs Gastroenteritis
    # Lab-required: blood glucose + ketones + ABG mandatory for diagnosis
    # ──────────────────────────────────────────────────────────────────
    "case_5": {
        "id": "case_5",
        "title": "The Student Who Cannot Stop Being Sick",
        "patient_intro": (
            "Aisha Khan, a 21-year-old university student, is brought to A&E by "
            "her flatmate. She has been vomiting all day with severe central "
            "abdominal pain and feels extremely unwell. She is dehydrated, "
            "tachycardic, and appears to be breathing unusually deeply and rapidly."
        ),
        "opening_line": (
            "I feel absolutely dreadful. I have been vomiting since this morning "
            "and my stomach is in agony. My flatmate had a stomach bug last week "
            "so I thought I caught it from her but I just keep getting worse. "
            "I can barely stand up."
        ),
        "system_prompt": (
            "You are playing Aisha Khan, a 21-year-old university student who "
            "feels completely awful — exhausted, nauseous, and in severe abdominal "
            "pain. You are breathing faster and deeper than normal, though you do "
            "not realise this yourself. Keep responses to 2-4 sentences.\n\n"
            "CRITICAL RULE: Only reveal information when DIRECTLY asked. "
            "Do not volunteer clinical details.\n\n"
            "YOUR HISTORY — reveal ONLY when asked:\n"
            "- Vomiting/nausea: Vomiting since morning, about 8 times. Cannot keep "
            "anything down, not even water.\n"
            "- Abdo pain: Central, constant, severe cramping pain. Not colicky.\n"
            "- Duration of THIS illness: Started yesterday evening with nausea, "
            "terrible today. If asked how long: 'About a day and a half.'\n"
            "- PRIOR SYMPTOMS (crucial — 4 weeks): Has been EXTREMELY THIRSTY for "
            "the past 4 weeks — drinking 4-5 litres of water a day. Also going to "
            "the toilet to urinate very frequently, even waking at night. Share "
            "ONLY if asked about thirst, urination, or whether she had symptoms "
            "before this vomiting started.\n"
            "- Weight loss: Has lost about 5-6 kg over the past 4-5 weeks without "
            "trying. Clothes are noticeably looser. Share ONLY if asked about "
            "weight.\n"
            "- Breathlessness/breathing: She does not notice anything unusual about "
            "her breathing — she just feels terrible. If specifically asked whether "
            "her breathing feels different: 'I suppose I am breathing quite fast, "
            "yes. I thought that was just the pain.'\n"
            "- Breath smell: She is NOT aware of any fruity or acetone smell — her "
            "flatmate mentioned it, not her.\n"
            "- Sick contacts: Her flatmate had a stomach bug 7-10 days ago and "
            "recovered in 2 days. Aisha's illness is now lasting much longer.\n"
            "- Past history: Nothing significant, no known diabetes, no regular "
            "medications, no allergies. No previous hospital admissions.\n"
            "- Family history: Both grandparents on mother's side have TYPE 2 "
            "diabetes. No family history of TYPE 1 diabetes that she knows of. "
            "Share ONLY if asked about family history or family diabetes.\n"
            "- Alcohol: Had a few drinks on Friday but nothing excessive.\n"
            "- Last meal: Ate normally yesterday lunchtime before the nausea started. "
            "Has not eaten today at all.\n\n"
            "PERSONALITY: Miserable, frightened, slightly confused from dehydration. "
            "Tries to answer questions but keeps saying she wants to be sick."
        ),
        "correct_diagnosis": (
            "Diabetic ketoacidosis (DKA) in new-onset type 1 diabetes mellitus"
        ),
        "anchor_topic": "gastroenteritis / food poisoning / viral illness",
        "anchor_keywords": [
            "gastroenteritis", "gastro", "food poisoning", "norovirus",
            "stomach bug", "vomiting bug", "viral", "self-limiting",
            "ondansetron", "metoclopramide", "antiemetic", "rehydration",
            "oral rehydration", "dioralyte", "caught from", "same as flatmate",
            "infectious", "contagious", "passed it on", "dehydrated from vomiting",
            "iv fluids for vomiting", "give it a few days", "rest fluids",
        ],
        "alternative_topics": [
            "glucose", "sugar", "diabetes", "dka", "ketones", "polydipsia",
            "polyuria", "thirst", "weight loss", "insulin", "hyperglycaemia",
            "blood sugar", "acetone", "fruity breath", "deep breathing",
            "kussmaul", "acidosis", "abg", "ph", "bicarbonate", "hba1c",
            "type 1", "t1dm", "blood glucose", "ketoacidosis",
        ],
        "required_topics": [
            "thirst_polyuria",
            "weight_history",
            "duration_pattern",
            "associated_symptoms",
            "pain_character",
            "medications",
            "family_history",
            "recent_illness",
        ],
        "minimum_questions": 8,
        # Curated disconfirming keyword sets (arguing AGAINST gastroenteritis,
        # for DKA). Specific to diabetes/ketoacidosis; no overlap with the anchor.
        "contradictory_clues": [
            ["thirsty", "thirst", "polydipsia", "drinking a lot", "drinking lots",
             "drinking more", "excessive drink"],
            ["urinating more", "passing more urine", "polyuria", "peeing more",
             "toilet more", "waking at night", "going more often"],
            ["weight loss", "lost weight", "losing weight", "clothes looser",
             "clothes are loose", "thinner"],
            ["fruity", "acetone", "pear drop", "sweet-smelling breath", "sweet breath"],
            ["deep breathing", "fast breathing", "rapid breathing", "kussmaul",
             "breathing fast", "breathing quickly", "sighing"],
            ["glucose", "blood sugar", "sugar level", "diabetes", "ketone",
             "hyperglyc", "hba1c", "type 1 diabetes"],
        ],
    },

    # ──────────────────────────────────────────────────────────────────
    # CASE 6: Priya Sharma — Headache — Hypertension vs stress/tension
    # Designed in docs/cases_design.md as "CASE 2: The Headache That Is
    # Not Stress". Examination-required: the diagnosis is on the cuff.
    # ──────────────────────────────────────────────────────────────────
    "case_6": {
        "id": "case_6",
        "title": "The Headache That Is Not Stress",
        "patient_intro": (
            "A 28-year-old female software engineer named Priya Sharma visits "
            "the clinic. She has been getting headaches almost every day for "
            "the past 2 weeks and is finding it difficult to concentrate at "
            "work."
        ),
        "opening_line": (
            "I have been getting these headaches almost every day for about "
            "two weeks. I cannot seem to shake them. It is affecting my work "
            "and I cannot concentrate properly."
        ),
        "system_prompt": (
            "You are playing Priya Sharma, a 28-year-old software engineer at "
            "a startup, with daily headaches for 2 weeks. Speak naturally, "
            "without medical jargon. Keep responses to 2-4 sentences.\n\n"
            "CRITICAL RULE: Only reveal information when DIRECTLY asked. "
            "Do not volunteer clinical details not asked about.\n\n"
            "YOUR HISTORY — reveal ONLY when asked:\n"
            "- Character: THROBBING and POUNDING, 'like pounding from inside'. "
            "NOT a tight band. Describe it that way ONLY if asked what it "
            "feels like.\n"
            "- Location: mainly at the BACK OF THE HEAD, towards the neck. "
            "Share ONLY if asked where it is.\n"
            "- Timing: WORST IN THE MORNING — already there on waking, eases "
            "during the day, returns later. Share ONLY if asked about timing.\n"
            "- Vision: things go BLURRY during the headache sometimes, a few "
            "times over the two weeks. Share ONLY if asked about vision.\n"
            "- Blood pressure: NEVER CHECKED since school. Say so ONLY if "
            "asked.\n"
            "- Medications: on the COMBINED ORAL CONTRACEPTIVE PILL for three "
            "years. Occasional paracetamol, which barely helps. Disclose ONLY "
            "if asked about medication, tablets, the pill, or contraception.\n"
            "- Family: MOTHER has high blood pressure, on tablets for years. "
            "Share ONLY if asked about family.\n"
            "- Stress: work is busy, but it is ALWAYS busy. Nothing changed "
            "when the headaches started — no deadline, no new project, no "
            "life event. Say this if asked about stress.\n"
            "- Sleep: FINE, about 7 hours. Not a sleep problem.\n"
            "- NOT present: no neck stiffness, no fever, no photophobia, no "
            "aura, no vomiting, no weakness, no head injury.\n\n"
            "PERSONALITY: Articulate, a little frustrated, assumes it is "
            "stress and expects to be told so."
        ),
        "correct_diagnosis": (
            "Hypertension, newly diagnosed — associated with combined oral "
            "contraceptive use"
        ),
        "anchor_topic": "stress / tension headache / lifestyle",
        # NOTE. Three terms from the design doc's anchor list are deliberately
        # absent, each for invariant C-4 or C-9:
        #   "tension"            ⊂ "hypertension" — the clue that solves it
        #   "vision for screens" ⊃ "vision"       — likewise
        #   "sleep"              ⊂ "sleeping"     — C-9, an ordinary word
        # The detectors match by substring, so each would have counted a
        # learner asking the right question as fixating on the wrong one.
        "anchor_keywords": [
            "stress", "stressed", "tension headache", "anxiety",
            "work pressure", "overwork", "burnout", "migraine", "painkiller",
            "relax", "rest", "screen time", "posture", "massage",
            "stress relief", "mental health", "tired", "exhausted",
            "caffeine headache", "dehydration headache", "eye strain",
            "glasses", "work life balance", "meditation", "yoga",
            "sleep quality", "time off",
        ],
        "alternative_topics": [
            "blood pressure", "hypertension", "bp reading", "bp check",
            "dizziness", "blurry vision", "floaters", "family history bp",
            "family history stroke", "kidney", "morning headache",
            "throbbing", "pulsating", "pounding", "back of head",
            "monitor", "measurement", "contraceptive", "oral contraceptive",
            "fundoscopy",
        ],
        "required_topics": [
            "headache_character",
            "timing_pattern",
            "visual_symptoms",
            "family_history",
            "BP_awareness",
            "medications",
            "lifestyle",
            "stress_assessment",
        ],
        "minimum_questions": 7,
        # Curated disconfirming keyword sets (arguing AGAINST stress/tension,
        # for hypertension), from the design doc's eight clues. Clue 4 ("no
        # specific stress event triggered it") is absent: it is a true clue but
        # there is no question a learner asks that matches it as a keyword.
        "contradictory_clues": [
            ["morning", "on waking", "wakes", "first thing", "worst in the"],
            ["blurry", "blurred vision", "vision", "visual", "eyesight",
             "spots"],
            ["blood pressure", "hypertension", "checked", "measured",
             "bp reading", "ever had it checked"],
            ["mother", "family history", "runs in the family", "parent",
             "hereditary", "relative"],
            ["throbbing", "pounding", "pulsating", "back of the head",
             "posterior", "neck"],
            ["contraceptive", "pill", "birth control", "hormonal",
             "the pill"],
        ],
    },

    # ──────────────────────────────────────────────────────────────────
    # CASE 7: Arjun Shah, 10M (mother Sunita) — Cough and wheeze —
    # First presentation of asthma vs chest infection.
    # Designed in docs/cases_design.md as "CASE 5: The Wheezing Child".
    # Two voices: the chatbot plays whoever the learner addresses.
    # ──────────────────────────────────────────────────────────────────
    "case_7": {
        "id": "case_7",
        "title": "The Wheezing Child",
        "patient_intro": (
            "Sunita brings her 10-year-old son Arjun to the clinic. She says "
            "he has had a cough and a wheezing sound in his chest for the past "
            "few days. Arjun is sitting next to her and looks a little "
            "uncomfortable but is not in severe distress."
        ),
        "opening_line": (
            "He has had this cough for a few days now. It seems worse at night "
            "when he is trying to sleep — it wakes him up sometimes. There is "
            "a wheezing sound in his chest."
        ),
        "system_prompt": (
            "You are playing TWO people: SUNITA, the worried but calm mother, "
            "and ARJUN, her 10-year-old son. Reply as whoever the learner "
            "addresses; default to Sunita. Arjun answers questions put to him "
            "directly, in a 10-year-old's words. Keep responses to 2-4 "
            "sentences.\n\n"
            "CRITICAL RULE: Only reveal information when DIRECTLY asked. "
            "Do not volunteer clinical details not asked about.\n\n"
            "YOUR HISTORY — reveal ONLY when asked:\n"
            "- Fever: NO fever. Sunita checked this morning: 36.8°C, normal. "
            "Say so ONLY if asked.\n"
            "- Coryza: NO runny nose, NO sore throat. Just the cough and the "
            "wheeze. Share ONLY if asked.\n"
            "- Timing: WORST AT NIGHT and in the EARLY MORNING. Wakes him. "
            "Share ONLY if asked about timing.\n"
            "- Exercise: at PE last week he coughed and wheezed badly after "
            "running; the teacher was concerned. Share ONLY if asked about "
            "exercise or sport.\n"
            "- Cold air: going outside on cool mornings makes it much worse. "
            "Share ONLY if asked about weather or cold.\n"
            "- Recurrence: it has happened TWICE BEFORE in the past year. "
            "Sunita thought it was a bad cough each time and it went away on "
            "its own. Share ONLY if asked whether this has happened before.\n"
            "- Family: Arjun's GRANDFATHER has asthma and uses an inhaler. "
            "Sunita has HAY FEVER and takes antihistamines every spring. "
            "Share ONLY if asked about family.\n"
            "- Impact: he went to school yesterday but was uncomfortable all "
            "day and did not do PE. He is usually very active. Share ONLY if "
            "asked about school or activity.\n"
            "- As ARJUN, if asked directly about his chest: 'Yeah, when I run "
            "a lot it gets really tight and then I start coughing and it "
            "sounds funny. It is embarrassing in front of my friends.'\n"
            "- NOT present: no weight loss, no night sweats, no choking "
            "episode, no pets at home, no damp at home, no smokers at home.\n\n"
            "PERSONALITY: Sunita is attentive and precise, and has not "
            "connected the episodes to each other. Arjun is cooperative and "
            "slightly embarrassed."
        ),
        "correct_diagnosis": "First presentation of asthma",
        "anchor_topic": "chest infection / viral illness / antibiotics",
        # NOTE. Four terms from the design doc's anchor list are deliberately
        # absent, and the first two matter most:
        #   "fever", "temperature" — these are clue[0]. The doc's own Anchor
        #     Test says the fever question "is actually correct regardless of
        #     the diagnosis"; leaving them in the anchor list would have
        #     scored the single most discriminating question in the case as
        #     evidence of fixating on infection (C-4).
        #   "cold"               ⊂ "cold air" — same collision
        #   "ear", "ill"         — too short to match safely: "ear" fires on
        #     "year" and "hear", "ill" on "still" and "will"
        "anchor_keywords": [
            "infection", "chest infection", "viral", "virus", "bacteria",
            "bacterial", "antibiotic", "penicillin", "amoxicillin",
            "common cold", "caught a cold", "flu", "contagious", "school bug",
            "paracetamol", "runny nose", "throat", "sore throat", "tonsils",
            "ear infection", "earache", "lymph node", "cough syrup",
            "inhale steam", "green mucus", "yellow mucus", "blocked nose",
            "caught something", "pneumonia", "bronchitis",
        ],
        "alternative_topics": [
            "asthma", "wheeze", "trigger", "exercise", "cold air", "night",
            "morning", "allergy", "eczema", "hay fever", "family asthma",
            "atopy", "inhaler", "recurring", "bronchospasm", "sport",
            "pe lesson", "running", "wake up coughing", "seasonal",
            "peak flow", "spirometry",
        ],
        "required_topics": [
            "fever_infection_signs",
            "symptom_timing_pattern",
            "exercise_trigger",
            "cold_air_trigger",
            "duration_recurrence",
            "family_atopy_history",
            "school_sport_impact",
        ],
        "minimum_questions": 7,
        # Curated disconfirming keyword sets (arguing AGAINST infection, for
        # asthma). The doc's clue 8 ("no sick contacts") is absent: every
        # phrasing of it collided with an anchor keyword under C-4.
        # "run" is absent from clue[2] because it is inside "runny nose".
        "contradictory_clues": [
            ["fever", "temperature", "febrile", "hot", "any temperature"],
            ["night", "at night", "early morning", "wakes", "waking",
             "nocturnal"],
            ["exercise", "running", "runs", "sport", "pe lesson", "exertion",
             "games", "football", "playing"],
            ["cold air", "cold weather", "winter", "outside", "outdoors",
             "weather"],
            ["happened before", "previous", "recurring", "again",
             "first time", "ever had", "in the past"],
            ["asthma", "inhaler", "grandfather", "hay fever", "eczema",
             "allergy", "atopic", "antihistamine"],
            ["wheeze", "wheezing", "whistling", "tight chest", "chest tight",
             "tightness"],
        ],
    },

    # ──────────────────────────────────────────────────────────────────
    # CASE 10: Harbans Singh, 68M — Collapse — Aortic stenosis vs a faint
    # The patient offers the trap himself in his opening line. Three of
    # the five discriminating features are history; two need the hands.
    # ──────────────────────────────────────────────────────────────────
    "case_10": {
        "id": "case_10",
        "title": "The Faint That Was Not a Faint",
        "patient_intro": (
            "A 68-year-old retired postmaster named Harbans Singh attends with "
            "his wife, who insisted he come. He has blacked out twice in the "
            "past six weeks. He looks well and is faintly embarrassed to be "
            "taking up anyone's time."
        ),
        "opening_line": (
            "I passed out twice in the last few weeks. My wife made me come. "
            "I expect I just stood up too quickly — that happens at my age, "
            "does it not?"
        ),
        "system_prompt": (
            "You are playing Harbans Singh, a 68-year-old retired postmaster "
            "who has had two blackouts in six weeks. Speak plainly, no medical "
            "jargon. Keep responses to 2-4 sentences. You are mildly "
            "embarrassed and keen not to make a fuss.\n\n"
            "CRITICAL RULE: Only reveal information when DIRECTLY asked. "
            "Do not volunteer clinical details not asked about.\n\n"
            "YOU BELIEVE this was just standing up too fast, and you will say "
            "so if given the chance. You are not hiding anything — nobody has "
            "asked you the right questions yet.\n\n"
            "YOUR HISTORY — reveal ONLY when asked:\n"
            "- Circumstances: BOTH times you were WALKING UPHILL — once on the "
            "stairs at home carrying washing, once on the slope to the market. "
            "Neither time were you getting up from a chair. Say this ONLY if "
            "asked what you were doing.\n"
            "- Warning: NONE AT ALL. No dizziness, no sickness, no sweating, "
            "no ringing in the ears, no going dark at the edges. 'One moment I "
            "was walking, the next I was on the ground.' Share ONLY if asked "
            "about warning.\n"
            "- Recovery: awake within a minute, knew exactly where you were. "
            "No confusion, no sleepiness, no bitten tongue, no wetting "
            "yourself. Your wife saw the second one: no shaking, no jerking. "
            "Share ONLY if asked about afterwards.\n"
            "- On exertion: for about 6 MONTHS you have been breathless "
            "walking up the slope and have to stop halfway. A TIGHT BAND "
            "across the chest when you push on, gone within two minutes of "
            "stopping. Never at rest. Share ONLY if asked.\n"
            "- Palpitations: NONE. No racing, no skipped beats, no fluttering. "
            "Share ONLY if asked.\n"
            "- Medications: TAMSULOSIN for the prostate, started 8 months ago. "
            "AMLODIPINE for blood pressure for 5 years. Nothing else. "
            "Disclose ONLY if asked about medication or tablets.\n"
            "- Past: a doctor mentioned a HEART MURMUR years ago and said to "
            "keep an eye on it. You forgot about it. Share ONLY if asked about "
            "past medical history or the heart.\n"
            "- Family: father died at 70 of 'heart trouble'. No young or "
            "sudden deaths in the family.\n"
            "- NOT present: no chest pain at rest, no breathlessness lying "
            "flat, no waking at night short of breath, no ankle swelling, no "
            "weight loss, no fever, no head injury, no alcohol, no drugs.\n\n"
            "PERSONALITY: Understated, polite, inclined to minimise. Answers "
            "exactly what is asked and no more."
        ),
        "correct_diagnosis": (
            "Severe calcific aortic stenosis causing exertional syncope"
        ),
        "anchor_topic": "vasovagal faint / postural hypotension / old age",
        # NOTE. The drug names are deliberately NOT anchor keywords, even
        # though blaming the tamsulosin is the trap's strongest branch.
        # "What are you taking?" is the `medications` required topic and is
        # good history; scoring it as fixation would punish the question and
        # reward skipping it. The fixation is in the conclusion, not the
        # question, so only "medication side effect" is listed.
        "anchor_keywords": [
            "vasovagal", "faint", "fainting", "simple faint", "blackout spell",
            "stood up too", "standing up too", "getting up quickly",
            "postural", "orthostatic", "dehydration", "dehydrated",
            "drink more water", "fluid intake", "low blood sugar",
            "hypoglycaemia", "skipped a meal", "missed breakfast",
            "hot weather", "overheated", "anxiety", "panic",
            "medication side effect", "old age", "getting older",
            "compression stockings", "get up slowly", "reassurance",
            "nothing to worry",
        ],
        "alternative_topics": [
            "aortic stenosis", "murmur", "heart murmur", "valve",
            "echocardiogram", "on exertion", "exertional", "uphill",
            "climbing stairs", "angina", "chest tightness", "slow rising",
            "carotid", "pulse character", "narrow pulse pressure",
            "arrhythmia", "holter", "left ventricular", "no warning",
            "sudden collapse", "auscultate",
        ],
        "required_topics": [
            "syncope_circumstances",
            "prodrome_warning",
            "recovery_pattern",
            "exertional_symptoms",
            "palpitations_rhythm",
            "medications",
            "family_history",
            "duration_recurrence",
        ],
        "minimum_questions": 8,
        # Curated disconfirming keyword sets (arguing AGAINST a simple faint,
        # for cardiac syncope). The first four are history and the fifth needs
        # a stethoscope, which is the shape of the case: a learner who asks
        # well gets most of the way, and examining finishes it.
        "contradictory_clues": [
            ["what were you doing", "doing when", "climbing", "uphill",
             "walking up", "on the stairs", "at the time"],
            ["warning", "no warning", "beforehand", "before you fell",
             "feel it coming", "any warning at all"],
            ["came round", "afterwards", "confused", "tongue", "jerking",
             "witness", "anyone see", "back to normal"],
            ["breathless", "short of breath", "chest tightness",
             "tight chest", "angina", "how far can you walk"],
            ["murmur", "heart murmur", "valve", "listen to the heart",
             "auscultate", "echocardiogram"],
            ["palpitation", "racing heart", "irregular", "skipped beat",
             "heart rhythm", "fluttering"],
        ],
    },

    # ──────────────────────────────────────────────────────────────────
    # CASE 8: Naveen Reddy, 58M — Rectal bleeding — Colorectal cancer vs
    # haemorrhoids. THE ANCHOR IS TRUE. He has haemorrhoids, they are
    # visible on examination, and they explain some of the story and none
    # of the rest. The only case in the bank where the trap is a correct
    # finding rather than a wrong one.
    # ──────────────────────────────────────────────────────────────────
    "case_8": {
        "id": "case_8",
        "title": "The Bleeding That Was Already Explained",
        "patient_intro": (
            "A 58-year-old bus depot manager named Naveen Reddy attends about "
            "bleeding from the back passage over the past four months. He was "
            "diagnosed with haemorrhoids twelve years ago and has come mainly "
            "because his wife kept asking him to."
        ),
        "opening_line": (
            "I have had a bit of bleeding again, on and off for a few months. "
            "I have had piles for years so I know what it is — but my wife "
            "would not let it go, so here I am."
        ),
        "system_prompt": (
            "You are playing Naveen Reddy, a 58-year-old bus depot manager "
            "with four months of rectal bleeding. Speak plainly, no medical "
            "jargon. Keep responses to 2-4 sentences. You are matter-of-fact "
            "and slightly dismissive — you are certain this is your piles.\n\n"
            "CRITICAL RULE: Only reveal information when DIRECTLY asked. "
            "Do not volunteer clinical details not asked about.\n\n"
            "YOU GENUINELY HAVE HAEMORRHOIDS and have had them for twelve "
            "years. You are not wrong about that, and you will say so. What "
            "you have NOT noticed is that this episode is different from "
            "every previous one. You are not withholding it — the comparison "
            "has simply never occurred to you. If asked directly whether this "
            "bleeding is the same as before, you will think about it and "
            "realise it is not.\n\n"
            "YOUR HISTORY — reveal ONLY when asked:\n"
            "- The blood NOW: MIXED THROUGH the stool, darker than before, "
            "sometimes with slime. Describe it that way ONLY if asked what "
            "the blood looks like or where it is.\n"
            "- The blood BEFORE (your usual piles): bright red, on the paper "
            "or a few drops in the pan, never mixed in, always with "
            "straining. Share ONLY if asked to compare.\n"
            "- Bowel habit: CHANGED about four months ago. Used to be once "
            "every morning, now THREE OR FOUR TIMES A DAY and looser. Share "
            "ONLY if asked about bowel habit.\n"
            "- Tenesmus: often feels like you have not finished, and have to "
            "go back within minutes. New. Share ONLY if asked.\n"
            "- Weight: about 6 kg down over four months without trying. "
            "Trousers loose. Share ONLY if asked about weight.\n"
            "- Energy: tired, and breathless going up the depot stairs where "
            "you were fine a year ago. Share ONLY if asked.\n"
            "- Family: FATHER had bowel cancer at 71 and was treated. Share "
            "ONLY if asked about family.\n"
            "- NOT present: no abdominal pain to speak of, no vomiting, no "
            "jaundice, no fever, no foreign travel, no new medication, no "
            "NSAIDs, no anal pain, no lump you can feel outside.\n\n"
            "PERSONALITY: Practical, understated, a little impatient. Will "
            "repeat that he knows it is his piles unless something makes him "
            "reconsider."
        ),
        "correct_diagnosis": (
            "Colorectal carcinoma (rectal), with coexisting haemorrhoids and "
            "iron-deficiency anaemia"
        ),
        "anchor_topic": "haemorrhoids / benign anorectal cause",
        # NOTE. "constipation" and "straining" are deliberately absent, even
        # though they are the vocabulary of the trap. They already belong to
        # the `bowel_habits` required topic, and asking about them is good
        # history. The anchor list uses the words of the CONCLUSION — piles,
        # cream, banding, nothing serious — not the words of the question.
        # Same reason case_10 excludes the drug names.
        "anchor_keywords": [
            "haemorrhoid", "hemorrhoid", "piles", "fissure", "anal fissure",
            "fibre", "laxative", "stool softener", "haemorrhoid cream",
            "suppositor", "witch hazel", "sitz bath", "banding",
            "rubber band", "ointment", "irritable bowel", "spicy",
            "nothing serious", "common at your age", "benign",
            "reassure", "no need to worry", "old age", "just the piles",
            "sit for too long", "driving all day",
        ],
        "alternative_topics": [
            "colonoscopy", "cancer", "malignancy", "tumour", "bowel cancer",
            "colorectal", "fit test", "faecal immunochemical", "red flag",
            "weight loss", "anaemia", "iron deficiency", "ferritin",
            "rectal examination", "per rectum", "tenesmus", "mucus",
            "two week wait", "urgent referral", "mass", "staging",
        ],
        "required_topics": [
            "bleeding_character",
            "change_from_baseline",
            "bowel_habits",
            "tenesmus_incomplete",
            "anaemia_symptoms",
            "weight_history",
            "family_history",
            "duration_pattern",
        ],
        "minimum_questions": 8,
        # Curated disconfirming keyword sets. Note clue[1]: the question that
        # unlocks this case is not "do you have piles?" — he does — but
        # "is this the same as your piles?", which he has never been asked.
        # "usual piles" is absent from it because "piles" is an anchor
        # keyword and the two would collide under C-4.
        "contradictory_clues": [
            ["mixed in", "mixed with", "mixed through", "in the stool",
             "dark blood", "darker", "colour of the blood", "mucus",
             "slime"],
            ["different from", "same as usual", "like before", "changed",
             "is this the same", "compared with", "new for you"],
            ["bowel habit", "looser", "more often", "times a day",
             "diarrhoea", "opening your bowels", "how often do you go"],
            ["weight", "lost weight", "losing weight", "weight loss",
             "trousers", "clothes looser"],
            ["tired", "fatigue", "breathless", "pale", "anaemia",
             "short of breath", "energy"],
            ["tenesmus", "incomplete", "not finished", "need to go again",
             "fully empty", "still need to go"],
            ["family", "father", "bowel cancer", "relative",
             "anyone in the family"],
        ],
    },
}


# ══════════════════════════════════════════════════════════════════════
# CLINICAL DATA LAYER — Comprehensive (Sprint 3 + enriched)
# ----------------------------------------------------------------------
# Adds, for each case:
#   - system_prompt        : enriched patient script (overrides the stub above)
#   - accepted_diagnoses   : phrases that count as the correct diagnosis
#   - partial_diagnoses    : "on the right track" phrases
#   - examination          : examinable systems -> {label, finding, key}
#   - investigations       : orderable tests -> {label, result, category}
#                            category ∈ {"key", "reasonable", "low_value"}
#
# Exam findings and lab results are DETERMINISTIC (authored here), not
# generated by the LLM — this makes them clinically accurate, consistent,
# and reduces API calls. The LLM only voices the verbal history.
# ══════════════════════════════════════════════════════════════════════

# Shared anti-hallucination rules injected into every patient prompt.
_RULES = (
    "GROUND RULES (follow strictly):\n"
    "1. Stay fully in character. Reply in 1-4 short, natural sentences. "
    "Use lay language, not medical jargon.\n"
    "2. Reveal a piece of information ONLY when the student asks a question "
    "that covers it. Never volunteer several findings at once.\n"
    "3. NEVER invent a new positive symptom or finding that is not written "
    "in your chart below. If asked about something not in the chart, say it "
    "is normal / you have not noticed it / it is fine.\n"
    "4. You do NOT know clinical measurements — your exact blood pressure, "
    "temperature, pulse, or any blood test or scan result. If asked for those, "
    "say the doctor would need to check or examine you. Do not invent numbers.\n"
    "5. Never state or guess your own diagnosis, even if asked directly.\n\n"
)

CLINICAL_DATA = {

    # ──────────────────────────────────────────────────────────────────
    # Case 1: GERD masquerading as ACS — must exclude cardiac first
    # ──────────────────────────────────────────────────────────────────
    "case_1": {
        "system_prompt": _RULES + (
            "YOU ARE: Ramesh Kumar, a 48-year-old male accountant. Mildly "
            "anxious, cooperative, busy professional. You have come about "
            "chest pain for 3 days.\n\n"
            "YOUR CHART — COMPLETE (reveal only what is asked):\n"
            "• Pain: BURNING sensation in the centre of the chest, sometimes rising "
            "into the throat and behind the sternum. NOT crushing, squeezing, or "
            "tight. Severity 4-5/10, comes and goes, episodes lasting 20-60 min. "
            "Started 3 days ago the evening after a large, spicy work dinner.\n"
            "• DOES NOT radiate to the arm, jaw, shoulder, neck, or back.\n"
            "• WORSE: after large meals, spicy food, coffee (2-3 cups/day), "
            "alcohol, lying flat after eating, bending forward. "
            "BETTER: sitting upright. An antacid tablet worked within 20 minutes "
            "when you tried it once.\n"
            "• NOT triggered by exertion, walking upstairs, or climbing. No "
            "relationship to physical activity.\n"
            "• NO shortness of breath, NO sweating, NO nausea, NO vomiting, "
            "NO palpitations, NO dizziness, NO cough, NO difficulty swallowing, "
            "NO weight loss, NO haematemesis or melaena, NO early satiety.\n"
            "• PMH: chronic lower back pain (years). No diabetes, no known high "
            "blood pressure, no previous cardiac disease.\n"
            "• Medications: ibuprofen 400mg EVERY day (sometimes 800mg) for back "
            "pain — has taken it daily for over a year without any stomach "
            "protection. Occasional paracetamol (acetaminophen). NO statins, "
              "NO antihypertensives, "
            "NO antacids regularly.\n"
            "• Social: smokes 10 cigarettes/day for 20 years. 2-3 coffees daily. "
            "Alcohol 15-18 units/week (mostly at work events). Sedentary desk job, "
            "high-pressure deadlines, irregular mealtimes.\n"
            "• Family: father has type 2 diabetes, NO family history of MI, angina, "
            "or sudden cardiac death.\n"
        ),
        "accepted_diagnoses": [
            "gerd", "gord", "gastro-oesophageal reflux", "gastroesophageal reflux",
            "acid reflux", "reflux oesophagitis", "reflux esophagitis", "reflux",
            "oesophagitis", "esophagitis", "nsaid gastritis", "nsaid-induced",
            "peptic ulcer", "peptic oesophagitis",
        ],
        "partial_diagnoses": [
            "indigestion", "dyspepsia", "gastritis", "heartburn",
            "gi cause", "gastrointestinal", "non-cardiac chest pain",
        ],
        "examination": {
            "general": {"label": "General inspection",
                "finding": "Comfortable at rest, no distress, no diaphoresis, "
                           "no pallor or cyanosis, no jaundice.",
                "key": False},
            "vitals": {"label": "Vital signs",
                "finding": "HR 76 bpm regular · BP 132/84 mmHg "
                           "· RR 14 · SpO₂ 98% on air · Temp 36.8°C.",
                "key": True},
            "cardiovascular": {"label": "Cardiovascular exam",
                "finding": "Heart sounds I+II, no added sounds or murmurs. "
                           "JVP not raised. No peripheral oedema. Peripheral "
                           "pulses present and equal. No chest-wall tenderness "
                           "on palpation (no costochondritis).",
                "key": True},
            "respiratory": {"label": "Respiratory exam",
                "finding": "Chest expansion equal. Air entry clear bilaterally, "
                           "no crackles, no wheeze, percussion resonant.",
                "key": False},
            "abdomen": {"label": "Abdominal exam",
                "finding": "Abdomen soft, non-distended. EPIGASTRIC tenderness "
                           "on deep palpation — patient points to epigastrium. "
                           "No guarding, no rigidity. No organomegaly. Bowel "
                           "sounds normal. No signs of peritonism.",
                "key": True},
            "ent": {"label": "Oropharynx / upper GI",
                "finding": "Mild erythema posterior pharynx. No dental erosion "
                           "noted. No epigastric mass.",
                "key": False},
        },
        "investigations": {
            "ecg": {"label": "ECG (12-lead)",
                "result": "Normal sinus rhythm at 76 bpm. Normal axis. "
                          "No ST elevation or depression. No T-wave inversion. "
                          "No Q waves or LBBB.",
                "category": "key"},
            "troponin_0h": {"label": "High-sensitivity Troponin (0 h)",
                "result": "2 ng/L (reference < 14 ng/L) — NEGATIVE. "
                          "No evidence of myocardial injury.",
                "category": "key"},
            "troponin_3h": {"label": "High-sensitivity Troponin (3 h)",
                "result": "2 ng/L — NEGATIVE. Delta troponin: 0. "
                          "ACS effectively excluded on serial troponins.",
                "category": "key"},
            "fbc": {"label": "Full blood count",
                "result": "Hb 138 g/L · WCC 7.2 · Platelets 224. Normal.",
                "category": "reasonable"},
            "u_e": {"label": "Urea & electrolytes",
                "result": "Na 138 · K 4.1 · Urea 5.8 · Creatinine 82. Normal.",
                "category": "reasonable"},
            "lft_amylase": {"label": "LFTs & Serum amylase",
                "result": "ALT, ALP, bilirubin all normal. Amylase 48 U/L "
                          "(normal). No hepatobiliary or pancreatic disease.",
                "category": "reasonable"},
            "cxr": {"label": "Chest X-ray",
                "result": "Clear lung fields. Normal cardiac silhouette. "
                          "No pneumothorax, consolidation, or pleural effusion.",
                "category": "reasonable"},
            "lipids": {"label": "Lipid profile",
                "result": "Total cholesterol 5.9 mmol/L (borderline high), "
                          "LDL 3.8. Relevant given smoking history.",
                "category": "reasonable"},
            "hba1c_glucose": {"label": "HbA1c & fasting glucose",
                "result": "HbA1c 38 mmol/mol, fasting glucose 5.2 — normal.",
                "category": "reasonable"},
            "ogd": {"label": "OGD (Gastroscopy)",
                "result": "Moderate oesophagitis with erythema and superficial "
                          "erosions in the lower oesophagus. Los Angeles Grade B "
                          "GORD. No Barrett's, no malignancy. Consistent with "
                          "NSAID + acid-related disease.",
                "category": "key"},
            "h_pylori": {"label": "H. pylori (urea breath test / stool Ag)",
                "result": "Negative — H. pylori not detected.",
                "category": "reasonable"},
            "exercise_ecg": {"label": "Exercise tolerance test",
                "result": "Not indicated — symptoms are NOT exertional. Pain not "
                          "reproduced at peak exercise. Normal study.",
                "category": "low_value"},
            "d_dimer": {"label": "D-dimer",
                "result": "Not indicated for this presentation. No clinical "
                          "features of PE.",
                "category": "low_value"},
            "ct_angiogram": {"label": "CT coronary angiogram",
                "result": "Not required — serial troponins negative, ECG normal. "
                          "Radiation exposure not justified.",
                "category": "low_value"},
        },
    },

    # ──────────────────────────────────────────────────────────────────
    # Case 2: PE — cannot diagnose without D-dimer + CTPA
    # ──────────────────────────────────────────────────────────────────
    "case_2": {
        "system_prompt": _RULES + (
            "YOU ARE: Kavya Menon, a 29-year-old marketing executive. You are "
            "clearly short of breath, scared, and in pain. You feel like you "
            "cannot get enough air in.\n\n"
            "YOUR CHART — COMPLETE (reveal only what is asked):\n"
            "• SOB: Progressive over 2 days. Now breathless even walking slowly. "
            "Was completely well before this episode.\n"
            "• Chest pain: SHARP, STABBING, right-sided, dramatically worse on "
            "deep inspiration and coughing — classic pleuritic quality.\n"
            "• Haemoptysis: Small amount of blood-tinged sputum this morning. "
            "Only once. Very frightening. Share ONLY if asked.\n"
            "• Flight: Returned from an 11-HOUR Dubai flight 5 days ago, window "
            "seat, barely moved the whole journey. Share ONLY if asked about "
            "travel, flights, or recent long journeys.\n"
            "• OCP: On MICROGYNON 30 (combined oral contraceptive pill) for "
            "2 years. Share ONLY if asked about medications or contraception.\n"
            "• Right calf: Has been ACHING and looks SWOLLEN compared to the left "
            "for 3 days. She thought it was a pulled muscle from the flight. "
            "Share ONLY if asked about leg pain or calf.\n"
            "• No fever, no sore throat, no runny nose, no productive sputum, "
            "no sick contacts. She was well before the flight.\n"
            "• PMH: Nil significant. No previous DVT or PE. No recent surgery.\n"
            "• FH: No known family history of blood clots, but one aunt on "
            "father's side she thinks had a DVT. Share ONLY if asked about FH.\n"
            "• Social: Non-smoker. BMI 22. Works in marketing, frequent travel.\n"
        ),
        "accepted_diagnoses": [
            "pe", "pulmonary embolism", "vte", "venous thromboembolism",
            "dvt and pe", "pe with dvt", "pulmonary thromboembolism",
        ],
        "partial_diagnoses": [
            "dvt", "deep vein thrombosis", "blood clot", "clot in lung",
            "thrombosis", "embolism", "venous clot",
        ],
        "examination": {
            "general": {"label": "General inspection",
                "finding": "Visibly anxious, tachypnoeic, RR ~22. Sitting "
                           "forward. No cyanosis at rest but looks distressed.",
                "key": False},
            "vitals": {"label": "Vital signs",
                "finding": "HR 108 bpm (sinus tachycardia) · RR 22 · "
                           "BP 118/74 · SpO₂ 93% on air · Temp 37.5°C.",
                "key": True},
            "respiratory": {"label": "Respiratory exam",
                "finding": "Reduced expansion right base. PLEURAL RUB audible "
                           "right lower zone on auscultation. No crackles. "
                           "Percussion dull at right base.",
                "key": True},
            "cardiovascular": {"label": "Cardiovascular exam",
                "finding": "Tachycardia (108 bpm). JVP RAISED at 5 cm above "
                           "sternal angle. Possible right ventricular heave. "
                           "Loud P2. No peripheral oedema (other than right calf).",
                "key": True},
            "legs": {"label": "Lower limb exam",
                "finding": "RIGHT CALF: 2 cm circumferential swelling vs left, "
                           "tender over popliteal fossa, warm. Homan's sign "
                           "positive (limited specificity). LEFT leg normal.",
                "key": True},
            "abdomen": {"label": "Abdominal exam",
                "finding": "Soft, non-tender, no organomegaly.",
                "key": False},
        },
        "investigations": {
            "wells_score": {"label": "Wells PE Score (clinical calculation)",
                "result": "DVT symptoms +3 · alternative Dx less likely +3 · "
                          "tachycardia +1.5 = SCORE 7.5 → HIGH probability PE. "
                          "Proceed directly to CTPA without waiting for D-dimer.",
                "category": "key"},
            "d_dimer": {"label": "D-dimer",
                "result": "2,840 ng/mL (reference <500) — MARKEDLY ELEVATED. "
                          "Supports thrombotic diagnosis. In high Wells, proceed "
                          "to CTPA regardless.",
                "category": "key"},
            "ctpa": {"label": "CT Pulmonary Angiogram (CTPA)",
                "result": "BILATERAL PULMONARY EMBOLI. Filling defects in right "
                          "main pulmonary artery and left lower lobe branches. "
                          "Mild right ventricular dilatation. Confirms PE.",
                "category": "key"},
            "ecg": {"label": "ECG (12-lead)",
                "result": "Sinus tachycardia 108 bpm. S1Q3T3 pattern present "
                          "(S wave lead I, Q wave + T inversion lead III). "
                          "Right axis deviation. Classic PE changes.",
                "category": "key"},
            "abg": {"label": "Arterial Blood Gas (ABG) on air",
                "result": "pH 7.46 · PaCO₂ 3.2 kPa / 24 mmHg (LOW) · "
                            "PaO₂ 7.8 kPa / 59 mmHg (LOW) "
                          "· HCO₃ 22 · SaO₂ 91%. Type 1 respiratory failure "
                          "with respiratory alkalosis — V/Q mismatch from PE.",
                "category": "key"},
            "cxr": {"label": "Chest X-ray",
                "result": "Subtle wedge-shaped opacity right lower zone "
                          "(Hampton's hump). Linear atelectasis. Mild right "
                          "pleural effusion. CXR frequently near-normal in PE.",
                "category": "key"},
            "leg_doppler": {"label": "Bilateral leg venous USS / Doppler",
                "result": "RIGHT popliteal and femoral DVT confirmed — "
                          "non-compressible vein with intraluminal thrombus. "
                          "Left leg clear.",
                "category": "key"},
            "pregnancy_test": {"label": "Urine pregnancy test (βhCG)",
                "result": "NEGATIVE. Must be checked before CTPA/anticoagulation "
                          "in any woman of childbearing age.",
                "category": "key"},
            "fbc": {"label": "Full blood count",
                "result": "Hb 132 · WCC 9.8 (mild reactive) · Plt 298. Normal.",
                "category": "reasonable"},
            "u_e_lft": {"label": "U&E, LFTs & coagulation",
                "result": "Renal and liver function normal. INR 1.0. APTT 28 s. "
                          "Baseline before anticoagulation.",
                "category": "reasonable"},
            "troponin": {"label": "Troponin",
                "result": "41 ng/L — mildly elevated (due to right ventricular "
                          "strain from PE). Not ACS.",
                "category": "reasonable"},
            "echo": {"label": "Echocardiogram",
                "result": "Right ventricular dilatation and hypokinesis. "
                          "Raised estimated PA pressure. D-sign (septal shift) "
                          "suggesting RV strain. No LV abnormality.",
                "category": "reasonable"},
            "thrombophilia_screen": {"label": "Thrombophilia screen",
                "result": "Sent — results pending. Factor V Leiden, protein C/S, "
                          "antithrombin, antiphospholipid antibodies. Consider "
                          "especially in young patient.",
                "category": "reasonable"},
            "vq_scan": {"label": "V/Q (ventilation-perfusion) scan",
                "result": "Alternative to CTPA. Would show high probability "
                          "pattern (perfusion defects with normal ventilation). "
                          "CTPA preferred when CXR is abnormal.",
                "category": "reasonable"},
            "blood_cultures": {"label": "Blood cultures",
                "result": "No indication in this presentation.",
                "category": "low_value"},
        },
    },

    # ──────────────────────────────────────────────────────────────────
    # Case 3: UTI → delirium in an elderly man
    # ──────────────────────────────────────────────────────────────────
    "case_3": {
        "system_prompt": _RULES + (
            "YOU PLAY TWO PEOPLE:\n"
            "• ANITA — Gopal's daughter (~45), calm, observant, primary historian. "
            "Answer as Anita by DEFAULT.\n"
            "• GOPAL — 74-year-old retired teacher, confused/drowsy/vague. "
            "Answer as Gopal ONLY when the student directly addresses him.\n\n"
            "CHART — COMPLETE (reveal only what is asked):\n"
            "• Onset: SUDDENLY yesterday afternoon. He was reading his newspaper "
            "in the morning — completely normal. By evening, not making sense.\n"
            "• It FLUCTUATES — worse in the evening, slightly better at times.\n"
            "• FEVER: has felt warm/feverish since last night. Anita checked — "
            "37.9°C.\n"
            "• URINARY: going to the toilet MUCH MORE OFTEN than usual, said it "
            "STINGS/HURTS when he urinates. Urine looks darker and smells stronger. "
            "Anita only noticed this when asked — did not connect it to confusion.\n"
            "• DEHYDRATED: barely drunk any fluids for 2 days, says not thirsty.\n"
            "• NO fall, NO head injury, NO recent travel, NO chest symptoms.\n"
            "• NO one-sided weakness, NO facial droop, NO slurred speech.\n"
            "• NO headache, NO neck stiffness, NO photophobia.\n"
            "• PMH: hypertension, mild osteoarthritis. Independent, sharp.\n"
            "• Medications: amlodipine 5mg OD, aspirin 75mg OD. No new medications, "
            "no antibiotics recently.\n"
            "• GOPAL's lines: 'I feel... confused. Not right.' / "
            "'It stings when I go.' (only if asked) — very brief, vague.\n"
        ),
        "accepted_diagnoses": [
            "uti", "urinary tract infection", "urinary infection",
            "urosepsis", "urine infection", "sepsis from uti",
        ],
        "partial_diagnoses": [
            "delirium", "acute confusion", "infection", "sepsis",
            "dehydration", "confusional state", "acute confusional state",
        ],
        "examination": {
            "general": {"label": "General inspection",
                "finding": "Drowsy but rousable, appears unwell, mildly agitated "
                           "and restless. Recognises Anita but cannot say the date.",
                "key": False},
            "vitals": {"label": "Vital signs",
                "finding": "Temp 37.9°C · HR 96 bpm regular · BP 138/80 mmHg "
                           "· RR 18 · SpO₂ 96% on air.",
                "key": True},
            "neuro_focal": {"label": "Neurological exam (focal signs)",
                "finding": "Power 5/5 all four limbs. Face symmetrical, equal "
                           "nasolabial folds. Speech slow but not dysarthric. "
                           "Pupils equal and reactive. No neck stiffness. "
                           "No focal neurological deficit.",
                "key": True},
            "cognitive": {"label": "Cognitive / delirium assessment (4AT)",
                "finding": "4AT score 7/12 — positive for delirium. "
                           "Disoriented to time and place. Inattentive: cannot "
                           "list months of year backwards. Fluctuating course "
                           "confirmed by Anita.",
                "key": True},
            "abdomen": {"label": "Abdominal exam",
                "finding": "SUPRAPUBIC tenderness on moderate palpation. "
                           "Bladder not palpably distended. No peritonism. "
                           "Bowel sounds normal.",
                "key": True},
            "hydration": {"label": "Hydration & skin turgor",
                "finding": "Dry oral mucous membranes. Reduced skin turgor. "
                           "Tongue dry. Mild signs of dehydration.",
                "key": False},
            "cardiovascular": {"label": "Cardiovascular exam",
                "finding": "Mild tachycardia (96 bpm). Regular rhythm. "
                           "Heart sounds normal. No oedema.",
                "key": False},
        },
        "investigations": {
            "urinalysis": {"label": "Urinalysis (dipstick)",
                "result": "LEUCOCYTES 3+ · NITRITES POSITIVE · BLOOD 2+ · "
                          "Protein 1+. Urine cloudy with strong smell. "
                          "→ Strongly suggestive of UTI.",
                "category": "key"},
            "blood_glucose": {"label": "Blood glucose (BM / capillary)",
                "result": "5.4 mmol/L — normal. Hypoglycaemia excluded as "
                          "reversible cause of confusion.",
                "category": "key"},
            "fbc": {"label": "Full blood count",
                "result": "WCC 14.2 × 10⁹/L with NEUTROPHILIA 11.8 (raised). "
                          "Hb 131, Plt 268 — otherwise normal.",
                "category": "key"},
            "crp": {"label": "CRP",
                "result": "CRP 112 mg/L (markedly elevated, normal < 5). "
                          "Confirms significant systemic inflammation/infection.",
                "category": "key"},
            "u_e_creatinine": {"label": "Urea & electrolytes / renal function",
                "result": "Na 134 (mildly low) · K 4.2 · Urea 12.4 (elevated) "
                          "· Creatinine 128 (raised from baseline ~85) — "
                          "ACUTE KIDNEY INJURY (AKI stage 1) from dehydration.",
                "category": "key"},
            "urine_culture": {"label": "Urine microscopy, culture & sensitivity",
                "result": "Sent. Microscopy: >100 WBC/mL, mixed organisms. "
                          "Culture: E. coli >10⁵ cfu/mL (result in 48 h). "
                          "Sensitivity results to guide antibiotic choice.",
                "category": "reasonable"},
            "blood_cultures": {"label": "Blood cultures × 2",
                "result": "Collected prior to antibiotics. Results pending "
                          "(48-72 h). Essential in sepsis pathway.",
                "category": "reasonable"},
            "lactate": {"label": "Serum lactate",
                "result": "1.9 mmol/L — mildly elevated but < 2. "
                          "Suggests early sepsis without shock. "
                          "Sepsis 6 bundle to be initiated.",
                "category": "reasonable"},
            "vbg": {"label": "Venous Blood Gas (VBG)",
                "result": "pH 7.36 · HCO₃ 20 · BE -4 · pCO₂ 5.2 — "
                          "mild metabolic acidosis compensated. Quick assessment "
                          "of acid-base and electrolytes.",
                "category": "reasonable"},
            "ecg": {"label": "ECG (12-lead)",
                "result": "Sinus tachycardia 96 bpm. No AF. No acute changes. "
                          "New AF can be precipitated by sepsis in elderly.",
                "category": "reasonable"},
            "cxr": {"label": "Chest X-ray",
                "result": "No consolidation or infiltrate. No pleural effusion. "
                          "Pneumonia excluded as source of sepsis.",
                "category": "reasonable"},
            "ct_head": {"label": "CT head (non-contrast)",
                "result": "Age-related white matter changes and mild generalised "
                          "atrophy. NO acute infarct, NO haemorrhage, NO SOL. "
                          "Stroke excluded as cause of confusion.",
                "category": "reasonable"},
            "lft": {"label": "Liver function tests",
                "result": "Mild transaminase rise (ALT 54, AST 42) — may be "
                          "sepsis-related. Bilirubin and ALP normal.",
                "category": "reasonable"},
            "tsh": {"label": "Thyroid function (TSH)",
                "result": "Normal — thyroid disease not causative in this "
                          "acute presentation.",
                "category": "low_value"},
            "b12_folate": {"label": "B12 & folate",
                "result": "Normal — not a cause of acute-onset delirium.",
                "category": "low_value"},
            "lumbar_puncture": {"label": "Lumbar puncture (LP)",
                "result": "Not indicated — no meningism (neck stiffness, "
                          "Kernig/Brudzinski), no petechiae, no fever with "
                          "photophobia. Carry out only if clinical suspicion "
                          "of meningitis persists after imaging.",
                "category": "low_value"},
        },
    },

    # ──────────────────────────────────────────────────────────────────
    # Case 4: Hypothyroidism — TFTs required; cannot diagnose clinically
    # ──────────────────────────────────────────────────────────────────
    "case_4": {
        "system_prompt": _RULES + (
            "YOU ARE: Meera Patel, a 35-year-old primary school teacher. "
            "Thoughtful, engaged with your job, genuinely puzzled. NOT depressed.\n\n"
            "YOUR CHART — COMPLETE (reveal only what is asked):\n"
            "• 3 months of constant tiredness — you sleep 8-9 hours but wake "
            "exhausted. Tired all day. Everything feels slow.\n"
            "• WEIGHT: Putting ON ~5 kg despite eating LESS than before. NOT "
            "overeating.\n"
            "• COLD: Always cold — wearing extra layers when colleagues are warm. "
            "Even in summer. Your husband notices it too.\n"
            "• HAIR: Falling out more than usual — on the brush and in the shower "
            "drain. Noticeably thinning.\n"
            "• SKIN: Dry and rough. Slightly puffy around the eyes in the morning.\n"
            "• BOWELS: Constipated for ~2 months — new for you. Normally regular.\n"
            "• PERIODS: Heavier over the past 2 months — needing more products.\n"
            "• THINKING: Mentally slow — re-reading emails, making small errors "
            "at work (unusual), concentration reduced.\n"
            "• MOOD: FINE. Still enjoy your job, your class, your husband. Not "
            "sad, not tearful, not hopeless, not anhedonic.\n"
            "• VOICE: Maybe slightly hoarser than before — colleagues noticed.\n"
            "• NO neck swelling you have noticed, no palpitations, no eye "
            "changes, no heat intolerance.\n"
            "• PMH: Nil. Medications: None — no pill, no supplements. Non-smoker, "
            "minimal alcohol. No major stressors.\n"
            "• FH: Mother has underactive thyroid and takes levothyroxine.\n"
        ),
        "accepted_diagnoses": [
            "hypothyroid", "hypothyroidism", "underactive thyroid",
            "hashimoto", "hashimoto's thyroiditis", "autoimmune thyroiditis",
            "primary hypothyroidism", "myxoedema", "myxedema",
        ],
        "partial_diagnoses": [
            "thyroid problem", "thyroid disease", "thyroid disorder",
            "thyroid", "endocrine", "hormonal", "anaemia and hypothyroid",
        ],
        "examination": {
            "general": {"label": "General inspection",
                "finding": "Dry, slightly coarse skin. Periorbital puffiness. "
                           "Thinning hair (diffuse). Movements slightly slow. "
                           "Hoarse voice on greeting. No pallor. No jaundice.",
                "key": False},
            "vitals": {"label": "Vital signs",
                "finding": "HR 54 bpm (BRADYCARDIA) · BP 118/76 · RR 13 "
                           "· Temp 36.1°C · SpO₂ 99%.",
                "key": True},
            "neck_thyroid": {"label": "Neck / thyroid exam",
                "finding": "Small, firm, non-tender, smooth GOITRE palpable. "
                           "No bruit. Moves on swallowing. No cervical "
                           "lymphadenopathy. No tracheal deviation.",
                "key": True},
            "reflexes": {"label": "Deep tendon reflexes",
                "finding": "SLOW-RELAXING ankle jerks ('hung-up' reflexes). "
                           "Characteristic of hypothyroidism. Other reflexes "
                           "present but generally muted.",
                "key": True},
            "hands_nails": {"label": "Hands & nails",
                "finding": "Cool, dry hands. Mild non-pitting oedema fingers. "
                           "Brittle, ridged nails. Tingling in both hands — "
                           "positive Tinel's sign bilaterally (carpal tunnel "
                           "syndrome associated with hypothyroidism).",
                "key": False},
            "cardiovascular": {"label": "Cardiovascular exam",
                "finding": "Bradycardia 54 bpm, regular. Heart sounds muffled "
                           "but no added sounds. No oedema. No pericardial rub.",
                "key": False},
            "mental_state": {"label": "Mood & mental state (PHQ-9 verbally)",
                "finding": "Euthymic, reactive affect, appropriate. PHQ-9 "
                           "verbal screen score ~4 — not consistent with "
                           "depressive disorder. Physical symptoms dominate.",
                "key": False},
        },
        "investigations": {
            "tfts": {"label": "Thyroid function tests (TSH + free T4)",
                "result": "TSH 28.4 mU/L (markedly raised; normal 0.4–4.0) · "
                          "Free T4 7.2 pmol/L (LOW; normal 12–22). "
                          "→ PRIMARY HYPOTHYROIDISM confirmed.",
                "category": "key"},
            "ft3": {"label": "Free T3",
                "result": "Free T3 3.1 pmol/L (low-normal; normal 3.1–6.8). "
                          "Usually not needed if TSH+T4 diagnostic.",
                "category": "reasonable"},
            "anti_tpo": {"label": "Anti-TPO antibodies",
                "result": "STRONGLY POSITIVE: 842 IU/mL (normal < 35). "
                          "Confirms AUTOIMMUNE (Hashimoto's) thyroiditis as "
                          "the aetiology.",
                "category": "key"},
            "fbc": {"label": "Full blood count",
                "result": "NORMOCHROMIC NORMOCYTIC ANAEMIA: Hb 106 g/L, MCV 88. "
                          "WCC and platelets normal. "
                          "Anaemia of hypothyroidism (reduced erythropoiesis).",
                "category": "key"},
            "lipids": {"label": "Lipid profile",
                "result": "Total cholesterol 7.2 mmol/L (HIGH) · LDL 4.9 (HIGH). "
                          "Secondary dyslipidaemia from hypothyroidism — "
                          "should normalise with levothyroxine.",
                "category": "key"},
            "iron_ferritin": {"label": "Iron studies & ferritin",
                "result": "Serum ferritin 18 µg/L (low-normal). Iron 11 µmol/L. "
                          "Contributing iron deficiency in context of menorrhagia.",
                "category": "reasonable"},
            "u_e": {"label": "Urea & electrolytes",
                "result": "Na 133 mmol/L (mildly LOW — hyponatraemia in "
                          "hypothyroidism from SIADH-like mechanism). "
                          "K, urea, creatinine normal.",
                "category": "reasonable"},
            "lft_ck": {"label": "LFTs & CK (creatine kinase)",
                "result": "CK 312 U/L (mildly elevated; normal <170) — "
                          "muscle enzyme rises in hypothyroidism. "
                          "ALT mildly raised (48). Bilirubin normal.",
                "category": "reasonable"},
            "hba1c_glucose": {"label": "HbA1c & glucose",
                "result": "HbA1c 36, glucose 5.0 — normal. Type 1 DM excluded "
                          "(autoimmune polyendocrine syndrome screen).",
                "category": "reasonable"},
            "neck_uSS": {"label": "Neck / thyroid ultrasound",
                "result": "Diffusely enlarged thyroid with heterogeneous, "
                          "hypoechoic echotexture. Increased vascularity on "
                          "Doppler. No nodules or focal lesions. Consistent "
                          "with Hashimoto's thyroiditis.",
                "category": "reasonable"},
            "coeliac_screen": {"label": "Coeliac screen (anti-tTG IgA)",
                "result": "Negative. Coeliac disease excluded (autoimmune "
                          "association with Hashimoto's).",
                "category": "reasonable"},
            "prolactin": {"label": "Prolactin",
                "result": "42 µg/L (mildly raised; normal <25). Elevated "
                          "prolactin secondary to hypothyroidism — explains "
                          "menstrual irregularity. Will normalise with treatment.",
                "category": "reasonable"},
            "cortisol": {"label": "Morning cortisol / short Synacthen test",
                "result": "Random cortisol 420 nmol/L — normal. Addison's "
                          "disease excluded (autoimmune polyendocrine syndrome 2).",
                "category": "reasonable"},
            "phq9": {"label": "PHQ-9 questionnaire",
                "result": "Score 4 — minimal/none. Physical symptoms (fatigue, "
                          "weight gain) not driven by depression.",
                "category": "low_value"},
            "mri_pituitary": {"label": "MRI pituitary",
                "result": "Not indicated — TSH + T4 confirm PRIMARY (thyroid) "
                          "cause. Secondary hypothyroidism (pituitary) excluded "
                          "by the raised TSH.",
                "category": "low_value"},
        },
    },

    # ──────────────────────────────────────────────────────────────────
    # Case 5: DKA — blood glucose + ketones + ABG are mandatory
    # ──────────────────────────────────────────────────────────────────
    "case_5": {
        "system_prompt": _RULES + (
            "YOU ARE: Aisha Khan, a 21-year-old university student. You feel "
            "absolutely terrible — wracked with nausea, severe abdominal pain, "
            "and utter exhaustion. You are breathing faster than normal (though "
            "you do not realise how deeply you are breathing).\n\n"
            "YOUR CHART — COMPLETE (reveal only what is asked):\n"
            "• Current illness: Nausea and vomiting since yesterday evening, "
            "worsening all day. Vomited ~8 times today. Central cramping abdominal "
            "pain, constant, 7/10 severity.\n"
            "• Duration of THIS episode: ~1.5 days.\n"
            "• PRE-EXISTING SYMPTOMS (4 weeks — these are CRUCIAL):\n"
            "  - Extreme THIRST — drinking 4-5 litres of water per day.\n"
            "  - URINATING excessively, waking at night 2-3 times.\n"
            "  - Lost 5-6 kg of WEIGHT over 4-5 weeks without trying. Clothes "
            "much looser.\n"
            "  Share these ONLY if specifically asked about thirst/urination, "
            "weight, or symptoms before this illness started.\n"
            "• Breathing: She is breathing deeply and rapidly but does not "
            "notice it. If asked directly: 'I suppose I am breathing quite fast "
            "and deeply — I thought it was just the pain.'\n"
            "• Breath smell: Her flatmate told her she smells of nail polish "
            "remover — she cannot smell it herself.\n"
            "• Sick contacts: Flatmate had a stomach bug 10 days ago and "
            "recovered in 2 days. Aisha's illness is much longer.\n"
            "• PMH: Nil. No known diabetes. No regular medications. No allergies.\n"
            "• FH: Maternal grandparents have TYPE 2 diabetes. No family member "
            "with TYPE 1 diabetes that she knows of. Share ONLY if asked.\n"
            "• Last ate: Yesterday lunchtime. Drank plenty of water before vomiting "
            "started.\n"
            "• Alcohol: A few drinks Friday evening, nothing excessive.\n"
        ),
        "accepted_diagnoses": [
            "dka", "diabetic ketoacidosis", "type 1 diabetes",
            "t1dm", "t1 diabetes", "new onset type 1", "new-onset t1dm",
            "type 1 dka", "dka in type 1",
        ],
        "partial_diagnoses": [
            "diabetes", "hyperglycaemia", "ketoacidosis", "metabolic acidosis",
            "ketones", "diabetic emergency",
        ],
        "examination": {
            "general": {"label": "General inspection",
                "finding": "Looks very unwell. Markedly dehydrated appearance. "
                           "KUSSMAUL BREATHING — deep, rapid, sighing respirations. "
                           "Faint PEAR DROP / ACETONE smell on breath. "
                           "Reduced skin turgor. Dry mucous membranes.",
                "key": True},
            "vitals": {"label": "Vital signs",
                "finding": "HR 118 bpm (tachycardia) · BP 98/62 mmHg "
                           "(borderline hypotensive) · RR 28 (tachypnoeic and "
                           "DEEP) · Temp 37.1°C · SpO₂ 98% on air.",
                "key": True},
            "abdomen": {"label": "Abdominal exam",
                "finding": "Diffuse central abdominal tenderness — moderate, "
                           "no guarding, no rigidity, no rebound. Bowel sounds "
                           "reduced. NOTE: DKA itself causes abdominal pain and "
                           "vomiting — but peritonism must still be excluded.",
                "key": True},
            "neuro_focal": {"label": "Neurological Examination",
                "finding": "GCS 14/15 (confused). Oriented to person but "
                           "not fully to time. No focal deficit, no meningism. "
                           "Sluggish but rousable.",
                "key": False},
            "hydration": {"label": "Dehydration assessment",
                "finding": "Estimated 8-10% dehydration based on: marked "
                           "skin turgor reduction, dry mucous membranes, "
                           "sunken eyes, capillary refill 3 seconds. "
                           "Orthostatic drop in BP.",
                "key": False},
            "cardiovascular": {"label": "Cardiovascular exam",
                "finding": "Sinus tachycardia 118 bpm. Peripheral pulses weak. "
                           "JVP flat (hypovolaemia). No chest signs.",
                "key": False},
        },
        "investigations": {
            "blood_glucose": {"label": "Blood glucose (BM / capillary)",
                "result": "27.4 mmol/L (CRITICALLY HIGH — normal 4-7). "
                          "→ Diagnostic of hyperglycaemia; DKA must be confirmed "
                          "with ketones and ABG.",
                "category": "key"},
            "blood_ketones": {"label": "Blood ketones (beta-hydroxybutyrate)",
                "result": "4.2 mmol/L (SEVERE ketosis — normal <0.6; DKA "
                          "diagnosis requires >3.0). Combined with glucose "
                          "and acidosis → DKA confirmed.",
                "category": "key"},
            "abg": {"label": "Arterial Blood Gas (ABG)",
                "result": "pH 7.18 (ACIDOSIS — normal 7.35-7.45) · "
                          "PaCO₂ 2.6 kPa / 20 mmHg (LOW — Kussmaul compensation) · "
                          "HCO₃ 9 mmol/L (VERY LOW) · BE -18 · PaO₂ 13.8. "
                          "→ SEVERE METABOLIC ACIDOSIS with respiratory "
                          "compensation. Confirms DKA diagnosis.",
                "category": "key"},
            "u_e": {"label": "Urea & electrolytes (STAT)",
                "result": "Na 128 mmol/L (low — pseudohyponatraemia from "
                          "hyperglycaemia) · K 5.9 mmol/L (HIGH — DKA depletes "
                          "TOTAL body K but serum raised from acidosis; will drop "
                          "dangerously with insulin) · Urea 11.2 · "
                          "Creatinine 142 (AKI from dehydration). "
                          "CRITICAL: monitor K closely when giving insulin.",
                "category": "key"},
            "hba1c": {"label": "HbA1c",
                "result": "97 mmol/mol (11.3%) — MARKEDLY ELEVATED. Normal "
                          "< 48 mmol/mol. Confirms months of chronic "
                          "hyperglycaemia — not just an acute event.",
                "category": "key"},
            "urinalysis": {"label": "Urinalysis (Dipstick)",
                "result": "Glucose 4+ (massive glycosuria) · Ketones 4+ "
                          "(ketonuria) · Protein 1+. Confirms systemic glucose "
                          "and ketone overflow.",
                "category": "key"},
            "fbc": {"label": "Full blood count",
                "result": "WCC 18.4 × 10⁹/L (ELEVATED — stress response in "
                          "DKA; does not necessarily mean infection). "
                          "Hb 138, Plt 312. Haemoconcentration from dehydration.",
                "category": "key"},
            "ecg": {"label": "ECG (12-lead)",
                "result": "Sinus tachycardia 118 bpm. PEAKED T WAVES in leads "
                          "II, V2-V5 — consistent with HYPERKALAEMIA (K 5.9). "
                          "Must monitor for widening QRS. Repeat ECG with K "
                          "normalisation.",
                "category": "reasonable"},
            "urine_culture": {"label": "Urine MC&S",
                "result": "Sent — leucocytes 2+ on dip (may be non-specific "
                          "in DKA). Urine culture to exclude UTI as DKA trigger.",
                "category": "reasonable"},
            "blood_cultures": {"label": "Blood cultures × 2",
                "result": "Collected on admission. No obvious source of "
                          "infection but DKA in young T1DM is often triggered "
                          "by intercurrent illness.",
                "category": "reasonable"},
            "amylase": {"label": "Serum amylase / lipase",
                "result": "Amylase 186 U/L (mildly elevated) · Lipase 92. "
                          "DKA itself causes abdominal pain and mild amylase "
                          "rise — does NOT confirm pancreatitis. If severely "
                          "elevated or clinical suspicion high, consider CT.",
                "category": "reasonable"},
            "lft": {"label": "LFTs",
                "result": "AST 62 (mildly elevated), ALT 48, bilirubin normal, "
                          "ALP normal. Mild hepatocellular changes in DKA.",
                "category": "reasonable"},
            "cxr": {"label": "Chest X-ray",
                "result": "Clear lung fields. No consolidation. Pneumonia "
                          "as DKA trigger excluded.",
                "category": "reasonable"},
            "c_peptide": {"label": "C-peptide",
                "result": "< 0.1 nmol/L (undetectable) — confirms ABSENT "
                          "endogenous insulin secretion → TYPE 1 DM (not T2DM).",
                "category": "reasonable"},
            "anti_gad": {"label": "Anti-GAD / anti-islet antibodies",
                "result": "Anti-GAD65 POSITIVE (titre > 200 IU/mL). Confirms "
                          "AUTOIMMUNE Type 1 DM (not MODY or T2DM).",
                "category": "reasonable"},
            "ct_abdomen": {"label": "CT abdomen",
                "result": "NOT INDICATED yet. DKA causes abdominal pain "
                          "mimicking an acute abdomen. Re-assess after DKA "
                          "correction — pain usually resolves with treatment.",
                "category": "low_value"},
            "troponin": {"label": "Troponin",
                "result": "No indication — no cardiac symptoms. Mild elevation "
                          "possible from tachycardia but not clinically meaningful.",
                "category": "low_value"},
        },
    },

    # ──────────────────────────────────────────────────────────────────
    # Case 6: Hypertension presenting as headache. The history genuinely
    # does sound like stress, and the diagnosis is on the cuff — a learner
    # can take a flawless history and still get it wrong by not examining.
    # The design doc predates this layer; exam and investigations are new.
    # ──────────────────────────────────────────────────────────────────
    "case_6": {
        "system_prompt": _RULES + (
            "YOU ARE: Priya Sharma, a 28-year-old software engineer at a "
            "startup. Articulate, mildly frustrated, assumes this is stress "
            "and half expects to be told so. You have come about daily "
            "headaches for 2 weeks.\n\n"
            "YOUR CHART — COMPLETE (reveal only what is asked):\n"
            "• Headache: THROBBING, POUNDING — 'pounding from inside', not a "
            "band around the head. Severity 5-7/10. Almost daily for 2 weeks, "
            "gradually more frequent.\n"
            "• Location: mainly OCCIPITAL — back of the head, towards the "
            "neck. Not one-sided, not behind the eye.\n"
            "• Timing: WORST ON WAKING, already present when you open your "
            "eyes. Eases through the morning, often returns by evening.\n"
            "• Vision: things go BLURRY during the headache, three or four "
            "times over the two weeks, lasting minutes. No aura, no zigzags, "
            "no flashing lights, no double vision, no loss of vision.\n"
            "• NOT: no neck stiffness, no fever, no rash, no photophobia, no "
            "vomiting, no weakness or numbness, no speech problems, no "
            "thunderclap onset, no worsening on coughing or lying flat, no "
            "head injury, no weight loss, no night sweats.\n"
            "• Medications: COMBINED ORAL CONTRACEPTIVE PILL for 3 years, "
            "taken daily, same brand throughout. Paracetamol 1 g perhaps "
            "three times a week for the headache — it barely helps. No "
            "NSAIDs, no triptans, no supplements, no herbal remedies, no "
            "decongestants, no recreational drugs.\n"
            "• Blood pressure: NEVER CHECKED since a school medical. You have "
            "never been told it was high.\n"
            "• PMH: nothing. No diabetes, no kidney disease, no migraine "
            "history, no pre-eclampsia (never pregnant).\n"
            "• Family: MOTHER has high blood pressure, on tablets for years. "
            "Father — you do not know. No known kidney disease, no early "
            "stroke or heart attack that you are aware of.\n"
            "• Social: work is busy, but it is ALWAYS busy — nothing changed "
            "when the headaches started, no new deadline, no life event. "
            "Sleeps ~7 hours and sleeps well. Non-smoker. Alcohol 4-6 "
            "units/week. 2 coffees a day, unchanged for years. Drinks water "
            "regularly. Walks and does yoga twice a week.\n"
        ),
        "accepted_diagnoses": [
            "hypertension", "high blood pressure", "raised blood pressure",
            "elevated blood pressure", "hypertensive", "newly diagnosed "
            "hypertension", "essential hypertension", "secondary hypertension",
            "drug-induced hypertension", "pill-induced hypertension",
            "oral contraceptive induced hypertension",
            "contraceptive related hypertension",
        ],
        "partial_diagnoses": [
            "secondary headache", "blood pressure related",
            "contraceptive side effect", "hormonal", "cardiovascular risk",
        ],
        "examination": {
            "general": {"label": "General inspection",
                "finding": "Well, comfortable, no distress. No rash, no neck "
                           "stiffness, not photophobic. Kernig's negative.",
                "key": False},
            "vitals": {"label": "Vital signs",
                "finding": "BP 168/104 mmHg right arm, 166/102 mmHg left arm; "
                           "repeated after 5 minutes seated rest 164/102 mmHg "
                           "(normal < 140/90; 160-179/100-119 is stage 2). "
                           "HR 76 bpm regular · RR 14 · SpO₂ 99% on air · "
                           "Temp 36.6°C. THE DIAGNOSIS IS HERE.",
                "key": True},
            "eyes_fundoscopy": {"label": "Fundoscopy",
                "finding": "Generalised ARTERIOLAR NARROWING with early "
                           "arteriovenous nipping. No haemorrhages, no "
                           "exudates, NO papilloedema. Keith-Wagener-Barker "
                           "GRADE I-II hypertensive retinopathy — changes of "
                           "raised pressure, but no acute damage.",
                "key": True},
            "cardiovascular": {"label": "Cardiovascular exam",
                "finding": "Apex beat normal in position and character — NOT "
                           "heaving or displaced. Heart sounds I+II, no "
                           "murmur. JVP not raised, no oedema. Radial and "
                           "femoral pulses synchronous (no radiofemoral "
                           "delay — coarctation excluded).",
                "key": True},
            "neuro_focal": {"label": "Focal neurological exam",
                "finding": "Power 5/5, tone, coordination and sensation "
                           "normal, plantars downgoing. NO focal deficit.",
                "key": False},
            "cranial_nerves": {"label": "Cranial nerve exam",
                "finding": "II-XII intact. Visual fields full to "
                           "confrontation. Pupils equal and reactive.",
                "key": False},
            "weight_bmi": {"label": "Weight and BMI",
                "finding": "64 kg, 1.63 m, BMI 24.1 kg/m² (normal 18.5-24.9). "
                           "Weight is NOT the explanation here.",
                "key": False},
            "abdomen": {"label": "Abdominal exam",
                "finding": "Soft, non-tender. NO renal bruit. No palpable or "
                           "ballotable kidneys, no masses.",
                "key": False},
            "neck_thyroid": {"label": "Neck and thyroid",
                "finding": "No goitre, no nodule, no bruit. Occipital muscles "
                           "not tender — no myofascial tenderness to support a "
                           "tension-type headache.",
                "key": False},
        },
        "investigations": {
            "urinalysis": {"label": "Urine dipstick",
                "result": "Protein negative · Blood negative · Glucose "
                          "negative · Leucocytes negative. NO proteinuria — "
                          "no evidence of kidney damage yet, which fits "
                          "recent-onset hypertension.",
                "category": "key"},
            "u_e_creatinine": {"label": "Urea, electrolytes & creatinine",
                "result": "Na 140 mmol/L · K 4.2 (ref 3.5-5.3) · Urea 4.4 "
                          "(ref 2.5-7.8) · Creatinine 71 µmol/L (ref 45-90) · "
                          "eGFR > 90 mL/min/1.73m². NORMAL. Normal potassium "
                          "makes primary hyperaldosteronism unlikely.",
                "category": "key"},
            "ecg": {"label": "ECG (12-lead)",
                "result": "Sinus rhythm 74 bpm. Normal axis. NO left "
                          "ventricular hypertrophy (S in V1 + R in V5 = "
                          "26 mm; Sokolow-Lyon threshold 35 mm). No ischaemic "
                          "change. A normal ECG is consistent with "
                          "hypertension of recent onset, and does not "
                          "exclude it.",
                "category": "key"},
            "pregnancy_test": {"label": "Urine pregnancy test",
                "result": "Negative. Relevant before changing or stopping "
                          "hormonal contraception, and before prescribing an "
                          "ACE inhibitor or ARB.",
                "category": "reasonable"},
            "lipids": {"label": "Lipid profile",
                "result": "Total cholesterol 4.4 mmol/L (target < 5.0) · "
                          "LDL 2.4 · HDL 1.6 · Triglycerides 0.9. Normal. "
                          "Part of cardiovascular risk assessment once "
                          "hypertension is found.",
                "category": "reasonable"},
            "hba1c": {"label": "HbA1c",
                "result": "33 mmol/mol (ref < 42). Normal.",
                "category": "reasonable"},
            "tfts": {"label": "Thyroid function tests",
                "result": "TSH 1.8 mU/L (ref 0.4-4.0) · Free T4 15 pmol/L "
                          "(ref 9-23). Normal — thyroid disease excluded as a "
                          "secondary cause.",
                "category": "reasonable"},
            "renal_uss": {"label": "Renal ultrasound",
                "result": "Both kidneys normal size and echotexture, no "
                          "obstruction, no asymmetry. Reasonable in a "
                          "28-year-old with new hypertension, where a "
                          "secondary cause is more likely than at 60.",
                "category": "reasonable"},
            "ct_head": {"label": "CT head",
                "result": "No haemorrhage, no mass, no hydrocephalus. NORMAL "
                          "— and it was never going to show the diagnosis, "
                          "which is on the blood pressure cuff.",
                "category": "low_value"},
            "mri_brain": {"label": "MRI brain",
                "result": "Normal. No space-occupying lesion, no venous sinus "
                          "thrombosis. Not indicated without red flags or "
                          "focal signs.",
                "category": "low_value"},
            "eeg": {"label": "EEG",
                "result": "Normal. No indication — this is not a seizure "
                          "disorder.",
                "category": "low_value"},
            "cortisol": {"label": "Morning serum cortisol",
                "result": "385 nmol/L (ref 140-690). Normal. Screening for "
                          "Cushing's with no clinical features is low yield.",
                "category": "low_value"},
        },
    },

    # ──────────────────────────────────────────────────────────────────
    # Case 7: First presentation of asthma, called a chest infection.
    # Two voices — Sunita and Arjun. The absence of fever is the single
    # most discriminating finding, which is why "fever" is a clue here and
    # NOT an anchor keyword (see the note on the stub above).
    # ──────────────────────────────────────────────────────────────────
    "case_7": {
        "system_prompt": _RULES + (
            "YOU ARE TWO PEOPLE. SUNITA: Arjun's mother, attentive, precise, "
            "worried but calm; she has not connected the episodes to each "
            "other. ARJUN: 10 years old, cooperative, slightly embarrassed, "
            "answers in a child's words. Reply as whoever the learner "
            "addresses; default to Sunita.\n\n"
            "YOUR CHART — COMPLETE (reveal only what is asked):\n"
            "• Cough: DRY, he brings nothing up. Present 4-5 days this time.\n"
            "• Timing: WORST AT NIGHT and in the EARLY MORNING. Wakes him. "
            "Much less during the school day.\n"
            "• Fever: NONE. Sunita measured 36.8°C this morning. He has not "
            "felt hot at any point.\n"
            "• Coryza: NO runny nose, NO sore throat, no earache. Nothing but "
            "the cough and the wheeze.\n"
            "• Exercise: at PE last week he coughed and wheezed badly after "
            "running, and the teacher was concerned. Settles with rest.\n"
            "• Cold air: going outside on a cool morning makes it much worse; "
            "he comes back in coughing.\n"
            "• Recurrence: TWICE BEFORE in the past year. Sunita thought it "
            "was a bad cough each time; it resolved by itself. Nobody "
            "connected them.\n"
            "• Family: GRANDFATHER (paternal) has asthma and uses an inhaler. "
            "SUNITA has hay fever and takes antihistamines every spring. No "
            "cystic fibrosis, no TB contact.\n"
            "• PMH: mild eczema as a toddler, in the elbow creases. Born at "
            "term, no neonatal problems, immunisations up to date. No "
            "hospital admissions, no pneumonia.\n"
            "• Impact: at school yesterday but uncomfortable all day; did not "
            "do PE. Usually very active. No school missed yet.\n"
            "• Environment: no pets, no damp or mould, nobody smokes at home.\n"
            "• NOT: no weight loss, no night sweats, no choking episode, no "
            "haemoptysis, no feeding or growth problems.\n"
            "• AS ARJUN, if addressed directly about his chest: 'Yeah, when I "
            "run a lot it gets really tight and then I start coughing and it "
            "sounds funny. It is embarrassing in front of my friends.'\n"
        ),
        "accepted_diagnoses": [
            "asthma", "bronchial asthma", "atopic asthma", "allergic asthma",
            "childhood asthma", "first presentation of asthma",
            "exercise induced asthma", "exercise-induced asthma",
            "exercise induced bronchoconstriction", "reversible airway",
            "reversible airways disease", "reversible airflow obstruction",
        ],
        "partial_diagnoses": [
            "atopy", "allergy", "allergic rhinitis", "recurrent wheeze",
            "viral induced wheeze", "bronchospasm", "airway "
            "hyperresponsiveness",
        ],
        "examination": {
            "general": {"label": "General inspection",
                "finding": "Well-grown 10-year-old, alert, comfortable at "
                           "rest, speaking in full sentences. No cyanosis, no "
                           "nasal flaring, no recession, no accessory muscle "
                           "use.",
                "key": False},
            "vitals": {"label": "Vital signs",
                "finding": "HR 92 bpm · RR 20 (normal 15-25 at age 10) · "
                           "SpO₂ 98% on air · Temp 36.8°C — AFEBRILE. Nothing "
                           "in the observations supports an active infection.",
                "key": True},
            "respiratory": {"label": "Respiratory exam",
                "finding": "Chest expansion equal, percussion resonant. "
                           "Scattered high-pitched EXPIRATORY WHEEZE "
                           "throughout, brought out by forced expiration. NO "
                           "crackles, no bronchial breathing, no focal "
                           "dullness. Mild hyperinflation.",
                "key": True},
            "peak_flow_exam": {"label": "Bedside peak expiratory flow",
                "finding": "Best of three: 190 L/min. Predicted for height "
                           "138 cm: 260 L/min — 73% of predicted (< 80% is "
                           "abnormal). 15 min after inhaled salbutamol: "
                           "245 L/min, a rise of 29%.",
                "key": True},
            "ent": {"label": "Ear, nose and throat",
                "finding": "Nasal mucosa PALE AND BOGGY with clear discharge "
                           "— allergic, not infective. Tonsils not enlarged "
                           "or inflamed, no exudate. Tympanic membranes "
                           "normal. Pharynx NOT injected.",
                "key": True},
            "skin": {"label": "Skin examination",
                "finding": "Mild dry, lichenified FLEXURAL ECZEMA in both "
                           "antecubital fossae. No urticaria, no rash.",
                "key": True},
            "lymph_nodes": {"label": "Lymph node examination",
                "finding": "No cervical, axillary or supraclavicular "
                           "lymphadenopathy — no reactive nodes.",
                "key": False},
            "hands_nails": {"label": "Hands and nails",
                "finding": "NO finger clubbing, no cyanosis. The absence of "
                           "clubbing argues against bronchiectasis and cystic "
                           "fibrosis.",
                "key": False},
        },
        "investigations": {
            "spirometry": {"label": "Spirometry with reversibility",
                "result": "Pre-bronchodilator: FEV₁ 1.32 L (71% predicted) · "
                          "FVC 1.92 L (93% predicted) · FEV₁/FVC 0.69 "
                          "(ref > 0.80 in a child) — OBSTRUCTIVE pattern. "
                          "15 min after 400 µg salbutamol: FEV₁ 1.58 L, an "
                          "increase of 260 mL and 20%. SIGNIFICANT "
                          "REVERSIBILITY (≥ 12%). This is the test that makes "
                          "the diagnosis.",
                "category": "key"},
            "peak_flow": {"label": "Two-week peak flow diary",
                "result": "Mean diurnal variability 23% (ref < 20%), with "
                          "consistent morning dipping and the lowest readings "
                          "after PE. Variability of this degree is diagnostic "
                          "of asthma.",
                "category": "key"},
            "fbc": {"label": "Full blood count",
                "result": "Hb 128 g/L (ref 115-155 at this age) · WCC 7.4 "
                          "×10⁹/L (ref 4.5-13.5) — NOT raised · Neutrophils "
                          "3.6 · EOSINOPHILS 0.58 ×10⁹/L (ref 0.0-0.4) — "
                          "MILDLY RAISED, consistent with atopy · Platelets "
                          "290.",
                "category": "reasonable"},
            "crp": {"label": "C-reactive protein",
                "result": "2 mg/L (ref < 5). NOT RAISED. No biochemical "
                          "evidence of bacterial infection — three courses of "
                          "antibiotics would have had nothing to treat.",
                "category": "reasonable"},
            "cxr": {"label": "Chest X-ray",
                "result": "Clear lung fields. No consolidation, no collapse, "
                          "no bronchiectasis, no inhaled foreign body, normal "
                          "cardiac silhouette. Mild hyperinflation only. "
                          "NORMAL — and a normal film during a third episode "
                          "is itself the finding.",
                "category": "reasonable"},
            "pcr_covid_flu": {"label": "Respiratory viral PCR",
                "result": "Negative for influenza A/B, RSV and SARS-CoV-2. No "
                          "current viral infection.",
                "category": "low_value"},
            "culture_sputum": {"label": "Sputum culture",
                "result": "No sample — the cough is dry and a 10-year-old "
                          "does not expectorate. That fact is worth more than "
                          "the test would have been.",
                "category": "low_value"},
            "blood_cultures": {"label": "Blood cultures",
                "result": "Not indicated — afebrile, systemically well, no "
                          "signs of sepsis. No growth at 48 hours.",
                "category": "low_value"},
            "procalcitonin": {"label": "Procalcitonin",
                "result": "0.03 µg/L (ref < 0.1). Not indicated; adds nothing "
                          "the CRP and the observations have not settled.",
                "category": "low_value"},
        },
    },

    # ──────────────────────────────────────────────────────────────────
    # Case 10: Severe aortic stenosis presenting as syncope. Two findings
    # kill the trap and neither can be asked for: no postural drop despite
    # two drugs that cause one, and a slow-rising pulse with an ejection
    # systolic murmur radiating to the carotids.
    # ──────────────────────────────────────────────────────────────────
    "case_10": {
        "system_prompt": _RULES + (
            "YOU ARE: Harbans Singh, a 68-year-old retired postmaster. "
            "Understated, polite, inclined to minimise, mildly embarrassed to "
            "be here. Your wife insisted. You believe you simply stood up too "
            "quickly and you will offer that explanation if given room to.\n\n"
            "YOUR CHART — COMPLETE (reveal only what is asked):\n"
            "• Episodes: TWO blackouts in 6 weeks. Episode 1: climbing the "
            "stairs at home carrying a basket of washing. Episode 2: walking "
            "up the slope to the market. BOTH DURING EXERTION. Neither on "
            "standing up from a chair or a bed.\n"
            "• Warning: NONE. No dizziness, no light-headedness, no nausea, "
            "no sweating, no clamminess, no tunnel vision, no ringing in the "
            "ears. 'One moment I was walking, the next I was on the ground.'\n"
            "• Recovery: came round inside a minute, orientated immediately. "
            "NO confusion, NO drowsiness afterwards, NO tongue biting, NO "
            "incontinence. Your wife witnessed the second: NO jerking, NO "
            "shaking, and you were pale then flushed as you came round.\n"
            "• On exertion, 6 months: breathless walking up the slope, must "
            "stop halfway where you used to walk it straight. A TIGHT BAND "
            "across the chest when you push on, settling within 2 minutes of "
            "stopping. Never at rest, never at night, never lying flat.\n"
            "• Palpitations: NONE — no racing, no skipped beats, no "
            "fluttering, no awareness of your heartbeat at any time.\n"
            "• Medications: TAMSULOSIN 400 µg nightly for the prostate, "
            "started 8 months ago. AMLODIPINE 5 mg daily for blood pressure "
            "for 5 years. Nothing else, no over-the-counter, no herbal, no "
            "nitrates, no diuretics.\n"
            "• PMH: a doctor mentioned a HEART MURMUR 'years ago' and said to "
            "keep an eye on it; nothing was arranged and you forgot. Benign "
            "prostatic hyperplasia. No diabetes, no previous heart attack, no "
            "stroke, no epilepsy, no rheumatic fever as a child that you know "
            "of.\n"
            "• Family: father died at 70 of 'heart trouble', details unknown. "
            "No sudden death in anyone young, no inherited heart condition.\n"
            "• Social: non-smoker for 20 years, 10 a day before that. No "
            "alcohol. Lives with his wife, independent, walks daily — or did "
            "until the slope became difficult. Still drives.\n"
        ),
        "accepted_diagnoses": [
            "aortic stenosis", "severe aortic stenosis", "aortic valve "
            "stenosis", "calcific aortic stenosis", "critical aortic stenosis",
            "exertional syncope", "cardiac syncope", "aortic valve disease",
            "outflow tract obstruction", "valvular heart disease",
        ],
        "partial_diagnoses": [
            "heart murmur", "valve problem", "structural heart disease",
            "cardiac cause", "arrhythmia",
        ],
        "examination": {
            "general": {"label": "General inspection",
                "finding": "Well, comfortable at rest, not breathless sitting. "
                           "No pallor, no cyanosis, no clubbing, no oedema. "
                           "Nothing here suggests how ill he is.",
                "key": False},
            "vitals": {"label": "Vital signs",
                "finding": "HR 68 bpm regular · BP 118/82 mmHg — NARROW PULSE "
                           "PRESSURE of 36 mmHg (normal 40-60) · RR 14 · "
                           "SpO₂ 97% on air · Temp 36.5°C · capillary glucose "
                           "5.4 mmol/L (ref 4.0-7.8).",
                "key": True},
            "cardiovascular": {"label": "Cardiovascular exam",
                "finding": "HARSH EJECTION SYSTOLIC MURMUR, grade 4/6, loudest "
                           "at the right second intercostal space, RADIATING "
                           "TO BOTH CAROTIDS, louder on expiration. SECOND "
                           "HEART SOUND SOFT AND SINGLE — the aortic component "
                           "is almost inaudible. Apex beat heaving but not "
                           "displaced. No diastolic murmur. JVP not raised, no "
                           "sacral or ankle oedema.",
                "key": True},
            "peripheral_pulses": {"label": "Peripheral pulses",
                "finding": "Carotid pulse SLOW-RISING AND LOW VOLUME (pulsus "
                           "parvus et tardus). All peripheral pulses present "
                           "and equal, no radio-radial or radio-femoral delay. "
                           "No carotid bruit distinguishable from the "
                           "radiating murmur.",
                "key": True},
            "postural_bp": {"label": "Lying and standing blood pressure",
                "finding": "Lying 120/82 mmHg · standing at 1 min 116/80 · at "
                           "3 min 118/80. NO POSTURAL DROP (a fall of ≥ 20 "
                           "systolic or ≥ 10 diastolic defines one). He is on "
                           "tamsulosin and amlodipine, which both cause "
                           "postural hypotension — and he does not have it.",
                "key": True},
            "neuro_focal": {"label": "Focal neurological exam",
                "finding": "Power 5/5, tone, sensation and coordination "
                           "normal, plantars downgoing, no neglect, speech "
                           "normal. NO focal deficit — this was not a stroke "
                           "or a TIA.",
                "key": True},
            "hydration": {"label": "Hydration assessment",
                "finding": "Mucous membranes moist, skin turgor normal, no "
                           "sunken eyes, capillary refill < 2 s. NOT "
                           "dehydrated.",
                "key": False},
            "respiratory": {"label": "Respiratory exam",
                "finding": "Chest clear, no crackles, no wheeze, percussion "
                           "resonant, expansion equal. No pulmonary oedema.",
                "key": False},
            "abdomen": {"label": "Abdominal exam",
                "finding": "Soft, non-tender. No pulsatile mass, no bruit — "
                           "no abdominal aortic aneurysm palpable.",
                "key": False},
        },
        "investigations": {
            "ecg": {"label": "ECG (12-lead)",
                "result": "Sinus rhythm 66 bpm. LEFT VENTRICULAR HYPERTROPHY "
                          "by voltage criteria (S in V1 + R in V5 = 39 mm; "
                          "Sokolow-Lyon threshold 35 mm) with lateral ST "
                          "depression and T-wave inversion — a strain "
                          "pattern. PR 168 ms, QRS 96 ms, no heart block, no "
                          "delta wave, QTc 420 ms. No acute ischaemia.",
                "category": "key"},
            "echo": {"label": "Transthoracic echocardiogram",
                "result": "SEVERE CALCIFIC AORTIC STENOSIS. Trileaflet valve, "
                          "heavily calcified, markedly restricted opening. "
                          "Peak gradient 76 mmHg · MEAN GRADIENT 48 mmHg "
                          "(severe ≥ 40) · valve area 0.8 cm² (severe < 1.0) · "
                          "dimensionless index 0.21. Concentric LV "
                          "hypertrophy, wall 14 mm. LV ejection fraction 58% "
                          "— still preserved. Mild aortic regurgitation, no "
                          "mitral disease. THIS IS THE DIAGNOSIS, and "
                          "exertional syncope in severe aortic stenosis is an "
                          "indication for urgent valve referral.",
                "category": "key"},
            "holter": {"label": "48-hour ambulatory ECG",
                "result": "Sinus rhythm throughout, rate 52-108 bpm. "
                          "Occasional ventricular ectopics (0.3% of beats). "
                          "NO pauses > 2 s, no AV block, no ventricular or "
                          "supraventricular tachycardia. Reasonable, and the "
                          "negative result matters: it excludes the OTHER "
                          "cardiac cause of syncope.",
                "category": "reasonable"},
            "bnp": {"label": "NT-proBNP",
                "result": "486 ng/L (ref < 125 under 75 years) — RAISED. "
                          "Evidence of cardiac wall stress. Not specific to "
                          "the valve, but not the result of a simple faint.",
                "category": "reasonable"},
            "troponin_0h": {"label": "High-sensitivity troponin",
                "result": "6 ng/L (ref < 14) — negative. No myocardial "
                          "injury; the exertional chest tightness is demand "
                          "ischaemia from the valve, not a coronary event.",
                "category": "reasonable"},
            "fbc": {"label": "Full blood count",
                "result": "Hb 141 g/L (ref 130-170) · WCC 6.8 · Platelets "
                          "232 · MCV 89 fL. Normal — anaemia excluded as a "
                          "cause of exertional breathlessness.",
                "category": "reasonable"},
            "u_e": {"label": "Urea & electrolytes",
                "result": "Na 139 mmol/L · K 4.3 · Urea 5.6 · Creatinine "
                          "88 µmol/L · eGFR > 60. Normal — no dehydration, no "
                          "electrolyte cause for collapse.",
                "category": "reasonable"},
            "cxr": {"label": "Chest X-ray",
                "result": "Heart size normal. Lung fields clear, no pulmonary "
                          "oedema. CALCIFIED AORTIC VALVE visible on the "
                          "lateral film.",
                "category": "reasonable"},
            "hba1c_glucose": {"label": "HbA1c & fasting glucose",
                "result": "HbA1c 39 mmol/mol (ref < 42), fasting glucose "
                          "5.1 mmol/L. Normal — hypoglycaemia excluded.",
                "category": "reasonable"},
            "ct_head": {"label": "CT head",
                "result": "No haemorrhage, no infarct, no mass. NORMAL. "
                          "Syncope with full immediate recovery and no focal "
                          "signs does not need brain imaging, and ordering it "
                          "is the commonest way this diagnosis is delayed.",
                "category": "low_value"},
            "eeg": {"label": "EEG",
                "result": "Normal, no epileptiform activity. There were no "
                          "seizure features: no aura, no jerking, no tongue "
                          "biting, no post-ictal confusion.",
                "category": "low_value"},
            "d_dimer": {"label": "D-dimer",
                "result": "Not indicated. No features of pulmonary embolism "
                          "or venous thromboembolism.",
                "category": "low_value"},
        },
    },

    # ──────────────────────────────────────────────────────────────────
    # Case 8: Rectal carcinoma with coexisting haemorrhoids. The rectal
    # examination returns BOTH findings in one report, on purpose — that
    # is the clinical reality, and a learner who stops reading at the
    # first one has made the same mistake inside the examination that
    # the case is about.
    # ──────────────────────────────────────────────────────────────────
    "case_8": {
        "system_prompt": _RULES + (
            "YOU ARE: Naveen Reddy, a 58-year-old bus depot manager. "
            "Practical, understated, slightly impatient, certain this is "
            "your piles. You have come about rectal bleeding for 4 months, "
            "and only because your wife insisted.\n\n"
            "YOU GENUINELY HAVE HAEMORRHOIDS, diagnosed 12 years ago. You "
            "are not wrong about that. What you have not noticed is that "
            "this episode differs from every previous one. If asked to "
            "compare, you will think and realise it is different.\n\n"
            "YOUR CHART — COMPLETE (reveal only what is asked):\n"
            "• Bleeding NOW: present 4 months, most days. MIXED THROUGH the "
            "stool rather than on the surface. DARKER than you remember, "
            "sometimes almost maroon. SLIME or jelly with it on occasion. "
            "Not related to straining.\n"
            "• Bleeding BEFORE (your usual piles, 12 years): BRIGHT RED, on "
            "the paper or a few drops in the pan, never mixed in, always "
            "after straining, settles in a day or two with cream.\n"
            "• Bowel habit: CHANGED 4 months ago. Was once every morning, "
            "reliably. Now THREE TO FOUR TIMES A DAY and looser, never "
            "properly formed. No nocturnal diarrhoea.\n"
            "• Tenesmus: frequently feel you have not finished and must go "
            "back within minutes, often passing little. New in 4 months.\n"
            "• Weight: 6 kg down in 4 months, unintentionally. Trousers "
            "loose on the same notch.\n"
            "• Energy: tired most days. BREATHLESS climbing the depot "
            "stairs, which you managed easily a year ago. No chest pain.\n"
            "• Appetite: slightly reduced but you still eat normally. No "
            "early satiety, no vomiting, no difficulty swallowing.\n"
            "• PMH: haemorrhoids (12 years). Type 2 diabetes — diet "
            "controlled, diagnosed 4 years ago. Nothing else. No previous "
            "colonoscopy, never invited for bowel screening that you "
            "recall, no inflammatory bowel disease.\n"
            "• Medications: metformin 500 mg twice daily. Occasional "
            "haemorrhoid cream. NO NSAIDs, NO aspirin, NO anticoagulant, NO "
            "iron tablets.\n"
            "• Family: FATHER had bowel cancer at 71, treated with surgery, "
            "lived another decade. No other cancers in the family.\n"
            "• Social: non-smoker. Alcohol 8 units/week. Sits for long "
            "periods at work, which is what you blame the piles on.\n"
            "• NOT present: no abdominal pain of note, no jaundice, no "
            "fever, no night sweats, no foreign travel, no anal pain, no "
            "external lump you can feel.\n"
        ),
        "accepted_diagnoses": [
            "colorectal cancer", "bowel cancer", "rectal cancer",
            "colorectal carcinoma", "rectal carcinoma", "colon cancer",
            "adenocarcinoma of the rectum", "large bowel malignancy",
            "colorectal malignancy", "bowel malignancy", "rectal tumour",
        ],
        "partial_diagnoses": [
            "malignancy", "cancer", "iron deficiency anaemia",
            "lower gi bleeding", "needs colonoscopy", "two week wait",
            "inflammatory bowel disease",
        ],
        "examination": {
            "general": {"label": "General inspection",
                "finding": "PALE conjunctivae. Comfortable, not jaundiced, "
                           "no clubbing, no lymphoedema. Looks slightly "
                           "thinner than his recorded weight from last year.",
                "key": True},
            "vitals": {"label": "Vital signs",
                "finding": "HR 92 bpm regular · BP 128/76 mmHg · RR 14 · "
                           "SpO₂ 98% on air · Temp 36.6°C. Mild resting "
                           "tachycardia; otherwise unremarkable.",
                "key": False},
            "rectal": {"label": "Digital rectal examination",
                "finding": "TWO findings, and both are real. "
                           "(1) EXTERNAL HAEMORRHOIDS at 3 and 7 o'clock, "
                           "non-thrombosed, non-tender — exactly as he "
                           "describes, and they do bleed. "
                           "(2) A FIRM, IRREGULAR, FIXED MASS palpable on "
                           "the posterior rectal wall about 7 cm from the "
                           "anal verge, roughly 4 cm across, not tender. "
                           "Dark altered blood and mucus on the glove. "
                           "Finding (1) does not account for finding (2).",
                "key": True},
            "abdomen": {"label": "Abdominal exam",
                "finding": "Soft, non-distended, non-tender. No palpable "
                           "mass, no hepatomegaly, no ascites. Bowel sounds "
                           "normal. A normal abdomen does not exclude a "
                           "rectal tumour that sits below the reach of "
                           "palpation.",
                "key": True},
            "hands_nails": {"label": "Hands and nails",
                "finding": "KOILONYCHIA — spoon-shaped nails — with pale "
                           "nail beds. No clubbing. Signs of chronic iron "
                           "deficiency.",
                "key": True},
            "lymph_nodes": {"label": "Lymph node examination",
                "finding": "No inguinal, cervical or supraclavicular "
                           "lymphadenopathy. No Virchow's node.",
                "key": False},
            "weight_bmi": {"label": "Weight and BMI",
                "finding": "78 kg, 1.74 m, BMI 25.8 kg/m². Recorded weight "
                           "14 months ago was 84 kg — a 6 kg fall, "
                           "documented rather than reported.",
                "key": False},
            "mental_state": {"label": "Mental state",
                "finding": "Calm, orientated, no anxiety or low mood. Keen "
                           "to be reassured and to get back to work.",
                "key": False},
        },
        "investigations": {
            "fbc": {"label": "Full blood count",
                "result": "Hb 94 g/L (ref 130-170) — ANAEMIC · MCV 71 fL "
                          "(ref 80-100) — MICROCYTIC · WCC 7.6 · Platelets "
                          "468 ×10⁹/L (ref 150-400) — raised. Microcytic "
                          "anaemia in a man of 58 is a red flag in its own "
                          "right and is never explained by haemorrhoids "
                          "bleeding a few drops onto the paper.",
                "category": "key"},
            "colonoscopy": {"label": "Colonoscopy",
                "result": "A FUNGATING, CIRCUMFERENTIAL TUMOUR at 8 cm from "
                          "the anal verge, partially obstructing the lumen; "
                          "the scope passed with difficulty. Biopsies taken. "
                          "Internal haemorrhoids also seen on retroflexion — "
                          "present, and not the cause. Histology: moderately "
                          "differentiated adenocarcinoma. THIS IS THE "
                          "DIAGNOSIS.",
                "category": "key"},
            "iron_ferritin": {"label": "Iron studies & ferritin",
                "result": "Ferritin 7 µg/L (ref 30-400) — VERY LOW · serum "
                          "iron 4 µmol/L · transferrin saturation 6%. "
                          "Confirmed iron deficiency from chronic blood "
                          "loss.",
                "category": "key"},
            "fit": {"label": "Faecal Immunochemical Test (FIT)",
                "result": "Faecal haemoglobin 340 µg Hb/g faeces (referral "
                          "threshold 10 in symptomatic patients) — STRONGLY "
                          "POSITIVE. Useful, but note what it cannot do: a "
                          "negative FIT would not have excluded this, and "
                          "the rectal examination had already found the "
                          "mass.",
                "category": "reasonable"},
            "cea_ca199": {"label": "CEA & CA 19-9",
                "result": "CEA 18.4 µg/L (ref < 5) — raised · CA 19-9 "
                          "32 U/mL (ref < 37). CEA is for monitoring after "
                          "treatment, not for diagnosis; a normal CEA would "
                          "have excluded nothing.",
                "category": "reasonable"},
            "ct_abdomen": {"label": "CT chest, abdomen and pelvis",
                "result": "A 4.2 cm rectal mass with extension through the "
                          "muscularis propria and three enlarged mesorectal "
                          "nodes. NO liver or lung metastases. Staging "
                          "cT3 N1 M0.",
                "category": "reasonable"},
            "u_e_lft": {"label": "U&E and liver function",
                "result": "Na 139 · K 4.1 · Creatinine 84 µmol/L · eGFR "
                          "> 60 · ALT 24 · ALP 88 · Bilirubin 11 · Albumin "
                          "36 g/L (ref 35-50). Essentially normal.",
                "category": "reasonable"},
            "crp": {"label": "C-reactive protein",
                "result": "14 mg/L (ref < 5) — mildly raised. Non-specific, "
                          "and not enough to point anywhere on its own.",
                "category": "reasonable"},
            "stool_mc_s": {"label": "Stool microscopy, culture & sensitivity",
                "result": "No growth. No ova, cysts or parasites. No "
                          "Clostridioides difficile toxin. Negative — and "
                          "four months of altered bowel habit with weight "
                          "loss was never going to be an infection.",
                "category": "low_value"},
            "abdo_uss": {"label": "Abdominal ultrasound",
                "result": "Liver, gallbladder, pancreas, spleen and kidneys "
                          "normal. No free fluid. Ultrasound does not image "
                          "the rectum; a normal scan here is reassurance "
                          "about nothing that was asked.",
                "category": "low_value"},
            "psa": {"label": "Prostate specific antigen",
                "result": "1.8 µg/L (ref < 4 at this age). Normal. Not "
                          "indicated — nothing in the history points at the "
                          "prostate.",
                "category": "low_value"},
            "coeliac_screen": {"label": "Coeliac serology",
                "result": "Anti-tTG IgA < 1 U/mL (ref < 7), total IgA "
                          "normal. Negative. Reasonable in young patients "
                          "with altered bowel habit; not in a man of 58 with "
                          "rectal bleeding and weight loss.",
                "category": "low_value"},
        },
    },
}

# Merge the clinical data layer into the base CASES definitions.
for _cid, _extra in CLINICAL_DATA.items():
    if _cid in CASES:
        CASES[_cid].update(_extra)


# ══════════════════════════════════════════════════════════════════════
# MASTER INVESTIGATIONS — Universal panel shown to students on EVERY case
# ----------------------------------------------------------------------
# All cases share this identical list of ~80 tests so students cannot
# infer the diagnosis from which tests are available.
#
# Each entry has:
#   label         : display name shown on the chip button
#   group         : section heading in the UI (groups chips visually)
#   normal_result : what the student sees when this test is ordered in a
#                   case where it is NOT relevant — always a plausible
#                   "nothing found here" report.
#
# Per-case RESULT OVERRIDES live in each case's "investigations" dict.
# app.py: if test_key is in case["investigations"], return that result;
#         otherwise return MASTER_INVESTIGATIONS[test_key]["normal_result"].
# clinical_evaluator.py: still grades on case["investigations"] only.
# ══════════════════════════════════════════════════════════════════════

MASTER_INVESTIGATIONS = {

    # ── Routine Bloods ───────────────────────────────────────────────────
    "fbc": {
        "label": "Full Blood Count (FBC)",
        "group": "Routine Bloods",
        "normal_result": (
            "Hb 138 g/L · WCC 7.2 × 10⁹/L · Neutrophils 4.5 · "
            "Lymphocytes 2.0 · Platelets 248 × 10⁹/L · MCV 88 fL. "
            "All within normal limits."
        ),
    },
    "u_e": {
        "label": "Urea & Electrolytes (U&E)",
        "group": "Routine Bloods",
        "normal_result": (
            "Na 138 mmol/L · K 4.1 · Urea 5.2 · Creatinine 78 µmol/L "
            "· eGFR >60 mL/min. All within normal limits."
        ),
    },
    "u_e_creatinine": {
        "label": "Urea, Electrolytes & Renal Function",
        "group": "Routine Bloods",
        "normal_result": (
            "Na 139 · K 4.0 · Urea 5.0 · Creatinine 76 µmol/L · "
            "eGFR >60 mL/min. Normal renal function."
        ),
    },
    "lft": {
        "label": "Liver Function Tests (LFTs)",
        "group": "Routine Bloods",
        "normal_result": (
            "ALT 28 U/L · AST 24 · ALP 72 · GGT 22 · "
            "Bilirubin 9 µmol/L · Albumin 42 g/L. All normal."
        ),
    },
    "lft_amylase": {
        "label": "LFTs & Serum Amylase",
        "group": "Routine Bloods",
        "normal_result": (
            "ALT 26 · AST 22 · ALP 68 · Bilirubin 8 — all normal. "
            "Serum amylase 45 U/L (normal < 100). "
            "No hepatobiliary or pancreatic pathology."
        ),
    },
    "lft_ck": {
        "label": "LFTs & CK (Creatine Kinase)",
        "group": "Routine Bloods",
        "normal_result": (
            "ALT 28 · AST 24 · ALP 70 · Bilirubin 9 — all normal. "
            "CK 92 U/L (normal < 170). "
            "No hepatocellular or muscle pathology."
        ),
    },
    "u_e_lft": {
        "label": "U&E, LFTs & Coagulation Screen",
        "group": "Routine Bloods",
        "normal_result": (
            "U&E: Na 138, K 4.1, Urea 5.0, Creatinine 78 — normal. "
            "LFTs all normal. INR 1.0, APTT 28 s. "
            "No haematological or metabolic abnormality."
        ),
    },
    "crp": {
        "label": "C-Reactive Protein (CRP)",
        "group": "Routine Bloods",
        "normal_result": (
            "CRP 2 mg/L (normal < 5). "
            "No significant systemic inflammation."
        ),
    },
    "esr": {
        "label": "ESR (Erythrocyte Sedimentation Rate)",
        "group": "Routine Bloods",
        "normal_result": (
            "ESR 8 mm/hr — within age-appropriate normal range. "
            "No significant inflammatory process detected."
        ),
    },
    "lipids": {
        "label": "Lipid Profile",
        "group": "Routine Bloods",
        "normal_result": (
            "Total cholesterol 4.6 mmol/L · LDL 2.8 · HDL 1.4 · "
            "Triglycerides 1.1. All within target range. No dyslipidaemia."
        ),
    },
    "hba1c_glucose": {
        "label": "HbA1c & Fasting Glucose",
        "group": "Routine Bloods",
        "normal_result": (
            "HbA1c 36 mmol/mol (normal < 48) · Fasting glucose 4.8 mmol/L. "
            "Diabetes and pre-diabetes excluded."
        ),
    },
    "hba1c": {
        "label": "HbA1c",
        "group": "Routine Bloods",
        "normal_result": (
            "HbA1c 38 mmol/mol (5.6%) — normal (< 48 mmol/mol). "
            "No evidence of chronic hyperglycaemia."
        ),
    },
    "iron_ferritin": {
        "label": "Iron Studies & Ferritin",
        "group": "Routine Bloods",
        "normal_result": (
            "Serum iron 16 µmol/L · Ferritin 62 µg/L · TIBC 52 µmol/L · "
            "Transferrin saturation 32%. Normal iron stores."
        ),
    },
    "b12_folate": {
        "label": "Vitamin B12 & Folate",
        "group": "Routine Bloods",
        "normal_result": (
            "Vitamin B12 388 ng/L (normal 200–900) · "
            "Serum folate 12.4 µg/L (normal > 4.0). Both within normal range."
        ),
    },
    "vitamin_d": {
        "label": "Vitamin D (25-OH)",
        "group": "Routine Bloods",
        "normal_result": (
            "25-OH Vitamin D 58 nmol/L — sufficient (> 50 nmol/L). "
            "No deficiency or insufficiency."
        ),
    },
    "urate": {
        "label": "Serum Uric Acid (Urate)",
        "group": "Routine Bloods",
        "normal_result": (
            "Serum urate 0.34 mmol/L (normal < 0.42 in women, < 0.48 in men). "
            "Gout and hyperuricaemia not supported."
        ),
    },
    "bone_profile": {
        "label": "Bone Profile (Ca, Phosphate, ALP)",
        "group": "Routine Bloods",
        "normal_result": (
            "Calcium 2.42 mmol/L (normal 2.2–2.6) · Phosphate 1.12 · "
            "ALP 72 U/L. Corrected calcium normal. "
            "No hypercalcaemia, hypocalcaemia, or metabolic bone disease."
        ),
    },

    # ── Haematology & Coagulation ────────────────────────────────────────
    "blood_film": {
        "label": "Peripheral Blood Film",
        "group": "Haematology & Coagulation",
        "normal_result": (
            "Normal red cell morphology — no fragments, spherocytes, or sickle cells. "
            "White cell differential normal. Platelets appear adequate on film. "
            "No blast cells. No malaria parasites."
        ),
    },
    "d_dimer": {
        "label": "D-dimer",
        "group": "Haematology & Coagulation",
        "normal_result": (
            "D-dimer 148 ng/mL (reference < 500 ng/mL) — NEGATIVE. "
            "Does not support active thrombosis in a low-pretest-probability context."
        ),
    },
    "thrombophilia_screen": {
        "label": "Thrombophilia Screen",
        "group": "Haematology & Coagulation",
        "normal_result": (
            "Factor V Leiden: not detected. Prothrombin G20210A: not detected. "
            "Protein C, Protein S, Antithrombin: all within normal range. "
            "Antiphospholipid antibodies (aCL, anti-β2GP1, lupus anticoagulant): all negative."
        ),
    },

    # ── Cardiac ──────────────────────────────────────────────────────────
    "ecg": {
        "label": "ECG (12-lead)",
        "group": "Cardiac",
        "normal_result": (
            "Normal sinus rhythm at 74 bpm. Normal axis. Normal PR (160 ms) and "
            "QRS (88 ms) intervals. No ST elevation or depression. No T-wave inversion. "
            "No Q waves or bundle branch block."
        ),
    },
    "troponin_0h": {
        "label": "High-sensitivity Troponin (0 h)",
        "group": "Cardiac",
        "normal_result": (
            "hs-Troponin I < 2 ng/L (reference < 14 ng/L) — NEGATIVE. "
            "No evidence of acute myocardial injury."
        ),
    },
    "troponin_3h": {
        "label": "High-sensitivity Troponin (3 h)",
        "group": "Cardiac",
        "normal_result": (
            "hs-Troponin I < 2 ng/L — NEGATIVE. Delta troponin 0. "
            "ACS effectively excluded on serial troponins."
        ),
    },
    "troponin": {
        "label": "Troponin (high-sensitivity)",
        "group": "Cardiac",
        "normal_result": (
            "hs-Troponin I 3 ng/L (reference < 14 ng/L) — NEGATIVE. "
            "No myocardial injury identified."
        ),
    },
    "echo": {
        "label": "Echocardiogram (TTE)",
        "group": "Cardiac",
        "normal_result": (
            "Normal LV size and systolic function. EF 62%. No RWMA. "
            "Normal valves — no stenosis or significant regurgitation. "
            "No pericardial effusion. RV size and function normal."
        ),
    },
    "exercise_ecg": {
        "label": "Exercise Tolerance Test (ETT)",
        "group": "Cardiac",
        "normal_result": (
            "Completed Bruce protocol to stage 4. No chest pain or presyncope induced. "
            "No ST changes at peak exercise. Normal HR and BP response. "
            "Negative for exercise-induced ischaemia."
        ),
    },
    "ct_angiogram": {
        "label": "CT Coronary Angiogram (CTCA)",
        "group": "Cardiac",
        "normal_result": (
            "No significant coronary artery stenosis. Coronary calcium score 0. "
            "Normal left main, LAD, LCx and RCA. No obstructive CAD."
        ),
    },
    "bnp": {
        "label": "BNP / NT-proBNP",
        "group": "Cardiac",
        "normal_result": (
            "NT-proBNP 48 pg/mL (normal < 125 pg/mL). "
            "Heart failure very unlikely. No significant myocardial wall stress."
        ),
    },
    "holter": {
        "label": "24-hour Holter Monitor",
        "group": "Cardiac",
        "normal_result": (
            "Predominantly sinus rhythm throughout 24 hours. Rare isolated SVEs "
            "(< 50 total) — not clinically significant. No AF, VT, or pauses. "
            "Symptoms diary: no correlation with arrhythmia."
        ),
    },

    # ── Respiratory ──────────────────────────────────────────────────────
    "cxr": {
        "label": "Chest X-ray (PA)",
        "group": "Respiratory",
        "normal_result": (
            "Clear lung fields bilaterally. Normal cardiac silhouette (CTR < 0.5). "
            "No consolidation, effusion, pneumothorax, or mass. "
            "Normal mediastinum and hila."
        ),
    },
    "abg": {
        "label": "Arterial Blood Gas (ABG) on air",
        "group": "Respiratory",
        "normal_result": (
            "pH 7.41 · PaO₂ 12.4 kPa / 93 mmHg · PaCO₂ 5.0 kPa / 38 mmHg · "
            "HCO₃ 24 mmol/L · SaO₂ 98% · BE 0. "
            "Normal acid-base balance. No respiratory failure."
        ),
    },
    "vbg": {
        "label": "Venous Blood Gas (VBG)",
        "group": "Respiratory",
        "normal_result": (
            "pH 7.38 · pCO₂ 5.4 · HCO₃ 23 · BE −1 · Lactate 0.9 mmol/L. "
            "Normal venous acid-base. Na 138, K 4.0, Glucose 5.1."
        ),
    },
    "ctpa": {
        "label": "CT Pulmonary Angiogram (CTPA)",
        "group": "Respiratory",
        "normal_result": (
            "No filling defects in the pulmonary vasculature. "
            "Main, lobar, segmental and subsegmental arteries all patent. "
            "Pulmonary embolism excluded. No incidental significant findings."
        ),
    },
    "vq_scan": {
        "label": "V/Q (Ventilation-Perfusion) Scan",
        "group": "Respiratory",
        "normal_result": (
            "Low probability (normal) V/Q scan. "
            "No ventilation-perfusion mismatch identified. "
            "Pulmonary embolism effectively excluded."
        ),
    },
    "peak_flow": {
        "label": "Peak Expiratory Flow (PEF)",
        "group": "Respiratory",
        "normal_result": (
            "PEF 510 L/min (102% predicted for age, sex, and height). "
            "Normal effort-dependent peak flow. No obstructive pattern."
        ),
    },
    "spirometry": {
        "label": "Spirometry / Pulmonary Function Tests",
        "group": "Respiratory",
        "normal_result": (
            "FEV₁ 3.62 L (98% predicted) · FVC 4.58 L (99% predicted) · "
            "FEV₁/FVC ratio 0.79 (normal > 0.7). "
            "No obstructive or restrictive pattern. DLCO normal."
        ),
    },

    # ── Microbiology ─────────────────────────────────────────────────────
    "urinalysis": {
        "label": "Urinalysis (Dipstick)",
        "group": "Microbiology",
        "normal_result": (
            "Leucocytes NEGATIVE · Nitrites NEGATIVE · Blood NEGATIVE · "
            "Protein NEGATIVE · Glucose NEGATIVE · Ketones NEGATIVE. "
            "No features of infection or systemic pathology."
        ),
    },
    "urine_culture": {
        "label": "Urine MC&S",
        "group": "Microbiology",
        "normal_result": (
            "< 10⁴ cfu/mL mixed organisms — not significant. "
            "No pure growth of uropathogens. UTI not confirmed on culture."
        ),
    },
    "blood_cultures": {
        "label": "Blood Cultures × 2",
        "group": "Microbiology",
        "normal_result": (
            "No growth at 48 hours. Both aerobic and anaerobic bottles negative. "
            "Bacteraemia not detected."
        ),
    },
    "culture_sputum": {
        "label": "Sputum Culture & Sensitivity",
        "group": "Microbiology",
        "normal_result": (
            "Normal upper respiratory flora only. No significant pathogens isolated. "
            "No growth on selective media for Legionella or TB. "
            "AFB smear negative."
        ),
    },
    "stool_mc_s": {
        "label": "Stool MC&S / Ova, Cysts & Parasites",
        "group": "Microbiology",
        "normal_result": (
            "No enteric pathogens isolated (no Salmonella, Shigella, Campylobacter, "
            "E. coli O157, or Clostridioides difficile toxin). "
            "No ova, cysts, or parasites seen on microscopy."
        ),
    },
    "pcr_covid_flu": {
        "label": "Viral PCR (COVID-19 / Influenza A & B)",
        "group": "Microbiology",
        "normal_result": (
            "SARS-CoV-2 PCR: NOT DETECTED. "
            "Influenza A PCR: NOT DETECTED. "
            "Influenza B PCR: NOT DETECTED."
        ),
    },
    "lactate": {
        "label": "Serum Lactate",
        "group": "Microbiology",
        "normal_result": (
            "Lactate 0.8 mmol/L (normal < 2.0). "
            "No evidence of tissue hypoperfusion or impending septic shock."
        ),
    },
    "procalcitonin": {
        "label": "Procalcitonin (PCT)",
        "group": "Microbiology",
        "normal_result": (
            "PCT 0.04 µg/L (normal < 0.1). "
            "Low procalcitonin — bacterial infection unlikely to be driving this presentation."
        ),
    },

    # ── Endocrine & Hormones ─────────────────────────────────────────────
    "tfts": {
        "label": "Thyroid Function Tests (TSH + Free T4)",
        "group": "Endocrine & Hormones",
        "normal_result": (
            "TSH 1.8 mU/L (normal 0.4–4.0) · Free T4 16.2 pmol/L (normal 12–22). "
            "Euthyroid. No thyroid dysfunction."
        ),
    },
    "tsh": {
        "label": "Thyroid Function (TSH)",
        "group": "Endocrine & Hormones",
        "normal_result": (
            "TSH 1.9 mU/L (normal 0.4–4.0). "
            "Normal thyroid function. No further testing required."
        ),
    },
    "ft3": {
        "label": "Free T3",
        "group": "Endocrine & Hormones",
        "normal_result": (
            "Free T3 4.8 pmol/L (normal 3.1–6.8). "
            "Normal T3. No T3 toxicosis."
        ),
    },
    "anti_tpo": {
        "label": "Anti-TPO Antibodies",
        "group": "Endocrine & Hormones",
        "normal_result": (
            "Anti-TPO antibodies 8 IU/mL (normal < 35). "
            "Negative. Autoimmune thyroiditis not supported."
        ),
    },
    "cortisol": {
        "label": "Morning Cortisol / Short Synacthen Test",
        "group": "Endocrine & Hormones",
        "normal_result": (
            "09:00 cortisol 462 nmol/L (normal > 350). "
            "Short Synacthen: stimulated cortisol 612 nmol/L at 30 min. "
            "Adrenal insufficiency excluded."
        ),
    },
    "prolactin": {
        "label": "Serum Prolactin",
        "group": "Endocrine & Hormones",
        "normal_result": (
            "Prolactin 14 µg/L (normal < 25 in women, < 15 in men). "
            "Normal. No hyperprolactinaemia."
        ),
    },
    "lh_fsh": {
        "label": "LH, FSH & Oestrogen",
        "group": "Endocrine & Hormones",
        "normal_result": (
            "LH 6.2 IU/L · FSH 5.8 IU/L · Oestradiol 280 pmol/L — "
            "all within normal mid-follicular phase range. "
            "No pattern of PCOS or ovarian failure."
        ),
    },
    "testosterone": {
        "label": "Testosterone (Total)",
        "group": "Endocrine & Hormones",
        "normal_result": (
            "Total testosterone 18.4 nmol/L (normal male 8–29 nmol/L; "
            "normal female 0.3–2.0 nmol/L). "
            "Normal. No hypogonadism or hyperandrogenism."
        ),
    },

    # ── Diabetes & Metabolic ─────────────────────────────────────────────
    "blood_glucose": {
        "label": "Blood Glucose (BM / Capillary)",
        "group": "Diabetes & Metabolic",
        "normal_result": (
            "Capillary glucose 5.2 mmol/L (normal range 4–7 mmol/L). "
            "Hypoglycaemia and hyperglycaemia both excluded."
        ),
    },
    "blood_ketones": {
        "label": "Blood Ketones (Beta-hydroxybutyrate)",
        "group": "Diabetes & Metabolic",
        "normal_result": (
            "Beta-hydroxybutyrate 0.2 mmol/L (normal < 0.6). "
            "No significant ketonaemia. DKA and starvation ketosis excluded."
        ),
    },
    "c_peptide": {
        "label": "C-peptide",
        "group": "Diabetes & Metabolic",
        "normal_result": (
            "Fasting C-peptide 0.72 nmol/L (normal 0.27–1.28). "
            "Normal endogenous insulin secretion. "
            "Type 1 DM (absent C-peptide) not supported."
        ),
    },
    "anti_gad": {
        "label": "Anti-GAD / Anti-islet Cell Antibodies",
        "group": "Diabetes & Metabolic",
        "normal_result": (
            "Anti-GAD65 < 5 IU/mL (normal < 10) — negative. "
            "Anti-islet cell antibodies: negative. "
            "Autoimmune Type 1 DM not supported."
        ),
    },
    "ogtt": {
        "label": "Oral Glucose Tolerance Test (OGTT)",
        "group": "Diabetes & Metabolic",
        "normal_result": (
            "Fasting glucose 4.6 mmol/L · 2-hour glucose 5.8 mmol/L. "
            "Both within normal range. Diabetes and impaired glucose tolerance excluded."
        ),
    },

    # ── GI & Hepatobiliary ───────────────────────────────────────────────
    "amylase": {
        "label": "Serum Amylase / Lipase",
        "group": "GI & Hepatobiliary",
        "normal_result": (
            "Amylase 42 U/L (normal < 100) · Lipase 28 U/L (normal < 60). "
            "No evidence of acute pancreatitis."
        ),
    },
    "h_pylori": {
        "label": "H. pylori Test (Urea Breath / Stool Ag)",
        "group": "GI & Hepatobiliary",
        "normal_result": (
            "Urea breath test: NEGATIVE. "
            "H. pylori stool antigen: NEGATIVE. "
            "H. pylori infection not detected."
        ),
    },
    "ogd": {
        "label": "OGD (Upper GI Endoscopy)",
        "group": "GI & Hepatobiliary",
        "normal_result": (
            "Normal oesophageal mucosa. Z-line in normal position. "
            "No erosions, no oesophagitis, no Barrett's change. "
            "Normal gastric body and antrum. Duodenum normal. "
            "No malignancy, no peptic ulcer."
        ),
    },
    "abdo_uss": {
        "label": "Abdominal Ultrasound",
        "group": "GI & Hepatobiliary",
        "normal_result": (
            "Normal liver echotexture and size. No focal hepatic lesion. "
            "Gallbladder normal — no stones, no wall thickening. "
            "No biliary duct dilatation. Spleen 10 cm, normal. "
            "Both kidneys normal. No free fluid."
        ),
    },
    "ct_abdomen": {
        "label": "CT Abdomen & Pelvis",
        "group": "GI & Hepatobiliary",
        "normal_result": (
            "No intra-abdominal mass, abscess, or free perforation. "
            "No bowel obstruction or ischaemia. "
            "Liver, spleen, pancreas, kidneys, and adrenals all normal. "
            "No free fluid. No lymphadenopathy."
        ),
    },
    "coeliac_screen": {
        "label": "Coeliac Screen (anti-tTG IgA)",
        "group": "GI & Hepatobiliary",
        "normal_result": (
            "Anti-tTG IgA < 4 U/mL — negative. "
            "Total IgA normal (selective IgA deficiency excluded). "
            "Coeliac disease not supported."
        ),
    },
    "cea_ca199": {
        "label": "CEA & CA 19-9 Tumour Markers",
        "group": "GI & Hepatobiliary",
        "normal_result": (
            "CEA 1.4 ng/mL (normal < 5) — normal. "
            "CA 19-9 12 U/mL (normal < 37) — normal. "
            "No elevation suggesting GI or pancreatic malignancy."
        ),
    },

    # ── Renal & Urological ────────────────────────────────────────────────
    "renal_uss": {
        "label": "Renal Ultrasound",
        "group": "Renal & Urological",
        "normal_result": (
            "Both kidneys normal size and echogenicity (right 11 cm, left 11.2 cm). "
            "No hydronephrosis, no stones, no cysts, no masses. "
            "Normal post-void residual volume."
        ),
    },
    "psa": {
        "label": "PSA (Prostate Specific Antigen)",
        "group": "Renal & Urological",
        "normal_result": (
            "Total PSA 1.2 ng/mL — age-appropriate normal. "
            "Free:Total PSA ratio within acceptable range. "
            "Prostate cancer not indicated by this result alone."
        ),
    },

    # ── Imaging & Radiology ───────────────────────────────────────────────
    "ct_head": {
        "label": "CT Head (Non-contrast)",
        "group": "Imaging & Radiology",
        "normal_result": (
            "No intracranial haemorrhage. No acute infarct. "
            "No space-occupying lesion. No hydrocephalus. "
            "Normal grey-white differentiation and posterior fossa."
        ),
    },
    "mri_brain": {
        "label": "MRI Brain (with contrast)",
        "group": "Imaging & Radiology",
        "normal_result": (
            "No acute ischaemia, haemorrhage, or mass lesion. "
            "No enhancing lesion post-gadolinium. "
            "Normal cortical and subcortical structures. "
            "No demyelination plaques. No meningeal enhancement."
        ),
    },
    "neck_uSS": {
        "label": "Neck / Thyroid Ultrasound",
        "group": "Imaging & Radiology",
        "normal_result": (
            "Thyroid gland normal size and homogeneous echogenicity. "
            "No nodules, cysts, or focal lesions. "
            "No cervical lymphadenopathy. Trachea central."
        ),
    },
    "pelvic_uss": {
        "label": "Pelvic Ultrasound (TV/TA)",
        "group": "Imaging & Radiology",
        "normal_result": (
            "Normal uterus size and morphology. "
            "Endometrial thickness appropriate for cycle phase. "
            "Normal bilateral ovaries. No adnexal mass or free fluid."
        ),
    },
    "mri_pituitary": {
        "label": "MRI Pituitary (with contrast)",
        "group": "Imaging & Radiology",
        "normal_result": (
            "Normal pituitary gland size and morphology. "
            "No microadenoma or macroadenoma. "
            "Normal pituitary stalk and optic chiasm. "
            "Hypothalamic region unremarkable."
        ),
    },
    "leg_doppler": {
        "label": "Bilateral Leg Venous USS / Doppler",
        "group": "Imaging & Radiology",
        "normal_result": (
            "Bilateral legs: compressible veins throughout. "
            "Normal venous flow in femoral, popliteal, and calf veins. "
            "No deep vein thrombosis (DVT) identified in either leg."
        ),
    },
    "bone_dexa": {
        "label": "DEXA Bone Density Scan",
        "group": "Imaging & Radiology",
        "normal_result": (
            "T-score: lumbar spine −0.6, femoral neck −0.4. "
            "Normal bone mineral density for age and sex. "
            "Osteopenia and osteoporosis excluded."
        ),
    },

    # ── Neurology ─────────────────────────────────────────────────────────
    "lumbar_puncture": {
        "label": "Lumbar Puncture (CSF Analysis)",
        "group": "Neurology",
        "normal_result": (
            "Opening pressure 14 cmH₂O (normal). Clear, colourless CSF. "
            "WCC 2 lymphocytes/mm³ (normal < 5). Protein 0.28 g/L (normal). "
            "Glucose 3.9 mmol/L (serum:CSF ratio normal). "
            "No xanthochromia. Culture: no growth."
        ),
    },
    "eeg": {
        "label": "EEG (Electroencephalogram)",
        "group": "Neurology",
        "normal_result": (
            "Normal alpha rhythm (10 Hz) over occipital regions. "
            "Normal beta activity frontally. No epileptiform discharges. "
            "No focal slowing or generalised spike-and-wave complexes."
        ),
    },
    "nerve_conduction": {
        "label": "Nerve Conduction Studies (NCS / EMG)",
        "group": "Neurology",
        "normal_result": (
            "Normal sensory and motor conduction velocities in tested limbs. "
            "No evidence of peripheral neuropathy, radiculopathy, or carpal tunnel syndrome. "
            "EMG: no abnormal spontaneous activity."
        ),
    },

    # ── Rheumatology & Immunology ─────────────────────────────────────────
    "ana": {
        "label": "ANA (Anti-nuclear Antibodies)",
        "group": "Rheumatology & Immunology",
        "normal_result": (
            "ANA: NEGATIVE (titre < 1:40). "
            "Systemic lupus erythematosus (SLE) not supported by this result."
        ),
    },
    "rf_anti_ccp": {
        "label": "Rheumatoid Factor & Anti-CCP",
        "group": "Rheumatology & Immunology",
        "normal_result": (
            "Rheumatoid factor 8 IU/mL (normal < 14) — negative. "
            "Anti-CCP antibodies < 7 U/mL (normal < 17) — negative. "
            "Rheumatoid arthritis not supported serologically."
        ),
    },
    "anca": {
        "label": "ANCA (Antineutrophil Cytoplasmic Abs)",
        "group": "Rheumatology & Immunology",
        "normal_result": (
            "c-ANCA (anti-PR3): negative. p-ANCA (anti-MPO): negative. "
            "No evidence of systemic vasculitis (GPA, MPA)."
        ),
    },

    # ── Gynaecology & Reproductive ────────────────────────────────────────
    "pregnancy_test": {
        "label": "Urine Pregnancy Test (βhCG)",
        "group": "Gynaecology & Reproductive",
        "normal_result": (
            "Urine βhCG: NEGATIVE. "
            "Intrauterine and ectopic pregnancy excluded."
        ),
    },
    "ca125": {
        "label": "CA-125 Tumour Marker",
        "group": "Gynaecology & Reproductive",
        "normal_result": (
            "CA-125 12 U/mL (normal < 35) — within normal range. "
            "Not elevated. Ovarian malignancy or significant endometriosis "
            "not indicated by this result alone."
        ),
    },

    # ── Vascular & Thrombosis ─────────────────────────────────────────────
    "wells_score": {
        "label": "Wells PE Score (Clinical Calculation)",
        "group": "Vascular & Thrombosis",
        "normal_result": (
            "Wells PE Score: 0 points — LOW pre-test probability. "
            "Alternative diagnosis equally or more likely. "
            "Proceed to D-dimer testing before considering CTPA."
        ),
    },
    "abpi": {
        "label": "ABPI (Ankle-Brachial Pressure Index)",
        "group": "Vascular & Thrombosis",
        "normal_result": (
            "ABPI right 1.08, left 1.06 (normal 0.9–1.3). "
            "No peripheral arterial disease. "
            "Arterial insufficiency excluded bilaterally."
        ),
    },

    # ── Clinical Assessment Tools ─────────────────────────────────────────
    "phq9": {
        "label": "PHQ-9 Depression Questionnaire",
        "group": "Clinical Assessment Tools",
        "normal_result": (
            "PHQ-9 score 3 — minimal or no depression. "
            "Patient denies low mood, anhedonia, or suicidal ideation. "
            "Depressive disorder not supported by this screening tool."
        ),
    },
    "4at_delirium": {
        "label": "4AT Delirium Assessment",
        "group": "Clinical Assessment Tools",
        "normal_result": (
            "4AT score 0 — no delirium or cognitive impairment detected. "
            "Alert, fully oriented, and cooperative. "
            "AMTS 10/10. No acute fluctuation reported."
        ),
    },
    "mmse_moca": {
        "label": "MMSE / MoCA (Cognitive Screen)",
        "group": "Clinical Assessment Tools",
        "normal_result": (
            "MoCA 28/30 — within normal range (normal ≥ 26). "
            "No significant cognitive impairment detected. "
            "MMSE 30/30. Normal orientation, memory, and executive function."
        ),
    },

    # ── Added 2026-10-29 for case_8, seeded by migration 029 ─────────
    # The first additions to this list since migration 017. Appended, never
    # inserted: `display_order` is position in this dict, and renumbering the
    # menu would move every chip a learner has learnt the place of.
    "fit": {
        "label": "Faecal Immunochemical Test (FIT)",
        "group": "Stool & GI",
        "normal_result": (
            "Faecal haemoglobin < 10 µg Hb/g faeces (threshold for urgent "
            "referral is 10 in symptomatic patients). Negative."
        ),
    },
    "colonoscopy": {
        "label": "Colonoscopy",
        "group": "Endoscopy",
        "normal_result": (
            "Caecum reached, good bowel preparation. Normal mucosa "
            "throughout the colon and rectum. No polyps, no mass, no "
            "inflammation. Normal examination."
        ),
    },
}


# ══════════════════════════════════════════════════════════════════════
# MASTER EXAMINATIONS — Universal panel shown to students on EVERY case
# ----------------------------------------------------------------------
# Mirrors the MASTER_INVESTIGATIONS approach for physical examination.
# All 5 cases share this identical list of ~28 examination systems so
# students cannot narrow the diagnosis from which systems are available.
#
# Each entry has:
#   label         : chip label shown in the UI
#   group         : section heading (groups chips visually)
#   normal_result : the finding returned when this system is NOT
#                   relevant to the current case — always a normal report.
#
# Per-case FINDING OVERRIDES live in each case's "examination" dict.
# app.py: if exam_key is in case["examination"], return that finding;
#         otherwise return MASTER_EXAMINATIONS[exam_key]["normal_result"].
# clinical_evaluator.py: still grades on case["examination"] only.
# ══════════════════════════════════════════════════════════════════════

MASTER_EXAMINATIONS = {

    # ── General & Vitals ─────────────────────────────────────────────────
    "general": {
        "label": "General Inspection",
        "group": "General & Vitals",
        "normal_result": (
            "Alert and orientated. Well-kempt appearance. No acute distress. "
            "No pallor, jaundice, cyanosis, or clubbing. "
            "No obvious wasting or oedema."
        ),
    },
    "vitals": {
        "label": "Vital Signs (HR · BP · RR · SpO₂ · Temp)",
        "group": "General & Vitals",
        "normal_result": (
            "HR 74 bpm (regular) · BP 122/78 mmHg · RR 14 · "
            "SpO₂ 99% on air · Temp 36.8°C. All within normal range."
        ),
    },
    "hydration": {
        "label": "Hydration & Fluid Status",
        "group": "General & Vitals",
        "normal_result": (
            "Moist oral mucous membranes. Normal skin turgor. "
            "Tongue moist. Urine output adequate. "
            "No clinical signs of dehydration or fluid overload."
        ),
    },
    "weight_bmi": {
        "label": "Weight, Height & BMI",
        "group": "General & Vitals",
        "normal_result": (
            "Weight 68 kg · Height 168 cm · BMI 24.1 kg/m² (normal range). "
            "No significant weight loss or gain on reported history."
        ),
    },

    # ── Head, Neck & ENT ─────────────────────────────────────────────────
    "ent": {
        "label": "Oropharynx & ENT Examination",
        "group": "Head, Neck & ENT",
        "normal_result": (
            "Oropharynx clear. Tonsils normal, no exudate. "
            "Tympanic membranes intact bilaterally. "
            "No nasal polyps. No sinus tenderness on palpation."
        ),
    },
    "neck_thyroid": {
        "label": "Neck & Thyroid Examination",
        "group": "Head, Neck & ENT",
        "normal_result": (
            "No goitre. Thyroid not enlarged or tender. "
            "No cervical lymphadenopathy. Trachea central. "
            "No neck stiffness. JVP not raised."
        ),
    },
    "eyes_fundoscopy": {
        "label": "Eye Examination & Fundoscopy",
        "group": "Head, Neck & ENT",
        "normal_result": (
            "Visual acuity normal. Eye movements full, no nystagmus. "
            "Pupils equal and reactive to light (3 mm → 2 mm). "
            "Fundoscopy: normal optic discs, no papilloedema, "
            "no haemorrhages or exudates. Normal retinal vessels."
        ),
    },
    "lymph_nodes": {
        "label": "Lymph Node Examination",
        "group": "Head, Neck & ENT",
        "normal_result": (
            "No palpable cervical, axillary, or inguinal lymphadenopathy. "
            "No epitrochlear or supraclavicular nodes. "
            "No splenomegaly on abdominal palpation."
        ),
    },

    # ── Cardiovascular ────────────────────────────────────────────────────
    "cardiovascular": {
        "label": "Cardiovascular Examination",
        "group": "Cardiovascular",
        "normal_result": (
            "Heart sounds I + II only, no added sounds or murmurs. "
            "Apex beat non-displaced. JVP not raised. "
            "No peripheral oedema. Peripheral pulses present and equal."
        ),
    },
    "peripheral_pulses": {
        "label": "Peripheral Pulses & Vascular",
        "group": "Cardiovascular",
        "normal_result": (
            "Radial, brachial, femoral, popliteal, dorsalis pedis and "
            "posterior tibial pulses all present and equal bilaterally. "
            "No radio-femoral delay. Capillary refill < 2 s."
        ),
    },
    "postural_bp": {
        "label": "Postural Blood Pressure",
        "group": "Cardiovascular",
        "normal_result": (
            "Supine BP 122/78 mmHg · Standing BP 120/80 mmHg. "
            "No significant postural drop (< 10 mmHg systolic). "
            "No symptoms of orthostatic hypotension."
        ),
    },

    # ── Respiratory ───────────────────────────────────────────────────────
    "respiratory": {
        "label": "Respiratory Examination",
        "group": "Respiratory",
        "normal_result": (
            "Chest expansion equal bilaterally. "
            "Air entry clear throughout, no crackles or wheeze. "
            "Percussion resonant. RR 14, no use of accessory muscles. "
            "Trachea central."
        ),
    },
    "peak_flow_exam": {
        "label": "Peak Flow Measurement (Bedside)",
        "group": "Respiratory",
        "normal_result": (
            "Best of three attempts: 520 L/min (105% of predicted for age and height). "
            "No significant diurnal variability. Technique adequate."
        ),
    },

    # ── Abdominal ─────────────────────────────────────────────────────────
    "abdomen": {
        "label": "Abdominal Examination",
        "group": "Abdominal & GI",
        "normal_result": (
            "Abdomen soft and non-tender throughout. "
            "No organomegaly. Bowel sounds present and normal. "
            "No guarding, rigidity, or peritonism. "
            "No hernia or visible masses."
        ),
    },
    "rectal": {
        "label": "Digital Rectal Examination (DRE)",
        "group": "Abdominal & GI",
        "normal_result": (
            "Normal anal tone. Rectum empty. "
            "No palpable mass or hard stool. "
            "Prostate smooth and non-tender (if male). "
            "No blood on glove."
        ),
    },

    # ── Neurological ──────────────────────────────────────────────────────
    "neuro_focal": {
        "label": "Neurological Examination",
        "group": "Neurological",
        "normal_result": (
            "GCS 15/15. Fully oriented to time, place, and person. "
            "Power 5/5 all four limbs. Face symmetrical. "
            "Speech clear and fluent. No focal neurological deficit. "
            "No meningism (neck supple, Kernig's negative)."
        ),
    },
    "cognitive": {
        "label": "Cognitive & Delirium Assessment (4AT)",
        "group": "Neurological",
        "normal_result": (
            "4AT score 0/12 — no delirium. "
            "Alert, fully oriented. AMTS 10/10. "
            "Attention intact: months of year backwards completed correctly. "
            "No acute fluctuation reported by informant."
        ),
    },
    "cranial_nerves": {
        "label": "Cranial Nerve Examination (I–XII)",
        "group": "Neurological",
        "normal_result": (
            "All 12 cranial nerves intact. Visual fields full to confrontation. "
            "PERLA 3 mm bilaterally. EOMs full, no diplopia. "
            "Facial sensation and movement symmetric. "
            "Hearing normal bilaterally. Palate elevates centrally."
        ),
    },
    "reflexes": {
        "label": "Deep Tendon Reflexes",
        "group": "Neurological",
        "normal_result": (
            "Biceps, triceps, and supinator reflexes 2+ bilaterally. "
            "Knee and ankle jerks 2+ bilaterally. "
            "Plantar responses flexor (downgoing). "
            "No clonus. Normal relaxation phase."
        ),
    },
    "gait": {
        "label": "Gait & Balance Assessment",
        "group": "Neurological",
        "normal_result": (
            "Normal gait pattern. Steady tandem walking. "
            "Romberg's test negative. "
            "No ataxia, festination, or hemiplegic gait. "
            "Able to rise from chair without use of arms."
        ),
    },

    # ── Musculoskeletal & Limbs ───────────────────────────────────────────
    "legs": {
        "label": "Lower Limb Examination",
        "group": "Musculoskeletal & Limbs",
        "normal_result": (
            "Both legs equal calf circumference — no asymmetric swelling. "
            "No erythema, warmth, or tenderness over calves. "
            "Full range of movement at hip, knee, and ankle. "
            "No varicosities or pitting oedema."
        ),
    },
    "hands_nails": {
        "label": "Hands, Nails & Peripheral Signs",
        "group": "Musculoskeletal & Limbs",
        "normal_result": (
            "Hands warm and well-perfused. Normal skin texture. "
            "Nails healthy with no koilonychia, clubbing, or ridging. "
            "No palmar erythema or Dupuytren's contracture. "
            "No peripheral oedema. Tinel's sign negative bilaterally."
        ),
    },
    "spine": {
        "label": "Spine & Back Examination",
        "group": "Musculoskeletal & Limbs",
        "normal_result": (
            "Normal spinal curvature (no scoliosis or kyphosis). "
            "Full range of lumbar and cervical movement. "
            "No vertebral or paraspinal tenderness. "
            "Straight-leg raise negative bilaterally."
        ),
    },
    "joints": {
        "label": "Joint Examination",
        "group": "Musculoskeletal & Limbs",
        "normal_result": (
            "No joint swelling, erythema, warmth, or deformity. "
            "Full range of movement in all examined joints. "
            "No crepitus or bony enlargement. "
            "No tophi, rheumatoid nodules, or psoriatic plaques."
        ),
    },

    # ── Skin & Integument ─────────────────────────────────────────────────
    "skin": {
        "label": "Skin & Dermatological Inspection",
        "group": "Skin & Integument",
        "normal_result": (
            "Skin normal texture, colour, and moisture. "
            "No rash, petechiae, purpura, or jaundice. "
            "No pressure sores. No suspicious lesions. "
            "Hair normal density and texture."
        ),
    },

    # ── Mental State ─────────────────────────────────────────────────────
    "mental_state": {
        "label": "Mental State Examination (MSE)",
        "group": "Mental State",
        "normal_result": (
            "Appearance neat and appropriate. Behaviour cooperative. "
            "Speech normal rate and volume. Mood euthymic (self-reported 'fine'). "
            "Affect normal and reactive. No thought disorder. "
            "No delusions or perceptual disturbance. Insight intact."
        ),
    },
    "mood_screen": {
        "label": "Mood & Affect Screen (PHQ-2 / GAD-2)",
        "group": "Mental State",
        "normal_result": (
            "PHQ-2 score 0 — no significant low mood or anhedonia reported. "
            "GAD-2 score 0 — no significant anxiety. "
            "Patient denies passive suicidal ideation. "
            "Normal mood confirmed on brief screen."
        ),
    },
}


# Stable, human-readable identifiers. `cases.slug` is UNIQUE in the database and
# is what a URL and the admin console use, so "case_1" would be a poor permanent
# identifier (DATA_MODEL §5.1).
#
# This map lived in scripts/generate_case_migration.py until T-013 needed it at
# runtime, to resolve a consultation to the `case_versions` row it belongs to.
# Copying it would have been two sources that drift silently; the generator now
# imports it from here, and tests/db/test_seed.py asserts these are exactly the
# slugs migration 019 seeded.
CASE_SLUGS: dict[str, str] = {
    "case_1": "chest-pain-gerd",
    "case_2": "breathlessness-pulmonary-embolism",
    "case_3": "confusion-delirium-uti",
    "case_4": "fatigue-hypothyroidism",
    "case_5": "vomiting-diabetic-ketoacidosis",
    "case_6": "headache-hypertension",
    "case_7": "wheezing-child-asthma",
    "case_8": "rectal-bleeding-colorectal-cancer",
    "case_10": "syncope-aortic-stenosis",
}


def get_case(case_id: str) -> Case | None:
    """
    Returns a single case config dict by ID.

    Args:
        case_id (str): e.g. "case_1"

    Returns:
        dict: Full case config, or None if case_id not found.
    """
    return CASES.get(case_id)


def get_all_cases() -> list[CaseSummary]:
    """
    Returns a lightweight list of all cases for the selection screen.
    Only includes id, title, and intro — not the full config.

    Returns:
        list: [{"id": ..., "title": ..., "intro": ...}, ...]
    """
    return [
        {
            "id": case_id,
            "title": str(data["title"]),
            "intro": str(data["patient_intro"]),
        }
        for case_id, data in CASES.items()
    ]
