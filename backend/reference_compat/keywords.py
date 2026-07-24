"""Reference emergency keyword behavior.

Source: Shivanikinagi/Medaid/backend_processing.py,
contains_emergency_keyword and its active EMERGENCY_KEYWORDS list.
"""

EMERGENCY_KEYWORDS = [
    "not breathing", "unconscious", "severe chest pain", "heavy bleeding",
    "sudden weakness", "slurred speech", "seizure", "severe burn",
    "blue lips", "very drowsy", "faint", "loss of consciousness",
    "can't breathe", "cannot breathe",
]


def contains_emergency_keyword(text: str) -> bool:
    """Return whether a case-insensitive substring occurs in text."""
    # Reference source: backend_processing.py::contains_emergency_keyword.
    if not text:
        return False
    lowered = text.lower()
    return any(keyword in lowered for keyword in EMERGENCY_KEYWORDS)
