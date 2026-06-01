import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { renderToStaticMarkup } from "react-dom/server";

import { IntakeForm } from "./IntakeForm";
import type { BasicFormState } from "../types/itr";

const form: BasicFormState = {
  pan: "ABCDE1234F",
  aadhaar: "123456789012",
  taxpayerName: "",
  entityType: "individual",
  residency: "resident",
  salaryIncome: "1000000",
  employerName: "",
  grossSalary: "1000000",
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
  returnFilingReason: "mandatory",
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

describe("IntakeForm workflow action", () => {
  it("renders the workflow action as a non-submit button with a stable selector", () => {
    const markup = renderToStaticMarkup(
      <IntakeForm
        form={form}
        missingFields={[]}
        disabled={false}
        aadhaarError={null}
        onChange={() => undefined}
        onSubmit={() => undefined}
      />,
    );

    assert.match(markup, /data-testid="run-agent-workflow"/);
    assert.match(markup, /type="button"/);
    assert.match(markup, /Run agent workflow/);
  });
});
