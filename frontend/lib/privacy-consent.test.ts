import assert from "node:assert/strict";
import test from "node:test";

import {
  canAnalyzeWithConsent,
  parseStoredPrivacyConsent,
  PRIVACY_CONSENT_STORAGE_KEY,
} from "./privacy-consent.ts";

test("solo reconoce las decisiones de consentimiento previstas", () => {
  assert.equal(parseStoredPrivacyConsent("accepted"), "accepted");
  assert.equal(parseStoredPrivacyConsent("declined"), "declined");
  assert.equal(parseStoredPrivacyConsent(null), null);
  assert.equal(parseStoredPrivacyConsent("true"), null);
  assert.equal(parseStoredPrivacyConsent("cualquier-otro-valor"), null);
});

test("solo permite analizar después de una aceptación explícita", () => {
  assert.equal(canAnalyzeWithConsent("accepted"), true);
  assert.equal(canAnalyzeWithConsent("declined"), false);
  assert.equal(canAnalyzeWithConsent(null), false);
});

test("la clave de almacenamiento está versionada", () => {
  assert.match(PRIVACY_CONSENT_STORAGE_KEY, /_v\d+$/);
});
