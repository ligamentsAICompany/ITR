import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { renderToStaticMarkup } from "react-dom/server";

import { DecisionCard } from "./DecisionCard";
import { FilingPackageArtifacts } from "./FilingPackageArtifacts";
import { FilingPackagePanel } from "./FilingPackagePanel";
import { FilingPackageWarnings } from "./FilingPackageWarnings";
import { TaxComputationPanel } from "./TaxComputationPanel";
import { ValidationReportPanel } from "./ValidationReportPanel";
import type { FilingPackage, TaxComputationResult, ValidationReport } from "../types/itr";

const validationReport: ValidationReport = {
  validation_run_id: "val-1",
  created_at: "2026-05-30T00:00:00Z",
  overall_status: "passed",
  readiness_score: 100,
  issues: [],
  missing_fields: [],
  conflicts: [],
  warnings: [],
  evidence_summary: { document_count: 1, approved_extracted_field_count: 1, document_types: ["form16"] },
};

const taxResult: TaxComputationResult = {
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
  deductions: { claimed_total: 0, allowed_total: 0, disallowed_total: 0, applied: [] },
  taxable_income: 1125000,
  tax_before_rebate: 52500,
  rebate: 52500,
  surcharge: 0,
  cess: 0,
  total_tax_liability: 0,
  credits: { tds_salary: 0, tds_other: 0, tcs: 0, advance_tax: 0, self_assessment_tax: 0, total_credits: 0 },
  refund_due: 0,
  tax_payable: 0,
  warnings: [],
  steps: [],
};

const filingPackage: FilingPackage = {
  package_id: "pkg-1",
  assessment_year: "2026-27",
  previous_year: "2025-26",
  candidate_itr: "ITR-1",
  status: "ready_for_ca_review",
  readiness_score: 90,
  validation_run_id: "val-1",
  computation_id: "tax-1",
  document_ids: ["doc-1"],
  warnings: [
    {
      warning_id: "warn-1",
      severity: "medium",
      message: "Official ITR schema validation is not yet implemented for this package.",
      source: "draft_itr_payload",
      recommendation: "Review with a qualified tax professional.",
    },
  ],
  artifacts: [
    {
      artifact_id: "art-1",
      artifact_type: "draft_itr_payload",
      filename: "draft_itr_payload.json",
      mime_type: "application/json",
      size: 128,
      sha256: "a".repeat(64),
      created_at: "2026-05-30T00:00:00Z",
    },
  ],
  created_at: "2026-05-30T00:00:00Z",
  updated_at: "2026-05-30T00:00:00Z",
};

describe("filing package UI", () => {
  it("renders status, artifacts, warnings, draft preview, and disclaimer", () => {
    const html = renderToStaticMarkup(
      <FilingPackagePanel
        filingPackage={filingPackage}
        draftPayload={{ payload_type: "draft_itr_payload", schema_status: "internal_draft_not_official" }}
        error={null}
        onGenerate={() => undefined}
        onDownloadArtifact={() => undefined}
        canGenerate={true}
        loading={false}
      />,
    );

    assert.match(html, /Filing package/i);
    assert.match(html, /ready for ca review/i);
    assert.match(html, /draft filing package for review/i);
    assert.match(html, /not been submitted to the Income Tax Department/i);
    assert.match(html, /draft_itr_payload\.json/i);
    assert.match(html, /internal_draft_not_official/i);
  });

  it("does not erase ITR recommendation, validation, or tax panels", () => {
    const html = renderToStaticMarkup(
      <>
        <DecisionCard
          decision={{ candidate_itr: "ITR-1", confidence: "high", missing_fields: [], reason_codes: [] }}
          explanation={null}
          missingFields={[]}
        />
        <ValidationReportPanel report={validationReport} />
        <TaxComputationPanel result={taxResult} validationReport={validationReport} />
        <FilingPackagePanel
          filingPackage={filingPackage}
          draftPayload={null}
          error={null}
          onGenerate={() => undefined}
          onDownloadArtifact={() => undefined}
          canGenerate={true}
          loading={false}
        />
      </>,
    );

    assert.match(html, /Candidate ITR/);
    assert.match(html, /Validation report/i);
    assert.match(html, /Tax computation/i);
    assert.match(html, /Filing package/i);
  });

  it("shows blocked package warning", () => {
    const html = renderToStaticMarkup(
      <FilingPackageWarnings warnings={filingPackage.warnings} status="blocked" />,
    );

    assert.match(html, /blocked/i);
    assert.match(html, /Official ITR schema validation/);
  });

  it("download button targets the artifact handler", () => {
    const html = renderToStaticMarkup(
      <FilingPackageArtifacts artifacts={filingPackage.artifacts} onDownloadArtifact={() => undefined} />,
    );

    assert.match(html, /Download/);
    assert.match(html, /draft_itr_payload\.json/);
  });
});
