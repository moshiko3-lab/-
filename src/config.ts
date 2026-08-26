import "dotenv/config";

export function requireEnv(name: string): string {
  const value = process.env[name];
  if (!value) {
    throw new Error(`Missing required environment variable: ${name}`);
  }
  return value;
}

export const config = {
  port: Number(process.env.PORT ?? 3000),
  google: {
    clientId: requireEnv("GOOGLE_CLIENT_ID"),
    clientSecret: requireEnv("GOOGLE_CLIENT_SECRET"),
    redirectUri: requireEnv("GOOGLE_REDIRECT_URI"),
  },
  // Only required when /automation/draft-replies is called - kept lazy so the
  // OAuth connect flow works even before Shopify/Anthropic are configured.
  shopify: {
    get storeDomain() {
      return requireEnv("SHOPIFY_STORE_DOMAIN"); // e.g. my-store.myshopify.com
    },
    get adminAccessToken() {
      return requireEnv("SHOPIFY_ADMIN_ACCESS_TOKEN");
    },
    apiVersion: process.env.SHOPIFY_API_VERSION ?? "2024-10",
  },
  anthropic: {
    get apiKey() {
      return requireEnv("ANTHROPIC_API_KEY");
    },
    model: process.env.ANTHROPIC_MODEL ?? "claude-sonnet-5",
  },
  draftLabelName: process.env.GMAIL_DRAFT_LABEL ?? "AI-Drafted",
  humanReviewLabelName: process.env.GMAIL_HUMAN_REVIEW_LABEL ?? "Needs-Human-Review",
  // Set AUTOMATION_ENABLED=false to disable the periodic background scan
  // and only run it on-demand via POST /automation/draft-replies.
  automationEnabled: process.env.AUTOMATION_ENABLED !== "false",
  automationIntervalMinutes: Number(process.env.AUTOMATION_INTERVAL_MINUTES ?? 5),
  // Where connected-account tokens are persisted. Point this at a mounted
  // persistent volume on your host, or they'll be lost on redeploy.
  tokenStorePath: process.env.TOKEN_STORE_PATH ?? "data/tokens.json",
};
