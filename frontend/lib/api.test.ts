import assert from "node:assert/strict";
import { afterEach, describe, it } from "node:test";

import { normalizeProfile } from "./api";
import type { BasicFormState } from "../types/itr";

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
