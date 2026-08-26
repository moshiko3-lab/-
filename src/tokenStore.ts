import type { Credentials } from "google-auth-library";
import { mkdirSync, readFileSync, writeFileSync } from "fs";
import { dirname } from "path";
import { config } from "./config";

/**
 * Token store keyed by the connected Google account's email, persisted to a
 * single JSON file on disk so connections survive a process restart or
 * redeploy. The file is written on every change and reloaded on boot.
 *
 * This is plaintext on disk - good enough for a small single-tenant
 * deployment as long as the volume/disk itself isn't publicly exposed.
 * Swap for a real database with encrypted refresh tokens before this
 * handles many accounts or sensitive stores.
 */
const storePath = config.tokenStorePath;

function loadFromDisk(): Map<string, Credentials> {
  try {
    const raw = readFileSync(storePath, "utf-8");
    const parsed = JSON.parse(raw) as Record<string, Credentials>;
    return new Map(Object.entries(parsed));
  } catch {
    return new Map();
  }
}

const tokensByEmail = loadFromDisk();

function persist(): void {
  mkdirSync(dirname(storePath), { recursive: true });
  const obj = Object.fromEntries(tokensByEmail);
  writeFileSync(storePath, JSON.stringify(obj, null, 2), "utf-8");
}

export function saveTokens(email: string, tokens: Credentials): void {
  tokensByEmail.set(email, tokens);
  persist();
}

export function getTokens(email: string): Credentials | undefined {
  return tokensByEmail.get(email);
}

export function listConnectedAccounts(): string[] {
  return [...tokensByEmail.keys()];
}
