import Anthropic from "@anthropic-ai/sdk";
import { config } from "./config";
import type { ShopifyOrderSummary } from "./shopifyService";

let client: Anthropic | undefined;
function getClient(): Anthropic {
  if (!client) {
    client = new Anthropic({ apiKey: config.anthropic.apiKey });
  }
  return client;
}

const SYSTEM_PROMPT = `You are a customer support assistant for an online store on Shopify.
You write a DRAFT reply to one incoming customer email - a human will review and send it, so it does not need a greeting/sign-off disclaimer.

Rules:
- Answer only using the order data provided below. Never invent an order status, tracking number, or delivery date that isn't in the data.
- If no matching order was found, say so and ask the customer to confirm the email/order number they used at checkout - don't guess.
- If multiple orders were found, address the most recent one unless the customer's message clearly refers to a different one.
- Match the customer's language and tone (formal/informal) and reply in the same language they wrote in.
- Keep it concise and specific to what they asked.
- Output only the email body text, no subject line, no explanation of your reasoning.`;

export async function generateDraftReply(params: {
  customerEmail: string;
  customerMessage: string;
  orders: ShopifyOrderSummary[];
}): Promise<string> {
  const ordersBlock =
    params.orders.length === 0
      ? "No orders found for this email address."
      : params.orders
          .map((order) =>
            [
              `Order ${order.name} (placed ${order.createdAt})`,
              `  Payment status: ${order.financialStatus ?? "unknown"}`,
              `  Fulfillment status: ${order.fulfillmentStatus ?? "unfulfilled"}`,
              `  Total: ${order.totalPrice} ${order.currency}`,
              `  Items: ${order.lineItems
                .map((item) => `${item.quantity}x ${item.title}`)
                .join(", ")}`,
              order.orderStatusUrl ? `  Tracking/status link: ${order.orderStatusUrl}` : null,
            ]
              .filter(Boolean)
              .join("\n")
          )
          .join("\n\n");

  const message = await getClient().messages.create({
    model: config.anthropic.model,
    max_tokens: 600,
    system: SYSTEM_PROMPT,
    messages: [
      {
        role: "user",
        content: `Customer email address: ${params.customerEmail}

Customer's message:
"""
${params.customerMessage}
"""

Shopify order data for this customer:
${ordersBlock}`,
      },
    ],
  });

  const textBlock = message.content.find((block) => block.type === "text");
  if (!textBlock || textBlock.type !== "text") {
    throw new Error("Anthropic response contained no text block");
  }
  return textBlock.text.trim();
}
