import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { renderToStaticMarkup } from "react-dom/server";

import { DecisionCard } from "./DecisionCard";
import { TaxComputationPanel } from "./TaxComputationPanel";
import { ValidationReportPanel } from "./ValidationReportPanel";
import type { TaxComputationResult, ValidationReport } from "../types/itr";

const result: TaxComputationResult = {
  computation_id: "tax-1",
  assessment_year: "2026-27",
  previous_year: "2025-26",
  selected_regime: "new",
  regime_label: "New regime",
  default_regime: "new",
  candidate_itr: "ITR-1",
  is_preview: false,
  income: {
    salary_income: 1200000,
    standard_deduction: 75000,
    house_property_income: 0,
    business_profession_income: 0,
    capital_gains_income: 0,
    capital_gains_subtypes: {},
    other_sources_income: 0,
    gross_total_income: 1200000,
  },
  deductions: {
    claimed_total: 0,
    allowed_total: 0,
    disallowed_total: 0,
    applied: [],
  },
  taxable_income: 1125000,
  tax_before_rebate: 52500,
  rebate: 52500,
  surcharge: 0,
  cess: 0,
  total_tax_liability: 0,
  credits: {
    tds_salary: 50000,
    tds_other: 0,
    tcs: 0,
    advance_tax: 0,
    self_assessment_tax: 0,
    total_credits: 50000,
  },
  refund_due: 50000,
  tax_payable: 0,
  warnings: [],
  steps: [
    {
      step_key: "gross_total_income",
      label: "Gross total income",
      amount: 1200000,
      formula: "Salary + house property + business/profession + capital gains + other sources",
    },
  ],
};

const validationReport: ValidationReport = {
  validation_run_id: "val-1",
  created_at: "2026-05-30T00:00:00Z",
  overall_status: "failed",
  readiness_score: 20,
  issues: [],
  missing_fields: [],
  conflicts: [],
  warnings: [],
  evidence_summary: {
    document_count: 0,
    approved_extracted_field_count: 0,
    document_types: [],
  },
};

describe("tax computation UI", () => {
  it("renders tax panel totals and selected regime", () => {
    const html = renderToStaticMarkup(<TaxComputationPanel result={result} validationReport={null} />);

    assert.match(html, /Tax computation/i);
    assert.match(html, /New regime/i);
    assert.match(html, /Gross total income/i);
    assert.match(html, /12,00,000/);
    assert.match(html, /Taxable income/i);
    assert.match(html, /11,25,000/);
  });

  it("renders refund or payable display", () => {
    const refundHtml = renderToStaticMarkup(<TaxComputationPanel result={result} validationReport={null} />);
    const payableHtml = renderToStaticMarkup(
      <TaxComputationPanel result={{ ...result, refund_due: 0, tax_payable: 319800 }} validationReport={null} />,
    );

    assert.match(refundHtml, /Refund due/i);
    assert.match(refundHtml, /50,000/);
    assert.match(payableHtml, /Tax payable/i);
    assert.match(payableHtml, /3,19,800/);
  });

  it("renders warnings and computation steps", () => {
    const html = renderToStaticMarkup(
      <TaxComputationPanel
        result={{
          ...result,
          warnings: [{ code: "SPECIAL_RATE_CAPITAL_GAINS_NOT_COMPUTED", message: "Special-rate gains need review." }],
        }}
        validationReport={null}
      />,
    );

    assert.match(html, /Special-rate gains need review/);
    assert.match(html, /Computation steps/i);
    assert.match(html, /Gross total income/);
  });

  it("shows validation failed preview warning", () => {
    const html = renderToStaticMarkup(
      <TaxComputationPanel result={{ ...result, is_preview: true }} validationReport={validationReport} />,
    );

    assert.match(html, /preview/i);
    assert.match(html, /validation failed/i);
  });

  it("does not erase ITR recommendation or validation report", () => {
    const html = renderToStaticMarkup(
      <>
        <DecisionCard
          decision={{ candidate_itr: "ITR-1", confidence: "high", missing_fields: [], reason_codes: [] }}
          explanation={null}
          missingFields={[]}
        />
        <ValidationReportPanel report={validationReport} />
        <TaxComputationPanel result={result} validationReport={validationReport} />
      </>,
    );

    assert.match(html, /Candidate ITR/);
    assert.match(html, /Validation report/i);
    assert.match(html, /Tax computation/i);
  });
});
