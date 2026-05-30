"use client";

import { useMemo, useState } from "react";
import { AgentPanel } from "@/components/AgentPanel";
import { DecisionCard } from "@/components/DecisionCard";
import { DemoAuthPanel } from "@/components/DemoAuthPanel";
import { DocumentUploadCenter } from "@/components/DocumentUploadCenter";
import { EscalationAlert } from "@/components/EscalationAlert";
import { ExtractionReviewPanel } from "@/components/ExtractionReviewPanel";
import { FilingPackagePanel } from "@/components/FilingPackagePanel";
import { IntakeForm } from "@/components/IntakeForm";
import { Navbar } from "@/components/Navbar";
import { Spinner } from "@/components/Spinner";
import { TaxComputationPanel } from "@/components/TaxComputationPanel";
import { ValidationReportPanel } from "@/components/ValidationReportPanel";
import { WorkflowLog } from "@/components/WorkflowLog";
import {
  computeTax,
  downloadFilingPackageArtifact,
  generateFilingPackage,
  getClarification,
  getDecision,
  getExplanation,
  getMissingFields,
  applyMergedPayloadToForm,
  mergeExtractionFields,
  normalizeProfile,
  runValidation,
} from "@/lib/api";
import { validateAadhaar } from "@/lib/aadhaar";
import { maskSensitiveProfile } from "@/lib/security";
import { validateWorkflowInput } from "@/lib/workflowValidation";
import type {
  BasicFormState,
  CanonicalTaxProfile,
  ClarificationResponse,
  DocumentRecord,
  DraftItrPayload,
  ExtractionResult,
  ExplanationResponse,
  FilingPackage,
  FilingPackageArtifact,
  ITRDecisionResponse,
  TaxComputationResult,
  ValidationReport,
} from "@/types/itr";

const highRiskFields = ["foreign_assets", "business_profession", "capital_gains", "exemptions_flags"];

