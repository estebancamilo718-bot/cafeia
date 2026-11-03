export type PrivacyConsentChoice = "accepted" | "declined" | null;

export function canAnalyzeWithConsent(choice: PrivacyConsentChoice): boolean {
  return choice === "accepted";
}
