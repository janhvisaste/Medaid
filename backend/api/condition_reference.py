"""Curated reference list of condition names for validating an LLM differential.

This is deliberately a curated common-presentations list, not ICD-10 or
SNOMED CT. It covers what a primary triage product realistically surfaces.
A name that misses this list is *flagged*, never dropped - see
assessment_quality.validate_conditions.

Names are stored lowercase. Matching (in assessment_quality) is substring +
token-overlap + edit-distance, so inflections and qualifiers like
"Acute Viral Gastroenteritis" still resolve to "gastroenteritis".
"""

COMMON_CONDITIONS = {
    # ---- Infectious / systemic -------------------------------------------
    'viral upper respiratory infection', 'upper respiratory tract infection',
    'common cold', 'influenza', 'covid-19', 'viral syndrome', 'viral illness',
    'self-limiting viral illness', 'acute viral syndrome', 'gastroenteritis',
    'viral gastroenteritis', 'bacterial gastroenteritis', 'food poisoning',
    'tonsillitis', 'pharyngitis', 'strep throat', 'laryngitis', 'sinusitis',
    'bronchitis', 'bronchiolitis', 'pneumonia', 'tuberculosis',
    'urinary tract infection', 'cystitis', 'pyelonephritis', 'cellulitis',
    'abscess', 'conjunctivitis', 'otitis media', 'otitis externa',
    'dengue', 'malaria', 'typhoid', 'chikungunya', 'hepatitis a', 'hepatitis b',
    'hepatitis c', 'chickenpox', 'measles', 'mumps', 'rubella', 'shingles',
    'herpes zoster', 'infectious mononucleosis', 'sepsis', 'meningitis',
    'encephalitis', 'tetanus', 'rabies', 'leptospirosis', 'scabies',
    'ringworm', 'oral thrush', 'candidiasis', 'covid', 'viral fever',

    # ---- Gastrointestinal -------------------------------------------------
    'gastritis', 'acid reflux', 'gastroesophageal reflux disease', 'peptic ulcer',
    'duodenal ulcer', 'irritable bowel syndrome', 'inflammatory bowel disease',
    'crohn disease', 'ulcerative colitis', 'constipation', 'diarrhea',
    'appendicitis', 'hemorrhoids', 'anal fissure', 'lactose intolerance',
    'celiac disease', 'indigestion', 'dyspepsia', 'cholecystitis', 'gallstones',
    'pancreatitis', 'hernia', 'inguinal hernia', 'hiatal hernia',
    'diverticulitis', 'diverticulosis', 'bowel obstruction', 'fatty liver disease',
    'cirrhosis', 'jaundice', 'gastroenteritis', 'colic', 'gastric ulcer',

    # ---- Cardiovascular ---------------------------------------------------
    'hypertension', 'hypotension', 'angina', 'stable angina', 'unstable angina',
    'myocardial infarction', 'heart attack', 'arrhythmia', 'atrial fibrillation',
    'tachycardia', 'bradycardia', 'heart failure', 'congestive heart failure',
    'cardiomyopathy', 'pericarditis', 'endocarditis', 'deep vein thrombosis',
    'pulmonary embolism', 'varicose veins', 'peripheral artery disease',
    'atherosclerosis', 'hyperlipidemia', 'high cholesterol', 'palpitations',
    'orthostatic hypotension', 'aortic stenosis',

    # ---- Respiratory ------------------------------------------------------
    'asthma', 'chronic obstructive pulmonary disease', 'copd', 'emphysema',
    'allergic rhinitis', 'hay fever', 'pleurisy', 'pneumothorax',
    'sleep apnea', 'obstructive sleep apnea', 'pulmonary edema',
    'respiratory tract infection', 'croup', 'whooping cough', 'pertussis',

    # ---- Neurological -----------------------------------------------------
    'migraine', 'tension-type headache', 'tension headache', 'cluster headache',
    'vertigo', 'benign paroxysmal positional vertigo', 'labyrinthitis',
    'concussion', 'sciatica', 'epilepsy', 'seizure disorder', 'stroke',
    'transient ischemic attack', 'peripheral neuropathy', 'neuropathy',
    'carpal tunnel syndrome', 'bell palsy', 'trigeminal neuralgia',
    'multiple sclerosis', 'parkinson disease', 'dementia', 'alzheimer disease',
    'syncope', 'fainting', 'dizziness', 'restless legs syndrome',
    'dehydration-related dizziness',

    # ---- Musculoskeletal --------------------------------------------------
    'musculoskeletal pain', 'muscle strain', 'ligament sprain', 'osteoarthritis',
    'rheumatoid arthritis', 'lower back pain', 'mechanical back pain',
    'tendinitis', 'tendinopathy', 'bursitis', 'frozen shoulder',
    'rotator cuff injury', 'plantar fasciitis', 'gout', 'fibromyalgia',
    'osteoporosis', 'fracture', 'stress fracture', 'dislocation',
    'whiplash', 'herniated disc', 'slipped disc', 'spondylosis', 'scoliosis',
    'shin splints', 'tennis elbow', 'golfer elbow', 'meniscus tear',
    'muscle cramp', 'myalgia', 'costochondritis',

    # ---- Endocrine / metabolic -------------------------------------------
    'diabetes mellitus', 'type 1 diabetes', 'type 2 diabetes', 'prediabetes',
    'hypothyroidism', 'hyperthyroidism', 'thyroiditis', 'goiter',
    'dehydration', 'anemia', 'iron deficiency anemia', 'vitamin b12 deficiency',
    'vitamin d deficiency', 'hypoglycemia', 'hyperglycemia', 'obesity',
    'metabolic syndrome', 'polycystic ovary syndrome', 'adrenal insufficiency',
    'cushing syndrome', 'electrolyte imbalance', 'hyponatremia', 'hypokalemia',
    'dehydration-related symptoms',

    # ---- Dermatological ---------------------------------------------------
    'eczema', 'atopic dermatitis', 'contact dermatitis', 'psoriasis',
    'urticaria', 'hives', 'fungal infection', 'acne', 'rosacea', 'impetigo',
    'folliculitis', 'seborrheic dermatitis', 'dandruff', 'vitiligo',
    'melasma', 'alopecia', 'hair loss', 'skin rash', 'insect bite',
    'sunburn', 'boil', 'wart', 'corn', 'callus', 'pressure ulcer',

    # ---- Ophthalmological / ENT ------------------------------------------
    'dry eye syndrome', 'stye', 'blepharitis', 'glaucoma', 'cataract',
    'refractive error', 'eye strain', 'uveitis', 'corneal abrasion',
    'tinnitus', 'hearing loss', 'earwax impaction', 'nasal polyps',
    'deviated septum', 'epistaxis', 'nosebleed', 'nasal congestion',

    # ---- Mental health ----------------------------------------------------
    'anxiety', 'generalized anxiety disorder', 'depression',
    'major depressive disorder', 'panic attack', 'panic disorder', 'insomnia',
    'stress reaction', 'acute stress reaction', 'burnout',
    'post-traumatic stress disorder', 'obsessive-compulsive disorder',
    'bipolar disorder', 'eating disorder', 'somatic symptom disorder',
    'adjustment disorder', 'seasonal affective disorder',

    # ---- Genitourinary / reproductive ------------------------------------
    'kidney stones', 'renal colic', 'chronic kidney disease', 'kidney infection',
    'benign prostatic hyperplasia', 'prostatitis', 'erectile dysfunction',
    'menstrual cramps', 'dysmenorrhea', 'amenorrhea', 'menorrhagia',
    'premenstrual syndrome', 'endometriosis', 'uterine fibroids',
    'ovarian cyst', 'vaginitis', 'bacterial vaginosis', 'yeast infection',
    'pelvic inflammatory disease', 'menopause', 'urinary incontinence',
    'urethritis', 'epididymitis',

    # ---- Allergy / immune -------------------------------------------------
    'allergic reaction', 'food allergy', 'drug allergy', 'anaphylaxis',
    'angioedema', 'lupus', 'systemic lupus erythematosus', 'vasculitis',
    'immunodeficiency',

    # ---- Paediatric-leaning ----------------------------------------------
    'teething', 'hand foot and mouth disease', 'febrile seizure',
    'diaper rash', 'colic in infants', 'growing pains',

    # ---- Injury / environmental ------------------------------------------
    'heat exhaustion', 'heat stroke', 'hypothermia', 'motion sickness',
    'altitude sickness', 'burn', 'laceration', 'contusion', 'bruise',
    'foreign body', 'poisoning', 'carbon monoxide poisoning',
    'alcohol intoxication', 'withdrawal syndrome',

    # ---- Non-specific but legitimate triage outputs -----------------------
    'benign condition', 'fatigue', 'malaise', 'fever of unknown origin',
    'chronic fatigue syndrome', 'nonspecific viral illness',
}


