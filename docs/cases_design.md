# Clinical Cases Design Document
# Project: Bias-Aware Virtual Patient Simulator
# Student: Roll No. 202301408 | DA-IICT
# Mentor: Abhishek Gupta
# Last updated: October 29, 2026
# Status: LIVING DOCUMENT — update this file before changing cases.py

---

## DOCUMENT PURPOSE

This file is the single source of truth for the clinical cases.
Every field in this file maps directly to a field in cases.py.
Never change cases.py without first updating this file.
The Case Update Log at the bottom tracks every change and why.

## NUMBERING — read this before matching a case to code

The numbers here are DESIGN numbers from May 2026 and they are NOT the
ids in cases.py. Two of the five cases designed here were not built in
the first pass; cases.py filled 2 and 5 with other presentations and the
designs waited. They were implemented on 29 October 2026 at the far end
of the list:

  Design CASE 1  The Chest Pain Trap          -> cases.py case_1
  Design CASE 2  The Headache That Is Not Stress -> cases.py case_6
  Design CASE 3  The Confused Elderly Man      -> cases.py case_3
  Design CASE 4  The Tired Teacher             -> cases.py case_4
  Design CASE 5  The Wheezing Child            -> cases.py case_7
  Design CASE 6  The Faint That Was Not a Faint -> cases.py case_10

  (cases.py case_2 is pulmonary embolism and case_5 is diabetic
   ketoacidosis. Neither was designed here; both were written directly
   into cases.py during the pilot build. cases.py has no case_8 or
   case_9 yet: those ids are reserved for the two cases still to be
   written, so the number names the content and not the order it was
   authored.)

The one piece of hard evidence that these designs were always meant to
be built: every topic key and every detection keyword listed under
CASE 2 and CASE 5 below is already present in TOPIC_KEYWORDS, seeded by
migration 017, and was used by no case at all until 29 October.

## AUDIENCE — this document predates the change

Every "Anchor Test" section below is written from a CS STUDENT's
perspective, because in May 2026 the evaluators were CS students. The
product's audience is now clinical-phase medical students in years 3-5
(PRD D-1, settled September 2026). The anchor traps survive the change,
but the Anchor Test sections should be read as historical.

## WHAT THIS DOCUMENT DOES NOT COVER

It predates the examination and investigation layer entirely. There is
no section here for exam findings or test results; those live in
CLINICAL_DATA in cases.py and were authored there. Anything this file
does specify still governs.

---

## DESIGN PRINCIPLES

Every case must satisfy all 4 of these:
1. One strong anchor trap — a salient symptom that triggers the
   wrong System 1 pattern recognition in a non-medical user
2. A non-obvious correct diagnosis reachable through thorough
   history-taking by a CS student with no medical background
3. At least 6 specific contradictory clues that rule out the anchor
   — only revealed when the user directly asks the right question
4. A minimum of 7 required history topics that a thorough workup
   must cover — missing more than 40% triggers premature closure

---

## HOW THIS FILE MAPS TO CODE

patient_persona        → opening text shown on chat.html
system_prompt          → system_instruction in app.py Gemini call
correct_diagnosis      → stored in case config, never shown to user
anchor_keywords        → list in bias_detector.py detect_anchoring()
alternative_topics     → list in bias_detector.py detect_anchoring()
required_topics        → list in session_tracker.py TOPIC_KEYWORDS
minimum_questions      → integer in bias_detector.py detect_premature_closure()
contradictory_clues    → list in bias_detector.py detect_confirmation_bias()
patient_voice_notes    → basis for writing system_prompt on Day 5

---
---

## CASE 1: The Chest Pain Trap

### Status: Design complete — verified Day 2

---

### Patient Persona
Name: Ramesh Kumar
Age / Gender: 48-year-old male
Occupation: Senior accountant at a private firm
Presenting complaint: Chest pain for the past 3 days

Opening line shown to user on chat screen:
"A 48-year-old male accountant named Ramesh Kumar visits the
clinic complaining of chest pain that has been present for the
past 3 days. He appears mildly anxious but is not in acute distress."

---

### Correct Diagnosis
GERD — Gastroesophageal Reflux Disease
Specifically: NSAID-induced GERD
(Daily ibuprofen for back pain + coffee habit + spicy food
= classic GERD trigger combination)

Why this works as a case: GERD presenting as chest pain in a
middle-aged male is one of the most common causes of unnecessary
cardiac workups in real clinical practice. The presentation is
deliberately designed to mimic early cardiac symptoms on the surface.

---

### Anchor Trap
Chest pain in a middle-aged male is the single strongest heuristic
trigger for myocardial infarction in both trained and untrained
populations. This is not an obscure medical fact — most people
know "chest pain + middle-aged man = possible heart attack" from
public health campaigns, movies, and general awareness. Almost
every user will anchor on cardiac disease immediately.

---

### Anchor Keywords
(These go directly into bias_detector.py as the anchor_keywords list)

heart, cardiac, MI, myocardial, infarction, angina, ECG, EKG,
electrocardiogram, troponin, cholesterol, coronary, arteries,
palpitation, heart attack, stent, bypass, cardiologist, cardiac
enzyme, stress test, blood pressure, hypertension, arrhythmia,
tachycardia, bradycardia, pulse, irregular heartbeat, chest tightness

---

### Alternative Topics Keywords
(These go into bias_detector.py — indicate correct GI exploration)

reflux, gastro, GI, gastrointestinal, stomach, oesophagus, esophagus,
food, meal, eating, diet, spicy, ibuprofen, NSAID, anti-inflammatory,
painkiller, acid, antacid, heartburn, burning, after eating,
lying down, coffee, alcohol, digestive, indigestion, bloating,
regurgitation, throat, swallowing

---

### Required Topics
(These map to TOPIC_KEYWORDS in session_tracker.py)
User must cover at least 5 of these 8 to avoid premature closure flag.

1. pain_character
   What does the pain feel like — burning, crushing, sharp, dull
   Detection keywords: burning, crushing, sharp, dull, aching,
   character, describe, feel like, what kind, pressure, tight

2. meal_relationship
   Is the pain related to eating or food
   Detection keywords: meal, food, eating, after eating, diet,
   drink, spicy, coffee, fasting, empty stomach, before eating

3. radiation
   Does the pain spread anywhere
   Detection keywords: radiate, spread, arm, jaw, shoulder, neck,
   back, anywhere else, go to, move to

4. associated_symptoms
   Any other symptoms alongside the pain
   Detection keywords: breathless, nausea, sweat, dizzy, fever,
   vomit, other symptoms, anything else, weakness, fatigue

5. medications
   What medicines is the patient currently taking
   Detection keywords: medication, medicine, drug, tablet, pill,
   taking, prescribed, supplements, painkillers, regular

6. family_history
   Any relevant family history
   Detection keywords: family, father, mother, parent, sibling,
   hereditary, runs in family, relative, grandfather, grandmother

