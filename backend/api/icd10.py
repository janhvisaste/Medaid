"""ICD-10-CM lookup used as the second-pass check on LLM condition names.

Data is vendored at api/data/icd10cm_terms.json.gz (CMS/NCHS ICD-10-CM
tabular list, US Government public domain), so lookups are in-process: no
network call, no runtime dependency, nothing on the triage path that can
block. See api/data/README.md for how to regenerate it.

Matching strategy, cheapest first:
  1. exact normalised term          -> O(1) dict hit
  2. token-indexed candidate search -> only terms sharing a rare-ish token
  3. edit distance over candidates  -> catches minor spelling drift

The token inverted index is what keeps this viable. A linear SequenceMatcher
sweep over 58k terms per condition would be far too slow to sit in a request.
"""

import gzip
import json
import logging
import re
import threading
from difflib import SequenceMatcher
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

DATA_PATH = Path(__file__).resolve().parent / 'data' / 'icd10cm_terms.json.gz'

# Matching thresholds.
EDIT_DISTANCE_RATIO = 0.88
MIN_TOKEN_LENGTH = 4
# Tokens appearing in more terms than this are too common to narrow a search
# ("with", "unspecified", "acute"). Skipped when gathering candidates.
MAX_TOKEN_POSTINGS = 3000
MAX_CANDIDATES = 400
# A token shared with at most this many ICD terms is "distinctive" enough to
# justify a match on its own. Corpus frequency is used instead of a hand-kept
# stopword list: without this, "Q fever" reduces to {fever} and "Tic disorder"
# to {disorder}, letting fabricated names inherit a real code.
DISTINCTIVE_TOKEN_MAX_DF = 400

_lock = threading.Lock()
_index: Optional[Dict] = None


def _normalise(text: str) -> str:
    text = (text or '').lower()
    text = re.sub(r'\[.*?\]|\(.*?\)', ' ', text)
    text = re.sub(r'[^a-z0-9\s\-]', ' ', text)
    return re.sub(r'\s+', ' ', text).strip()


def _tokens(text: str) -> set:
    return {t for t in text.replace('-', ' ').split() if len(t) >= MIN_TOKEN_LENGTH}


def _build_index() -> Dict:
    """Load the vendored dataset and build the token inverted index."""
    if not DATA_PATH.exists():
        logger.warning('icd10.dataset_missing', extra={'path': str(DATA_PATH)})
        return {'terms': {}, 'codes': {}, 'postings': {}, 'available': False}

    with gzip.open(DATA_PATH, 'rt', encoding='utf-8') as handle:
        payload = json.load(handle)

    terms: Dict[str, str] = payload.get('terms', {})
    postings: Dict[str, List[str]] = {}
    for term in terms:
        for token in _tokens(term):
            postings.setdefault(token, []).append(term)

    logger.info(
        'icd10.index_built',
        extra={'term_count': len(terms), 'token_count': len(postings)},
    )
    return {
        'terms': terms,
        'codes': payload.get('codes', {}),
        'postings': postings,
        'version': payload.get('version', 'unknown'),
        'available': True,
    }


def get_index() -> Dict:
    """Return the lazily-built index (thread-safe, built once per process)."""
    global _index
    if _index is None:
        with _lock:
            if _index is None:
                try:
                    _index = _build_index()
                except Exception as error:
                    logger.exception(
                        'icd10.index_build_failed',
                        extra={'error_type': type(error).__name__},
                    )
                    _index = {'terms': {}, 'codes': {}, 'postings': {}, 'available': False}
    return _index


def is_available() -> bool:
    return bool(get_index().get('available'))


def _candidates(normalised: str, index: Dict) -> List[str]:
    """Terms worth scoring, gathered via the token inverted index."""
    postings = index['postings']
    query_tokens = _tokens(normalised)
    if not query_tokens:
        return []

    seen: Dict[str, int] = {}
    for token in query_tokens:
        bucket = postings.get(token)
        if not bucket or len(bucket) > MAX_TOKEN_POSTINGS:
            continue
        for term in bucket:
            seen[term] = seen.get(term, 0) + 1

    if not seen:
        return []
    # Prefer terms sharing the most query tokens.
    ranked = sorted(seen.items(), key=lambda kv: (-kv[1], len(kv[0])))
    return [term for term, _ in ranked[:MAX_CANDIDATES]]


def lookup(name: str) -> Optional[Tuple[str, str, str]]:
    """Resolve a condition name against ICD-10-CM.

    Returns (icd10_code, canonical_description, match_kind) or None.
    match_kind is 'exact', 'substring', 'token overlap' or 'near-identical spelling'.
    """
    normalised = _normalise(name)
    if len(normalised) < 4:
        return None

    index = get_index()
    if not index.get('available'):
        return None

    terms = index['terms']
    codes = index['codes']

    def result(term, kind):
        code = terms[term]
        return code, codes.get(code, term), kind

    # 1. Exact normalised match.
    if normalised in terms:
        return result(normalised, 'exact')

    candidates = _candidates(normalised, index)
    if not candidates:
        return None

    query_tokens = _tokens(normalised)
    postings = index['postings']

    def has_distinctive_overlap(shared: set) -> bool:
        """True if the shared tokens include something corpus-rare.

        Guards against a fabricated name matching purely on a generic word
        that happens to be the only surviving token of a short ICD term.
        """
        return any(len(postings.get(token, ())) <= DISTINCTIVE_TOKEN_MAX_DF for token in shared)

    # 2. Substring / full-token-containment against candidates.
    for term in candidates:
        if term == normalised:
            return result(term, 'exact')
        term_tokens = _tokens(term)
        if not term_tokens:
            continue
        # The whole ICD term appears inside the model's name, or vice versa.
        if term in normalised or normalised in term:
            return result(term, 'substring')
        # A single-token ICD term ("Q fever" -> {fever}) carries too little
        # signal to justify a subset match; such terms are still reachable
        # via the exact and substring passes above.
        if len(term_tokens) < 2:
            continue
        shared = term_tokens & query_tokens
        if not has_distinctive_overlap(shared):
            continue
        if term_tokens.issubset(query_tokens) or query_tokens.issubset(term_tokens):
            return result(term, 'token overlap')

    # 3. Edit distance over the narrowed candidate set only.
    best, best_ratio = None, 0.0
    for term in candidates:
        if abs(len(term) - len(normalised)) > 6:
            continue
        ratio = SequenceMatcher(None, term, normalised).ratio()
        if ratio > best_ratio:
            best, best_ratio = term, ratio
    if best and best_ratio >= EDIT_DISTANCE_RATIO:
        return result(best, 'near-identical spelling')

    return None
