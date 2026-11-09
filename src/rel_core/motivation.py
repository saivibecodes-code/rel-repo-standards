"""
Canonical Motivation Scoring & Priority Tiering Engine.
Defines standardized scoring weights, compound distress multipliers, and lead prioritization.
"""

from __future__ import annotations

from typing import Any

DISTRESS_WEIGHTS = {
    "has_pre_foreclosure": 40,
    "has_auction_scheduled": 15,
    "has_tax_lawsuit": 35,
    "has_delinquent_tax": 25,
    "has_probate": 25,
    "is_unsettled_estate": 10,
    "has_hoa_lien": 15,
    "is_absentee": 10,
    "non_homestead": 5,
}


def calculate_motivation_score(flags: dict[str, Any]) -> int:
    """Calculate normalized motivation score (0 - 100) based on weighted distress signals.
    
    Args:
        flags: Dictionary containing boolean/integer indicators e.g.:
               has_pre_foreclosure, has_auction_scheduled, has_delinquent_tax,
               has_tax_lawsuit, has_probate, is_absentee, is_unsettled_estate
               
    Returns:
        Integer score clamped between 0 and 100
    """
    score = 0
    distress_signals = 0

    if flags.get("has_pre_foreclosure"):
        score += DISTRESS_WEIGHTS["has_pre_foreclosure"]
        distress_signals += 1

    if flags.get("has_auction_scheduled"):
        score += DISTRESS_WEIGHTS["has_auction_scheduled"]

    if flags.get("has_tax_lawsuit"):
        score += DISTRESS_WEIGHTS["has_tax_lawsuit"]
        distress_signals += 1

    if flags.get("has_delinquent_tax"):
        score += DISTRESS_WEIGHTS["has_delinquent_tax"]
        distress_signals += 1

    if flags.get("has_probate") or flags.get("is_probate"):
        score += DISTRESS_WEIGHTS["has_probate"]
        distress_signals += 1

    if flags.get("is_unsettled_estate"):
        score += DISTRESS_WEIGHTS["is_unsettled_estate"]

    if flags.get("has_hoa_lien") or flags.get("is_hoa_lien"):
        score += DISTRESS_WEIGHTS["has_hoa_lien"]
        distress_signals += 1

    if flags.get("is_absentee"):
        score += DISTRESS_WEIGHTS["is_absentee"]

    # Compound multiplier: overlapping distress signals amplify seller motivation
    if distress_signals >= 3:
        score = int(score * 1.2)
    elif distress_signals >= 2:
        score = int(score * 1.1)

    return min(100, max(0, score))


def get_priority_tier(score: int, has_auction: bool = False) -> str:
    """Determine human-readable operational priority tier.
    
    Args:
        score: Motivation score (0 - 100)
        has_auction: True if a public foreclosure auction date is scheduled
        
    Returns:
        One of: 'URGENT', 'HIGH', 'MEDIUM', 'WATCHLIST'
    """
    if has_auction or score >= 60:
        return "URGENT"
    if score >= 40:
        return "HIGH"
    if score >= 20:
        return "MEDIUM"
    return "WATCHLIST"
