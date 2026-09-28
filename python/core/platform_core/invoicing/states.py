"""GST state codes and GSTIN checks (Capability Universe §14.4).

Place of supply decides CGST + SGST (same state) or IGST (other state), and a
GSTIN's first two digits are its state. This is reference data, not tax
advice; the list is the GST state-code table (verify at build: VB-19).
"""

from __future__ import annotations

import re

STATES: dict[str, str] = {
    "01": "Jammu and Kashmir", "02": "Himachal Pradesh", "03": "Punjab", "04": "Chandigarh",
    "05": "Uttarakhand", "06": "Haryana", "07": "Delhi", "08": "Rajasthan", "09": "Uttar Pradesh",
    "10": "Bihar", "11": "Sikkim", "12": "Arunachal Pradesh", "13": "Nagaland", "14": "Manipur",
    "15": "Mizoram", "16": "Tripura", "17": "Meghalaya", "18": "Assam", "19": "West Bengal",
    "20": "Jharkhand", "21": "Odisha", "22": "Chhattisgarh", "23": "Madhya Pradesh", "24": "Gujarat",
    "26": "Dadra and Nagar Haveli and Daman and Diu", "27": "Maharashtra", "29": "Karnataka",
    "30": "Goa", "31": "Lakshadweep", "32": "Kerala", "33": "Tamil Nadu", "34": "Puducherry",
    "35": "Andaman and Nicobar Islands", "36": "Telangana", "37": "Andhra Pradesh", "38": "Ladakh",
    "97": "Other Territory",
}

_GSTIN = re.compile(r"^[0-9]{2}[A-Z0-9]{10}[0-9A-Z]Z[0-9A-Z]$")
_CHARS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def state_label(code: str | None) -> str:
    if not code:
        return ""
    return f"{STATES.get(code, 'Unknown state')} ({code})"


def _check_char(first14: str) -> str:
    total = 0
    for i, ch in enumerate(first14):
        v = _CHARS.index(ch) * (2 if i % 2 else 1)
        total += v // 36 + v % 36
    return _CHARS[(36 - total % 36) % 36]


def gstin_problem(gstin: str) -> str | None:
    """Why this GSTIN cannot be right, in plain words — or None."""
    g = (gstin or "").strip().upper()
    if len(g) != 15:
        return "A GSTIN has 15 characters"
    if not _GSTIN.match(g):
        return "That does not look like a GSTIN (2-digit state, PAN, entity number, Z, check character)"
    if g[:2] not in STATES:
        return f"{g[:2]} is not a GST state code"
    if _check_char(g[:14]) != g[14]:
        return "The last character does not match — check for a typing mistake"
    return None


def normalise_gstin(gstin: str | None) -> str | None:
    g = (gstin or "").strip().upper().replace(" ", "")
    return g or None
