"""Stanbic batch bank codes: the receiving bank's code and branch.

Used at batching when the paying bank is Stanbic.
"""

from __future__ import annotations

import re
from typing import Optional, Tuple

# (bank name, code, branch) in the order supplied by the business
STANBIC_BANK_CODES = [
    ("POSB", "25000", "HEAD OFFICE"),
    ("CABS", "24000", "HEAD OFFICE"),
    ("STANCHART", "05140", "AFRICA UNITY SQUARE"),
    ("ZB", "04112", "FIRST STREET RETAIL"),
    ("NMB", "11101", "HEAD OFFICE"),
    ("STANBIC", "03115", "SAMORA MACHEL"),
    ("NEDBANK", "18101", "JASON MOYO"),
    ("AGRIBANK", "10102", "HEAD OFFICE"),
    ("FIRST CAPITAL", "02101", "HEAD OFFICE"),
    ("BANC ABC", "21301", "JASON MOYO"),
    ("CBZ", "06100", "HEAD OFFICE"),
]

# Other spellings users are likely to type
_ALIASES = {
    "STANCHART": ["STANDARD CHARTERED"],
    "FIRST CAPITAL": ["FIRST CAPITAL BANK", "FCB"],
    "BANC ABC": ["ABC", "ABC BANK"],
}


def _norm(text: str) -> str:
    return " ".join(re.sub(r"[^A-Z0-9 ]", " ", (text or "").upper()).split())


def is_stanbic(bank_name: Optional[str]) -> bool:
    return "STANBIC" in _norm(bank_name or "")


def lookup_bank_code(bank_name: Optional[str]) -> Optional[Tuple[str, str]]:
    """Return (code, branch) for a receiving bank name, or None if unknown."""
    name = _norm(bank_name or "")
    if not name:
        return None
    candidates = []
    for bank, code, branch in STANBIC_BANK_CODES:
        for key in [bank, *_ALIASES.get(bank, [])]:
            candidates.append((key, code, branch))
    for key, code, branch in sorted(candidates, key=lambda c: -len(c[0])):
        if re.search(rf"(?<![A-Z0-9]){re.escape(key)}(?![A-Z0-9])", name):
            return code, branch
    return None
