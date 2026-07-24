"""Grounding checks applied to an LLM triage assessment before a patient sees it.

Two independent concerns live here:

1. Confidence calibration. An LLM's self-reported ``confidence`` is not
   grounded in anything - it will happily return 0.9 for "i feel bad". We
   score how much the patient actually told us and cap confidence against
   that ceiling, so a confident-sounding number can never outrun its input.

2. Condition-name plausibility. A hallucinated condition name presented next
   to a percentage reads as a diagnosis. We check returned names against a
   curated list of common conditions and, failing that, against medical
   morphology, and mark anything we cannot recognise.

Neither check tries to decide whether a diagnosis is *correct* - that is not
something this layer can know. They bound how confidently an ungrounded or
unrecognisable answer is allowed to present itself.
"""

import re
from difflib import SequenceMatcher
from typing import Dict, List, Optional, Tuple

from . import icd10
from .condition_reference import (
    COMMON_CONDITIONS,
    GENERIC_CONDITION_MARKERS,
    MEDICAL_SUFFIXES,
    MEDICAL_WORDS,
)

# --------------------------------------------------------------------------
# 1. Confidence calibration
# --------------------------------------------------------------------------

# Confidence ceilings by how specific the patient's report was.
CONFIDENCE_CEILINGS = {
    'rich': 0.90,
    'moderate': 0.70,
    'sparse': 0.50,
    'minimal': 0.30,
}

# Signals that a report carries real clinical detail.
_DURATION_PATTERN = re.compile(
    r'\b(\d+\s*(hour|hr|day|week|month|year)s?|since\s+\w+|for\s+the\s+(last|past)\s+\w+|'
    r'yesterday|today|this\s+(morning|evening|week)|last\s+night|overnight|suddenly|gradually)\b',
    re.IGNORECASE,
)
_SEVERITY_PATTERN = re.compile(
    r'\b(mild|moderate|severe|slight|intense|excruciating|unbearable|sharp|dull|throbbing|'
    r'burning|constant|intermittent|worse|worsening|better|improving|\d\s*/\s*10)\b',
    re.IGNORECASE,
)
_LOCATION_PATTERN = re.compile(
    r'\b(head|chest|abdomen|abdominal|stomach|back|neck|throat|arm|leg|knee|shoulder|eye|ear|'
    r'left|right|lower|upper|side|joint|skin|hand|foot|hip|jaw)\b',
    re.IGNORECASE,
)
_MODIFIER_PATTERN = re.compile(
    r'\b(after|before|when i|worse with|better with|triggered|relieved|aggravated|'
    r'radiat\w+|associated|along with|accompanied)\b',
    re.IGNORECASE,
)

MIN_WORDS_FOR_DETAIL = 6

# Hard ceiling for short reports that never went through a clarifying-question
# round. This is a floor-of-last-resort on top of the signal-based ceilings
# above: a brief, unclarified report cannot yield a confident assessment no
# matter what the model claims, and no matter which signals happened to match.
SHORT_INPUT_WORD_THRESHOLD = 15
SHORT_INPUT_CONFIDENCE_CAP = 0.4


def score_input_specificity(symptoms_text: Optional[str]) -> Dict:
    """Score how much clinically usable detail the patient actually provided.

    Returns {'level', 'score', 'signals', 'missing'} where score is 0-4.
    """
    text = (symptoms_text or '').strip()
    word_count = len(text.split())

    signals = {
        'duration': bool(_DURATION_PATTERN.search(text)),
        'severity': bool(_SEVERITY_PATTERN.search(text)),
        'location': bool(_LOCATION_PATTERN.search(text)),
        'modifiers': bool(_MODIFIER_PATTERN.search(text)),
    }
    score = sum(signals.values())

    if word_count < MIN_WORDS_FOR_DETAIL:
        # Too short to carry a usable history no matter what matched.
        level = 'minimal' if score <= 1 else 'sparse'
    elif score >= 3:
        level = 'rich'
    elif score == 2:
        level = 'moderate'
    elif score == 1:
        level = 'sparse'
    else:
        level = 'minimal'

    return {
        'level': level,
        'score': score,
        'word_count': word_count,
        'signals': signals,
        'missing': sorted(name for name, present in signals.items() if not present),
    }


