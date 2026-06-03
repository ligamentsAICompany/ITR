import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { renderToStaticMarkup } from "react-dom/server";

import { AcknowledgementPanel } from "./AcknowledgementPanel";
import { EVerificationPanel } from "./EVerificationPanel";
import { FilingApprovalPanel } from "./FilingApprovalPanel";
import { FilingConsentPanel } from "./FilingConsentPanel";
import { FilingProviderModeBadge } from "./FilingProviderModeBadge";
import { FilingReadinessPanel } from "./FilingReadinessPanel";
import { FilingSubmissionPanel } from "./FilingSubmissionPanel";
import { ProviderErrorPanel } from "./ProviderErrorPanel";
import { ProviderStatusPanel } from "./ProviderStatusPanel";
import type {
  Acknowledgement,
  FilingApproval,
  FilingConsent,
  FilingReadinessResult,
  FilingSubmission,
  ItrExport,
} from "../types/itr";

const readiness: FilingReadinessResult = {
  ready: false,
  blockers: ["missing_consent", "approval_pending"],
  warnings: ["This is a mock/sandbox filing workflow for testing. It does not file a real tax return."],
  required_actions: ["Grant consent.", "Obtain reviewer approval."],
  provider: "mock",
  provider_mode: "mock",
};

const consent: FilingConsent = {
  consent_id: "consent-1",
  user_id: "user-1",
  organization_id: "org-1",
  package_id: "pkg-1",
  export_id: "exp-1",
  consent_status: "requested",
  consent_text: "I consent to submit this specific validated export package.",
  granted_at: null,
  revoked_at: null,
  expires_at: null,
  ip_hash: null,
  user_agent_hash: null,
  created_at: "2026-05-30T00:00:00Z",
};

const approval: FilingApproval = {
  approval_id: "approval-1",
  package_id: "pkg-1",
  export_id: "exp-1",
  approver_user_id: null,
  organization_id: "org-1",
  approval_status: "pending",
  approval_notes: null,
  approved_at: null,
  rejected_at: null,
  created_at: "2026-05-30T00:00:00Z",
};

const submission: FilingSubmission = {
  submission_id: "submission-1",
  package_id: "pkg-1",
  export_id: "exp-1",
  provider: "mock",
  provider_mode: "mock",
  submission_status: "draft",
  everification_status: "not_started",
  provider_reference_id: null,
  submitted_at: null,
  last_checked_at: null,
  failure_reason: null,
  acknowledgement_id: null,
  created_at: "2026-05-30T00:00:00Z",
  updated_at: "2026-05-30T00:00:00Z",
};

const readyExport: ItrExport = {
  export_id: "exp-1",
  package_id: "pkg-1",
  assessment_year: "2026-27",
  previous_year: "2025-26",
  candidate_itr: "ITR-3",
  schema_pack_id: "schema-1",
  status: "ready_for_download",
  validation_result: {
    validation_id: "schema-val-1",
    schema_pack_id: "schema-1",
    candidate_itr: "ITR-3",
    assessment_year: "2026-27",
    status: "passed",
    errors: [],
    warnings: [],
    validated_at: "2026-05-30T00:00:00Z",
  },
  artifacts: [],
  warnings: [],
  created_at: "2026-05-30T00:00:00Z",
  updated_at: "2026-05-30T00:00:00Z",
};

function buttonTag(html: string, label: string): string {
  const match = html.match(new RegExp(`<button[^>]*>${label}</button>`));
  assert.ok(match, `Expected ${label} button`);
  return match[0];
}

