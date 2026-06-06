export const AADHAAR_VALIDATION_MESSAGE =
  "Enter a valid 12-digit Aadhaar number, or leave this blank.";

export const AADHAAR_INPUT_MAX_LENGTH = 14;

export type AadhaarValidationResult = {
  error: string | null;
  normalizedValue: string;
};

export function normalizeAadhaar(value: string): string {
  return value.trim().replace(/\s+/g, "");
}

export function validateAadhaar(value: string): AadhaarValidationResult {
  const normalizedValue = normalizeAadhaar(value);

  if (normalizedValue === "" || /^\d{12}$/.test(normalizedValue)) {
    return { error: null, normalizedValue };
  }

  return {
    error: AADHAAR_VALIDATION_MESSAGE,
    normalizedValue,
  };
}