7. duration_pattern
   Exactly when did it start, is it constant or intermittent
   Detection keywords: how long, when did, since when, started,
   days, weeks, months, constant, comes and goes, pattern

8. relieving_factors
   What makes the pain better or worse
   Detection keywords: better, worse, relief, helps, aggravate,
   trigger, lying down, sitting up, activity, rest, position

---

### Minimum Questions Before Concluding: 7

---

### Contradictory Clues
(Reveal ONLY when directly asked — these go into bias_detector.py)

1. Pain character is BURNING, not crushing or squeezing
   (Burning = GI, Crushing = cardiac — this is the clearest differentiator)

2. Pain is WORSE AFTER MEALS, especially spicy food and coffee
   (Cardiac pain is not related to eating — meal worsening = GERD)

3. Patient takes IBUPROFEN 400mg EVERY DAY for chronic back pain
   (Daily NSAIDs are a direct pharmacological cause of GERD —
   this is the most important clue in the case. Only revealed if
   user asks about medications.)

4. Pain does NOT radiate to arm or jaw at all
   (Arm/jaw radiation is a hallmark of cardiac ischaemia —
   absence of radiation significantly lowers cardiac probability)

5. NO shortness of breath, sweating, or nausea
   (These autonomic symptoms typically accompany acute cardiac events —
   their absence makes cardiac cause less likely)

6. Sitting upright helps slightly / lying down makes it worse
   (Postural worsening is classic GERD — acid reflux worsens
   when lying flat due to gravity)

7. Tried antacids once and they helped
   (Response to antacids is diagnostic of acid-related disease —
   antacids do not help cardiac pain)

8. Father had TYPE 2 DIABETES, no family history of heart attacks
   (Absence of family cardiac history reduces cardiac risk —
   only revealed if user asks about family history)

---

### Bias Detection Summary for This Case

Anchoring fires if:
- User asks 3+ questions containing anchor_keywords
- AND user asked 0 questions containing alternative_topics keywords
- Score = (anchor_keyword_question_count / total_questions)

Premature closure fires if:
- User submits diagnosis after fewer than 7 questions
- OR user covered fewer than 5 of 8 required_topics before concluding
- Score = 1 - (questions_asked / minimum_questions) for rule 1
- Score = 1 - (topics_covered / total_required) for rule 2

Confirmation bias fires if:
- User diagnosed cardiac cause
- AND user never asked about ANY of the 8 contradictory clues above
- Score = 0.9 (strong signal)

---

### Patient Voice Notes
(Use these directly when writing the Gemini system prompt on Day 5)

Q: "What brings you in today?"
A: "I have been having this pain in my chest for about 3 days now.
    It started after a work dinner and has not really gone away.
    I am a bit worried about it."

Q: "Can you describe what the pain feels like?"
A: "It is more of a burning feeling, right in the middle of my chest.
    Sometimes I feel it up in my throat as well."

Q: "Does the pain go anywhere — like your arm or jaw?"
A: "No, it is just in my chest and throat area. Nothing goes to
    my arm or jaw."

Q: "Are you on any regular medications?"
A: "Yes, I take ibuprofen every day for my back. I have had
    chronic lower back pain for a few years now and ibuprofen
    is the only thing that helps."

Q: "Does eating affect the pain at all?"
A: "Yes, actually — it is definitely worse after meals, especially
    if I eat spicy food. And coffee seems to make it worse too.
    I drink two or three coffees a day."

Q: "Do you have any shortness of breath, sweating, or nausea?"
A: "No, none of that. Just the burning in my chest."

Q: "Any family history of heart problems?"
A: "My father had diabetes but no heart attacks. My mother is
    fine. I do not think anyone in my family had heart problems."

Q: "What makes it better or worse?"
A: "Sitting upright helps a little bit. I tried an antacid once
    out of curiosity and it helped for a while. Lying down after
    eating is the worst."

Q: "How bad is the pain on a scale of 1 to 10?"
A: "Maybe a 4 or 5. It is uncomfortable but I can manage. It is
    not unbearable."

Q: "Have you had this before?"
A: "Not exactly like this. Sometimes after spicy food I get a
    bit of burning but it always went away quickly. This one
    has been going on for 3 days."

---

### Anchor Test — CS Student Perspective

Imagined first 5 questions from a CS student seeing this case:
1. "Does the pain go to your arm?" — ANCHOR (cardiac)
2. "Do you have shortness of breath?" — ANCHOR (cardiac)
3. "Any family history of heart disease?" — ANCHOR (cardiac)
4. "How bad is the pain out of 10?" — NEUTRAL
5. "Have you had this before?" — NEUTRAL

Result: 3 of 5 natural first questions are cardiac-focused.
Anchor trap is working. PASS.

---
---

## CASE 2: The Headache That Is Not Stress

### Status: IMPLEMENTED 29 Oct 2026 as cases.py `case_6`,
### slug `headache-hypertension`, seeded as draft by migration 026.
### Three divergences, all recorded in the Case Update Log.

---

### Patient Persona
Name: Priya Sharma
Age / Gender: 28-year-old female
Occupation: Software engineer at a tech startup
Presenting complaint: Recurring headaches for the past 2 weeks

Opening line shown to user on chat screen:
"A 28-year-old female software engineer named Priya Sharma visits
the clinic. She has been getting headaches almost every day for
the past 2 weeks and is finding it difficult to concentrate at work."

---

### Correct Diagnosis
Early-stage hypertension presenting with headaches
(Newly elevated blood pressure — not yet diagnosed)

Why this works as a case: Young professional woman with headaches
is almost universally attributed to stress, screen time, or tension
by non-medical people. The question about blood pressure is one
most people simply do not think to ask unless they are medically
trained, making this a reliable anchoring scenario.

---

### Anchor Trap
Young woman + stressful tech job + headaches = tension headache
or stress headache. This is an overwhelmingly common assumption.
People also commonly suggest migraine for young women with headaches.
Almost no one without medical training immediately thinks about blood
pressure when they see this presentation.

---

### Anchor Keywords
(bias_detector.py anchor_keywords list)

stress, tension, anxiety, work pressure, overwork, migraine,
painkiller, ibuprofen for headache, relax, sleep, rest, screen time,
posture, massage, stress relief, mental health, burnout, tired,
exhausted, caffeine headache, dehydration headache, eye strain,
glasses, vision for screens, work life balance, meditation, yoga

---

### Alternative Topics Keywords
(bias_detector.py — indicate correct hypertension exploration)

blood pressure, BP, hypertension, dizziness, vision, blurry vision,
spots, floaters, family history BP, family history stroke, heart,
kidney, morning headache, throbbing, pulsating, measurement,
monitor, check pressure, pounding, back of head, neck stiffness

---

### Required Topics
(session_tracker.py TOPIC_KEYWORDS — user must cover 5 of 8)

1. headache_character
   Throbbing, pressure, band-like, one side or both sides, location
   Detection keywords: throbbing, pressure, tight, band, one side,
   both sides, where, location, describe, pulsating, pounding

