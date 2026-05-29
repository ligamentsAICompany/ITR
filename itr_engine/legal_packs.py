"""Versioned legal-pack values consumed by deterministic rules.

These values are deliberately centralized so rule logic does not embed
assessment-year thresholds inline.
"""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ITR4EligibilityLimits:
    total_income_limit: int
    ltcg_112a_limit: int
    agricultural_income_limit: int


@dataclass(frozen=True)
class LegalPack:
    version: str
    itr4: ITR4EligibilityLimits


DEFAULT_LEGAL_PACK_VERSION = "AY2026-27"

LEGAL_PACKS = {
    "AY2026-27": LegalPack(
        version="AY2026-27",
        itr4=ITR4EligibilityLimits(
            total_income_limit=5_000_000,
            ltcg_112a_limit=125_000,
            agricultural_income_limit=5_000,
        ),
    )
}


def legal_pack_for_profile(profile: dict[str, Any]) -> LegalPack:
    assessment_year = profile.get("assessment_year")
    version = f"AY{assessment_year}" if assessment_year else DEFAULT_LEGAL_PACK_VERSION
    return LEGAL_PACKS.get(version, LEGAL_PACKS[DEFAULT_LEGAL_PACK_VERSION])
