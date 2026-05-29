"""Small Language Model service boundary.

This module is intentionally constrained: it may explain deterministic outputs,
ask clarification questions, and assist normalization. It must not select,
override, or modify ITR classification results.
"""

from typing import Any, Protocol

EXPLANATION_PROMPT = (
    "Explain why this ITR was selected using reason codes. "
    "Do not decide ITR, do not add tax advice, and do not contradict the "
    "deterministic candidate_itr."
)

CLARIFICATION_PROMPT = (
    "Ask the minimum question required to resolve missing fields. "
    "Ask one concise question only. Do not decide ITR."
)

NORMALIZATION_PROMPT = (
    "Normalize user input into structured fields only. "
    "Do not classify ITR or infer tax-law conclusions."
)


class SLMClient(Protocol):
    """Future-swappable client interface for vLLM/OpenAI-compatible backends."""

    def complete(self, prompt: str, payload: dict[str, Any]) -> str:
        """Return model text for a bounded prompt and structured payload."""


class MockSLMClient:
    """Deterministic placeholder SLM client used until model serving is wired."""

    def __init__(self, fixed_response: str | None = None) -> None:
        self.fixed_response = fixed_response

    def complete(self, prompt: str, payload: dict[str, Any]) -> str:
        if self.fixed_response is not None:
            return self.fixed_response
        if prompt == EXPLANATION_PROMPT:
            return _mock_explanation(payload)
        if prompt == CLARIFICATION_PROMPT:
            return _mock_question(payload)
        return "Normalized structured fields are ready for deterministic validation."


class SLMService:
    """Safe SLM facade for explanation, clarification, and normalization help."""

    def __init__(self, client: SLMClient | None = None) -> None:
        self.client = client or MockSLMClient()

    def generate_explanation(
        self,
        *,
        candidate_itr: str,
        reason_codes: list[str],
        missing_fields: list[str],
    ) -> str:
        payload = {
            "candidate_itr": candidate_itr,
            "reason_codes": reason_codes,
            "missing_fields": missing_fields,
        }
        output = self.client.complete(EXPLANATION_PROMPT, payload)
        return self._safe_explanation(output, payload)

    def generate_clarification_question(
        self,
        *,
        missing_fields: list[str],
        context: dict[str, Any],
    ) -> str:
        payload = {"missing_fields": missing_fields, "context": context}
        output = self.client.complete(CLARIFICATION_PROMPT, payload)
        return self._safe_question(output, missing_fields)

    def normalize_user_input(self, raw_input: dict[str, Any]) -> dict[str, Any]:
        self.client.complete(NORMALIZATION_PROMPT, {"raw_input": raw_input})
        return dict(raw_input)

    def _safe_explanation(self, output: str, payload: dict[str, Any]) -> str:
        candidate_itr = payload["candidate_itr"]
        if _contains_itr_override(output, candidate_itr) or _contains_tax_advice(output):
            return _fallback_explanation(payload)
        if candidate_itr and candidate_itr not in output:
            return _fallback_explanation(payload)
        return output

    def _safe_question(self, output: str, missing_fields: list[str]) -> str:
        if _contains_tax_advice(output) or "ITR-" in output:
            return _fallback_question(missing_fields)
        question = output.strip()
        if not question.endswith("?"):
            question = f"{question}?"
        return question


def get_default_slm_service() -> SLMService:
    return SLMService()


def _mock_explanation(payload: dict[str, Any]) -> str:
    candidate_itr = payload["candidate_itr"]
    reason_codes = payload["reason_codes"]
    missing_fields = payload["missing_fields"]
    simpler_form_reasons = _simpler_form_reasons(reason_codes)
    selected_reasons = _selected_itr_reasons(candidate_itr, reason_codes)
    review_reasons = _review_reasons(reason_codes, missing_fields)

    sections = [
        f"The deterministic engine selected {candidate_itr}.",
        "",
        "Why simpler forms are not allowed:",
        *_bullet_lines(simpler_form_reasons),
        "",
        f"Why {candidate_itr} is the correct candidate:",
        *_bullet_lines(selected_reasons),
    ]

    if review_reasons:
        sections.extend(["", "Review notes:", *_bullet_lines(review_reasons)])

    return "\n".join(sections)


