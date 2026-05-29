export type YesNoUnknown = "yes" | "no" | "unknown";
export type Confidence = "high" | "medium" | "low";

export type BasicFormState = {
  pan: string;
  aadhaar: string;
  entityType: string;
  residency: string;
  salaryIncome: string;
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
  has80C: YesNoUnknown;
  has80D: YesNoUnknown;
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