def calibrate_confidence(
    reported_confidence: float,
    symptoms_text: Optional[str],
    *,
    had_clarifying_round: bool = False,
) -> Dict:
    """Cap a model's self-reported confidence at what the input can support.

    Two ceilings apply, and the lower wins:
      1. A signal-based ceiling from how much clinical detail was provided.
      2. A hard short-input cap, when the report is under
         SHORT_INPUT_WORD_THRESHOLD words AND no clarifying-question round
         happened. Answering follow-up questions lifts this second cap,
         because the patient has then been given a chance to elaborate.

    Returns a dict describing both the final value and why it was adjusted,
    so the UI can show the reason instead of an unexplained number.
    """
    specificity = score_input_specificity(symptoms_text)
    signal_ceiling = CONFIDENCE_CEILINGS[specificity['level']]

    is_short_unclarified = (
        specificity['word_count'] < SHORT_INPUT_WORD_THRESHOLD and not had_clarifying_round
    )
    ceiling = min(signal_ceiling, SHORT_INPUT_CONFIDENCE_CAP) if is_short_unclarified else signal_ceiling

    try:
        reported = float(reported_confidence)
    except (TypeError, ValueError):
        reported = 0.0
    reported = max(0.0, min(1.0, reported))

    calibrated = min(reported, ceiling)
    was_capped = calibrated < reported

    # The short-input rule counts as applied whenever the report was short and
    # unclarified and we ended up capping - even if the signal-based ceiling
    # happened to be the tighter of the two constraints. Reporting otherwise
    # would tell a patient their brevity was not a factor when it was.
    short_cap_applied = is_short_unclarified and was_capped

    if short_cap_applied:
        explanation = (
            f"Confidence was reduced from {reported:.0%} to {calibrated:.0%} because the "
            f"description is only {specificity['word_count']} words and no follow-up "
            "questions were answered. Answering follow-up questions would improve this."
        )
    elif was_capped:
        missing = ', '.join(specificity['missing']) or 'additional detail'
        explanation = (
            f"Confidence was reduced from {reported:.0%} to {calibrated:.0%} because the "
            f"symptom description is {specificity['level']} in detail (missing: {missing}). "
            "Answering follow-up questions would improve this."
        )
    else:
        explanation = (
            f"Confidence of {calibrated:.0%} is supported by the level of detail provided."
        )

    return {
        'confidence': round(calibrated, 2),
        'reported_confidence': round(reported, 2),
        'confidence_ceiling': ceiling,
        'confidence_was_capped': was_capped,
        'input_specificity': specificity['level'],
        'input_specificity_score': specificity['score'],
        'input_word_count': specificity['word_count'],
        'short_input_cap_applied': short_cap_applied,
        'had_clarifying_round': had_clarifying_round,
        'missing_detail': specificity['missing'],
        'confidence_explanation': explanation,
    }


def should_request_clarification(
    symptoms_text: Optional[str],
    *,
    had_clarifying_round: bool = False,
) -> bool:
    """Decide whether a symptom report is too vague to assess confidently
    without first asking a clarifying follow-up.

    This is the single source of truth for the "is this input vague?" gate, so
    every entry point (the consultation wizard, ``/triage/assess/`` and chat)
    stays consistent instead of each re-deriving its own heuristic. It mirrors
    the confidence-cap triggers in ``calibrate_confidence``: an input that would
    be hard-capped for brevity, or that carries too few clinical signals, is
    exactly the input worth a clarifying round. A report only ever yields a
    "low-confidence" ceiling (minimal/sparse level, or the short-input cap) when
    this returns True.

    Returns False once a clarifying round has already happened - we ask at most
    once and then proceed with whatever the patient could provide.
    """
    if had_clarifying_round:
        return False

    specificity = score_input_specificity(symptoms_text)
    if not specificity['word_count']:
        # Empty input has nothing to clarify against; callers reject it earlier.
        return False

    is_short = specificity['word_count'] < SHORT_INPUT_WORD_THRESHOLD
    is_low_signal = specificity['level'] in ('minimal', 'sparse')
    return is_short or is_low_signal


