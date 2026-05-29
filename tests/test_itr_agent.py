from app.agents.itr_agent import ITRAgent


class FakeAPIClient:
    def __init__(self, responses):
        self.responses = {path: list(values) for path, values in responses.items()}
        self.calls = []

    def post(self, path, payload):
        self.calls.append((path, payload))
        queue = self.responses[path]
        if len(queue) > 1:
            return queue.pop(0)
        return queue[0]


def profile():
    return {
        "schema_version": "canonical-tax-profile/v0.1",
        "assessment_year": "2026-27",
        "previous_year": "2025-26",
        "return_filing_reason": {"type": "voluntary"},
        "is_defective_return_case": "no",
        "user_identity": {"pan": "ABCDE1234F"},
        "entity_type": "individual",
        "residency_status": {"status": "resident"},
        "income_heads": {
            "salary": {"has_income": "yes", "gross_amount": 1200000},
            "house_property": {"has_income": "no", "gross_amount": 0},
            "capital_gains": {"has_income": "no", "gross_amount": 0},
            "business_profession": {
                "has_income": "no",
                "gross_amount": 0,
                "presumptive_taxation": "no",
            },
            "other_sources": {"has_income": "no", "gross_amount": 0},
        },
        "deductions": {"has_deductions": "unknown", "section_claims": []},
        "foreign_assets": {"has_foreign_assets": "no", "has_foreign_income": "no"},
        "exemptions_flags": {
            "claims_section_11_exemption": "no",
            "trust_or_institution_case": "no",
            "political_party_case": "no",
            "university_or_research_case": "no",
        },
        "special_conditions": {
            "director_in_company": "no",
            "unlisted_equity_held": "no",
            "brought_forward_losses": "no",
            "esop_tax_deferred": "no",
            "audit_required": "no",
            "presumptive_taxation_ambiguity": "no",
            "business_profession_ambiguity": "no",
            "capital_gains_edge_case": "no",
            "evidence_mismatch": "no",
            "low_confidence_extraction": "no",
            "pack_resolution_conflict": "no",
        },
    }


def test_agent_full_valid_case_calls_versioned_apis_and_explains():
    client = FakeAPIClient(
        {
            "/v1/itr-decision": [
                {
                    "candidate_itr": "ITR-1",
                    "reason_codes": ["ITR1_ELIGIBLE_SIMPLE_RESIDENT_INDIVIDUAL"],
                    "missing_fields": [],
                    "confidence": "high",
                }
            ],
            "/v1/missing-fields": [{"missing_fields": []}],
            "/v1/explain": [
                {
                    "candidate_itr": "ITR-1",
                    "explanation": "The deterministic engine selected ITR-1.",
                    "reason_codes": ["ITR1_ELIGIBLE_SIMPLE_RESIDENT_INDIVIDUAL"],
                    "missing_fields": [],
                    "confidence": "high",
                }
            ],
        }
    )

    result = ITRAgent(client).run(profile())
    print("full valid agent result", result)

    assert result["decision"]["candidate_itr"] == "ITR-1"
    assert result["explanation"]["candidate_itr"] == "ITR-1"
    assert result["escalation"] is False
    assert "decision_router_node: route=explain reason=no_missing_fields" in result["execution_log"]
    assert [path for path, _ in client.calls] == [
        "/v1/itr-decision",
        "/v1/missing-fields",
        "/v1/explain",
    ]


def test_agent_low_confidence_with_missing_fields_clarifies_before_escalating():
    client = FakeAPIClient(
        {
            "/v1/itr-decision": [
                {
                    "candidate_itr": "ITR-1",
                    "reason_codes": ["MISSING_FIELDS_PRESENT"],
                    "missing_fields": ["previous_year"],
                    "confidence": "low",
                }
            ],
            "/v1/missing-fields": [
                {"missing_fields": ["previous_year"]},
            ],
            "/v1/clarify": [{"question": "Please provide previous_year?"}],
        }
    )

    result = ITRAgent(client, max_clarification_iterations=3).run(profile())
    print("low confidence agent result", result)

    assert result["escalation"] is True
    assert result["clarification_iterations"] == 3
    assert len(result["questions_asked"]) == 3
    assert [path for path, _ in client.calls].count("/v1/clarify") == 3
    assert result["escalation_reason"] == "clarification_limit_reached"
    assert (
        "decision_router_node: route=clarify reason=clarification_available"
        in result["execution_log"]
    )


def test_agent_low_confidence_without_missing_fields_escalates():
    client = FakeAPIClient(
        {
            "/v1/itr-decision": [
                {
                    "candidate_itr": "ITR-3",
                    "reason_codes": ["HUMAN_REVIEW_SIGNAL_PRESENT"],
                    "missing_fields": [],
                    "confidence": "low",
                }
            ],
            "/v1/missing-fields": [{"missing_fields": []}],
        }
    )

    result = ITRAgent(client).run(profile())
    print("low confidence no missing agent result", result)

    assert result["escalation"] is True
    assert result["clarification_iterations"] == 0
    assert result["escalation_reason"] == "low_confidence"
    assert "decision_router_node: route=escalate reason=low_confidence" in result["execution_log"]


def test_agent_high_risk_missing_field_clarifies_then_escalates_if_unresolved():
    client = FakeAPIClient(
        {
            "/v1/itr-decision": [
                {
                    "candidate_itr": "ITR-3",
                    "reason_codes": ["MISSING_FIELDS_PRESENT"],
                    "missing_fields": ["foreign_assets.has_foreign_assets"],
                    "confidence": "medium",
                }
            ],
            "/v1/missing-fields": [{"missing_fields": ["foreign_assets.has_foreign_assets"]}],
            "/v1/clarify": [
                {"question": "Did you hold any foreign asset during the relevant previous year?"}
            ],
        }
    )

    result = ITRAgent(client).run(profile())
    print("high-risk missing agent result", result)

    assert result["decision"]["candidate_itr"] == "ITR-3"
    assert result["escalation"] is True
    assert result["clarification_iterations"] == 3
    assert result["escalation_reason"] == "unresolved_high_risk_missing_fields"
    assert [path for path, _ in client.calls].count("/v1/clarify") == 3
    assert (
        "decision_router_node: route=clarify reason=clarification_available"
        in result["execution_log"]
    )


def test_agent_normal_missing_field_routes_to_clarification_then_limit_escalates():
    client = FakeAPIClient(
        {
            "/v1/itr-decision": [
                {
                    "candidate_itr": "ITR-1",
                    "reason_codes": ["MISSING_FIELDS_PRESENT"],
                    "missing_fields": ["previous_year"],
                    "confidence": "medium",
                }
            ],
            "/v1/missing-fields": [
                {"missing_fields": ["previous_year"]},
            ],
            "/v1/clarify": [{"question": "Please provide previous_year?"}],
        }
    )

    result = ITRAgent(client, max_clarification_iterations=3).run(profile())
    print("normal missing agent result", result)

    assert result["escalation"] is True
    assert result["clarification_iterations"] == 3
    assert len(result["questions_asked"]) == 3
    assert [path for path, _ in client.calls].count("/v1/clarify") == 3
    assert result["escalation_reason"] == "clarification_limit_reached"
    assert (
        "decision_router_node: route=clarify reason=clarification_available"
        in result["execution_log"]
    )