def _mock_question(payload: dict[str, Any]) -> str:
    missing_fields = payload["missing_fields"]
    return _fallback_question(missing_fields)


def _fallback_explanation(payload: dict[str, Any]) -> str:
    return _mock_explanation(payload)


def _simpler_form_reasons(reason_codes: list[str]) -> list[str]:
    reasons = []
    grouped = {
        "ITR-1": [
            ("NOT_RESIDENT", "the taxpayer is not a simple resident individual case"),
            ("TOTAL_INCOME_ABOVE_50_LAKH", "total income is above the simple return threshold"),
            ("BUSINESS_PROFESSION_INCOME", "business or professional income is present"),
            ("CAPITAL_GAINS", "capital gains are present"),
            ("FOREIGN_ASSETS_OR_INCOME", "foreign assets or foreign income are present"),
            ("DIRECTOR_IN_COMPANY", "the taxpayer is a company director"),
            ("UNLISTED_EQUITY_HELD", "unlisted equity is held"),
            ("SPECIAL_CONDITION", "special reporting conditions are present"),
        ],
        "ITR-2": [
            ("BUSINESS_PROFESSION_INCOME", "business or professional income is present"),
        ],
        "ITR-4": [
            ("NOT_RESIDENT", "the taxpayer is not a resident case eligible for this form"),
            ("NOT_PRESUMPTIVE", "business or professional income is not confirmed as presumptive"),
            ("TOTAL_INCOME_ABOVE_50_LAKH", "total income is above the presumptive return threshold"),
            ("SHORT_TERM_CAPITAL_GAINS", "short-term capital gains are present"),
            ("112A_LTCG_ABOVE_THRESHOLD", "LTCG under section 112A is above the permitted threshold"),
            ("OTHER_LTCG", "non-112A long-term capital gains are present"),
            ("LAND_BUILDING_CAPITAL_GAINS", "capital gains from land or building are present"),
            ("SPECIAL_RATE_CAPITAL_GAINS", "special-rate capital gains are present"),
            ("AGRICULTURAL_INCOME_ABOVE_THRESHOLD", "agricultural income is above the permitted threshold"),
            ("FOREIGN_ASSETS_OR_INCOME", "foreign assets or foreign income are present"),
            ("SPECIAL_CONDITION", "special reporting conditions are present"),
        ],
    }

    for form_name, mappings in grouped.items():
        form_reasons = [
            text
            for marker, text in mappings
            if any(code.startswith(form_name.replace("-", "")) and marker in code for code in reason_codes)
        ]
        if form_reasons:
            reasons.append(f"{form_name} is not suitable because {_join_phrases(form_reasons)}.")

    return reasons or ["No simpler-form exclusion was reported by the deterministic engine."]


def _selected_itr_reasons(candidate_itr: str, reason_codes: list[str]) -> list[str]:
    candidate_reason_map = {
        "ITR-1": "the profile fits the simple resident individual return conditions",
        "ITR-2": "there is no business or professional income, but the case is beyond a simple ITR-1 profile",
        "ITR-3": "business or professional income is present, so the case belongs in the business/profession return path",
        "ITR-4": "presumptive business or professional income conditions are satisfied",
        "ITR-5": "the entity is a non-company entity that does not fall under the institutional return path",
        "ITR-6": "the entity is a company and no ITR-7 institutional signal has priority",
        "ITR-7": "institutional, trust, exemption, or similar ITR-7 signals are present",
    }
    reasons = [candidate_reason_map.get(candidate_itr, "this is the highest-priority eligible form.")]

    if any("FOREIGN_ASSETS_OR_INCOME" in code for code in reason_codes):
        reasons.append("foreign asset or foreign income reporting makes the case compliance-sensitive")
    if candidate_itr != "ITR-4" and any("CAPITAL_GAINS" in code for code in reason_codes):
        reasons.append("capital gains require schedules that simpler forms cannot handle")
    if "ITR4_ALLOWED_112A_LTCG_WITHIN_THRESHOLD" in reason_codes:
        reasons.append(
            "ITR-4 remains allowed because the only capital gain is LTCG under section 112A within the permitted threshold"
        )
    if "ITR4_ALLOWED_AGRICULTURAL_INCOME_WITHIN_THRESHOLD" in reason_codes:
        reasons.append("agricultural income is within the permitted threshold")
    if any("DIRECTOR_IN_COMPANY" in code for code in reason_codes):
        reasons.append("director status requires additional reporting checks")
    if any("UNLISTED_EQUITY_HELD" in code for code in reason_codes):
        reasons.append("unlisted equity holding requires additional reporting checks")

    return reasons


