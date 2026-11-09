"""
Unit tests for rel_core utilities in rel-repo-standards.
"""

import pytest

from rel_core.addresses import (
    clean_address,
    normalize_street_address,
    parse_street_address,
)
from rel_core.motivation import (
    calculate_motivation_score,
    get_priority_tier,
)
from rel_core.universal_id import (
    generate_universal_id,
    parse_universal_id,
    resolve_fips,
)


def test_resolve_fips():
    assert resolve_fips("Collin") == "48085"
    assert resolve_fips("DENTON") == "48121"
    assert resolve_fips("48113") == "48113"
    with pytest.raises(ValueError):
        resolve_fips("UNKNOWN_COUNTY")


def test_generate_and_parse_universal_id():
    uid_collin = generate_universal_id("Collin", 821)
    assert uid_collin == "48085_821"

    uid_denton = generate_universal_id("48121", "100")
    assert uid_denton == "48121_100"

    fips, prop_id = parse_universal_id("48085_821")
    assert fips == "48085"
    assert prop_id == "821"


def test_clean_and_normalize_address():
    raw = "1234 North Main Street, Apt 4B."
    cleaned = clean_address(raw)
    assert "." not in cleaned
    assert "," not in cleaned

    normalized = normalize_street_address(raw)
    assert normalized == "1234 N MAIN ST APT 4B"

    norm_court = normalize_street_address("555 Elm Court")
    assert norm_court == "555 ELM CT"


def test_parse_street_address():
    num, pre_dir, street, suffix = parse_street_address("789 W ELM ST")
    assert num == "789"
    assert pre_dir == "W"
    assert street == "ELM"
    assert suffix == "ST"

    num2, pre_dir2, street2, suffix2 = parse_street_address("100 MAIN")
    assert num2 == "100"
    assert pre_dir2 is None
    assert street2 == "MAIN"
    assert suffix2 is None


def test_motivation_score_and_priority():
    flags_urgent = {
        "has_pre_foreclosure": 1,
        "has_auction_scheduled": 1,
        "has_delinquent_tax": 1,
    }
    score = calculate_motivation_score(flags_urgent)
    # (40 + 15 + 25) * 1.1 = 88
    assert score >= 80
    assert get_priority_tier(score, has_auction=True) == "URGENT"

    flags_watch = {"is_absentee": 1}
    score_watch = calculate_motivation_score(flags_watch)
    assert score_watch == 10
    assert get_priority_tier(score_watch, has_auction=False) == "WATCHLIST"
