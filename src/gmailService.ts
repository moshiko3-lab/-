import { google } from "googleapis";
import type { Credentials } from "google-auth-library";
import { createOAuthClient } from "./googleAuth";

export async function listRecentMessages(tokens: Credentials, maxResults = 10) {
  const auth = createOAuthClient();
  auth.setCredentials(tokens);

  const gmail = google.gmail({ version: "v1", auth });
  const { data } = await gmail.users.messages.list({
    userId: "me",
    maxResults,
  });

  return data.messages ?? [];
}
