import express from "express";
import { google } from "googleapis";
import { config } from "./config";
import { createOAuthClient, getAuthUrl } from "./googleAuth";
import { saveTokens, getTokens, listConnectedAccounts } from "./tokenStore";
import { listRecentMessages } from "./gmailService";
import { listUnprocessedInboxMessages, createDraftReply, addLabelsToMessage } from "./gmailInboxService";
import { findOrdersByEmail } from "./shopifyService";
import { generateDraftReply } from "./aiDraft";

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

/**
 * Core automation: for every unprocessed inbound message in the connected
 * mailbox, look up the sender's Shopify orders, ask Claude to draft a reply
 * grounded in that order data, and save it as a Gmail draft in the same
 * thread. Nothing is ever sent automatically - a human reviews and sends
 * each draft from Gmail.
 */
app.post("/automation/draft-replies", async (req, res) => {
  const email = req.query.email;
  if (typeof email !== "string") {
    return res.status(400).json({ error: "Missing 'email' query parameter" });
  }

  const tokens = getTokens(email);
  if (!tokens) {
    return res.status(404).json({ error: `No connected Google account for ${email}` });
  }

  try {
    const { gmail, draftLabelId, humanReviewLabelId, messages } = await listUnprocessedInboxMessages(
      tokens,
      email
    );

    const results = [];
    for (const message of messages) {
      try {
        const orders = await findOrdersByEmail(message.fromEmail);
        const draft = await generateDraftReply({
          customerEmail: message.fromEmail,
          customerMessage: message.bodyText,
          orders,
        });

        if (draft.requiresHumanReview) {
          await addLabelsToMessage(gmail, message.id, [humanReviewLabelId]);
          results.push({
            messageId: message.id,
            from: message.fromEmail,
            subject: message.subject,
            ordersFound: orders.length,
            status: "needs_human_review",
            reason: draft.text,
          });
          continue;
        }

        const draftId = await createDraftReply(gmail, message, draft.text);
        await addLabelsToMessage(gmail, message.id, [draftLabelId]);

        results.push({
          messageId: message.id,
          from: message.fromEmail,
          subject: message.subject,
          ordersFound: orders.length,
          draftId,
          status: "drafted",
        });
      } catch (err) {
        console.error(`Failed to draft a reply for message ${message.id}`, err);
        results.push({
          messageId: message.id,
          from: message.fromEmail,
          subject: message.subject,
          status: "failed",
          error: err instanceof Error ? err.message : String(err),
        });
      }
    }

    res.json({ processed: results.length, results });
  } catch (err) {
    console.error("Failed to run the draft-replies automation", err);
    res.status(500).json({ error: "Failed to run the draft-replies automation" });
  }
});

app.listen(config.port, () => {
  console.log(`Server listening on http://localhost:${config.port}`);
  console.log(`Connect a Google account at http://localhost:${config.port}/auth/google`);
});
