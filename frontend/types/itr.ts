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
  content_type: string;
  size_bytes: number;
  sha256: string;
  storage_path: string;
  status: string;
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