const initialForm: BasicFormState = {
  pan: "ABCDE1234F",
  aadhaar: "",
  taxpayerName: "",
  entityType: "individual",
  residency: "resident",
  salaryIncome: "1200000",
  employerName: "",
  grossSalary: "1200000",
  standardDeduction: "",
  professionalTax: "",
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
  stcgAmount: "",
  otherLtcgAmount: "",
  hasOtherLtcg: "no",
  hasLandBuildingGains: "no",
  hasSpecialRateCapitalGains: "no",
  otherSourcesIncome: "0",
  otherSourcesInterest: "0",
  savingsInterest: "",
  fixedDepositInterest: "",
  agriculturalIncome: "0",
  housePropertyInterest: "",
  tdsSalary: "",
  tdsOther: "",
  tcs: "",
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
  const [uploadedDocument, setUploadedDocument] = useState<DocumentRecord | null>(null);
  const [extraction, setExtraction] = useState<ExtractionResult | null>(null);
  const [documents, setDocuments] = useState<DocumentRecord[]>([]);
  const [extractions, setExtractions] = useState<ExtractionResult[]>([]);
  const [approvedFieldIds, setApprovedFieldIds] = useState<string[]>([]);
  const [validationReport, setValidationReport] = useState<ValidationReport | null>(null);
  const [taxComputation, setTaxComputation] = useState<TaxComputationResult | null>(null);
  const [filingPackage, setFilingPackage] = useState<FilingPackage | null>(null);
  const [draftPayload, setDraftPayload] = useState<DraftItrPayload | null>(null);
  const [filingPackageError, setFilingPackageError] = useState<string | null>(null);

  const questions = useMemo(
    () => (clarification?.question ? [clarification.question] : []),
    [clarification],
  );
  const progress = useMemo(
    () => getProgressState({ decision, explanation, clarification, missingFields, escalation, loading, error }),
    [decision, explanation, clarification, missingFields, escalation, loading, error],
  );
  const aadhaarError = useMemo(() => validateAadhaar(form.aadhaar).error, [form.aadhaar]);

  function updateForm(field: keyof BasicFormState, value: string) {
    setForm((current) => ({ ...current, [field]: value }));
    clearFilingPackage();
  }

  function pushLog(message: string) {
    setLogs((current) => [...current, message]);
  }

  function clearFilingPackage() {
    setFilingPackage(null);
    setDraftPayload(null);
    setFilingPackageError(null);
  }

  function handleExtraction(document: DocumentRecord, extractionResult: ExtractionResult) {
    setUploadedDocument(document);
    setExtraction(extractionResult);
    setDocuments((current) => [...current.filter((item) => item.document_id !== document.document_id), document]);
    setExtractions((current) => [
      ...current.filter((item) => item.document_id !== extractionResult.document_id),
      extractionResult,
    ]);
    clearFilingPackage();
    pushLog(`extract: ${extractionResult.fields.length} candidate field(s) ready for review`);
  }

  async function acceptExtractedFields(fieldIds: string[], reviewedExtraction = extraction) {
    if (!extraction) {
      return;
    }
    setLoading(true);
    setError(null);
    try {
      pushLog("merge: POST /v1/intake/merge-extractions");
      const mergeResult = await mergeExtractionFields(form, reviewedExtraction ?? extraction, fieldIds);
      const nextForm = normalizeDocumentMerge(applyMergedPayloadToForm(form, mergeResult.merged_payload));
      setForm(nextForm);
      clearFilingPackage();
      setApprovedFieldIds((current) => [...new Set([...current, ...mergeResult.applied_field_ids])]);
      setExtractions((current) => [
        ...current.filter((item) => item.document_id !== (reviewedExtraction ?? extraction).document_id),
        reviewedExtraction ?? extraction,
      ]);
      pushLog(`merge: accepted ${mergeResult.applied_field_ids.length} reviewed field(s)`);
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : "Could not merge extracted fields.");
    } finally {
      setLoading(false);
    }
  }

  async function runWorkflow(nextForm = form, options: { resetLogs?: boolean; unresolvedFields?: string[] } = {}) {
    const shouldResetLogs = options.resetLogs ?? true;
    const nextUnresolvedFields = options.unresolvedFields ?? (shouldResetLogs ? [] : unresolvedFields);
    setLoading(true);
    setError(null);
    setEscalation(false);
    setDecision(null);
    setValidationReport(null);
    setTaxComputation(null);
    setFilingPackage(null);
    setDraftPayload(null);
    setFilingPackageError(null);
    setMissingFields([]);
    setProfile(null);
    setExplanation(null);
    setClarification(null);
    if (shouldResetLogs) {
      setLogs([]);
    }
    setUnresolvedFields(nextUnresolvedFields);

    try {
      const validationError = validateWorkflowInput(nextForm);
      if (validationError) {
        setError(validationError);
        pushLog(`validation: ${validationError}`);
        return;
      }

      pushLog("normalize: POST /v1/normalize");
      const normalized = await normalizeProfile(nextForm);
      setProfile(normalized);

      pushLog("validation: POST /v1/validation/run");
      const validationResult = await runValidation({
        profile: normalized,
        documents,
        extractions,
        approvedFieldIds,
      });
      setValidationReport(validationResult);

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

      pushLog("tax: POST /v1/tax/compute");
      const taxResult = await computeTax({
        profile: normalized,
        decision: decisionResult,
        validationReport: validationResult,
      });
      setTaxComputation(taxResult);

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

  async function handleGenerateFilingPackage() {
    if (!profile || !decision || !validationReport || !taxComputation) {
      setFilingPackageError("Run ITR recommendation, validation, and tax computation before generating a package.");
      return;
    }

    setLoading(true);
    setFilingPackageError(null);
    try {
      pushLog("filing-package: POST /v1/filing-packages/generate");
      const packageResult = await generateFilingPackage({
        profile,
        decision,
        validationReport,
        taxComputation,
        documents,
      });
      setFilingPackage(packageResult);
      const draftArtifact = packageResult.artifacts.find((artifact) => artifact.artifact_type === "draft_itr_payload");
      if (draftArtifact) {
        const blob = await downloadFilingPackageArtifact(packageResult.package_id, draftArtifact.artifact_id);
        setDraftPayload(JSON.parse(await blob.text()) as DraftItrPayload);
      }
      pushLog(`filing-package: generated ${packageResult.artifacts.length} artifact(s)`);
    } catch (caughtError) {
      setFilingPackageError(
        caughtError instanceof Error ? caughtError.message : "Could not generate the filing package.",
      );
    } finally {
      setLoading(false);
    }
  }

  async function handleDownloadArtifact(artifact: FilingPackageArtifact) {
    if (!filingPackage) {
      return;
    }

    try {
      const blob = await downloadFilingPackageArtifact(filingPackage.package_id, artifact.artifact_id);
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = artifact.filename;
      link.click();
      URL.revokeObjectURL(url);
    } catch (caughtError) {
      setFilingPackageError(
        caughtError instanceof Error ? caughtError.message : "Could not download the selected artifact.",
      );
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
          <DemoAuthPanel />
          <DocumentUploadCenter
            disabled={loading}
            onExtracted={handleExtraction}
            onLog={pushLog}
            onError={(message) => setError(message || null)}
          />
          <ExtractionReviewPanel
            document={uploadedDocument}
            extraction={extraction}
            disabled={loading}
            onAccept={(fieldIds, reviewedExtraction) => void acceptExtractedFields(fieldIds, reviewedExtraction)}
          />

          <IntakeForm
            form={form}
            missingFields={missingFields}
            disabled={loading}
            aadhaarError={aadhaarError}
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
          <ValidationReportPanel report={validationReport} />
          <TaxComputationPanel result={taxComputation} validationReport={validationReport} />
          <FilingPackagePanel
            filingPackage={filingPackage}
            draftPayload={draftPayload}
            error={filingPackageError}
            onGenerate={() => void handleGenerateFilingPackage()}
            onDownloadArtifact={(artifact) => void handleDownloadArtifact(artifact)}
            canGenerate={Boolean(profile && decision && validationReport && taxComputation)}
            loading={loading}
          />
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

function normalizeDocumentMerge(form: BasicFormState): BasicFormState {
  const nextForm = { ...form };
  if (Number(nextForm.deduction80CAmount || 0) > 0) {
    nextForm.has80C = "yes";
    nextForm.hasDeductions = "yes";
  }
  if (Number(nextForm.deduction80DAmount || 0) > 0) {
    nextForm.has80D = "yes";
    nextForm.hasDeductions = "yes";
  }
  if (Number(nextForm.otherSourcesInterest || 0) > 0 && Number(nextForm.otherSourcesIncome || 0) === 0) {
    nextForm.otherSourcesIncome = nextForm.otherSourcesInterest;
  }
  if (Number(nextForm.salaryIncome || 0) === 0 && Number(nextForm.grossSalary || 0) > 0) {
    nextForm.salaryIncome = nextForm.grossSalary;
  }
  return nextForm;
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
