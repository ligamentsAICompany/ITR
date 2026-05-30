export type YesNoUnknown = "yes" | "no" | "unknown";
export type Confidence = "high" | "medium" | "low";

export type BasicFormState = {
  pan: string;
  aadhaar: string;
  entityType: string;
  residency: string;
  salaryIncome: string;
  housePropertyHasIncome: YesNoUnknown;
  housePropertyIncome: string;
  housePropertyCount: string;
  hasSelfOccupiedProperty: YesNoUnknown;
  hasLetOutProperty: YesNoUnknown;
  businessProfessionIncome: string;
  capitalGainsIncome: string;
  hasStcg: YesNoUnknown;
  hasLtcg112A: YesNoUnknown;
  ltcg112AAmount: string;
  hasOtherLtcg: YesNoUnknown;
  hasLandBuildingGains: YesNoUnknown;
  hasSpecialRateCapitalGains: YesNoUnknown;
  otherSourcesIncome: string;
  agriculturalIncome: string;
  previousYear: string;
  returnFilingReason: string;
  isDefectiveReturnCase: YesNoUnknown;
  hasForeignAssets: YesNoUnknown;
  hasForeignIncome: YesNoUnknown;
  presumptiveTaxation: YesNoUnknown;
  directorInCompany: YesNoUnknown;
  unlistedEquityHeld: YesNoUnknown;
  broughtForwardLosses: YesNoUnknown;
  capitalGainsEdgeCase: YesNoUnknown;
  hasDeductions: YesNoUnknown;
  has80C: YesNoUnknown;
  deduction80CAmount: string;
  has80D: YesNoUnknown;
  deduction80DAmount: string;
  taxpayerName: string;
  employerName: string;
  grossSalary: string;
  standardDeduction: string;
  professionalTax: string;
  tdsSalary: string;
  tdsOther: string;
  tcs: string;
  otherSourcesInterest: string;
  savingsInterest: string;
  fixedDepositInterest: string;
  housePropertyInterest: string;
  stcgAmount: string;
  otherLtcgAmount: string;
};

export type CanonicalTaxProfile = Record<string, unknown>;

export type ITRDecisionResponse = {
  candidate_itr: string;
  reason_codes: string[];
  missing_fields: string[];
  confidence: Confidence;
};

export type ExplanationResponse = ITRDecisionResponse & {
  explanation: string;
};

export type ClarificationResponse = {
  question: string;
};

export type DocumentType = "form16" | "ais" | "bank_statement" | "pdf_text" | "other";

export type DocumentRecord = {
  document_id: string;
  document_type: DocumentType;
  original_filename: string;
  safe_filename: string;
  mime_type: string;
  size: number;
  sha256: string;
  status: string;
  uploaded_at: string;
};

export type ExtractedField = {
  field_id: string;
  label: string;
  value: string | number | boolean;
  raw_path: keyof BasicFormState | string;
  canonical_path: string;
  confidence: number;
  source: {
    document_id: string;
    locator: string;
  };
};

export type ExtractionResult = {
  document_id: string;
  status: "completed" | "rejected" | "warning";
  fields: ExtractedField[];
  warnings?: string[];
};

export type MergeExtractionResult = {
  merged_payload: Record<string, unknown>;
  applied_field_ids: string[];
  skipped_field_ids: string[];
};

export type ValidationSeverity = "critical" | "high" | "medium" | "low" | "info";
export type ValidationStatus = "passed" | "warning" | "failed" | "needs_review";

export type ValidationIssue = {
  issue_id: string;
  rule_id: string;
  severity: ValidationSeverity;
  status: ValidationStatus;
  title: string;
  message: string;
  field_path: string;
  expected_value: unknown;
  actual_value: unknown;
  source_documents: string[];
  evidence_refs: string[];
  recommendation: string;
  blocks_filing_package: boolean;
};

export type ReconciliationConflict = {
  field_path: string;
  profile_value: unknown;
  extracted_value: unknown;
  source_documents: string[];
  evidence_refs: string[];
  source_confidences?: number[];
};

