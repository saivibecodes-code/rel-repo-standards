"""
Canonical USPS Address Normalization & Parsing Module.
Eliminates false mismatches between MLS feeds, CAD property records, and Clerk deed recordings.
"""

from __future__ import annotations

import re

DIRECTIONAL_MAP = {
    "NORTH": "N",
    "SOUTH": "S",
    "EAST": "E",
    "WEST": "W",
    "NORTHEAST": "NE",
    "NORTHWEST": "NW",
    "SOUTHEAST": "SE",
    "SOUTHWEST": "SW",
    "N": "N",
    "S": "S",
    "E": "E",
    "W": "W",
    "NE": "NE",
    "NW": "NW",
    "SE": "SE",
    "SW": "SW",
}

STREET_SUFFIX_MAP = {
    "STREET": "ST",
    "AVENUE": "AVE",
    "ROAD": "RD",
    "BOULEVARD": "BLVD",
    "DRIVE": "DR",
    "LANE": "LN",
    "COURT": "CT",
    "CIRCLE": "CIR",
    "WAY": "WAY",
    "PARKWAY": "PKWY",
    "HIGHWAY": "HWY",
    "TRACE": "TRCE",
    "TRAIL": "TRL",
    "LOOP": "LOOP",
    "RUN": "RUN",
    "PASS": "PASS",
    "BEND": "BND",
    "CROSSING": "XING",
    "COVE": "CV",
    "PLACE": "PL",
    "TERRACE": "TER",
    "EXPRESSWAY": "EXPY",
    "FREEWAY": "FWY",
    "TURNPIKE": "TPKE",
}

UNIT_PREFIXES = {"APT", "STE", "SUITE", "UNIT", "BLDG", "BUILDING", "LOT", "SPCE", "SPACE", "#"}

STREET_NUMBER_WORDS = {
    "FIRST": "1ST",
    "SECOND": "2ND",
    "THIRD": "3RD",
    "FOURTH": "4TH",
    "FIFTH": "5TH",
    "SIXTH": "6TH",
    "SEVENTH": "7TH",
    "EIGHTH": "8TH",
    "NINTH": "9TH",
    "TENTH": "10TH",
}


def clean_address(raw_address: str) -> str:
    """Clean raw address string by stripping punctuation and normalizing whitespace."""
    if not raw_address:
        return ""
    text = str(raw_address).upper()
    # Replace commas, periods, hashes, apostrophes with spaces
    text = re.sub(r"[,.#']", " ", text)
    # Strip non-alphanumeric except space and hyphen
    text = re.sub(r"[^A-Z0-9\s-]", "", text)
    # Consolidate whitespace
    return re.sub(r"\s+", " ", text).strip()


def normalize_street_address(raw_address: str) -> str:
    """Normalize a full street address into USPS abbreviation standard.
    
    Example:
        '1234 North Main Street, Apt 4B' -> '1234 N MAIN ST APT 4B'
    """
    cleaned = clean_address(raw_address)
    if not cleaned:
        return ""

    tokens = cleaned.split()
    normalized_tokens = []

    for t in tokens:
        # Check directional
        if t in DIRECTIONAL_MAP:
            normalized_tokens.append(DIRECTIONAL_MAP[t])
        # Check street suffix
        elif t in STREET_SUFFIX_MAP:
            normalized_tokens.append(STREET_SUFFIX_MAP[t])
        # Check numbered street words
        elif t in STREET_NUMBER_WORDS:
            normalized_tokens.append(STREET_NUMBER_WORDS[t])
        else:
            normalized_tokens.append(t)

    return " ".join(normalized_tokens)


def parse_street_address(raw_address: str) -> tuple[str | None, str | None, str | None, str | None]:
    """Parse address into (house_number, pre_directional, street_name, street_suffix).
    
    Example:
        '789 W ELM ST' -> ('789', 'W', 'ELM', 'ST')
        '100 MAIN' -> ('100', None, 'MAIN', None)
    """
    norm = normalize_street_address(raw_address)
    if not norm:
        return None, None, None, None

    tokens = norm.split()
    if not tokens:
        return None, None, None, None

    # First token must be a house number
    if not re.match(r"^\d+", tokens[0]):
        return None, None, None, None

    house_num = tokens[0]
    idx = 1
    pre_dir = None

    if idx < len(tokens) and tokens[idx] in {"N", "S", "E", "W", "NE", "NW", "SE", "SW"}:
        pre_dir = tokens[idx]
        idx += 1

    if idx >= len(tokens):
        return house_num, pre_dir, None, None

    street_parts = []
    suffix = None

    while idx < len(tokens):
        token = tokens[idx]
        if token in UNIT_PREFIXES:
            break
        if token in set(STREET_SUFFIX_MAP.values()) and idx == len(tokens) - 1:
            suffix = token
            break
        street_parts.append(token)
        idx += 1

    street_name = " ".join(street_parts) if street_parts else None
    return house_num, pre_dir, street_name, suffix