describe("filing integration UI", () => {
  it("renders readiness blockers, actions, mode badge, disclaimers, and disabled submit", () => {
    const html = renderToStaticMarkup(
      <>
        <FilingReadinessPanel readiness={readiness} onCheck={() => undefined} loading={false} />
        <FilingSubmissionPanel
          submission={submission}
          readiness={readiness}
          error={null}
          loading={false}
          onCreate={() => undefined}
          onSubmit={() => undefined}
          onStatusCheck={() => undefined}
        />
      </>,
    );

    assert.match(html, /missing consent/i);
    assert.match(html, /approval pending/i);
    assert.match(html, /Provider mode: mock/i);
    assert.match(html, /This action has not submitted anything to the Income Tax Department unless provider mode is live and submission succeeds\./);
    assert.match(html, /This is a mock\/sandbox filing workflow for testing\. It does not file a real tax return\./);
    assert.match(html, /disabled=""/);
  });

  it("renders consent, approval, e-verification, acknowledgement, and friendly errors", () => {
    const acknowledgement: Acknowledgement = {
      acknowledgement_id: "ack-1",
      submission_id: "submission-1",
      provider_reference_id: "MOCK-ref",
      acknowledgement_number: "MOCK-ACK-1234",
      acknowledgement_date: "2026-05-30T00:00:00Z",
      artifact_id: null,
      created_at: "2026-05-30T00:00:00Z",
    };
    const html = renderToStaticMarkup(
      <>
        <FilingConsentPanel consent={consent} error="Please sign in before continuing." loading={false} onRequest={() => undefined} onGrant={() => undefined} onRevoke={() => undefined} />
        <FilingApprovalPanel
          approval={approval}
          canApprove={true}
          canRequest={true}
          guardMessage={null}
          error="You do not have access to this record."
          loading={false}
          onRequest={() => undefined}
          onApprove={() => undefined}
          onReject={() => undefined}
        />
        <EVerificationPanel submission={{ ...submission, everification_status: "initiated" }} loading={false} onInitiate={() => undefined} onRefresh={() => undefined} />
        <AcknowledgementPanel acknowledgement={acknowledgement} error={null} loading={false} onRefresh={() => undefined} />
      </>,
    );

    assert.match(html, /Consent requested/i);
    assert.match(html, /Grant consent/i);
    assert.match(html, /Approval pending/i);
    assert.match(html, /Approve/i);
    assert.match(html, /E-verification/i);
    assert.match(html, /initiated/i);
    assert.match(html, /MOCK-ACK-1234/i);
    assert.match(html, /Please sign in/i);
    assert.match(html, /do not have access/i);
  });

  it("guards approval and submission buttons before export readiness", () => {
    const approvalGuardHtml = renderToStaticMarkup(
      <FilingApprovalPanel
        approval={null}
        canApprove={false}
        canRequest={false}
        guardMessage="Approval cannot be requested yet because schema export is not ready. Please generate a schema-validated export first."
        error={null}
        loading={false}
        onRequest={() => undefined}
        onApprove={() => undefined}
        onReject={() => undefined}
      />,
    );
    const submissionGuardHtml = renderToStaticMarkup(
      <FilingSubmissionPanel
        submission={submission}
        readiness={readiness}
        error="Submission is not ready yet. Complete consent, reviewer approval, and export validation first."
        loading={false}
        canCreate={false}
        createGuardMessage="Generate a schema-validated export before creating a filing submission."
        onCreate={() => undefined}
        onSubmit={() => undefined}
        onStatusCheck={() => undefined}
      />,
    );

    assert.match(approvalGuardHtml, /Approval cannot be requested yet because schema export is not ready/i);
    assert.match(approvalGuardHtml, /disabled=""/);
    assert.match(submissionGuardHtml, /Submission is not ready yet\. Complete consent, reviewer approval, and export validation first\./);
    assert.match(submissionGuardHtml, /Generate a schema-validated export before creating a filing submission\./);
    assert.match(submissionGuardHtml, /disabled=""/);
    assert.doesNotMatch(`${approvalGuardHtml}${submissionGuardHtml}`, /\/v1\/filing/);
  });

  it("enables approval request when export is ready for download", () => {
    const html = renderToStaticMarkup(
      <FilingApprovalPanel
        approval={null}
        canApprove={false}
        canRequest={readyExport.status === "ready_for_download"}
        guardMessage={null}
        error={null}
        loading={false}
        onRequest={() => undefined}
        onApprove={() => undefined}
        onReject={() => undefined}
      />,
    );

    assert.doesNotMatch(html, /Approval cannot be requested/i);
    assert.match(html, /<button[^>]*>Request approval<\/button>/);
    assert.match(html, /Request approval/);
  });

  it("enables submit only when a draft has ready filing readiness", () => {
    const notReadyHtml = renderToStaticMarkup(
      <FilingSubmissionPanel
        submission={submission}
        readiness={readiness}
        error={null}
        loading={false}
        onCreate={() => undefined}
        onSubmit={() => undefined}
        onStatusCheck={() => undefined}
      />,
    );
    const readyHtml = renderToStaticMarkup(
      <FilingSubmissionPanel
        submission={submission}
        readiness={{ ...readiness, ready: true, blockers: [], required_actions: [] }}
        error={null}
        loading={false}
        onCreate={() => undefined}
        onSubmit={() => undefined}
        onStatusCheck={() => undefined}
      />,
    );

    assert.match(buttonTag(notReadyHtml, "Submit through provider"), /\sdisabled=""/);
    assert.doesNotMatch(buttonTag(readyHtml, "Submit through provider"), /\sdisabled=""/);
  });

  it("enables e-verification only after provider reference exists", () => {
    const draftHtml = renderToStaticMarkup(
      <EVerificationPanel submission={submission} loading={false} onInitiate={() => undefined} onRefresh={() => undefined} />,
    );
    const submittedHtml = renderToStaticMarkup(
      <EVerificationPanel
        submission={{ ...submission, submission_status: "submitted", provider_reference_id: "MOCK-pkg-export" }}
        loading={false}
        onInitiate={() => undefined}
        onRefresh={() => undefined}
      />,
    );

    assert.match(buttonTag(draftHtml, "Initiate e-verification"), /\sdisabled=""/);
    assert.doesNotMatch(buttonTag(submittedHtml, "Initiate e-verification"), /\sdisabled=""/);
  });

  it("renders provider diagnostics, live warning, missing config, retryable error, and capabilities", () => {
    const sandboxReadiness: FilingReadinessResult = {
      ready: false,
      blockers: ["provider_not_configured"],
      warnings: ["ERI sandbox configuration is missing."],
      required_actions: ["Configure ERI sandbox credentials in Secret Manager."],
      provider: "eri_sandbox",
      provider_mode: "sandbox",
    };
    const html = renderToStaticMarkup(
      <>
        <FilingProviderModeBadge provider="eri_live" mode="live" liveAllowed={false} />
        <ProviderStatusPanel
          readiness={sandboxReadiness}
          submission={{
            ...submission,
            provider: "eri_sandbox",
            provider_mode: "sandbox",
            last_checked_at: "2026-05-30T00:00:00Z",
          }}
          diagnostics={{
            provider: "eri_sandbox",
            mode: "sandbox",
            configured: false,
            live_filing_enabled: false,
            secret_backend: "env",
            sandbox_configured: false,
            sandbox_secrets_verified: false,
            sandbox_spec_active: false,
            sandbox_calls_allowed: false,
            sandbox_contract_status: "not_verified",
            sandbox_smoke_status: "not_verified",
            last_sandbox_contract_test_at: "2026-05-30T00:00:00Z",
            last_sandbox_smoke_at: null,
            pilot_ready: false,
            pilot_blockers: ["sandbox_secrets_not_verified", "sandbox_spec_missing"],
            pilot_warnings: ["Live filing remains disabled."],
            pilot_verified_items: ["no_live_filing_enabled"],
            pilot_not_verified_items: ["sandbox_contract_tests_passed"],
            live_configured: false,
            live_enabled: false,
            live_blocked_reason: "Live filing is disabled until approval metadata and ALLOW_LIVE_FILING are configured.",
            provider_capabilities: ["submit_return", "status_check", "callback"],
            safe_missing_config: ["ERI_SANDBOX_CLIENT_ID", "sandbox_provider_calls_disabled"],
            supported_operations: ["submit_return", "status_check", "callback"],
            safe_readiness: "not_configured",
            last_contract_test: {
              status: "not_verified",
              tested_at: "2026-05-30T00:00:00Z",
            },
            retryable_provider_error: "Provider rate limit reached. Please retry after the provider interval.",
            last_status_check: "2026-05-30T00:00:00Z",
          }}
          everificationSupported={false}
          acknowledgementAvailable={false}
        />
        <ProviderErrorPanel
          error={{
            code: "RATE_LIMITED",
            safe_message: "Provider rate limit reached. Please retry after the provider interval.",
            retryable: true,
            severity: "warning",
          }}
        />
      </>,
    );

    assert.match(html, /Live filing requires approved credentials, legal approval, and explicit enablement\./);
    assert.match(html, /not configured/i);
    assert.match(html, /contract test/i);
    assert.match(html, /not verified/i);
    assert.match(html, /submit return/i);
    assert.match(html, /safe readiness/i);
    assert.match(html, /live filing disabled/i);
    assert.match(html, /provider configuration missing/i);
    assert.match(html, /last status check/i);
    assert.match(html, /retryable/i);
    assert.match(html, /e-verification unsupported/i);
    assert.match(html, /acknowledgement unavailable/i);
    assert.match(html, /sandbox calls disabled/i);
    assert.match(html, /sandbox contract/i);
    assert.match(html, /pilot readiness/i);
    assert.match(html, /sandbox secrets not verified/i);
    assert.match(html, /sandbox spec missing/i);
    assert.match(html, /Live filing remains disabled\./);
    assert.match(html, /no live filing enabled/i);
    assert.match(html, /sandbox contract tests passed/i);
    assert.match(html, /Client pilot readiness does not mean live filing is enabled\./);
    assert.match(html, /live disabled reason/i);
    assert.match(html, /ERI_SANDBOX_CLIENT_ID/i);
    assert.doesNotMatch(html, /client_secret|access token|raw payload|sandbox-secret-value/i);
  });

  it("renders sandbox configured diagnostics without leaking secrets", () => {
    const html = renderToStaticMarkup(
      <ProviderStatusPanel
        readiness={{
          ready: true,
          blockers: [],
          warnings: ["Sandbox submission only. This is not a real tax filing."],
          required_actions: [],
          provider: "eri_sandbox",
          provider_mode: "sandbox",
        }}
        submission={{ ...submission, provider: "eri_sandbox", provider_mode: "sandbox", submission_status: "submitted" }}
        diagnostics={{
          provider: "eri_sandbox",
          mode: "sandbox",
          configured: true,
          live_filing_enabled: false,
          secret_backend: "gcp_secret_manager",
          sandbox_configured: true,
          sandbox_secrets_verified: true,
          sandbox_spec_active: true,
          sandbox_calls_allowed: true,
          sandbox_contract_status: "passed",
          sandbox_smoke_status: "passed",
          last_sandbox_contract_test_at: "2026-05-30T00:00:00Z",
          last_sandbox_smoke_at: "2026-05-30T00:00:00Z",
          pilot_ready: true,
          pilot_blockers: [],
          pilot_warnings: ["Ready only for controlled sandbox client pilot."],
          pilot_verified_items: ["sandbox_secrets_verified", "sandbox_smoke_passed"],
          pilot_not_verified_items: [],
          live_configured: false,
          live_enabled: false,
          live_blocked_reason: "Live filing remains disabled for Phase 11.",
          provider_capabilities: ["submit_return", "status_check", "callback"],
          safe_missing_config: [],
          supported_operations: ["submit_return", "status_check", "callback"],
          safe_readiness: "configured",
          last_contract_test: { status: "passed", tested_at: "2026-05-30T00:00:00Z" },
          retryable_provider_error: null,
          last_status_check: null,
        }}
        everificationSupported={false}
        acknowledgementAvailable={false}
      />,
    );

    assert.match(html, /Sandbox submission only\. This is not a real tax filing\./);
    assert.match(html, /sandbox configured/i);
    assert.match(html, /sandbox calls enabled/i);
    assert.match(html, /pilot ready/i);
    assert.match(html, /sandbox smoke passed/i);
    assert.match(html, /Ready only for controlled sandbox client pilot\./);
    assert.match(html, /Client pilot readiness does not mean live filing is enabled\./);
    assert.match(html, /gcp secret manager/i);
    assert.match(html, /submit return/i);
    assert.doesNotMatch(html, /sandbox-secret|client_secret|access token|raw payload/i);
  });
});
