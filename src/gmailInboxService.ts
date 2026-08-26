import type { gmail_v1 } from "googleapis";
import { google } from "googleapis";
import type { Credentials } from "google-auth-library";
import { createOAuthClient } from "./googleAuth";
import { config } from "./config";
import { extractEmailAddress, extractPlainTextBody, getHeader } from "./mailParser";

export interface InboundMessage {
  id: string;
  threadId: string;
  fromEmail: string;
  subject: string;
  bodyText: string;
  messageIdHeader: string | undefined;
}

function getGmailClient(tokens: Credentials): gmail_v1.Gmail {
  const auth = createOAuthClient();
  auth.setCredentials(tokens);
  return google.gmail({ version: "v1", auth });
}

async function getOrCreateLabelId(gmail: gmail_v1.Gmail, name: string): Promise<string> {
  const { data } = await gmail.users.labels.list({ userId: "me" });
  const existing = data.labels?.find((label) => label.name === name);
  if (existing?.id) return existing.id;

  const { data: created } = await gmail.users.labels.create({
    userId: "me",
    requestBody: { name, labelListVisibility: "labelShow", messageListVisibility: "show" },
  });
  if (!created.id) throw new Error(`Failed to create Gmail label "${name}"`);
  return created.id;
}

/**
 * Lists inbox messages that haven't been processed yet (no AI-Drafted label),
 * excluding anything sent by the connected account itself, and returns them
 * parsed and ready for the AI drafting step.
 */
export async function listUnprocessedInboxMessages(
  tokens: Credentials,
  connectedEmail: string,
  maxResults = 20
): Promise<{ gmail: gmail_v1.Gmail; draftLabelId: string; messages: InboundMessage[] }> {
  const gmail = getGmailClient(tokens);
  const draftLabelId = await getOrCreateLabelId(gmail, config.draftLabelName);

  const { data: list } = await gmail.users.messages.list({
    userId: "me",
    q: `in:inbox -label:${config.draftLabelName}`,
    maxResults,
  });

  const messages: InboundMessage[] = [];
  for (const ref of list.messages ?? []) {
    if (!ref.id) continue;
    const { data: full } = await gmail.users.messages.get({
      userId: "me",
      id: ref.id,
      format: "full",
    });

    const headers = full.payload?.headers;
    const fromEmail = extractEmailAddress(getHeader(headers, "From"));
    if (!fromEmail || fromEmail === connectedEmail.toLowerCase()) {
      // Skip mail sent by the connected mailbox itself (e.g. its own sent copies).
      continue;
    }

    messages.push({
      id: ref.id,
      threadId: full.threadId ?? ref.id,
      fromEmail,
      subject: getHeader(headers, "Subject") ?? "(no subject)",
      bodyText: extractPlainTextBody(full.payload) || "(empty message)",
      messageIdHeader: getHeader(headers, "Message-ID"),
    });
  }

  return { gmail, draftLabelId, messages };
}

function toBase64Url(input: string): string {
  return Buffer.from(input, "utf-8").toString("base64url");
}

/** Creates a Gmail draft replying in the same thread. Does NOT send anything. */
export async function createDraftReply(
  gmail: gmail_v1.Gmail,
  original: InboundMessage,
  bodyText: string
): Promise<string> {
  const subject = original.subject.toLowerCase().startsWith("re:")
    ? original.subject
    : `Re: ${original.subject}`;

  const headerLines = [
    `To: ${original.fromEmail}`,
    `Subject: ${subject}`,
    original.messageIdHeader ? `In-Reply-To: ${original.messageIdHeader}` : null,
    original.messageIdHeader ? `References: ${original.messageIdHeader}` : null,
    `Content-Type: text/plain; charset="UTF-8"`,
    `MIME-Version: 1.0`,
  ].filter((line): line is string => Boolean(line));

  const raw = toBase64Url(`${headerLines.join("\r\n")}\r\n\r\n${bodyText}`);

  const { data } = await gmail.users.drafts.create({
    userId: "me",
    requestBody: {
      message: { raw, threadId: original.threadId },
    },
  });

  if (!data.id) throw new Error("Gmail did not return a draft id");
  return data.id;
}

export async function markMessageProcessed(
  gmail: gmail_v1.Gmail,
  messageId: string,
  draftLabelId: string
): Promise<void> {
  await gmail.users.messages.modify({
    userId: "me",
    id: messageId,
    requestBody: { addLabelIds: [draftLabelId] },
  });
}
