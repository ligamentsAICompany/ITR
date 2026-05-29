from app.services.slm_service import MockSLMClient, SLMService


def test_slm_safety_rejects_itr_override():
    service = SLMService(
        client=MockSLMClient(
            fixed_response="The deterministic engine selected ITR-4 instead."
        )
    )

    explanation = service.generate_explanation(
        candidate_itr="ITR-2",
        reason_codes=["ITR2_ELIGIBLE_NON_BUSINESS_INCOME"],
        missing_fields=[],
    )

    assert "ITR-2" in explanation
    assert "ITR-4" not in explanation
    assert "deterministic engine selected ITR-2" in explanation


def test_slm_clarification_asks_one_minimum_question():
    service = SLMService()

    question = service.generate_clarification_question(
        missing_fields=["foreign_assets.has_foreign_assets"],
        context={"candidate_itr": "ITR-2"},
    )

    assert question.endswith("?")
    assert "foreign asset" in question.lower()
    assert "ITR-2" not in question


def test_slm_explanation_groups_reason_codes_in_ca_style_language():
    service = SLMService()

    explanation = service.generate_explanation(
        candidate_itr="ITR-3",
        reason_codes=[
            "ITR4_DISQUALIFIED_NOT_PRESUMPTIVE",
            "ITR4_DISQUALIFIED_CAPITAL_GAINS",
            "ITR4_DISQUALIFIED_FOREIGN_ASSETS_OR_INCOME",
            "ITR2_DISQUALIFIED_BUSINESS_PROFESSION_INCOME",
            "ITR1_DISQUALIFIED_NOT_RESIDENT_INDIVIDUAL",
            "ITR1_DISQUALIFIED_DIRECTOR_IN_COMPANY",
            "ITR1_DISQUALIFIED_UNLISTED_EQUITY_HELD",
            "ITR3_ELIGIBLE_BUSINESS_PROFESSION",
            "MISSING_FIELDS_PRESENT",
            "HUMAN_REVIEW_SIGNAL_PRESENT",
        ],
        missing_fields=["special_conditions.capital_gains_edge_case"],
    )

    assert "Why simpler forms are not allowed" in explanation
    assert "Why ITR-3 is the correct candidate" in explanation
    assert "- ITR-1 is not suitable" in explanation
    assert "business or professional income" in explanation.lower()
    assert "foreign assets or foreign income" in explanation.lower()
    assert "expert review" in explanation.lower()
    assert "ITR4_DISQUALIFIED" not in explanation
    assert "reason codes" not in explanation.lower()
