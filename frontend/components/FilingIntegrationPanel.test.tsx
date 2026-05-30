import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { renderToStaticMarkup } from "react-dom/server";

import { AcknowledgementPanel } from "./AcknowledgementPanel";
import { EVerificationPanel } from "./EVerificationPanel";
import { FilingApprovalPanel } from "./FilingApprovalPanel";
import { FilingConsentPanel } from "./FilingConsentPanel";
import { FilingReadinessPanel } from "./FilingReadinessPanel";
import { FilingSubmissionPanel } from "./FilingSubmissionPanel";
import type {
  Acknowledgement,
  FilingApproval,
  FilingConsent,
  FilingReadinessResult,
  FilingSubmission,
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
        <FilingApprovalPanel approval={approval} canApprove={true} error="You do not have access to this record." loading={false} onRequest={() => undefined} onApprove={() => undefined} onReject={() => undefined} />
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
});
