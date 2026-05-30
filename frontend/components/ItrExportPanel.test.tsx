import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { renderToStaticMarkup } from "react-dom/server";

import { DecisionCard } from "./DecisionCard";
import { FilingPackagePanel } from "./FilingPackagePanel";
import { ItrExportPanel } from "./ItrExportPanel";
import { ItrSchemaValidationErrors } from "./ItrSchemaValidationErrors";
import { SchemaPackStatus } from "./SchemaPackStatus";
import type { FilingPackage, ItrExport } from "../types/itr";

const filingPackage: FilingPackage = {
  package_id: "pkg-1",
  assessment_year: "2026-27",
  previous_year: "2025-26",
  candidate_itr: "ITR-1",
  status: "ready_for_ca_review",
  readiness_score: 90,
  validation_run_id: "val-1",
  computation_id: "tax-1",
  document_ids: [],
  warnings: [],
  artifacts: [],
  created_at: "2026-05-30T00:00:00Z",
  updated_at: "2026-05-30T00:00:00Z",
};

const readyExport: ItrExport = {
  export_id: "exp-1",
  package_id: "pkg-1",
  assessment_year: "2026-27",
  previous_year: "2025-26",
  candidate_itr: "ITR-1",
  schema_pack_id: "schema-1",
  status: "ready_for_download",
  validation_result: {
    validation_id: "val-schema-1",
    schema_pack_id: "schema-1",
    candidate_itr: "ITR-1",
    assessment_year: "2026-27",
    status: "passed",
    errors: [],
    warnings: [],
    validated_at: "2026-05-30T00:00:00Z",
  },
  artifacts: [
    {
      artifact_id: "artifact-1",
      artifact_type: "official_itr_json",
      filename: "itr-1_export.json",
      mime_type: "application/json",
      size: 128,
      sha256: "a".repeat(64),
      created_at: "2026-05-30T00:00:00Z",
    },
  ],
  warnings: [],
  created_at: "2026-05-30T00:00:00Z",
  updated_at: "2026-05-30T00:00:00Z",
};

describe("ITR export UI", () => {
  it("renders no-schema setup message without misleading download", () => {
    const html = renderToStaticMarkup(
      <ItrExportPanel
        filingPackage={filingPackage}
        itrExport={{ ...readyExport, status: "not_configured", artifacts: [], schema_pack_id: null, validation_result: { ...readyExport.validation_result, status: "not_configured", errors: [] } }}
        error={null}
        loading={false}
        canGenerate={true}
        onGenerate={() => undefined}
        onDownloadArtifact={() => undefined}
      />,
    );

    assert.match(html, /No active schema pack is configured/i);
    assert.doesNotMatch(html, /Download official export/i);
    assert.match(html, /has not been submitted to the Income Tax Department/i);
  });

  it("renders schema errors and ready download state", () => {
    const failed: ItrExport = {
      ...readyExport,
      status: "schema_failed",
      artifacts: [],
      validation_result: {
        ...readyExport.validation_result,
        status: "failed",
        errors: [
          {
            code: "missing_required",
            message: "A required schema field is missing.",
            field_path: "TaxPaid",
            schema_path: "required.0",
            severity: "high",
          },
        ],
      },
    };
    const failedHtml = renderToStaticMarkup(
      <ItrSchemaValidationErrors result={failed.validation_result} />,
    );
    const readyHtml = renderToStaticMarkup(
      <ItrExportPanel
        filingPackage={filingPackage}
        itrExport={readyExport}
        error={null}
        loading={false}
        canGenerate={true}
        onGenerate={() => undefined}
        onDownloadArtifact={() => undefined}
      />,
    );

    assert.match(failedHtml, /missing_required/);
    assert.match(failedHtml, /TaxPaid/);
    assert.match(readyHtml, /Download official export/);
    assert.match(readyHtml, /Schema validation means the payload matched the configured schema pack/i);
  });

  it("keeps previous panels visible and shows friendly errors", () => {
    const html = renderToStaticMarkup(
      <>
        <DecisionCard
          decision={{ candidate_itr: "ITR-1", confidence: "high", missing_fields: [], reason_codes: [] }}
          explanation={null}
          missingFields={[]}
        />
        <FilingPackagePanel
          filingPackage={filingPackage}
          draftPayload={null}
          error={null}
          onGenerate={() => undefined}
          onDownloadArtifact={() => undefined}
          canGenerate={true}
          loading={false}
        />
        <ItrExportPanel
          filingPackage={filingPackage}
          itrExport={null}
          error="You do not have access to this export."
          loading={false}
          canGenerate={true}
          onGenerate={() => undefined}
          onDownloadArtifact={() => undefined}
        />
      </>,
    );

    assert.match(html, /Candidate ITR/);
    assert.match(html, /Filing package/i);
    assert.match(html, /Official ITR export/i);
    assert.match(html, /do not have access/i);
  });

  it("renders schema pack status", () => {
    const configured = renderToStaticMarkup(<SchemaPackStatus exportResult={readyExport} />);
    const missing = renderToStaticMarkup(<SchemaPackStatus exportResult={null} />);

    assert.match(configured, /Schema pack configured/i);
    assert.match(missing, /Schema pack status appears after export validation/i);
  });
});
