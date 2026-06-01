import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { DEFAULT_DEMO_BACKEND_INTERNAL_URL, resolveBackendInternalUrl } from "./apiRouting";

describe("frontend API routing", () => {
  it("keeps same-origin v1 rewrites available for default demo builds", () => {
    assert.equal(resolveBackendInternalUrl(undefined), DEFAULT_DEMO_BACKEND_INTERNAL_URL);
  });

  it("uses an explicitly configured backend rewrite target", () => {
    assert.equal(resolveBackendInternalUrl("https://backend.example.com"), "https://backend.example.com");
  });

  it("treats blank backend rewrite config as the demo default", () => {
    assert.equal(resolveBackendInternalUrl("   "), DEFAULT_DEMO_BACKEND_INTERNAL_URL);
  });
});
