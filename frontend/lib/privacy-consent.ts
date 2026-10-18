export const PRIVACY_CONSENT_STORAGE_KEY = "cafeia_image_processing_consent_v1";

export type PrivacyConsentChoice = "accepted" | "declined" | null;

export function parseStoredPrivacyConsent(value: string | null): PrivacyConsentChoice {
  if (value === "accepted" || value === "declined") return value;
  return null;
}

export function canAnalyzeWithConsent(choice: PrivacyConsentChoice): boolean {
  return choice === "accepted";
}