# --------------------------------------------------------------------------
# 2. Condition-name plausibility ("lightweight ontology check")
# --------------------------------------------------------------------------

# The curated reference list and morphology vocabulary live in
# condition_reference.py so the list can grow without touching this logic.

# Fuzzy-match thresholds.
TOKEN_OVERLAP_THRESHOLD = 0.6   # share of reference tokens present in the name
EDIT_DISTANCE_RATIO = 0.85      # SequenceMatcher ratio for near-miss spellings
MIN_TOKEN_LENGTH = 4            # ignore short filler tokens when overlapping

# Tokens that carry no distinguishing power on their own. A token-overlap
# match resting solely on these would let "Sparkle Fever Extreme" match
# "hay fever", or "Purple Monday Syndrome" match "dry eye syndrome".
LOW_INFORMATION_TOKENS = set(MEDICAL_WORDS) | {
    'fever', 'type', 'tract', 'severe', 'mild', 'moderate', 'severity',
    'related', 'unknown', 'general', 'common', 'primary', 'secondary',
}


def _normalise(name: str) -> str:
    return re.sub(r'[^a-z0-9\s\-]', '', (name or '').lower()).strip()


def _tokens(text: str) -> set:
    return {t for t in text.replace('-', ' ').split() if len(t) >= MIN_TOKEN_LENGTH}


def _fuzzy_match(normalised: str) -> Optional[Tuple[str, str]]:
    """Return (matched_reference_name, how) for a curated match, else None.

    Three passes, cheapest first:
      1. substring either direction  ("acute viral gastroenteritis" ~ "gastroenteritis")
      2. token overlap               ("diabetes type 2 mellitus" ~ "diabetes mellitus")
      3. edit distance               ("migrane" ~ "migraine")

    Token overlap deliberately requires the reference to have at least two
    meaningful tokens AND the shared tokens to include something specific.
    Without both guards a single generic word ("fever", "syndrome") is enough
    to launder a fabricated name into a curated match.
    """
    for known in COMMON_CONDITIONS:
        if known in normalised or normalised in known:
            return known, 'substring'

    name_tokens = _tokens(normalised)
    if name_tokens:
        for known in COMMON_CONDITIONS:
            known_tokens = _tokens(known)
            if len(known_tokens) < 2:
                # Single-token references are handled by the substring pass;
                # allowing them here matches on one generic word.
                continue
            shared = known_tokens & name_tokens
            overlap = len(shared) / len(known_tokens)
            if overlap < TOKEN_OVERLAP_THRESHOLD:
                continue
            if not (shared - LOW_INFORMATION_TOKENS):
                # Everything shared is a generic medical filler word.
                continue
            return known, 'token overlap'

    for known in COMMON_CONDITIONS:
        if abs(len(known) - len(normalised)) > 4:
            continue
        if SequenceMatcher(None, known, normalised).ratio() >= EDIT_DISTANCE_RATIO:
            return known, 'near-identical spelling'

    return None