export type ValidationReport = {
  validation_run_id: string;
  profile_id?: string | null;
  session_id?: string | null;
  created_at: string;
  overall_status: ValidationStatus;
  readiness_score: number;
  issues: ValidationIssue[];
  missing_fields: string[];
  conflicts: ReconciliationConflict[];
  warnings: string[];
  evidence_summary: {
    document_count: number;
    approved_extracted_field_count: number;
    document_types: string[];
  };
};

export type TaxRegime = "old" | "new";

export type IncomeBreakdown = {
  salary_income: number;
  standard_deduction: number;
  house_property_income: number;
  business_profession_income: number;
  capital_gains_income: number;
  capital_gains_subtypes: Record<string, number>;
  other_sources_income: number;
  gross_total_income: number;
};

export type AppliedDeduction = {
  section_code: string;
  claimed_amount: number;
  allowed_amount: number;
  limit: number;
  notes: string;
};

export type DeductionBreakdown = {
  claimed_total: number;
  allowed_total: number;
  disallowed_total: number;
  applied: AppliedDeduction[];
};

export type TaxCreditBreakdown = {
  tds_salary: number;
  tds_other: number;
  tcs: number;
  advance_tax: number;
  self_assessment_tax: number;
  total_credits: number;
};

export type TaxComputationWarning = {
  code: string;
  message: string;
};

export type TaxComputationStep = {
  step_key: string;
  label: string;
  amount: number;
  formula: string;
};

export type TaxComputationResult = {
  computation_id: string;
  assessment_year: string;
  previous_year?: string | null;
  selected_regime: TaxRegime;
  regime_label: string;
  default_regime: TaxRegime;
  candidate_itr: string;
  is_preview: boolean;
  income: IncomeBreakdown;
  deductions: DeductionBreakdown;
  taxable_income: number;
  tax_before_rebate: number;
  rebate: number;
  surcharge: number;
  cess: number;
  total_tax_liability: number;
  credits: TaxCreditBreakdown;
  refund_due: number;
  tax_payable: number;
  warnings: TaxComputationWarning[];
  steps: TaxComputationStep[];
};

export type FilingPackageStatus =
  | "draft"
  | "needs_review"
  | "ready_for_ca_review"
  | "ready_for_export"
  | "blocked";

export type FilingPackageArtifactType =
  | "filing_summary_json"
  | "tax_computation_report"
  | "validation_report_json"
  | "draft_itr_payload"
  | "package_manifest";

export type FilingPackageWarning = {
  warning_id: string;
  severity: "critical" | "high" | "medium" | "low" | "info";
  message: string;
  source: string;
  recommendation: string;
};

export type FilingPackageArtifact = {
  artifact_id: string;
  artifact_type: FilingPackageArtifactType;
  filename: string;
  mime_type: string;
  size: number;
  sha256: string;
  created_at: string;
};

export type FilingPackage = {
  package_id: string;
  assessment_year: string;
  previous_year?: string | null;
  candidate_itr: string;
  status: FilingPackageStatus;
  readiness_score: number;
  validation_run_id: string;
  computation_id: string;
  document_ids: string[];
  warnings: FilingPackageWarning[];
  artifacts: FilingPackageArtifact[];
  created_at: string;
  updated_at: string;
};

export type FilingPackageExplanation = {
  package_id: string;
  explanation: string;
  grounded_artifact_ids: string[];
};

export type DraftItrPayload = Record<string, unknown> & {
  payload_type?: "draft_itr_payload";
  schema_status?: "internal_draft_not_official";
};

export type ItrExportStatus =
  | "not_configured"
  | "draft"
  | "schema_failed"
  | "schema_passed"
  | "ready_for_download"
  | "blocked";

export type OfficialSchemaValidationStatus = "not_configured" | "failed" | "passed" | "needs_review";

export type OfficialSchemaValidationError = {
  code: string;
  message: string;
  field_path?: string | null;
  schema_path?: string | null;
  severity: "critical" | "high" | "medium" | "low" | "info";
};

export type OfficialSchemaValidationResult = {
  validation_id: string;
  schema_pack_id?: string | null;
  candidate_itr: string;
  assessment_year: string;
  status: OfficialSchemaValidationStatus;
  errors: OfficialSchemaValidationError[];
  warnings: OfficialSchemaValidationError[];
  validated_at: string;
};