2. timing_pattern
   When does it happen, morning vs evening, how long it lasts
   Detection keywords: morning, night, evening, after, before,
   always, sometimes, pattern, when, how long, duration

3. visual_symptoms
   Any changes in vision during or before headache
   Detection keywords: vision, blurry, blur, spots, floaters,
   see, eyes, visual, aura, light, sensitivity to light

4. family_history
   Any family history of high blood pressure, stroke, or heart disease
   Detection keywords: family, father, mother, parent, sibling,
   hereditary, relative, runs in family, high blood pressure,
   stroke, heart attack

5. BP_awareness
   Has she ever had blood pressure checked or been told it is high
   Detection keywords: blood pressure, BP, checked, measured,
   monitor, high pressure, reading, hypertension

6. medications
   Any pills, supplements, or contraceptive medication
   Detection keywords: medication, medicine, pill, tablet, taking,
   prescribed, supplements, contraceptive, birth control

7. lifestyle
   Sleep quality, diet, hydration, caffeine, alcohol
   Detection keywords: sleep, diet, water, hydration, caffeine,
   coffee, alcohol, exercise, routine, lifestyle

8. stress_assessment
   Specific recent stressors or life events — not just assumption
   Detection keywords: stress, pressure, deadline, event, recently,
   changed, happened, difficult, problem, worry, anxious

---

### Minimum Questions Before Concluding: 7

---

### Contradictory Clues
(reveal only when directly asked)

1. Headaches are WORST IN THE MORNING, shortly after waking up
   (Tension headaches typically worsen as the day progresses —
   morning headaches on waking are a classic hypertension symptom)

2. She has had EPISODES OF BLURRY VISION during the headaches
   (Blurry vision with headache is a red flag for elevated BP —
   not typical of tension headache or migraine without aura)

3. Her MOTHER takes medication for high blood pressure
   (Direct family history of hypertension is a significant risk
   factor — only revealed if user asks about family history)

4. No specific stress event triggered the headaches
   (They appeared gradually without any identifiable stressor —
   if stress were the cause, there would usually be a trigger)

5. Headache is THROBBING AND POUNDING in character
   (Throbbing = vascular, consistent with hypertension.
   Band-like = tension headache. Pulsating = migraine)

6. Pain is at the BACK OF THE HEAD AND NECK
   (Posterior headaches are more typical of hypertension.
   Tension headaches are usually frontal or temporal band-like.)

7. No neck stiffness, no fever, no photophobia
   (Rules out meningitis and migraine with photophobia easily)

8. She has NEVER had her blood pressure checked as an adult
   (Many young people have never had BP measured — undiagnosed
   hypertension is very common in the 25–35 age group)

---

### Bias Detection Summary for This Case

Anchoring fires if:
- User asks 3+ questions containing stress/tension/migraine keywords
- AND user never asks about blood pressure or family cardiac history

Premature closure fires if:
- User concludes "stress headache" or "tension headache" or "migraine"
  after fewer than 7 questions OR covering fewer than 5 topics

Confirmation bias fires if:
- User recommends rest/stress management/painkillers
- AND never asked about BP, visual symptoms, or morning timing

---

### Patient Voice Notes

Q: "What seems to be the problem today?"
A: "I have been getting these headaches almost every day for about
    two weeks. I cannot seem to shake them. It is affecting my
    work and I cannot concentrate properly."

Q: "Where exactly is the headache and what does it feel like?"
A: "It is mainly at the back of my head, towards the neck area.
    It is a throbbing, pounding kind of pain. Not like a band
    around my head — more like pounding from inside."

Q: "When during the day do they happen?"
A: "They are worst in the morning, actually. I wake up and the
    headache is already there. It eases off a bit during the day
    but then comes back."

Q: "Do you get any vision changes with the headaches?"
A: "Actually yes — sometimes things go a bit blurry during the
    headache. Not always, but a few times it happened."

Q: "Any family history of high blood pressure?"
A: "Yes — my mother has high blood pressure. She has been on
    tablets for it for years. I do not know about my father."

Q: "Have you ever had your blood pressure checked?"
A: "Not since school honestly. I have never really needed to."

Q: "Would you say you are under a lot of stress at work?"
A: "Work is quite busy but it is always busy. Nothing particularly
    new or different has happened recently. I cannot point to
    anything that changed when the headaches started."

Q: "How is your sleep?"
A: "Sleep is fine actually, about 7 hours most nights. I do not
    think it is a sleep issue."

---

### Anchor Test — CS Student Perspective

Imagined first 5 questions from a CS student:
1. "Are you stressed at work?" — ANCHOR (stress)
2. "How is your sleep?" — ANCHOR (lifestyle/stress)
3. "Are you staring at screens all day?" — ANCHOR (stress/screen)
4. "Have you tried taking a painkiller?" — ANCHOR (stress)
5. "Are you drinking enough water?" — NEUTRAL/ANCHOR (dehydration)

Result: 4 of 5 natural first questions are stress/lifestyle focused.
Nobody asks about blood pressure. Anchor trap is strong. PASS.

---
---

## CASE 3: The Confused Elderly Man

### Status: Design complete — verified Day 2

---

### Patient Persona
Name: Gopal Mehta (brought in by his daughter Anita)
Age / Gender: 74-year-old male
Occupation: Retired school teacher
Presenting complaint: "My father has been confused since yesterday"
Note: The daughter is the main historian. The patient can speak but
gives vague answers. The chatbot plays BOTH the patient (Gopal) AND
the daughter (Anita) — the user can direct questions to either.

Opening line shown to user on chat screen:
"A 74-year-old retired school teacher named Gopal Mehta is brought
to the clinic by his daughter Anita. She says he has been confused
and acting differently since yesterday. He is with her and can
speak but is not his usual self."

---

### Correct Diagnosis
Urinary Tract Infection (UTI) causing acute confusional state
(Delirium secondary to UTI — extremely common in elderly patients
and one of the most frequently missed diagnoses in geriatrics)

Why this works: Acute confusion in elderly patients is one of the
most dangerous anchoring scenarios in real medicine. The immediate
assumption is almost universally neurological — stroke or dementia.
This case is responsible for significant real-world patient harm
and is directly relevant to the clinical safety argument in your
Introduction.

---

### Anchor Trap
Elderly man + sudden confusion = stroke or dementia.
This is perhaps the strongest and most clinically dangerous
anchor trap in all of medicine. Even trained clinicians fall for
this — Greengrass (2026) specifically cites acute confusion in
elderly as a high-risk premature closure scenario. For a CS student
with no medical training, the leap to "brain problem" is immediate
and almost certain.

---

### Anchor Keywords
(bias_detector.py anchor_keywords list)

dementia, Alzheimer, stroke, brain, CT scan, neurologist, TIA,
mini-stroke, memory loss, age, senile, brain scan, MRI head,
psychiatric, mental decline, cognitive, confusion brain, neuro,
neurological, brain bleed, haemorrhage, blood clot, brain tumor,
transient, focal, weakness one side, face droop, speech problem

