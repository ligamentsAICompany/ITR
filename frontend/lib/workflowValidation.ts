import type { BasicFormState } from "@/types/itr";
import { validateAadhaar } from "./aadhaar";

export function validateWorkflowInput(form: BasicFormState): string | null {
  const aadhaarValidation = validateAadhaar(form.aadhaar);
  if (aadhaarValidation.error) {
    return aadhaarValidation.error;
  }

  if (form.housePropertyHasIncome === "yes") {
    const propertyCount = Number(form.housePropertyCount);
    if (!Number.isFinite(propertyCount) || propertyCount < 1) {
      return "Please enter the number of house properties when house property income/details are marked yes.";
    }
  }

  if (form.has80C === "yes" && !isValidAmount(form.deduction80CAmount)) {
    return "Please enter a valid Section 80C deduction amount.";
  }
  if (form.has80D === "yes" && !isValidAmount(form.deduction80DAmount)) {
    return "Please enter a valid Section 80D deduction amount.";
  }

  return null;
}

function isValidAmount(value: string): boolean {
  if (value.trim() === "") {
    return false;
  }
  const amount = Number(value);
  return Number.isFinite(amount) && amount >= 0;
}
