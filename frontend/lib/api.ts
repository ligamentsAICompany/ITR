import type {
  BasicFormState,
  CanonicalTaxProfile,
  ClarificationResponse,
  ExplanationResponse,
  ITRDecisionResponse,
} from "@/types/itr";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

type ApiErrorBody = {
  error?: string;
  message?: string;
  details?: unknown;
};

async function postJson<TResponse>(path: string, payload: unknown): Promise<TResponse> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const errorBody = await response.text();
    throw new Error(toFriendlyErrorMessage(path, response.status, errorBody));
  }

  return (await response.json()) as TResponse;
}

export function normalizeProfile(form: BasicFormState): Promise<CanonicalTaxProfile> {
  return postJson<CanonicalTaxProfile>("/v1/normalize", {
    pan: form.pan,
    aadhaar_number: form.aadhaar || undefined,
    assessment_year: "2026-27",
    previous_year: form.previousYear || undefined,
    entity_type: form.entityType,
    residency_status: form.residency,
    salary_income: Number(form.salaryIncome || 0),
    house_property_has_income: form.housePropertyHasIncome,
    house_property_income: Number(form.housePropertyIncome || 0),
    house_property_count:
      form.housePropertyHasIncome === "yes" && form.housePropertyCount !== ""
        ? Number(form.housePropertyCount)
        : undefined,
    has_self_occupied_property: form.hasSelfOccupiedProperty,
    has_let_out_property: form.hasLetOutProperty,
    business_profession_income: Number(form.businessProfessionIncome || 0),
    capital_gains_income: Number(form.capitalGainsIncome || form.ltcg112AAmount || 0),
    has_stcg: form.hasStcg,
    has_ltcg_112a: form.hasLtcg112A,
    ltcg_112a_amount: Number(form.ltcg112AAmount || 0),
    has_other_ltcg: form.hasOtherLtcg,
    has_land_building_gains: form.hasLandBuildingGains,
    has_special_rate_capital_gains: form.hasSpecialRateCapitalGains,
    other_sources_income: Number(form.otherSourcesIncome || 0),
    agricultural_income_amount: Number(form.agriculturalIncome || 0),
    return_filing_reason: form.returnFilingReason,
    is_defective_return_case: form.isDefectiveReturnCase,
    has_foreign_assets: form.hasForeignAssets,
    has_foreign_income: form.hasForeignIncome,
    presumptive_taxation: form.presumptiveTaxation,
    director_in_company: form.directorInCompany,
    unlisted_equity_held: form.unlistedEquityHeld,
    brought_forward_losses: form.broughtForwardLosses,
    capital_gains_edge_case: form.capitalGainsEdgeCase,
    low_confidence_extraction: form.capitalGainsEdgeCase,
    section_claims: [
      ...(form.has80C === "yes" ? [{ section_code: "80C", amount: Number(form.deduction80CAmount) }] : []),
      ...(form.has80D === "yes" ? [{ section_code: "80D", amount: Number(form.deduction80DAmount) }] : []),
    ],
    has_deductions: form.has80C === "yes" || form.has80D === "yes" ? "yes" : form.hasDeductions,
  });
}

function toFriendlyErrorMessage(path: string, status: number, rawBody: string): string {
  const body = parseErrorBody(rawBody);
  const detailText = JSON.stringify(body?.details ?? "").toLowerCase();
  const messageText = `${body?.message ?? ""} ${body?.error ?? ""} ${detailText}`.toLowerCase();

  if (messageText.includes("pan")) {
    return "Please enter a valid PAN (e.g., ABCDE1234F).";
  }
  if (messageText.includes("aadhaar")) {
    return "Please enter a valid Aadhaar number, or leave it blank if it is not available.";
  }
  if (body?.error === "invalid_payload") {
    return "Please remove script-like or unsafe text from the form before continuing.";
  }
  if (body?.error === "malformed_json") {
    return "The request could not be read. Please refresh and try again.";
  }
  if (status === 429) {
    return "Too many requests. Please wait a minute and try again.";
  }
  if (status >= 500) {
    return "The server could not complete this step. Please try again shortly.";
  }

  return `We could not complete ${path}. Please review the highlighted information and try again.`;
}

function parseErrorBody(rawBody: string): ApiErrorBody | null {
  try {
    return JSON.parse(rawBody) as ApiErrorBody;
  } catch {
    return null;
  }
}

export function getDecision(profile: CanonicalTaxProfile): Promise<ITRDecisionResponse> {
  return postJson<ITRDecisionResponse>("/v1/itr-decision", profile);
}

export function getMissingFields(profile: CanonicalTaxProfile): Promise<{ missing_fields: string[] }> {
  return postJson<{ missing_fields: string[] }>("/v1/missing-fields", profile);
}

export function getExplanation(decision: ITRDecisionResponse): Promise<ExplanationResponse> {
  return postJson<ExplanationResponse>("/v1/explain", decision);
}

export function getClarification(
  missingFields: string[],
  context: Record<string, unknown>,
): Promise<ClarificationResponse> {
  return postJson<ClarificationResponse>("/v1/clarify", {
    missing_fields: missingFields,
    context,
  });
}
