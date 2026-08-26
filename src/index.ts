import express from "express";
import { google } from "googleapis";
import { config } from "./config";
import { createOAuthClient, getAuthUrl } from "./googleAuth";
import { saveTokens, getTokens, listConnectedAccounts } from "./tokenStore";
import { listRecentMessages } from "./gmailService";

const app = express();

app.get("/", (_req, res) => {
  res.json({
    connectGoogle: "/auth/google",
    connectedAccounts: listConnectedAccounts(),
    listMessages: "/gmail/messages?email=you@example.com",
  });
});

// Step 1: send the user to Google's consent screen.
app.get("/auth/google", (_req, res) => {
  res.redirect(getAuthUrl());
});

// Step 2: Google redirects back here with a one-time authorization code.
app.get("/auth/google/callback", async (req, res) => {
  const code = req.query.code;
  const error = req.query.error;

  if (error) {
    return res.status(400).json({ error });
  }
  if (typeof code !== "string") {
    return res.status(400).json({ error: "Missing 'code' query parameter" });
  }

  try {
    const client = createOAuthClient();
    const { tokens } = await client.getToken(code);
    client.setCredentials(tokens);

    const oauth2 = google.oauth2({ version: "v2", auth: client });
    const { data: userInfo } = await oauth2.userinfo.get();

    if (!userInfo.email) {
      return res.status(400).json({ error: "Could not determine account email" });
    }

    saveTokens(userInfo.email, tokens);

    res.json({
      message: "Google account connected successfully",
      email: userInfo.email,
      hasRefreshToken: Boolean(tokens.refresh_token),
    });
  } catch (err) {
    console.error("OAuth callback failed", err);
    res.status(500).json({ error: "Failed to exchange authorization code for tokens" });
  }
});

// Example of using the stored tokens to call the Gmail API.
app.get("/gmail/messages", async (req, res) => {
  const email = req.query.email;
  if (typeof email !== "string") {
    return res.status(400).json({ error: "Missing 'email' query parameter" });
  }

  const tokens = getTokens(email);
  if (!tokens) {
    return res.status(404).json({ error: `No connected Google account for ${email}` });
  }

  try {
    const messages = await listRecentMessages(tokens);
    res.json({ email, messages });
  } catch (err) {
    console.error("Failed to list Gmail messages", err);
    res.status(500).json({ error: "Failed to fetch Gmail messages" });
  }
});

app.listen(config.port, () => {
  console.log(`Server listening on http://localhost:${config.port}`);
  console.log(`Connect a Google account at http://localhost:${config.port}/auth/google`);
});