---

### Alternative Topics Keywords
(bias_detector.py — correct UTI exploration)

urine, urinary, pee, frequency, burning urine, colour of urine,
smell of urine, fever, temperature, infection, UTI, antibiotic,
catheter, waterworks, toilet, passing water, painful urination,
incontinence, cloudy urine, strong smell, going more often

---

### Required Topics
(session_tracker.py — user must cover 5 of 8)

1. onset_timing
   Exactly when did confusion start — hours, days, sudden vs gradual
   Detection keywords: when, how long, started, sudden, gradual,
   yesterday, this morning, last week, always, recent

2. baseline_cognition
   What was he like last week — is this different from normal
   Detection keywords: normal, usual, before, last week, always
   like this, change, different, baseline, normally, was he

3. fever
   Any fever, chills, or temperature elevation
   Detection keywords: fever, temperature, hot, chills, sweating,
   warm, cold, shivering, unwell, sick

4. urinary_symptoms
   Any changes in urination — frequency, pain, colour, smell
   Detection keywords: urinate, urine, pee, toilet, frequency,
   burning, colour, smell, waterworks, going more, less

5. medications
   What regular medications does he take
   Detection keywords: medication, medicine, pill, tablet, taking,
   prescribed, regular, daily, drug

6. recent_illness
   Any recent illness, fall, hospital visit, or change in health
   Detection keywords: recently, fell, hospital, unwell, sick,
   illness, injury, change, last few days

7. focal_neuro_signs
   Any one-sided weakness, facial droop, speech change
   Detection keywords: weakness, arm, leg, face, drooping, speech,
   slurred, one side, movement, paralysis, can he move

8. hydration
   Has he been eating and drinking normally
   Detection keywords: eating, drinking, water, food, appetite,
   fluids, dehydrated, thirsty, hungry

---

### Minimum Questions Before Concluding: 8

---

### Contradictory Clues
(reveal only when directly asked)

1. Confusion started SUDDENLY — just since yesterday afternoon
   (Dementia is gradual over months or years — sudden overnight
   onset is not dementia. This is the most important single clue.)

2. He was COMPLETELY NORMAL 3 days ago — sharp, reading newspaper
   (The daughter can confirm he was his usual self very recently —
   acute onset rules out progressive neurological decline)

3. He has a LOW-GRADE FEVER of 37.8°C
   (Infections cause fever — stroke and dementia do not)

4. He has been going to the TOILET MORE FREQUENTLY than usual
   (Urinary frequency is a hallmark UTI symptom — daughter noticed
   this but did not connect it to the confusion)

5. He mentioned it was UNCOMFORTABLE when urinating
   (Dysuria = painful urination = classic UTI symptom —
   only revealed if user asks specifically about urination)

6. NO FOCAL NEUROLOGICAL SIGNS — no arm weakness, no face droop,
   no slurred speech, both sides move equally
   (Absence of focal signs makes stroke significantly less likely)

7. NO HEADACHE, no neck stiffness
   (Rules out meningitis and subarachnoid haemorrhage)

8. He has NOT been drinking much water for the past 2 days
   (Dehydration both concentrates urine worsening UTI and
   independently causes confusion in elderly — compound effect)

---

### Bias Detection Summary for This Case

Anchoring fires if:
- User asks 3+ questions about neurological symptoms (CT, stroke,
  weakness, face, speech) without asking about fever or urine

Premature closure fires if:
- User concludes neurological cause after fewer than 8 questions
  or without covering urinary symptoms and fever topics

Confirmation bias fires if:
- User recommends CT head or neurology referral
- AND never asked about urinary symptoms, fever, or hydration

---

### Patient Voice Notes

(Playing GOPAL — confused, vague, answers briefly)
Q: "How are you feeling, sir?"
A: "I am... not feeling very well. A bit confused. I cannot
    think properly today." (vague, slow)

Q: "Can you tell me where you are?"
A: "I am... at the clinic. Anita brought me." (oriented to place)

(Playing ANITA — daughter, concerned, more informative)
Q: "When did this start?"
A: "Yesterday afternoon. He was fine in the morning —
    he was reading his newspaper as usual. By evening
    he was not making sense. This is very unlike him."

Q: "Was he like this last week?"
A: "Absolutely not. He was completely normal 3 days ago.
    Sharp as anything. This came on very suddenly."

Q: "Does he have a fever?"
A: "Yes, I checked — 37.8. Slightly elevated. He has been
    feeling warm since last night."

Q: "Any changes in urination?"
A: "Now that you mention it — yes, he has been going to the
    toilet more often. And he said it was uncomfortable.
    I did not think to connect that."

Q: "Any weakness in arms or legs, facial drooping?"
A: "No — both his arms and legs move fine. His face looks
    normal. His speech is slow but not slurred."

Q: "Has he been drinking water normally?"
A: "No, actually. The past 2 days he has barely touched
    his water. He said he is not thirsty."

---

### Anchor Test — CS Student Perspective

Imagined first 5 questions from a CS student:
1. "Did he hit his head recently?" — ANCHOR (brain injury)
2. "Does he have dementia?" — ANCHOR (neurological)
3. "Could it be a stroke?" — ANCHOR (neurological)
4. "Is he on any brain medications?" — ANCHOR (neurological)
5. "Can he recognize you?" — NEUTRAL/ANCHOR (cognitive)

Result: 4 of 5 questions are neurological. Nobody asks about
urine or fever. Anchor trap is very strong. PASS.

---
---

## CASE 4: The Tired Teacher

### Status: Design complete — verified Day 2

---

### Patient Persona
Name: Meera Patel
Age / Gender: 35-year-old female
Occupation: Primary school teacher (Year 3 class)
Presenting complaint: Persistent tiredness and unexplained weight
gain for the past 3 months

Opening line shown to user on chat screen:
"A 35-year-old primary school teacher named Meera Patel visits
the clinic. She has been feeling very tired for the past 3 months
and has noticed she is putting on weight despite no change in her
eating habits. She is concerned and wants to find out what is wrong."

---

### Correct Diagnosis
Hypothyroidism (underactive thyroid gland)
Specifically: Primary hypothyroidism — likely autoimmune
(Hashimoto's thyroiditis is the most common cause in women
aged 30–50)

Why this works: Fatigue + weight gain in a young to middle-aged
woman is one of the most over-attributed presentations for
depression, stress, and "lifestyle issues" in primary care.
Hypothyroidism is frequently missed and delayed because the symptoms
are so easily explained away. The NICE guidelines in the UK
specifically flag this as a common diagnostic error.

---

### Anchor Trap
Young woman + tiredness + weight gain + stressful job (teaching)
= depression, burnout, or lifestyle issues. This is an incredibly
strong anchor because it is socially and culturally reinforced —
society expects young female teachers to be tired and stressed.
Almost everyone will go to the mental health or lifestyle pathway.

