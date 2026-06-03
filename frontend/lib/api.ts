import type {
  BasicFormState,
  Acknowledgement,
  CanonicalTaxProfile,
  ClarificationResponse,
  DocumentRecord,
  DocumentType,
  ExtractionResult,
  ExplanationResponse,
  FilingApproval,
  FilingConsent,
  FilingPackage,
  FilingReadinessResult,
  FilingSubmission,
  ProviderDiagnostics,
  ITRDecisionResponse,
  ItrExport,
  ItrExportArtifact,
  MergeExtractionResult,
  TaxComputationResult,
  ValidationReport,
} from "@/types/itr";
import { normalizeAadhaar } from "./aadhaar";
import { demoAuthHeaders } from "./auth";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "";

type ApiErrorBody = {
  error?: string;
  message?: string;
  detail?: unknown;
  details?: unknown;
};

async function postJson<TResponse>(path: string, payload: unknown): Promise<TResponse> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...demoAuthHeaders(),
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
  const aadhaarNumber = normalizeAadhaar(form.aadhaar);

  return postJson<CanonicalTaxProfile>("/v1/normalize", {
    pan: form.pan,
    aadhaar_number: aadhaarNumber || undefined,
    assessment_year: "2026-27",
    previous_year: form.previousYear || undefined,
    taxpayer_name: form.taxpayerName || undefined,
    entity_type: form.entityType,
    residency_status: form.residency,
    salary_income: Number(form.salaryIncome || 0),
    employer_name: form.employerName || undefined,
    standard_deduction: Number(form.standardDeduction || 0),
    professional_tax: Number(form.professionalTax || 0),
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
    stcg_amount: Number(form.stcgAmount || 0),
    other_ltcg_amount: Number(form.otherLtcgAmount || 0),
    other_sources_income: Number(form.otherSourcesIncome || 0),
    other_sources_interest: Number(form.otherSourcesInterest || 0),
    interest_savings_amount: Number(form.savingsInterest || form.otherSourcesInterest || 0),
    interest_fixed_deposit_amount: Number(form.fixedDepositInterest || 0),
    house_property_interest: Number(form.housePropertyInterest || 0),
    agricultural_income_amount: Number(form.agriculturalIncome || 0),
    tds_salary: Number(form.tdsSalary || 0),
    tds_other: Number(form.tdsOther || 0),
    tcs: Number(form.tcs || 0),
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
    section_80c_amount: Number(form.deduction80CAmount || 0),
    section_80d_amount: Number(form.deduction80DAmount || 0),
    has_deductions: form.has80C === "yes" || form.has80D === "yes" ? "yes" : form.hasDeductions,
  });
}

export async function uploadDocument(file: File, documentType: DocumentType): Promise<DocumentRecord> {
  const formData = new FormData();
  formData.append("document_type", documentType);
  formData.append("file", file);

  const response = await fetch(`${API_BASE_URL}/v1/uploads`, {
    method: "POST",
    headers: demoAuthHeaders(),
    body: formData,
  });

  if (!response.ok) {
    const errorBody = await response.text();
    throw new Error(toFriendlyErrorMessage("/v1/uploads", response.status, errorBody));
  }

  return (await response.json()) as DocumentRecord;
}

export function extractDocument(documentId: string): Promise<ExtractionResult> {
  return postJson<ExtractionResult>(`/v1/uploads/${documentId}/extract`, {});
}

export function mergeExtractionFields(
  currentPayload: BasicFormState,
  extractionResult: ExtractionResult,
  approvedFieldIds: string[],
): Promise<MergeExtractionResult> {
  return postJson<MergeExtractionResult>("/v1/intake/merge-extractions", {
    current_payload: currentPayload,
    extraction_result: extractionResult,
    approved_field_ids: approvedFieldIds,
  });
}

export function applyMergedPayloadToForm(
  currentForm: BasicFormState,
  mergedPayload: Record<string, unknown>,
): BasicFormState {
  const nextForm = { ...currentForm } as Record<string, string>;
  for (const [key, value] of Object.entries(mergedPayload)) {
    if (key in nextForm) {
      nextForm[key] = String(value);
    }
  }
  return nextForm as BasicFormState;
}

