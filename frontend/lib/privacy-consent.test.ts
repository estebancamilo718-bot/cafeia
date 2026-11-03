import assert from "node:assert/strict";
import test from "node:test";

import { canAnalyzeWithConsent } from "./privacy-consent.ts";

test("solo permite analizar después de una aceptación explícita", () => {
  assert.equal(canAnalyzeWithConsent("accepted"), true);
  assert.equal(canAnalyzeWithConsent("declined"), false);
  assert.equal(canAnalyzeWithConsent(null), false);
});