---

### Anchor Keywords
(bias_detector.py anchor_keywords list)

depression, anxiety, stress, mental health, counselling, therapy,
mood, sadness, emotional, sleep hygiene, exercise, diet, calories,
weight loss program, lifestyle, burnout, motivation, psychiatrist,
psychologist, CBT, antidepressant, sad, hopeless, helpless,
work stress, teacher stress, emotional eating, binge eating,
gym, workout, physical activity

---

### Alternative Topics Keywords
(bias_detector.py — correct thyroid exploration)

thyroid, cold, temperature, hair, constipation, skin, dry skin,
slow, bowel, period, menstrual, family thyroid, metabolism,
swelling neck, hoarse voice, goitre, T4, TSH, hormone, thyroid
test, always cold, intolerant to cold, brittle nails, puffy face,
hair loss, thinning hair, weight gain despite eating less

---

### Required Topics
(session_tracker.py — user must cover 5 of 8)

1. mood_vs_physical
   Is she sad and hopeless or physically slow — key differentiator
   Detection keywords: mood, sad, hopeless, happy, emotional,
   how do you feel emotionally, crying, enjoying things, interests,
   depression, anxious, worried, mentally

2. weight_change_pattern
   Is the weight gain happening despite normal or reduced eating
   Detection keywords: eating, food, appetite, diet, more, less,
   same, calories, changed eating, portion, hungry

3. temperature_tolerance
   Does she feel cold when others around her are comfortable
   Detection keywords: cold, temperature, always cold, chilly,
   layers, warm, heating, hot, intolerant, feel cold

4. bowel_habits
   Any change in bowel frequency or character
   Detection keywords: bowel, constipated, constipation, toilet,
   frequency, going less, difficulty, hard, sluggish

5. hair_skin_changes
   Hair falling out more than usual, dry skin, brittle nails
   Detection keywords: hair, falling out, hair loss, skin, dry,
   brittle, nails, rough, texture, changed

6. family_thyroid_history
   Anyone in the family with thyroid condition
   Detection keywords: family, thyroid, mother, father, sister,
   relative, runs in family, thyroid condition, underactive,
   overactive, levothyroxine

7. menstrual_changes
   Any change to period — heavier, irregular, missed
   Detection keywords: period, menstrual, cycle, regular, heavy,
   irregular, missed, monthly, flow, spotting

8. energy_time_pattern
   Is she tired at a specific time or all day — also any improvement
   Detection keywords: morning, afternoon, all day, worse when,
   better when, energy level, when tired, time of day

---

### Minimum Questions Before Concluding: 8

---

### Contradictory Clues
(reveal only when directly asked)

1. Weight is going UP despite eating LESS than before
   (Unexplained weight gain despite reduced food intake =
   metabolic slowing — this rules out overeating as the cause
   and is a hallmark of hypothyroidism)

2. She is ALWAYS COLD — wears an extra layer when colleagues
   are comfortable, even in summer
   (Cold intolerance is a hallmark symptom of hypothyroidism —
   the thyroid regulates metabolic rate and body temperature)

3. Her HAIR IS FALLING OUT more than usual — she notices it
   on her brush and in the shower drain
   (Diffuse hair loss is a classic hypothyroidism symptom)

4. She has been CONSTIPATED for the past 2 months — a change
   from her normal bowel habits
   (Slowed gut motility = hypothyroidism. Depression does not
   specifically cause constipation in this pattern.)

5. Her MOOD IS FINE — she is not sad, not hopeless, still
   enjoying things, no loss of interest in activities
   (This specifically rules out primary depression as the
   cause — hypothyroidism causes physical slowing, not the
   classic psychological features of depression)

6. Her MOTHER has a thyroid condition and takes levothyroxine
   (Hashimoto's has a strong genetic component — family
   thyroid history is a major risk factor, especially in women)

7. Her THINKING FEELS SLOW — she has to read things twice
   and has been making small errors at work
   (Cognitive slowing is a physical symptom of thyroid deficiency —
   again NOT the same as the cognitive symptoms of depression)

8. Her PERIODS have become HEAVIER over the past 2 months
   (Heavy periods are a specific gynaecological sign of
   hypothyroidism — oestrogen clearance is affected)

---

### Bias Detection Summary for This Case

Anchoring fires if:
- User asks 3+ questions about mood, stress, sleep, or lifestyle
- AND user never asks about temperature, hair, bowel, or thyroid

Premature closure fires if:
- User concludes depression or burnout after fewer than 8 questions
  or without covering at least physical symptom topics

Confirmation bias fires if:
- User recommends counselling, therapy, or antidepressants
- AND never asked about cold intolerance, hair loss, or family
  thyroid history — the 3 most specific hypothyroid indicators

---

### Patient Voice Notes

Q: "What is the main thing bothering you today?"
A: "I have been so tired for about 3 months. I sleep fine but
    I wake up exhausted. And I have been putting on weight even
    though I am not eating more — if anything I am eating less."

Q: "How is your mood — are you feeling down or depressed?"
A: "No, actually my mood is fine. I still enjoy things, I am
    happy at work with my children. I am not sad or hopeless.
    Just physically exhausted and slow."

Q: "Do you feel cold a lot?"
A: "Yes — I am always cold. My colleagues complain the office
    is too warm and I am sitting there in a cardigan. Even
    in summer I need layers. My husband notices it too."

Q: "Has your hair changed at all?"
A: "Actually yes — I have been losing more hair than usual.
    My brush is full of it and I see it in the shower drain.
    I thought it was just stress."

Q: "Any changes with your bowel habits?"
A: "I have been a bit constipated actually. That is new for me.
    I normally have no issues but for the past 2 months it has
    been quite slow."

Q: "Does anyone in your family have a thyroid condition?"
A: "My mother — yes. She takes levothyroxine for an underactive
    thyroid. Has done for years."

Q: "Has your period changed at all?"
A: "Yes, they have become heavier recently. Much heavier than
    they used to be."

Q: "How do you feel mentally — is your thinking clear?"
A: "That is the thing — I feel mentally slow. I have to read
    things twice. I made a few silly mistakes at work which is
    not like me. But I am not depressed — I just feel like
    everything is running in slow motion."

---

### Anchor Test — CS Student Perspective

Imagined first 5 questions from a CS student:
1. "Are you stressed at work?" — ANCHOR (stress/depression)
2. "How is your sleep?" — ANCHOR (lifestyle)
3. "Are you eating more than usual?" — ANCHOR (lifestyle)
4. "Do you feel depressed?" — ANCHOR (mental health)
5. "Are you exercising?" — ANCHOR (lifestyle)

Result: 5 of 5 natural first questions are stress/depression/
lifestyle focused. Nobody asks about thyroid. Anchor trap is
extremely strong. PASS.

---
---

## CASE 5: The Wheezing Child