# Names that are well-formed but carry no diagnostic information. These are
# distinct from unrecognised names: the model followed instructions, it just
# said nothing useful.
GENERIC_CONDITION_MARKERS = (
    'medical condition', 'unknown condition', 'condition requiring evaluation',
    'medical issue', 'unspecified', 'not determined', 'undetermined',
    'requires evaluation', 'general illness', 'various causes', 'multiple causes',
)


# Morphology typical of real medical terminology, used only as a secondary
# signal for names outside the curated list.
MEDICAL_SUFFIXES = (
    'itis', 'osis', 'emia', 'aemia', 'pathy', 'algia', 'ectomy', 'otomy',
    'plasia', 'trophy', 'oma', 'iasis', 'ism', 'uria', 'penia', 'megaly',
    'sclerosis', 'stenosis', 'dynia', 'rrhea', 'rrhoea', 'phagia', 'plegia',
    'paresis', 'opia', 'cytosis', 'itis', 'aemia', 'blastoma', 'pnea', 'ptosis',
)

MEDICAL_WORDS = (
    'syndrome', 'disease', 'disorder', 'infection', 'deficiency', 'failure',
    'insufficiency', 'injury', 'fracture', 'strain', 'sprain', 'acute',
    'chronic', 'viral', 'bacterial', 'fungal', 'allergic', 'inflammation',
    'inflammatory', 'benign', 'malignant', 'reaction', 'attack', 'pain',
    'idiopathic', 'congenital', 'lesion', 'ulcer', 'obstruction', 'infarction',
    'ischemia', 'hemorrhage', 'haemorrhage', 'thrombosis', 'embolism',
)
