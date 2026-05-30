import assert from "node:assert/strict";
import { afterEach, describe, it } from "node:test";

import {
  applyMergedPayloadToForm,
  extractDocument,
  mergeExtractionFields,
  normalizeProfile,
  runValidation,
  uploadDocument,
} from "./api";
import type { BasicFormState, ExtractionResult } from "../types/itr";

const baseForm: BasicFormState = {
  pan: "ABCDE1234F",
  aadhaar: "",
  entityType: "individual",
  residency: "resident",
  salaryIncome: "1200000",
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
  hasOtherLtcg: "no",
  hasLandBuildingGains: "no",
  hasSpecialRateCapitalGains: "no",
  otherSourcesIncome: "0",
  agriculturalIncome: "0",
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
  taxpayerName: "",
  employerName: "",
  grossSalary: "1200000",
  standardDeduction: "",
  professionalTax: "",
  tdsSalary: "",
  tdsOther: "",
  tcs: "",
  otherSourcesInterest: "0",
  savingsInterest: "",
  fixedDepositInterest: "",
  housePropertyInterest: "",
  stcgAmount: "",
  otherLtcgAmount: "",
};

describe("normalizeProfile Aadhaar payload", () => {
  afterEach(() => {
    delete (globalThis as { fetch?: typeof fetch }).fetch;
  });

  it("sends valid Aadhaar unchanged", async () => {
    const payload = await captureNormalizePayload({ ...baseForm, aadhaar: "123456789012" });

    assert.equal(payload.aadhaar_number, "123456789012");
  });

  it("omits blank Aadhaar", async () => {
    const payload = await captureNormalizePayload({ ...baseForm, aadhaar: "   " });

    assert.equal(Object.hasOwn(payload, "aadhaar_number"), false);
  });

  it("sends spaced Aadhaar as exactly 12 digits", async () => {
    const payload = await captureNormalizePayload({ ...baseForm, aadhaar: "1234 5678 9012" });

    assert.equal(payload.aadhaar_number, "123456789012");
  });

  it("sends reviewed deduction amounts to scalar canonical fields", async () => {
    const payload = await captureNormalizePayload({
      ...baseForm,
      has80C: "yes",
      deduction80CAmount: "55555",
      has80D: "yes",
      deduction80DAmount: "25000",
    });

    assert.equal(payload.section_80c_amount, 55555);
    assert.equal(payload.section_80d_amount, 25000);
  });
});

describe("document intake API helpers", () => {
  afterEach(() => {
    delete (globalThis as { fetch?: typeof fetch }).fetch;
  });

  it("uploads multipart documents with document type", async () => {
    let capturedBody: FormData | undefined;
    globalThis.fetch = (async (_input: string | URL | Request, init?: RequestInit) => {
      capturedBody = init?.body as FormData;
      return new Response(JSON.stringify({ document_id: "doc-1" }), { status: 200 });
    }) as typeof fetch;

    await uploadDocument(new File(["Gross Salary\n1200000"], "form16.csv", { type: "text/csv" }), "form16");

    assert.ok(capturedBody);
    assert.equal(capturedBody.get("document_type"), "form16");
    assert.equal((capturedBody.get("file") as File).name, "form16.csv");
  });

  it("extracts and merges only approved extraction fields", async () => {
    const extraction: ExtractionResult = {
      document_id: "doc-1",
      status: "completed",
      fields: [
        {
          field_id: "salary-1",
          label: "Gross Salary",
          value: 1200000,
          raw_path: "salaryIncome",
          canonical_path: "income_heads.salary.gross_amount",
          confidence: 0.9,
          source: { document_id: "doc-1", locator: "csv:Gross Salary" },
        },
      ],
    };
    const calls: string[] = [];
    globalThis.fetch = (async (input: string | URL | Request, init?: RequestInit) => {
      calls.push(String(input));
      if (String(input).endsWith("/extract")) {
        return new Response(JSON.stringify(extraction), { status: 200 });
      }
      const body = JSON.parse(String(init?.body)) as Record<string, unknown>;
      assert.deepEqual(body.approved_field_ids, ["salary-1"]);
      return new Response(
        JSON.stringify({
          merged_payload: { salaryIncome: "1200000" },
          applied_field_ids: ["salary-1"],
          skipped_field_ids: [],
        }),
        { status: 200 },
      );
    }) as typeof fetch;

    const extracted = await extractDocument("doc-1");
    const merge = await mergeExtractionFields(baseForm, extracted, ["salary-1"]);
    const nextForm = applyMergedPayloadToForm(baseForm, merge.merged_payload);

    assert.deepEqual(calls, ["/v1/uploads/doc-1/extract", "/v1/intake/merge-extractions"]);
    assert.equal(nextForm.salaryIncome, "1200000");
  });
});

describe("validation API helpers", () => {
  afterEach(() => {
    delete (globalThis as { fetch?: typeof fetch }).fetch;
  });

  it("runs validation without sending unapproved extracted values as authority", async () => {
    let capturedPayload: Record<string, unknown> | null = null;
    globalThis.fetch = (async (_input: string | URL | Request, init?: RequestInit) => {
      capturedPayload = JSON.parse(String(init?.body)) as Record<string, unknown>;
      return new Response(
        JSON.stringify({
          validation_run_id: "val-1",
          profile_id: "profile-1",
          session_id: "session-1",
          created_at: "2026-05-30T00:00:00Z",
          overall_status: "passed",
          readiness_score: 100,
          issues: [],
          missing_fields: [],
          conflicts: [],
          warnings: [],
          evidence_summary: { document_count: 0, approved_extracted_field_count: 0, document_types: [] },
        }),
        { status: 200 },
      );
    }) as typeof fetch;

    const report = await runValidation({
      profile: { user_identity: { pan: "ABCDE1234F" } },
      documents: [],
      extractions: [{ document_id: "doc-1", status: "completed", fields: [] }],
      approvedFieldIds: ["field-1"],
    });

    assert.equal(report.validation_run_id, "val-1");
    if (capturedPayload === null) {
      throw new Error("runValidation did not call fetch");
    }
    const payload = capturedPayload as Record<string, unknown>;
    assert.deepEqual(payload.approved_field_ids, ["field-1"]);
    assert.ok(Object.hasOwn(payload, "extractions"));
  });
});

async function captureNormalizePayload(form: BasicFormState): Promise<Record<string, unknown>> {
  let capturedPayload: Record<string, unknown> | null = null;
  globalThis.fetch = (async (_input: string | URL | Request, init?: RequestInit) => {
    capturedPayload = JSON.parse(String(init?.body)) as Record<string, unknown>;
    return new Response(JSON.stringify({ ok: true }), { status: 200 });
  }) as typeof fetch;

  await normalizeProfile(form);

  if (capturedPayload === null) {
    throw new Error("normalizeProfile did not call fetch");
  }
  return capturedPayload;
}