export type ItrExportArtifact = {
  artifact_id: string;
  artifact_type: "official_itr_json";
  filename: string;
  mime_type: string;
  size: number;
  sha256: string;
  created_at: string;
};

export type ItrExport = {
  export_id: string;
  package_id?: string | null;
  assessment_year: string;
  previous_year?: string | null;
  candidate_itr: string;
  schema_pack_id?: string | null;
  status: ItrExportStatus;
  validation_result: OfficialSchemaValidationResult;
  artifacts: ItrExportArtifact[];
  warnings: string[];
  created_at: string;
  updated_at: string;
};

export type FilingProviderName = "mock" | "eri_sandbox" | "eri_live" | "sandbox" | "live";
export type ProviderMode = "mock" | "sandbox" | "live";
export type ConsentStatus = "not_requested" | "requested" | "granted" | "revoked" | "expired";
export type ApprovalStatus = "not_required" | "pending" | "approved" | "rejected";
export type SubmissionStatus =
  | "draft"
  | "blocked"
  | "ready"
  | "submitted"
  | "submission_failed"
  | "pending_verification"
  | "verified"
  | "acknowledgement_available"
  | "cancelled";
export type EVerificationStatus = "not_started" | "initiated" | "pending" | "verified" | "failed" | "expired";

export type FilingReadinessResult = {
  ready: boolean;
  blockers: string[];
  warnings: string[];
  required_actions: string[];
  provider: FilingProviderName;
  provider_mode: ProviderMode;
};

export type FilingConsent = {
  consent_id: string;
  user_id: string;
  organization_id: string;
  package_id: string;
  export_id: string;
  consent_status: ConsentStatus;
  consent_text: string;
  granted_at?: string | null;
  revoked_at?: string | null;
  expires_at?: string | null;
  ip_hash?: string | null;
  user_agent_hash?: string | null;
  created_at: string;
};

export type FilingApproval = {
  approval_id: string;
  package_id: string;
  export_id: string;
  approver_user_id?: string | null;
  organization_id: string;
  approval_status: ApprovalStatus;
  approval_notes?: string | null;
  approved_at?: string | null;
  rejected_at?: string | null;
  created_at: string;
};

export type FilingSubmission = {
  submission_id: string;
  package_id: string;
  export_id: string;
  provider: FilingProviderName | string;
  provider_mode: ProviderMode;
  submission_status: SubmissionStatus;
  everification_status: EVerificationStatus;
  provider_reference_id?: string | null;
  submitted_at?: string | null;
  last_checked_at?: string | null;
  failure_reason?: string | null;
  acknowledgement_id?: string | null;
  created_at: string;
  updated_at: string;
};

export type Acknowledgement = {
  acknowledgement_id: string;
  submission_id: string;
  provider_reference_id: string;
  acknowledgement_number: string;
  acknowledgement_date: string;
  artifact_id?: string | null;
  created_at: string;
};

export type ProviderError = {
  code: string;
  safe_message: string;
  retryable: boolean;
  severity: "info" | "warning" | "error" | "critical";
};

export type ProviderContractTestSummary = {
  status?: "passed" | "failed" | "not_verified";
  tested_at?: string;
};

export type ProviderDiagnostics = {
  provider: string;
  mode: ProviderMode;
  configured: boolean;
  live_filing_enabled: boolean;
  secret_backend: "env" | "gcp_secret_manager" | string;
  sandbox_configured: boolean;
  sandbox_calls_allowed: boolean;
  sandbox_contract_status: "passed" | "failed" | "not_verified" | string;
  last_sandbox_contract_test_at?: string | null;
  live_configured: boolean;
  live_enabled: boolean;
  live_blocked_reason?: string | null;
  provider_capabilities: string[];
  safe_missing_config: string[];
  supported_operations: string[];
  status?: string;
  safe_readiness: string;
  safe_error?: string | null;
  last_contract_test?: ProviderContractTestSummary;
  retryable_provider_error?: string | null;
  last_status_check?: string | null;
};
