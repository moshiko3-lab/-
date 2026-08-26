import { config } from "./config";
import { listConnectedAccounts } from "./tokenStore";
import { draftRepliesForAccount } from "./automation";

let running = false;

async function runOnce(): Promise<void> {
  if (running) {
    console.warn("Skipping scheduled run: previous run is still in progress");
    return;
  }
  running = true;
  try {
    for (const email of listConnectedAccounts()) {
      try {
        const results = await draftRepliesForAccount(email);
        if (results.length > 0) {
          console.log(`[scheduler] ${email}: processed ${results.length} message(s)`, results);
        }
      } catch (err) {
        console.error(`[scheduler] Failed to process account ${email}`, err);
      }
    }
  } finally {
    running = false;
  }
}

/** Starts the periodic draft-replies run for every connected mailbox. */
export function startAutomationScheduler(): void {
  const intervalMs = config.automationIntervalMinutes * 60_000;
  console.log(
    `Automation scheduler enabled: checking connected inboxes every ${config.automationIntervalMinutes} minute(s)`
  );
  setInterval(() => {
    void runOnce();
  }, intervalMs);
}
