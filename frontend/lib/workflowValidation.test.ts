import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { AADHAAR_VALIDATION_MESSAGE } from "./aadhaar";
import { validateWorkflowInput } from "./workflowValidation";
import type { BasicFormState } from "../types/itr";

const baseForm: BasicFormState = {
  pan: "ABCDE1234F",
  aadhaar: "",
  taxpayerName: "",
  entityType: "individual",
  residency: "resident",
  salaryIncome: "1200000",
  employerName: "",
  grossSalary: "1200000",
  standardDeduction: "",
  professionalTax: "",
  housePropertyHasIncome: "no",
  housePropertyIncome: "0",
  housePropertyCount: "0",
  hasSelfOccupiedProperty: "no",
  hasLetOutProperty: "no",
  businessProfessionIncome: "0",
  capitalGainsIncome: "0",
  hasStcg: "no",
  hasLtcg112A: "no",
  ltcg112AAmount: "0",
  stcgAmount: "",
  otherLtcgAmount: "",
  hasOtherLtcg: "no",
  hasLandBuildingGains: "no",
  hasSpecialRateCapitalGains: "no",
  otherSourcesIncome: "0",
  otherSourcesInterest: "0",
  savingsInterest: "",
  fixedDepositInterest: "",
  agriculturalIncome: "0",
  housePropertyInterest: "",
  tdsSalary: "",
  tdsOther: "",
  tcs: "",
  previousYear: "2025-26",
  returnFilingReason: "voluntary",
  isDefectiveReturnCase: "no",
  hasForeignAssets: "no",
  hasForeignIncome: "no",
  presumptiveTaxation: "no",
  directorInCompany: "no",
  unlistedEquityHeld: "no",
  broughtForwardLosses: "no",
  capitalGainsEdgeCase: "no",
  hasDeductions: "no",
  has80C: "no",
  deduction80CAmount: "",
  has80D: "no",
  deduction80DAmount: "",
};

describe("workflow validation", () => {
  it("blocks invalid PAN before workflow endpoints are called", () => {
    assert.equal(validateWorkflowInput({ ...baseForm, pan: "ABCDE12345" }), "Please enter a valid PAN (e.g., ABCDE1234F).");
  });

  it("allows valid Aadhaar to continue to workflow endpoints", () => {
    assert.equal(validateWorkflowInput({ ...baseForm, aadhaar: "123456789012" }), null);
  });

  it("allows blank Aadhaar to continue to workflow endpoints", () => {
    assert.equal(validateWorkflowInput({ ...baseForm, aadhaar: "" }), null);
  });

  it("blocks invalid Aadhaar before workflow endpoints are called", () => {
    assert.equal(validateWorkflowInput({ ...baseForm, aadhaar: "12345" }), AADHAAR_VALIDATION_MESSAGE);
  });
});
