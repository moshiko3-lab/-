import { getTokens } from "./tokenStore";
import {
  listUnprocessedInboxMessages,
  createDraftReply,
  addLabelsToMessage,
} from "./gmailInboxService";
import { findOrdersByEmail } from "./shopifyService";
import { generateDraftReply } from "./aiDraft";

export type AutomationResult =
  | {
      messageId: string;
      from: string;
      subject: string;
      ordersFound: number;
      draftId: string;
      status: "drafted";
    }
  | {
      messageId: string;
      from: string;
      subject: string;
      ordersFound: number;
      status: "needs_human_review";
      reason: string;
    }
  | {
      messageId: string;
      from: string;
      subject: string;
      status: "failed";
      error: string;
    };

/**
 * Runs the full draft-replies pipeline for one connected mailbox: scans the
 * inbox for unprocessed customer messages, looks up their Shopify orders,
 * asks Claude for a draft (or a human-review flag), and saves the result to
 * Gmail. Never sends anything - only creates drafts or applies labels.
 */
export async function draftRepliesForAccount(email: string): Promise<AutomationResult[]> {
  const tokens = getTokens(email);
  if (!tokens) {
    throw new Error(`No connected Google account for ${email}`);
  }

  const { gmail, draftLabelId, humanReviewLabelId, messages } = await listUnprocessedInboxMessages(
    tokens,
    email
  );

  const results: AutomationResult[] = [];
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

  return results;
}
