import assert from "node:assert/strict";
import { describe, it } from "node:test";

import {
  AADHAAR_VALIDATION_MESSAGE,
  normalizeAadhaar,
  validateAadhaar,
} from "./aadhaar";

describe("Aadhaar validation", () => {
  it("accepts exactly 12 digits", () => {
    assert.deepEqual(validateAadhaar("123456789012"), {
      error: null,
      normalizedValue: "123456789012",
    });
  });

  it("accepts blank Aadhaar", () => {
    assert.deepEqual(validateAadhaar("   "), {
      error: null,
      normalizedValue: "",
    });
  });

  it("normalizes spaced Aadhaar before validation", () => {
    assert.equal(normalizeAadhaar("1234 5678 9012"), "123456789012");
    assert.deepEqual(validateAadhaar("1234 5678 9012"), {
      error: null,
      normalizedValue: "123456789012",
    });
  });

  it("rejects too-short Aadhaar before workflow submission", () => {
    assert.deepEqual(validateAadhaar("12345"), {
      error: AADHAAR_VALIDATION_MESSAGE,
      normalizedValue: "12345",
    });
  });

  it("rejects too-long Aadhaar before workflow submission", () => {
    assert.deepEqual(validateAadhaar("1234567890123"), {
      error: AADHAAR_VALIDATION_MESSAGE,
      normalizedValue: "1234567890123",
    });
  });

  it("rejects letters and symbols before workflow submission", () => {
    assert.deepEqual(validateAadhaar("1234-ABCD-9012"), {
      error: AADHAAR_VALIDATION_MESSAGE,
      normalizedValue: "1234-ABCD-9012",
    });
  });
});
