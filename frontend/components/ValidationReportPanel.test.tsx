import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { renderToStaticMarkup } from "react-dom/server";

import { DecisionCard } from "./DecisionCard";
import { ReconciliationConflictPanel } from "./ReconciliationConflictPanel";
import { ValidationReportPanel, sortValidationIssues } from "./ValidationReportPanel";
import type { ValidationReport } from "../types/itr";

const baseReport: ValidationReport = {
  validation_run_id: "val-1",
  profile_id: "profile-1",
  session_id: "session-1",
  created_at: "2026-05-30T00:00:00Z",
  overall_status: "needs_review",
  readiness_score: 77,
  issues: [
    {
      issue_id: "low-1",
      rule_id: "documents.optional_review",
      severity: "low",
      status: "warning",
      title: "Optional document review suggested",
      message: "Review optional documents when available.",
      field_path: "documents",
      expected_value: null,
      actual_value: null,
      source_documents: [],
      evidence_refs: [],
      recommendation: "Continue with manual review.",
      blocks_filing_package: false,
    },
    {
      issue_id: "high-1",
      rule_id: "reconciliation.salary_mismatch",
      severity: "high",
      status: "needs_review",
      title: "Salary does not match evidence",
      message: "Approved evidence differs from the profile salary.",
      field_path: "income_heads.salary.gross_amount",
      expected_value: 1200000,
      actual_value: 1400000,
      source_documents: ["doc-form16"],
      evidence_refs: ["csv:1"],
      recommendation: "Review salary evidence.",
      blocks_filing_package: false,
    },
  ],
  missing_fields: ["income_heads.salary.employer_name"],
  conflicts: [
    {
      field_path: "income_heads.salary.gross_amount",
      profile_value: 1200000,
      extracted_value: 1400000,
      source_documents: ["doc-form16"],
      evidence_refs: ["csv:1"],
    },
  ],
  warnings: ["No documents uploaded; validation is limited to manual entries."],
  evidence_summary: {
    document_count: 0,
    approved_extracted_field_count: 0,
    document_types: [],
  },
};

describe("validation report UI", () => {
  it("renders overall status and readiness score", () => {
    const html = renderToStaticMarkup(<ValidationReportPanel report={baseReport} />);

    assert.match(html, /needs review/i);
    assert.match(html, /77/);
    assert.match(html, /income_heads\.salary\.employer_name/);
  });

  it("sorts critical and high severity issues first", () => {
    const sorted = sortValidationIssues([
      { ...baseReport.issues[0], severity: "low" },
      { ...baseReport.issues[1], severity: "critical" },
      { ...baseReport.issues[0], issue_id: "medium-1", severity: "medium" },
    ]);

    assert.deepEqual(
      sorted.map((issue) => issue.severity),
      ["critical", "medium", "low"],
    );
  });

  it("conflict panel shows profile and extracted values with evidence", () => {
    const html = renderToStaticMarkup(<ReconciliationConflictPanel conflicts={baseReport.conflicts} />);

    assert.match(html, /Profile value/);
    assert.match(html, /Extracted value/);
    assert.match(html, /1200000/);
    assert.match(html, /1400000/);
    assert.match(html, /doc-form16/);
  });

  it("validation report does not erase ITR recommendation", () => {
    const html = renderToStaticMarkup(
      <>
        <ValidationReportPanel report={baseReport} />
        <DecisionCard
          decision={{ candidate_itr: "ITR-2", confidence: "high", missing_fields: [], reason_codes: [] }}
          explanation={null}
          missingFields={[]}
        />
      </>,
    );

    assert.match(html, /Validation report/i);
    assert.match(html, /Candidate ITR/);
    assert.match(html, /ITR-2/);
  });

  it("shows no-document warning without fatal blocking language", () => {
    const report = {
      ...baseReport,
      overall_status: "warning" as const,
      readiness_score: 97,
      issues: [
        {
          ...baseReport.issues[0],
          rule_id: "documents.none_manual_review",
          severity: "low" as const,
          title: "No documents uploaded",
          message: "Validation is limited to manual entries until documents are uploaded.",
        },
      ],
    };
    const html = renderToStaticMarkup(<ValidationReportPanel report={report} />);

    assert.match(html, /No documents uploaded/);
    assert.doesNotMatch(html, /blocked/i);
  });
});
