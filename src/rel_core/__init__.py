"""
rel_core: Canonical zero-dependency utilities for the rel-* real estate intelligence ecosystem.
"""

from .addresses import (
    clean_address,
    normalize_street_address,
    parse_street_address,
)
from .motivation import (
    DISTRESS_WEIGHTS,
    calculate_motivation_score,
    get_priority_tier,
)
from .universal_id import (
    COUNTY_FIPS_MAP,
    FIPS_COUNTY_MAP,
    generate_universal_id,
    parse_universal_id,
    resolve_fips,
)

__all__ = [
    "COUNTY_FIPS_MAP",
    "DISTRESS_WEIGHTS",
    "FIPS_COUNTY_MAP",
    "calculate_motivation_score",
    "clean_address",
    "generate_universal_id",
    "get_priority_tier",
    "normalize_street_address",
    "parse_street_address",
    "parse_universal_id",
    "resolve_fips",
]
