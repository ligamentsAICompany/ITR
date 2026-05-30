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
});
