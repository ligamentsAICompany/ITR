"""Versioned legal-pack values consumed by deterministic rules.

These values are deliberately centralized so rule logic does not embed
assessment-year thresholds inline.
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Any


@dataclass(frozen=True)
class ITR4EligibilityLimits:
    total_income_limit: int
    ltcg_112a_limit: int
    agricultural_income_limit: int


@dataclass(frozen=True)
class TaxSlab:
    lower: int
    upper: int | None
    rate: Decimal


@dataclass(frozen=True)
class DeductionLimitConfig:
    section_code: str
    limit: int
    notes: str


@dataclass(frozen=True)
class TaxRegimeConfig:
    regime_id: str
    label: str
    slabs: tuple[TaxSlab, ...]
    standard_deduction: int
    rebate_threshold: int
    rebate_limit: int
    cess_rate: Decimal
    surcharge_rules: tuple[dict[str, Any], ...]
    deduction_limits: tuple[DeductionLimitConfig, ...]
    special_rate_rules: tuple[dict[str, Any], ...]


@dataclass(frozen=True)
class TaxComputationPack:
    assessment_year: str
    previous_year: str
    old_regime: TaxRegimeConfig
    new_regime: TaxRegimeConfig
    default_regime: str


@dataclass(frozen=True)
class LegalPack:
    version: str
    itr4: ITR4EligibilityLimits
    tax_computation: TaxComputationPack


DEFAULT_LEGAL_PACK_VERSION = "AY2026-27"

LEGAL_PACKS = {
    "AY2026-27": LegalPack(
        version="AY2026-27",
        itr4=ITR4EligibilityLimits(
            total_income_limit=5_000_000,
            ltcg_112a_limit=125_000,
            agricultural_income_limit=5_000,
        ),
        tax_computation=TaxComputationPack(
            assessment_year="2026-27",
            previous_year="2025-26",
            default_regime="new",
            old_regime=TaxRegimeConfig(
                regime_id="old",
                label="Old regime",
                slabs=(
                    TaxSlab(lower=0, upper=250_000, rate=Decimal("0")),
                    TaxSlab(lower=250_000, upper=500_000, rate=Decimal("0.05")),
                    TaxSlab(lower=500_000, upper=1_000_000, rate=Decimal("0.20")),
                    TaxSlab(lower=1_000_000, upper=None, rate=Decimal("0.30")),
                ),
                standard_deduction=50_000,
                rebate_threshold=500_000,
                rebate_limit=12_500,
                cess_rate=Decimal("0.04"),
                surcharge_rules=(),
                deduction_limits=(
                    DeductionLimitConfig("80C", 150_000, "Requires legal verification for AY2026-27."),
                    DeductionLimitConfig("80D", 25_000, "Base non-senior-citizen limit; requires verification."),
                    DeductionLimitConfig("80CCD(1B)", 50_000, "Requires legal verification for AY2026-27."),
                ),
                special_rate_rules=(),
            ),
            new_regime=TaxRegimeConfig(
                regime_id="new",
                label="New regime",
                slabs=(
                    TaxSlab(lower=0, upper=400_000, rate=Decimal("0")),
                    TaxSlab(lower=400_000, upper=800_000, rate=Decimal("0.05")),
                    TaxSlab(lower=800_000, upper=1_200_000, rate=Decimal("0.10")),
                    TaxSlab(lower=1_200_000, upper=1_600_000, rate=Decimal("0.15")),
                    TaxSlab(lower=1_600_000, upper=2_000_000, rate=Decimal("0.20")),
                    TaxSlab(lower=2_000_000, upper=2_400_000, rate=Decimal("0.25")),
                    TaxSlab(lower=2_400_000, upper=None, rate=Decimal("0.30")),
                ),
                standard_deduction=75_000,
                rebate_threshold=1_200_000,
                rebate_limit=60_000,
                cess_rate=Decimal("0.04"),
                surcharge_rules=(),
                deduction_limits=(),
                special_rate_rules=(),
            ),
        ),
    )
}


def legal_pack_for_profile(profile: dict[str, Any]) -> LegalPack:
    assessment_year = profile.get("assessment_year")
    version = f"AY{assessment_year}" if assessment_year else DEFAULT_LEGAL_PACK_VERSION
    return LEGAL_PACKS.get(version, LEGAL_PACKS[DEFAULT_LEGAL_PACK_VERSION])