function toFriendlyErrorMessage(path: string, status: number, rawBody: string): string {
  const body = parseErrorBody(rawBody);
  const detailText = JSON.stringify(body?.detail ?? body?.details ?? "").toLowerCase();
  const messageText = `${body?.message ?? ""} ${body?.error ?? ""} ${detailText}`.toLowerCase();

  if (messageText.includes("schema export is not ready") || messageText.includes("failed validation blocks approval")) {
    return "Approval cannot be requested yet because schema export is not ready. Please generate a schema-validated export first.";
  }
  if (messageText.includes("filing submission is blocked") || messageText.includes("submission is not ready yet")) {
    return "Submission is not ready yet. Complete consent, reviewer approval, and export validation first.";
  }
  if (messageText.includes("schema_pack_not_configured") || messageText.includes("no active schema pack")) {
    return "Export validation is not configured for this ITR form and assessment year. Load or activate a demo schema pack before requesting approval or mock filing.";
  }
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
  if (status === 401) {
    return "Please sign in before continuing.";
  }
  if (status === 403) {
    return "You do not have access to this record. Switch to the correct demo user or organization.";
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

export function computeTax({
  profile,
  decision,
  validationReport,
}: {
  profile: CanonicalTaxProfile;
  decision: ITRDecisionResponse;
  validationReport: ValidationReport | null;
}): Promise<TaxComputationResult> {
  return postJson<TaxComputationResult>("/v1/tax/compute", {
    profile,
    candidate_itr: decision,
    validation_report: validationReport,
  });
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

export function runValidation({
  profile,
  documents,
  extractions,
  approvedFieldIds,
}: {
  profile: CanonicalTaxProfile;
  documents: DocumentRecord[];
  extractions: ExtractionResult[];
  approvedFieldIds: string[];
}): Promise<ValidationReport> {
  return postJson<ValidationReport>("/v1/validation/run", {
    profile_id: "frontend-profile",
    session_id: "frontend-session",
    profile,
    documents,
    extractions,
    approved_field_ids: approvedFieldIds,
  });
}

export function generateFilingPackage({
  profile,
  decision,
  validationReport,
  taxComputation,
  documents,
}: {
  profile: CanonicalTaxProfile;
  decision: ITRDecisionResponse;
  validationReport: ValidationReport;
  taxComputation: TaxComputationResult;
  documents: DocumentRecord[];
}): Promise<FilingPackage> {
  return postJson<FilingPackage>("/v1/filing-packages/generate", {
    profile,
    candidate_itr: decision,
    validation_report: validationReport,
    tax_computation_result: taxComputation,
    documents,
  });
}

export async function downloadFilingPackageArtifact(packageId: string, artifactId: string): Promise<Blob> {
  const response = await fetch(`${API_BASE_URL}/v1/filing-packages/${packageId}/artifacts/${artifactId}`, {
    headers: demoAuthHeaders(),
  });
  if (!response.ok) {
    const errorBody = await response.text();
    throw new Error(toFriendlyErrorMessage("/v1/filing-packages/artifacts", response.status, errorBody));
  }
  return response.blob();
}

export function generateItrExport({
  packageId,
  profile,
  decision,
  validationReport,
  taxComputation,
}: {
  packageId: string;
  profile: CanonicalTaxProfile;
  decision: ITRDecisionResponse;
  validationReport: ValidationReport;
  taxComputation: TaxComputationResult;
}): Promise<ItrExport> {
  return postJson<ItrExport>("/v1/itr-exports/generate", {
    package_id: packageId,
    profile,
    candidate_itr: decision,
    validation_report: validationReport,
    tax_computation_result: taxComputation,
  });
}

export async function downloadItrExportArtifact(exportId: string, artifact: ItrExportArtifact): Promise<Blob> {
  const response = await fetch(`${API_BASE_URL}/v1/itr-exports/${exportId}/artifacts/${artifact.artifact_id}`, {
    headers: demoAuthHeaders(),
  });
  if (!response.ok) {
    const errorBody = await response.text();
    throw new Error(toFriendlyErrorMessage("/v1/itr-exports/artifacts", response.status, errorBody));
  }
  return response.blob();
}

export function createFilingSubmission(packageId: string, exportId: string): Promise<FilingSubmission> {
  return postJson<FilingSubmission>("/v1/filing/submissions", { package_id: packageId, export_id: exportId });
}

export function checkFilingReadiness(submissionId: string): Promise<FilingReadinessResult> {
  return postJson<FilingReadinessResult>(`/v1/filing/submissions/${submissionId}/readiness`, {});
}

export function submitFilingSubmission(submissionId: string): Promise<FilingSubmission> {
  return postJson<FilingSubmission>(`/v1/filing/submissions/${submissionId}/submit`, {});
}

export function refreshFilingStatus(submissionId: string): Promise<FilingSubmission> {
  return postJson<FilingSubmission>(`/v1/filing/submissions/${submissionId}/status-check`, {});
}

export function requestFilingConsent(
  packageId: string,
  exportId: string,
  consentText: string,
): Promise<FilingConsent> {
  return postJson<FilingConsent>("/v1/filing/consents/request", {
    package_id: packageId,
    export_id: exportId,
    consent_text: consentText,
  });
}

export function grantFilingConsent(consentId: string): Promise<FilingConsent> {
  return postJson<FilingConsent>(`/v1/filing/consents/${consentId}/grant`, {});
}

export function revokeFilingConsent(consentId: string): Promise<FilingConsent> {
  return postJson<FilingConsent>(`/v1/filing/consents/${consentId}/revoke`, {});
}

export function requestFilingApproval(packageId: string, exportId: string): Promise<FilingApproval> {
  return postJson<FilingApproval>("/v1/filing/approvals/request", { package_id: packageId, export_id: exportId });
}

export function approveFilingApproval(approvalId: string): Promise<FilingApproval> {
  return postJson<FilingApproval>(`/v1/filing/approvals/${approvalId}/approve`, {});
}

export function rejectFilingApproval(approvalId: string): Promise<FilingApproval> {
  return postJson<FilingApproval>(`/v1/filing/approvals/${approvalId}/reject`, {});
}

export function initiateEVerification(submissionId: string): Promise<FilingSubmission> {
  return postJson<FilingSubmission>(`/v1/filing/submissions/${submissionId}/everification/initiate`, {});
}

export async function getEVerificationStatus(submissionId: string): Promise<FilingSubmission> {
  const response = await fetch(`${API_BASE_URL}/v1/filing/submissions/${submissionId}/everification`, {
    headers: demoAuthHeaders(),
  });
  if (!response.ok) {
    const errorBody = await response.text();
    throw new Error(toFriendlyErrorMessage("/v1/filing/submissions/everification", response.status, errorBody));
  }
  return (await response.json()) as FilingSubmission;
}

export async function getAcknowledgement(submissionId: string): Promise<Acknowledgement> {
  const response = await fetch(`${API_BASE_URL}/v1/filing/submissions/${submissionId}/acknowledgement`, {
    headers: demoAuthHeaders(),
  });
  if (!response.ok) {
    const errorBody = await response.text();
    throw new Error(toFriendlyErrorMessage("/v1/filing/submissions/acknowledgement", response.status, errorBody));
  }
  return (await response.json()) as Acknowledgement;
}

export async function getProviderDiagnostics(): Promise<ProviderDiagnostics> {
  const response = await fetch(`${API_BASE_URL}/v1/filing/provider-diagnostics`, {
    headers: demoAuthHeaders(),
  });
  if (!response.ok) {
    const errorBody = await response.text();
    throw new Error(toFriendlyErrorMessage("/v1/filing/provider-diagnostics", response.status, errorBody));
  }
  return (await response.json()) as ProviderDiagnostics;
}
