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
