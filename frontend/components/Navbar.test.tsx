import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { renderToStaticMarkup } from "react-dom/server";

import { Navbar } from "./Navbar";

describe("navbar pilot status banner", () => {
  it("renders a visible pilot mode live-filing-disabled banner by default", () => {
    const markup = renderToStaticMarkup(<Navbar />);

    assert.match(markup, /Pilot mode:/);
    assert.match(markup, /Live government filing is disabled/);
  });

  it("can hide the pilot mode banner through public config", () => {
    const previousFlag = process.env.NEXT_PUBLIC_SHOW_PILOT_STATUS_BANNER;
    process.env.NEXT_PUBLIC_SHOW_PILOT_STATUS_BANNER = "false";

    try {
      const markup = renderToStaticMarkup(<Navbar />);

      assert.doesNotMatch(markup, /Pilot mode:/);
    } finally {
      if (previousFlag === undefined) {
        delete process.env.NEXT_PUBLIC_SHOW_PILOT_STATUS_BANNER;
      } else {
        process.env.NEXT_PUBLIC_SHOW_PILOT_STATUS_BANNER = previousFlag;
      }
    }
  });
});
