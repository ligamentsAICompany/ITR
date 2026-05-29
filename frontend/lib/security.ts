export function maskPan(value: unknown): unknown {
  if (typeof value !== "string") {
    return value;
  }
  const normalized = value.trim().toUpperCase();
  if (normalized.length < 6) {
    return "****";
  }
  return `${normalized.slice(0, 5)}****${normalized.slice(-1)}`;
}

export function maskAadhaar(value: unknown): unknown {
  if (typeof value !== "string") {
    return value;
  }
  const digits = value.replace(/\D/g, "");
  if (digits.length < 4) {
    return "****";
  }
  return `**** **** ${digits.slice(-4)}`;
}

export function maskSensitiveProfile<T>(value: T): T {
  if (Array.isArray(value)) {
    return value.map((item) => maskSensitiveProfile(item)) as T;
  }
  if (value && typeof value === "object") {
    const masked: Record<string, unknown> = {};
    for (const [key, item] of Object.entries(value)) {
      if (key === "pan") {
        masked[key] = maskPan(item);
      } else if (key === "aadhaar_number" || key === "aadhaar") {
        masked[key] = maskAadhaar(item);
      } else if (key === "aadhaar_last4") {
        masked[key] = "****";
      } else {
        masked[key] = maskSensitiveProfile(item);
      }
    }
    return masked as T;
  }
  return value;
}
