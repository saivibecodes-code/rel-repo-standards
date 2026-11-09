"""
Canonical Universal Property Identifier module.
Standardizes property key derivation across Texas county CADs, clerk recordings, and MLS feeds.
"""

from __future__ import annotations

import re

COUNTY_FIPS_MAP = {
    "COLLIN": "48085",
    "DENTON": "48121",
    "DALLAS": "48113",
    "TARRANT": "48439",
    "ROCKWALL": "48397",
    "KAUFMAN": "48257",
    "GRAYSON": "48181",
    "WISE": "48497",
    "PARKER": "48367",
    "JOHNSON": "48251",
    "ELLIS": "48139",
}

FIPS_COUNTY_MAP = {v: k for k, v in COUNTY_FIPS_MAP.items()}


def resolve_fips(county_identifier: str) -> str:
    """Resolve a county name or FIPS code to standard 5-digit Texas FIPS.
    
    Examples:
        'Collin' -> '48085'
        '48085'  -> '48085'
        'Denton' -> '48121'
    """
    clean = str(county_identifier).strip().upper()
    if clean.isdigit() and len(clean) == 5:
        return clean
    if clean in COUNTY_FIPS_MAP:
        return COUNTY_FIPS_MAP[clean]
    raise ValueError(f"Unknown county or FIPS code: {county_identifier}")


def generate_universal_id(county_or_fips: str, prop_id: str | int) -> str:
    """Generate canonical Universal Property ID in '{fips}_{prop_id}' format.
    
    Args:
        county_or_fips: County name ('Collin', 'Denton') or 5-digit FIPS ('48085', '48121')
        prop_id: The CAD internal property ID or account number
        
    Returns:
        Canonical string e.g. '48085_821', '48121_100'
    """
    fips = resolve_fips(county_or_fips)
    clean_prop = re.sub(r"[^A-Za-z0-9]", "", str(prop_id)).strip()
    if not clean_prop:
        raise ValueError(f"Invalid prop_id: {prop_id}")
    return f"{fips}_{clean_prop}"


def parse_universal_id(universal_id: str) -> tuple[str, str]:
    """Parse a universal ID into (fips, prop_id).
    
    Args:
        universal_id: String e.g. '48085_821'
        
    Returns:
        Tuple of (fips, prop_id) e.g. ('48085', '821')
    """
    if not universal_id or "_" not in universal_id:
        raise ValueError(f"Invalid universal_id format: {universal_id}")
    fips, prop_id = universal_id.split("_", 1)
    return fips, prop_id
