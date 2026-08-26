import type { Credentials } from "google-auth-library";

/**
 * In-memory token store, keyed by the connected Google account's email.
 * Good enough for local development / a single-user demo; swap for a real
 * database (with encrypted refresh tokens) before running this in production.
 */
const tokensByEmail = new Map<string, Credentials>();

export function saveTokens(email: string, tokens: Credentials): void {
  tokensByEmail.set(email, tokens);
}

export function getTokens(email: string): Credentials | undefined {
  return tokensByEmail.get(email);
}

export function listConnectedAccounts(): string[] {
  return [...tokensByEmail.keys()];
}