### Status: IMPLEMENTED 29 Oct 2026 as cases.py `case_7`,
### slug `wheezing-child-asthma`, seeded as draft by migration 026.
### Four divergences, all recorded in the Case Update Log.

---

### Patient Persona
Name: Arjun Shah (brought in by his mother Sunita)
Age / Gender: 10-year-old male
Occupation: Year 5 student
Presenting complaint: "My son has had a cough and wheezing
for the past few days"
Note: Mother is the primary historian. Arjun is present and
can answer direct questions to him. The chatbot plays both
Arjun AND Sunita depending on who the user addresses.

Opening line shown to user on chat screen:
"Sunita brings her 10-year-old son Arjun to the clinic.
She says he has had a cough and a wheezing sound in his chest
for the past few days. Arjun is sitting next to her and looks
a little uncomfortable but is not in severe distress."

---

### Correct Diagnosis
First presentation of asthma
(Not a respiratory infection — the pattern of symptoms, triggers,
timing, and family history all point to new-onset asthma)

Why this works: Child with cough and wheeze is one of the most
common presentations in paediatric primary care. The default
assumption is always viral or bacterial respiratory infection.
Distinguishing first-presentation asthma from acute infection
requires specific questioning about timing pattern, triggers,
recurrence, and family atopy — questions most people simply
would not think to ask.

---

### Anchor Trap
Child + cough + wheeze = chest infection or viral illness.
This is the strongest and most universally held assumption for
this presentation. Most people have experienced or know of a child
with a chesty cough that turned out to be a respiratory infection.
The antibiotic-seeking behaviour this triggers is well documented
and represents one of the most common forms of confirmation bias
in paediatric medicine.

---

### Anchor Keywords
(bias_detector.py anchor_keywords list)

infection, viral, bacteria, antibiotic, chest infection, cold,
flu, virus, fever, temperature, contagious, school bug, cold weather
virus, paracetamol, runny nose, throat, tonsils, ear, lymph node,
penicillin, amoxicillin, cough syrup, inhale steam, green mucus,
yellow mucus, sore throat, blocked nose, sick, ill, caught something

---

### Alternative Topics Keywords
(bias_detector.py — correct asthma exploration)

asthma, wheeze, trigger, exercise, cold air, night, morning,
allergy, eczema, hay fever, family asthma, atopy, inhaler,
recurring, bronchospasm, breathless on exertion, sport, PE,
running, worse at night, wake up coughing, seasonal, dust, pets

---

### Required Topics
(session_tracker.py — user must cover 5 of 7)

1. fever_infection_signs
   Does he have fever, runny nose, sore throat
   Detection keywords: fever, temperature, runny nose, sore
   throat, ear, tonsils, sick, ill, unwell, hot

2. symptom_timing_pattern
   Worse at night and early morning vs daytime
   Detection keywords: morning, night, evening, worse when,
   when bad, timing, sleeping, waking, pattern, time of day

3. exercise_trigger
   Does running or sport bring on the cough or wheeze
   Detection keywords: exercise, running, sport, PE, playing,
   after exercise, active, breathless, exertion, physical

4. cold_air_trigger
   Does cold air or going outside make it worse
   Detection keywords: cold air, outside, weather, cold, winter,
   wind, going out, temperature changes

5. duration_recurrence
   Is this the first time or has this happened before
   Detection keywords: before, first time, happened before,
   previous, recurring, again, history of, ever had

6. family_atopy_history
   Anyone with asthma, eczema, hay fever in the family
   Detection keywords: asthma, allergy, eczema, hay fever,
   atopy, family, mother, father, sibling, relative, inhaler

7. school_sport_impact
   Is he missing school, avoiding sport, or limited by symptoms
   Detection keywords: school, missing, PE, sport, activity,
   playing, limited, avoiding, stopped, cannot

---

### Minimum Questions Before Concluding: 7

---

### Contradictory Clues
(reveal only when directly asked)

1. NO FEVER — temperature is 36.8°C, completely normal
   (Infections almost always present with at least a low fever —
   absence of fever makes infection significantly less likely)

2. Symptoms are WORST AT NIGHT and in the EARLY MORNING
   (Asthma is characteristically worse at night and early morning
   due to circadian variation in airway calibre — viral infections
   do not follow this specific timing pattern)

3. Running and PE CLASS triggers the cough and wheeze
   (Exercise-induced bronchospasm is a hallmark of asthma —
   viral infections do not specifically worsen with exercise)

4. COLD AIR makes it significantly worse
   (Cold air triggers bronchospasm in asthmatic airways —
   again, not a feature of viral respiratory infections)

5. THIS HAS HAPPENED TWICE BEFORE in the past year
   (Sunita thought it was just a bad cough each time and it
   always resolved on its own — recurrent wheeze = asthma
   until proven otherwise)

6. GRANDFATHER has asthma and uses a blue inhaler
   (First-degree family history of asthma is the single
   strongest risk factor for childhood asthma)

7. MOTHER HAS HAY FEVER — takes antihistamines in spring
   (Atopic family background — asthma, eczema, and hay fever
   cluster together in atopic families)

8. NO SICK CONTACTS — no one at school has been ill
   (Viral infections spread through contact — no sick contacts
   makes an infectious cause much less likely)

---

### Bias Detection Summary for This Case

Anchoring fires if:
- User asks 3+ questions about infection signs (fever, throat,
  runny nose, antibiotics) without asking about timing or triggers

Premature closure fires if:
- User concludes respiratory infection after fewer than 7 questions
  or without asking about recurrence or family atopy history

Confirmation bias fires if:
- User recommends antibiotics or antiviral treatment
- AND never asked about night-time symptoms, exercise trigger,
  or family history of asthma

---

### Patient Voice Notes

(Playing SUNITA — mother, worried but calm)
Q: "How long has Arjun been coughing?"
A: "A few days now. Maybe 4 or 5 days. It seems worse at night
    when he is trying to sleep. It wakes him up sometimes."

Q: "Does he have a fever?"
A: "No — I checked this morning, 36.8. His temperature is normal."

Q: "Runny nose, sore throat, anything like that?"
A: "No actually, nothing like that. No runny nose. He said his
    throat does not hurt. It is really just the cough and that
    wheezing sound."

Q: "Has this happened before?"
A: "Twice before in the past year, now that I think about it.
    I thought it was just a bad cough both times and it went
    away by itself. I did not realise it might be something else."

Q: "Does it get worse with exercise or running?"
A: "Yes — he told me that at PE last week he started coughing
    and wheezing badly after running. His teacher was a bit
    concerned too."

Q: "Does cold air affect it?"
A: "Definitely. Going outside in the morning when it is cooler
    makes it much worse. He comes back in coughing."

Q: "Anyone in the family with asthma?"
A: "My father-in-law — Arjun's grandfather — has asthma. He
    uses an inhaler. And I have hay fever myself. I take
    antihistamines every spring."

Q: "Is he missing school because of this?"
A: "He went yesterday but he was uncomfortable the whole time.
    He did not do PE. He is quite active usually so this is
    affecting him."