def _review_reasons(reason_codes: list[str], missing_fields: list[str]) -> list[str]:
    reasons = []
    if "HUMAN_REVIEW_SIGNAL_PRESENT" in reason_codes:
        reasons.append("This case requires expert review before filing.")
    if "MISSING_FIELDS_PRESENT" in reason_codes and missing_fields:
        reasons.append(
            f"The decision still depends on unresolved information: {_join_phrases([_field_label(field) for field in missing_fields])}."
        )
    if any("PRESUMPTIVE_STATUS_UNKNOWN" in code for code in reason_codes):
        reasons.append("Presumptive taxation status is not fully resolved.")
    return reasons


def _bullet_lines(items: list[str]) -> list[str]:
    return [f"- {item}" for item in items]


def _join_phrases(items: list[str]) -> str:
    unique_items = list(dict.fromkeys(items))
    if len(unique_items) == 1:
        return unique_items[0]
    return ", ".join(unique_items[:-1]) + f", and {unique_items[-1]}"


def _field_label(field: str) -> str:
    labels = {
        "income_heads.business_profession.presumptive_taxation": "whether professional income is under presumptive taxation",
        "foreign_assets.has_foreign_assets": "whether foreign assets are held",
        "foreign_assets.has_foreign_income": "whether foreign income is present",
        "special_conditions.brought_forward_losses": "whether brought-forward losses exist",
        "special_conditions.capital_gains_edge_case": "whether RSU or capital-gain classification is unclear",
    }
    return labels.get(field, field.replace("_", " ").replace(".", " "))


def _fallback_question(missing_fields: list[str]) -> str:
    first_missing = missing_fields[0] if missing_fields else "the missing tax profile field"
    question_map = {
        "previous_year": (
            "Which previous year should we use for this return, for example 2025-26?"
        ),
        "return_filing_reason.type": (
            "What is the filing reason: voluntary, mandatory, notice, or unknown?"
        ),
        "is_defective_return_case": (
            "Is this being filed as a defective return correction: yes, no, or unknown?"
        ),
        "income_heads.business_profession.presumptive_taxation": (
            "Is the business or profession income being reported under presumptive taxation: yes, no, or unknown?"
        ),
        "foreign_assets.has_foreign_assets": (
            "Did you hold any foreign asset during the relevant previous year: yes, no, or unknown?"
        ),
        "foreign_assets.has_foreign_income": (
            "Did you have any foreign income during the relevant previous year: yes, no, or unknown?"
        ),
        "residency_status.status": "What was your residential status for the relevant previous year?",
        "special_conditions.brought_forward_losses": (
            "Are there any brought-forward capital or business losses to consider: yes, no, or unknown?"
        ),
        "special_conditions.capital_gains_edge_case": (
            "Are any RSU, foreign security, or capital-gain classifications unclear: yes, no, or unknown?"
        ),
    }
    return question_map.get(first_missing, f"Please provide {first_missing}?")


def _humanize_reason(code: str) -> str:
    return code.lower().replace("_", " ")


def _contains_itr_override(output: str, candidate_itr: str) -> bool:
    itr_mentions = {part.strip(".,;:()[]") for part in output.split() if part.startswith("ITR-")}
    return any(itr != candidate_itr for itr in itr_mentions)


def _contains_tax_advice(output: str) -> bool:
    lowered = output.lower()
    blocked_phrases = (
        "legal advice",
        "guaranteed",
        "you must file",
        "final legal",
        "ignore the deterministic",
    )
    return any(phrase in lowered for phrase in blocked_phrases)
