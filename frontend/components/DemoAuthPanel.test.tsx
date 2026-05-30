import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { renderToStaticMarkup } from "react-dom/server";

import { DemoAuthPanel } from "./DemoAuthPanel";

describe("demo auth panel", () => {
  it("renders role and organization indicators in dev mode", () => {
    const markup = renderToStaticMarkup(<DemoAuthPanel />);

    assert.match(markup, /Demo auth context/);
    assert.match(markup, /Role:/);
    assert.match(markup, /taxpayer/);
    assert.match(markup, /Org:/);
  });

  it("hides demo identity controls in production mode", () => {
    const previousAuthMode = process.env.NEXT_PUBLIC_AUTH_MODE;
    const previousDemoFlag = process.env.NEXT_PUBLIC_DEMO_AUTH_ENABLED;
    process.env.NEXT_PUBLIC_AUTH_MODE = "jwt";
    delete process.env.NEXT_PUBLIC_DEMO_AUTH_ENABLED;

    try {
      const markup = renderToStaticMarkup(<DemoAuthPanel />);

      assert.match(markup, /Production authentication is required/);
      assert.doesNotMatch(markup, /<select/);
      assert.doesNotMatch(markup, /Demo user/);
    } finally {
      if (previousAuthMode === undefined) {
        delete process.env.NEXT_PUBLIC_AUTH_MODE;
      } else {
        process.env.NEXT_PUBLIC_AUTH_MODE = previousAuthMode;
      }
      if (previousDemoFlag === undefined) {
        delete process.env.NEXT_PUBLIC_DEMO_AUTH_ENABLED;
      } else {
        process.env.NEXT_PUBLIC_DEMO_AUTH_ENABLED = previousDemoFlag;
      }
    }
  });
});
