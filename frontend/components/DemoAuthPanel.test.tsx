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

  it("keeps the first render stable when a demo user is stored in the browser", () => {
    const previousWindow = globalThis.window;
    globalThis.window = {
      localStorage: {
        getItem: () => "00000000-0000-4000-8000-000000000002",
      },
    } as unknown as Window & typeof globalThis;

    try {
      const markup = renderToStaticMarkup(<DemoAuthPanel />);

      assert.match(markup, /taxpayer/);
      assert.doesNotMatch(markup, /selected="">Demo Reviewer/);
    } finally {
      globalThis.window = previousWindow;
    }
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