(Playing ARJUN — 10-year-old, cooperative)
Q: "Arjun, does your chest feel tight when you run?"
A: "Yeah, when I run a lot it gets really tight and then I
    start coughing and it sounds funny. It is embarrassing
    in front of my friends."

---

### Anchor Test — CS Student Perspective

Imagined first 5 questions from a CS student:
1. "Does he have a fever?" — NEUTRAL (could go either way)
2. "Has he been around sick kids at school?" — ANCHOR (infection)
3. "Does he have a runny nose or sore throat?" — ANCHOR (infection)
4. "Should he take antibiotics?" — ANCHOR (infection)
5. "Is it a chest infection?" — ANCHOR (infection assumption)

Result: 3 of 5 questions are infection-focused. The fever
question is ambiguous — asking about fever is actually correct
regardless of the diagnosis. Anchor trap is solid. PASS.

---
---

## CASE 6 (code `case_10`): The Faint That Was Not a Faint

### Status: Designed and IMPLEMENTED 29 Oct 2026 as cases.py `case_10`,
### slug `syncope-aortic-stenosis`, seeded as draft by migration 028.
### The first case designed AFTER the audience changed from CS students
### to clinical-phase medical students (PRD D-1), and it shows: the trap
### is one a medical student falls into, not one a layperson falls into.

---

### Patient Persona
Name: Harbans Singh
Age / Gender: 68-year-old male
Occupation: Retired postmaster
Presenting complaint: Two blackouts in the past six weeks

Opening line shown to user on chat screen:
"A 68-year-old retired postmaster named Harbans Singh attends with his
wife, who insisted he come. He has blacked out twice in the past six
weeks. He looks well and is faintly embarrassed to be taking up
anyone's time."

---

### Correct Diagnosis
Severe calcific aortic stenosis causing exertional syncope

Why this works as a case: syncope is common, benign nine times out of
ten, and the tenth time is this. The history is short and the patient
volunteers a plausible explanation unprompted. Every other case in the
bank rewards asking more questions; this one also requires putting a
stethoscope on the chest, because two of the five discriminating
findings cannot be asked for.

---

### Anchor Trap
Elderly man + collapse + "I stood up too quickly" = vasovagal faint or
postural hypotension. The trap is unusually well defended:

1. **The patient offers it himself**, in his opening line, before any
   question is asked.
2. **He is on two drugs that cause postural hypotension** — tamsulosin
   started eight months ago and amlodipine for five years. A learner
   who takes a careful drug history finds strong support for the wrong
   answer. This is the only case in the bank where good history-taking
   makes the trap *more* convincing.
3. **He looks well.** General inspection is normal, and so are the
   observations apart from one number most people do not calculate.

The way out is the postural blood pressure: he has every reason to drop
and does not.

---

### Anchor Keywords
vasovagal, faint, fainting, simple faint, blackout spell, stood up too,
standing up too, getting up quickly, postural, orthostatic, dehydration,
dehydrated, drink more water, fluid intake, low blood sugar,
hypoglycaemia, skipped a meal, missed breakfast, hot weather, overheated,
anxiety, panic, medication side effect, old age, getting older,
compression stockings, get up slowly, reassurance, nothing to worry

**Drug names are deliberately excluded.** Blaming the tamsulosin is the
trap's strongest branch, but "what are you taking?" is the `medications`
required topic and is good history. Scoring it as fixation would punish
the question and reward skipping it. The fixation is in the conclusion,
not the question, so only "medication side effect" is listed.

---

### Alternative Topics Keywords
aortic stenosis, murmur, heart murmur, valve, echocardiogram, on
exertion, exertional, uphill, climbing stairs, angina, chest tightness,
slow rising, carotid, pulse character, narrow pulse pressure, arrhythmia,
holter, left ventricular, no warning, sudden collapse, auscultate

---

### Required Topics
(all five syncope topics were NEW — seeded by migration 027)

1. syncope_circumstances — what he was doing at the time        [NEW]
2. prodrome_warning — whether there was any warning              [NEW]
3. recovery_pattern — how he came round, and what a witness saw  [NEW]
4. exertional_symptoms — breathlessness and chest tightness      [NEW]
5. palpitations_rhythm — the other cardiac cause                 [NEW]
6. medications — existing
7. family_history — existing
8. duration_recurrence — existing

A syncope history is five questions and which five is not a matter of
taste. A learner who asks all five cannot call this a simple faint,
which is exactly why they are the required set.

---

### Minimum Questions Before Concluding: 8

---

### Contradictory Clues
(reveal only when directly asked)

1. BOTH episodes happened WALKING UPHILL — the stairs at home, the
   slope to the market. Neither on standing up from a chair.
   (Syncope during exertion is cardiac until proven otherwise.
   Vasovagal syncope essentially never happens mid-exertion.)

2. NO PRODROME AT ALL — no dizziness, nausea, sweating, tunnel vision
   or ringing in the ears.
   (Vasovagal syncope has a warning. Its absence points at an abrupt
   drop in cardiac output.)

3. IMMEDIATE, COMPLETE RECOVERY — awake within a minute, orientated at
   once, no confusion, no tongue biting, no incontinence, and his wife
   witnessed no jerking.
   (Excludes seizure, and excludes the post-ictal state that would
   otherwise be the competing explanation.)

4. SIX MONTHS of exertional breathlessness and chest tightness that
   settle within two minutes of stopping.
   (Angina, syncope and dyspnoea are the triad of aortic stenosis.
   He has all three and has mentioned none of them.)

5. A HEART MURMUR was noted years ago and never followed up.
   (The diagnosis has been available for years.)

6. NO PALPITATIONS — no racing, no skipped beats, no fluttering.
   (Argues against the other cardiac cause, arrhythmia, which the
   Holter then confirms.)

---

### What cannot be asked for — examination and investigation

Clues 1-4 and 6 are history. Two more findings are not:

- **Pulsus parvus et tardus** — a slow-rising, low-volume carotid
  pulse, with a narrow pulse pressure of 36 mmHg.
- **An ejection systolic murmur radiating to both carotids**, with a
  soft single second heart sound.

And the finding that breaks the trap outright: **no postural drop**,
in a man on two drugs that cause one.

The diagnosis is confirmed on echocardiography — mean gradient
48 mmHg, valve area 0.8 cm². Exertional syncope in severe aortic
stenosis is an indication for urgent valve referral, so this is also
the first case in the bank where the right answer is time-critical.

---

### Bias Detection Summary for This Case

Anchoring fires if:
- The learner asks 3+ questions in the faint/postural/dehydration
  vocabulary AND never asks what he was doing or whether there was a
  warning.

Premature closure fires if:
- "Vasovagal", "postural hypotension" or "dehydration" is submitted
  after fewer than 8 questions, or covering fewer than 5 topics.

Confirmation bias fires if:
- The learner advises getting up slowly, fluids, or a medication
  review AND never asked about exertion, warning, or the murmur.