def classify_condition_name(name: str) -> Tuple[str, str, Optional[str], Optional[str]]:
    """Classify a condition name as 'known' | 'plausible' | 'generic' | 'unrecognized'.

    Returns (status, reason, match_source, icd10_code) where match_source is
    'curated', 'icd10', 'morphology' or None. Two-pass by design: the curated
    list is a fast first filter, ICD-10-CM is the standardized second pass for
    anything it misses.
    """
    normalised = _normalise(name)
    if not normalised:
        return 'unrecognized', 'Empty condition name.', None, None

    if any(marker in normalised for marker in GENERIC_CONDITION_MARKERS):
        return 'generic', 'Name carries no diagnostic information.', None, None

    # Pass 1: curated common-presentations list. Small, fast, no I/O.
    matched = _fuzzy_match(normalised)
    if matched:
        reference, how = matched
        return 'known', f'Matches curated condition "{reference}" ({how}).', 'curated', None

    # Pass 2: ICD-10-CM. Only reached for names the curated list missed, so
    # the common case never pays for it. This is what admits real conditions
    # outside our curated few hundred (Sarcoidosis, Osteomyelitis, ...)
    # instead of sending them for human review as if they were nonsense.
    icd_match = icd10.lookup(name)
    if icd_match:
        code, description, how = icd_match
        return 'known', f'Matches ICD-10-CM {code} "{description}" ({how}).', 'icd10', code

    tokens = normalised.replace('-', ' ').split()
    if any(token.endswith(MEDICAL_SUFFIXES) for token in tokens):
        return ('plausible', 'Not in curated list or ICD-10-CM, but uses medical morphology.',
                'morphology', None)
    if any(word in tokens for word in MEDICAL_WORDS):
        return ('plausible',
                'Not in curated list or ICD-10-CM, but uses recognised medical terminology.',
                'morphology', None)

    return 'unrecognized', 'Does not match any known condition or medical naming pattern.', None, None


def validate_conditions(conditions: List[Dict]) -> Dict:
    """Annotate each condition with a recognition status.

    Returns {'conditions': [...annotated...], 'unrecognized_count': int,
             'any_unrecognized': bool, 'all_unrecognized': bool,
             'non_curated_count': int}.

    Conditions are annotated rather than dropped: silently removing a name the
    model returned would hide a real failure from clinicians reviewing the case.

    'known' now means the name resolved against either the curated list or
    ICD-10-CM, and match_source records which. 'plausible' means it only
    matched medical morphology - enough to admit an unusual real term, but NOT
    enough to rule out a well-formed fabrication like "Quantum Bone Disorder".
    A name that reaches ICD-10-CM and still fails is a strong signal.
    """
    annotated = []
    unrecognized = 0
    non_curated = 0
    icd10_matched = 0
    authoritative = 0

    for condition in conditions or []:
        if not isinstance(condition, dict):
            condition = {'disease': str(condition), 'confidence': 0.0, 'supporting_evidence': []}

        status, reason, source, icd_code = classify_condition_name(condition.get('disease', ''))
        entry = dict(condition)
        entry['name_status'] = status
        entry['name_status_reason'] = reason
        entry['match_source'] = source
        entry['icd10_code'] = icd_code
        entry['recognized'] = status in ('known', 'plausible')
        # 'curated' stays narrow: matched our own vetted list, not ICD-10 at
        # large. ICD-10 covers ~46k codes including many a triage product
        # should treat with more caution than its curated common set.
        entry['curated'] = source == 'curated'
        if not entry['recognized']:
            unrecognized += 1
        if not entry['curated']:
            non_curated += 1
        if source == 'icd10':
            icd10_matched += 1
        # 'authoritative' = resolved against a real terminology (our curated
        # list or ICD-10-CM), as opposed to merely looking medical.
        entry['authoritative'] = source in ('curated', 'icd10')
        if entry['authoritative']:
            authoritative += 1
        annotated.append(entry)

    total = len(annotated)
    return {
        'conditions': annotated,
        'unrecognized_count': unrecognized,
        'non_curated_count': non_curated,
        'icd10_matched_count': icd10_matched,
        'authoritative_count': authoritative,
        'any_unrecognized': unrecognized > 0,
        'all_unrecognized': total > 0 and unrecognized == total,
        # Nothing in the differential resolved against either terminology.
        # Now that ICD-10-CM's ~46k codes have been consulted and missed,
        # morphology alone ("...itis", "syndrome") is too weak to let a
        # differential through unreviewed.
        'none_authoritative': total > 0 and authoritative == 0,
    }
