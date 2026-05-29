"use client";

import { useMemo, useState } from "react";
import { AgentPanel } from "@/components/AgentPanel";
import { DecisionCard } from "@/components/DecisionCard";
import { EscalationAlert } from "@/components/EscalationAlert";
import { IntakeForm } from "@/components/IntakeForm";
import { Navbar } from "@/components/Navbar";
import { Spinner } from "@/components/Spinner";
import { WorkflowLog } from "@/components/WorkflowLog";
import {
  getClarification,
  getDecision,
  getExplanation,
  getMissingFields,
  normalizeProfile,
} from "@/lib/api";
import { maskSensitiveProfile } from "@/lib/security";
import type {
  BasicFormState,
  CanonicalTaxProfile,
  ClarificationResponse,
  ExplanationResponse,
  ITRDecisionResponse,
} from "@/types/itr";

const highRiskFields = ["foreign_assets", "business_profession", "capital_gains", "exemptions_flags"];

const initialForm: BasicFormState = {
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

export default function Home() {
  const [form, setForm] = useState<BasicFormState>(initialForm);
  const [profile, setProfile] = useState<CanonicalTaxProfile | null>(null);
  const [decision, setDecision] = useState<ITRDecisionResponse | null>(null);
  const [explanation, setExplanation] = useState<ExplanationResponse | null>(null);
  const [clarification, setClarification] = useState<ClarificationResponse | null>(null);
  const [answer, setAnswer] = useState("");
  const [missingFields, setMissingFields] = useState<string[]>([]);
  const [escalation, setEscalation] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [logs, setLogs] = useState<string[]>([]);
  const [unresolvedFields, setUnresolvedFields] = useState<string[]>([]);

  const questions = useMemo(
    () => (clarification?.question ? [clarification.question] : []),
    [clarification],
  );
  const progress = useMemo(
    () => getProgressState({ decision, explanation, clarification, missingFields, escalation, loading, error }),
    [decision, explanation, clarification, missingFields, escalation, loading, error],
  );

  function updateForm(field: keyof BasicFormState, value: string) {
    setForm((current) => ({ ...current, [field]: value }));
  }

  function pushLog(message: string) {
    setLogs((current) => [...current, message]);
  }

  async function runWorkflow(nextForm = form, options: { resetLogs?: boolean; unresolvedFields?: string[] } = {}) {
    const shouldResetLogs = options.resetLogs ?? true;
    const nextUnresolvedFields = options.unresolvedFields ?? (shouldResetLogs ? [] : unresolvedFields);
    setLoading(true);
    setError(null);
    setEscalation(false);
    setDecision(null);
    setMissingFields([]);
    setProfile(null);
    setExplanation(null);
    setClarification(null);
    if (shouldResetLogs) {
      setLogs([]);
    }
    setUnresolvedFields(nextUnresolvedFields);

    try {
      const validationError = validateForm(nextForm);
      if (validationError) {
        setError(validationError);
        pushLog(`validation: ${validationError}`);
        return;
      }

      pushLog("normalize: POST /v1/normalize");
      const normalized = await normalizeProfile(nextForm);
      setProfile(normalized);

      pushLog("decision: POST /v1/itr-decision");
      const decisionResult = await getDecision(normalized);
      setDecision(decisionResult);

      pushLog("missing-fields: POST /v1/missing-fields");
      const missingResult = await getMissingFields(normalized);
      setMissingFields(missingResult.missing_fields);

      const unresolvedStillMissing = missingResult.missing_fields.some((field) =>
        nextUnresolvedFields.includes(field),
      );
      if (unresolvedStillMissing) {
        pushLog("routing: unresolved ambiguity remains, escalating for expert review");
        pushLog("explain: POST /v1/explain");
        const explanationResult = await getExplanation(decisionResult);
        setExplanation(explanationResult);
        setEscalation(true);
        return;
      }

      if (missingResult.missing_fields.length > 0) {
        const hasHighRiskMissing = missingResult.missing_fields.some((field) =>
          highRiskFields.some((risk) => field.includes(risk)),
        );
        pushLog(
          hasHighRiskMissing
            ? "routing: high-risk field is missing; asking the smallest safe clarification first"
            : "routing: missing fields detected; asking clarification",
        );
        pushLog("clarify: POST /v1/clarify");
        const question = await getClarification(missingResult.missing_fields, {
          decision: decisionResult,
        });
        setClarification(question);
        return;
      }

      pushLog("explain: POST /v1/explain");
      const explanationResult = await getExplanation(decisionResult);
      setExplanation(explanationResult);

      if (
        decisionResult.confidence === "low" ||
        decisionResult.reason_codes.includes("HUMAN_REVIEW_SIGNAL_PRESENT")
      ) {
        pushLog("routing: confidence/review flag requires escalation");
        setEscalation(true);
      }
    } catch (caughtError) {
      const message = caughtError instanceof Error ? caughtError.message : "Unexpected frontend error";
      setError(message);
      pushLog(`error: ${message}`);
    } finally {
      setLoading(false);
    }
  }

  function applyAnswer() {
    const firstMissing = missingFields[0];
    if (!firstMissing) {
      return;
    }

    const trimmed = answer.trim();
    const isUnresolvedAnswer = isUnresolved(trimmed);
    const nextForm = { ...form };
    const nextUnresolvedFields = isUnresolvedAnswer
      ? [...new Set([...unresolvedFields, firstMissing])]
      : unresolvedFields.filter((field) => field !== firstMissing);
    if (firstMissing === "previous_year") {
      nextForm.previousYear = trimmed;
    } else if (firstMissing === "return_filing_reason.type") {
      nextForm.returnFilingReason = normalizeSelectAnswer(trimmed, ["voluntary", "mandatory", "notice"]);
    } else if (firstMissing === "is_defective_return_case") {
      nextForm.isDefectiveReturnCase = normalizeYesNo(trimmed);
    } else if (firstMissing === "income_heads.house_property.has_income") {
      nextForm.housePropertyHasIncome = normalizeYesNo(trimmed);
    } else if (firstMissing === "foreign_assets.has_foreign_assets") {
      nextForm.hasForeignAssets = normalizeYesNo(trimmed);
    } else if (firstMissing === "foreign_assets.has_foreign_income") {
      nextForm.hasForeignIncome = normalizeYesNo(trimmed);
    } else if (firstMissing === "income_heads.business_profession.presumptive_taxation") {
      nextForm.presumptiveTaxation = normalizeYesNo(trimmed);
    } else if (firstMissing === "special_conditions.brought_forward_losses") {
      nextForm.broughtForwardLosses = normalizeYesNo(trimmed);
    } else if (firstMissing === "special_conditions.capital_gains_edge_case") {
      nextForm.capitalGainsEdgeCase = normalizeYesNo(trimmed);
    }

    setForm(nextForm);
    setAnswer("");
    pushLog(
      isUnresolvedAnswer
        ? `answer unresolved for ${formatFieldName(firstMissing)}`
        : `answer applied for ${formatFieldName(firstMissing)}`,
    );
    void runWorkflow(nextForm, { resetLogs: false, unresolvedFields: nextUnresolvedFields });
  }

  return (
    <main className="min-h-screen bg-[#f9fafb]">
      <Navbar />

      <div className="mx-auto max-w-[900px] px-5 py-8">
        <section className="mb-8 rounded-3xl border border-[#e5e7eb] bg-white p-7 shadow-sm">
          <p className="text-sm font-semibold uppercase tracking-[0.2em] text-[#22c55e]">
            Governed tax decision workflow
          </p>
        </section>

        <div className="space-y-6">
          <IntakeForm
            form={form}
            missingFields={missingFields}
            disabled={loading}
            onChange={updateForm}
            onSubmit={() => void runWorkflow()}
          />

          <ProgressCard percentage={progress.percentage} title={progress.title} detail={progress.detail} />

          {error ? (
            <div className="rounded-2xl border border-red-300 bg-red-50 p-4 text-sm text-red-800">
              {error}
            </div>
          ) : null}

          {loading ? (
            <div className="flex items-center gap-3 rounded-2xl border border-[#e5e7eb] bg-white p-4 text-sm font-medium text-gray-700">
              <span className="rounded-full bg-[#22c55e] p-2">
                <Spinner />
              </span>
              Processing workflow through the backend APIs...
            </div>
          ) : null}

          <AgentPanel
            questions={questions}
            answer={answer}
            disabled={loading}
            onAnswerChange={setAnswer}
            onApplyAnswer={applyAnswer}
          />

          <DecisionCard decision={decision} explanation={explanation} missingFields={missingFields} />
          <EscalationAlert show={escalation} />
          <WorkflowLog logs={logs} />

          {profile ? (
            <details className="rounded-2xl border border-[#e5e7eb] bg-white p-5 text-sm text-gray-700 shadow-sm">
              <summary className="cursor-pointer font-semibold text-[#111827]">
                Canonical profile preview
              </summary>
              <pre className="mt-4 max-h-80 overflow-auto rounded-xl bg-[#f9fafb] p-4 text-xs leading-5">
                {JSON.stringify(maskSensitiveProfile(profile), null, 2)}
              </pre>
            </details>
          ) : null}
        </div>
      </div>
    </main>
  );
}

function normalizeYesNo(value: string): "yes" | "no" | "unknown" {
  const lowered = value.toLowerCase();
  if (lowered.startsWith("y")) {
    return "yes";
  }
  if (lowered.startsWith("n")) {
    return "no";
  }
  return "unknown";
}

function validateForm(form: BasicFormState): string | null {
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

function normalizeSelectAnswer(value: string, allowed: string[]): string {
  const lowered = value.toLowerCase();
  return allowed.includes(lowered) ? lowered : "unknown";
}

function isUnresolved(value: string): boolean {
  const lowered = value.toLowerCase();
  return ["unknown", "not sure", "not_sure", "unsure", "i don't know", "dont know", "don't know"].some(
    (phrase) => lowered.includes(phrase),
  );
}

function getProgressState({
  decision,
  explanation,
  clarification,
  missingFields,
  escalation,
  loading,
  error,
}: {
  decision: ITRDecisionResponse | null;
  explanation: ExplanationResponse | null;
  clarification: ClarificationResponse | null;
  missingFields: string[];
  escalation: boolean;
  loading: boolean;
  error: string | null;
}) {
  if (error) {
    return {
      percentage: 40,
      title: "Needs attention",
      detail: "Please fix the highlighted message, then run the workflow again.",
    };
  }
  if (loading) {
    return {
      percentage: 45,
      title: "Checking your profile",
      detail: "The backend is normalizing inputs and running deterministic rules.",
    };
  }
  if (escalation) {
    return {
      percentage: 100,
      title: "Expert review needed",
      detail: "The case is preserved for review instead of guessing.",
    };
  }
  if (explanation) {
    return {
      percentage: 100,
      title: "Ready for review",
      detail: "The ITR candidate and explanation are available.",
    };
  }
  if (clarification || missingFields.length > 0) {
    return {
      percentage: 70,
      title: "You are 70% done",
      detail: `Answer ${formatFieldName(missingFields[0] ?? "the next required field")} to continue.`,
    };
  }
  if (decision) {
    return {
      percentage: 85,
      title: "Decision prepared",
      detail: "No blocking field is currently visible. Explanation is next.",
    };
  }
  return {
    percentage: 30,
    title: "Profile started",
    detail: "Enter the basic taxpayer details, then run the guided workflow.",
  };
}

function ProgressCard({
  percentage,
  title,
  detail,
}: {
  percentage: number;
  title: string;
  detail: string;
}) {
  return (
    <section className="rounded-2xl border border-[#e5e7eb] bg-white p-5 shadow-sm">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="text-sm font-semibold uppercase tracking-[0.18em] text-[#22c55e]">Progress</p>
          <h2 className="mt-1 text-xl font-semibold text-[#111827]">{title}</h2>
          <p className="mt-1 text-sm leading-6 text-gray-600">{detail}</p>
        </div>
        <div className="text-3xl font-semibold text-[#22c55e]">{percentage}%</div>
      </div>
      <div className="mt-4 h-2.5 overflow-hidden rounded-full bg-gray-100">
        <div
          className="h-full rounded-full bg-[#22c55e] transition-all duration-300"
          style={{ width: `${percentage}%` }}
        />
      </div>
    </section>
  );
}

function formatFieldName(field: string): string {
  const labels: Record<string, string> = {
    previous_year: "the previous year",
    "return_filing_reason.type": "why this return is being filed",
    is_defective_return_case: "whether this is a defective return case",
    "income_heads.capital_gains.has_income": "whether there are capital gains",
    "income_heads.other_sources.has_income": "whether there is interest or other income",
    "foreign_assets.has_foreign_assets": "whether you held foreign assets",
    "foreign_assets.has_foreign_income": "whether you had foreign income",
    "income_heads.business_profession.presumptive_taxation": "whether business income is presumptive",
    "special_conditions.brought_forward_losses": "whether there are brought-forward losses",
    "special_conditions.capital_gains_edge_case": "whether RSU or capital-gain classification is unclear",
  };
  return labels[field] ?? field.replaceAll("_", " ");
}