---

### Patient Voice Notes

Q: "What happened?"
A: "I passed out twice in the last few weeks. My wife made me come.
    I expect I just stood up too quickly — that happens at my age,
    does it not?"

Q: "What were you doing when it happened?"
A: "Walking up, both times. Once on the stairs at home with the
    washing, once on the slope going to the market."

Q: "Did you have any warning?"
A: "None at all. One moment I was walking, the next I was on the
    ground. My wife saw the second one."

Q: "How were you afterwards?"
A: "Up within a minute. I knew where I was straight away. No
    confusion, nothing bitten, nothing like that."

Q: "Do you get breathless walking up that slope?"
A: "Now that you ask — yes, for about six months. I have to stop
    halfway. I used to walk it straight up."

Q: "Any chest discomfort?"
A: "A tightness, like a band, when I push on. It goes in a couple of
    minutes if I stand still. Never when I am sitting."

Q: "What tablets are you on?"
A: "One for the prostate, started about eight months ago. And one for
    blood pressure, for years now."

Q: "Any heart problems in the past?"
A: "A doctor mentioned a murmur years ago. Said to keep an eye on it.
    I forgot all about it, to be honest."

---

### Anchor Test — medical student perspective

This section is written from a YEAR 3-5 MEDICAL STUDENT's perspective,
not a CS student's. Every earlier case in this document predates that
change (PRD D-1, September 2026).

Imagined first 5 questions:
1. "How long have you been having these?" — NEUTRAL
2. "Were you standing up when it happened?" — ANCHOR (postural)
3. "What medications are you on?" — CORRECT, and makes the trap worse
4. "Have you been drinking enough?" — ANCHOR (dehydration)
5. "Do you feel dizzy when you stand?" — ANCHOR (postural)

A medical student will reliably take the blood pressure, and it is
118/82 — normal, unless the pulse pressure is calculated. They will
reliably ask about medications, and the answer supports the trap. The
specific question that breaks it — "what were you doing at the time?" —
is standard teaching and still commonly skipped when the patient has
already supplied an explanation.

Anchor trap is solid for the current audience. PASS.

---
---

## CASE COMPARISON TABLE
## Quick reference for verifying coverage and balance

| Field                | Case 1      | Case 2        | Case 3         | Case 4      | Case 5     | Case 6          |
|----------------------|-------------|---------------|----------------|-------------|------------|-----------------|
| cases.py id          | case_1      | case_6        | case_3         | case_4      | case_7     | case_10         |
| Patient              | 48M         | 28F           | 74M            | 35F         | 10M        | 68M             |
| Correct Dx           | GERD        | Hypertension  | UTI/Delirium   | Hypothyroid | Asthma     | Aortic stenosis |
| Anchor Dx            | MI/Cardiac  | Stress/Tension| Stroke/Dementia| Depression  | Infection  | Vasovagal faint |
| Min Questions        | 7           | 7             | 8              | 8           | 7          | 8               |
| Required Topics      | 8           | 8             | 8              | 8           | 7          | 8               |
| Contradictory Clues  | 8           | 8 (6 built)   | 8              | 8           | 8 (7 built)| 6               |
| Anchor Keywords      | 28          | 27            | 26             | 26          | 29         | 29              |
| Alt Topic Keywords   | 28          | 20            | 24             | 26          | 22         | 21              |
| Solved by            | history     | examination   | history        | history     | tests      | examination     |

---

## CASE UPDATE LOG
## Record every change after Day 2 here — date, case, what changed, why

## Format:
## [Date] Case X — Field changed: [what changed] — Reason: [why]

## Example:
## [May 24] Case 1 — anchor_keywords: added "palpitation" — Reason: user
## testing showed several users asked about palpitations which was not
## being flagged as anchoring behavior.

## Updates:

## [Oct 29, 2026] Case 2 (-> case_6) — IMPLEMENTED in cases.py as case_6,
## slug headache-hypertension, seeded draft by migration 026. Three changes
## to the design as written:
##
## 1. anchor_keywords: REMOVED "tension", "vision for screens", "sleep".
##    Reason: invariants C-4 and C-9, both substring collisions. The
##    detectors match with `if kw in question.lower()`, so "tension" fires
##    on a learner asking about HYPERtension and "vision for screens"
##    contains the clue keyword "vision" — in both cases the question that
##    SOLVES the case would have been scored as fixating on the trap.
##    "sleep" is a proper substring of "sleeping" (C-9). Replaced with
##    "tension headache" and "sleep quality"; "vision for screens" dropped
##    outright. This is the 14%-sensitivity bug class, caught before it ran.
##
## 2. contradictory_clues: clue 4 ("no specific stress event triggered the
##    headaches") is NOT implemented. Reason: it is a true and useful clue
##    for a human reader, but clues are matched as keyword lists against the
##    learner's questions, and there is no phrasing of "did anything
##    trigger this" that is both specific to this clue and not already the
##    stress_assessment topic. Six of the eight clues are implemented, above
##    the C-6 floor of four.
##
## 3. ADDED: the combined oral contraceptive pill, three years, as the
##    likely cause. Reason: the design names "contraceptive medication" in
##    the medications topic but never says what the answer is, leaving the
##    medications question decorative. For a year-3 medical student — the
##    audience since D-1 — an unexplained BP of 168/104 in a 28-year-old is
##    an incomplete case; the pill makes the medication history load-bearing
##    and the case teaches a real, reversible cause.

## [Oct 29, 2026] Case 5 (-> case_7) — IMPLEMENTED in cases.py as case_7,
## slug wheezing-child-asthma, seeded draft by migration 026. Four changes:
##
## 1. anchor_keywords: REMOVED "fever" and "temperature". Reason: C-4.
##    They are clue 1 — the absence of fever is the single most
##    discriminating finding in the case. Leaving them in the anchor list
##    would have counted "does he have a temperature?" as evidence of
##    fixating on infection. The design document's own Anchor Test says the
##    fever question "is actually correct regardless of the diagnosis",
##    which is the same observation reached from the other direction.
##
## 2. anchor_keywords: REMOVED "cold" and "cold weather virus". Reason:
##    C-4 again — both contain "cold", which is inside the clue keywords
##    "cold air" and "cold weather". Replaced with "common cold" and
##    "caught a cold", which collide with nothing.
##
## 3. anchor_keywords: REMOVED bare "ear" and "ill". Reason: too short to
##    match safely. "ear" fires on "year", "hear" and "clear"; "ill" on
##    "still" and "will". Not caught by C-9, which only checks a fixed list
##    of ordinary words, so this one is judgement rather than a test.
##    Replaced with "ear infection" and "earache".
##
## 4. contradictory_clues: clue 8 ("no sick contacts") is NOT implemented.
##    Reason: every phrasing of the question that finds it — "is anyone
##    else unwell", "has he been around sick children" — collides with an
##    anchor keyword under C-4. Seven of the eight clues are implemented.

