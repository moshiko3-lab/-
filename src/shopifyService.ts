import { config } from "./config";

export interface ShopifyOrderSummary {
  name: string; // e.g. "#1001"
  orderStatusUrl: string | null;
  financialStatus: string | null;
  fulfillmentStatus: string | null;
  createdAt: string;
  totalPrice: string;
  currency: string;
  lineItems: { title: string; quantity: number }[];
}

/**
 * Looks up recent orders placed by a customer, by email, via the Shopify
 * Admin REST API. Requires a custom/private app Admin API access token with
 * the `read_orders` scope.
 */
export async function findOrdersByEmail(
  email: string,
  limit = 5
): Promise<ShopifyOrderSummary[]> {
  const url = new URL(
    `https://${config.shopify.storeDomain}/admin/api/${config.shopify.apiVersion}/orders.json`
  );
  url.searchParams.set("status", "any");
  url.searchParams.set("email", email);
  url.searchParams.set("limit", String(limit));
  url.searchParams.set(
    "fields",
    "name,order_status_url,financial_status,fulfillment_status,created_at,total_price,currency,line_items"
  );

  const response = await fetch(url, {
    headers: {
      "X-Shopify-Access-Token": config.shopify.adminAccessToken,
      Accept: "application/json",
    },
  });

  if (!response.ok) {
    throw new Error(
      `Shopify orders lookup failed: ${response.status} ${await response.text()}`
    );
  }

  const data = (await response.json()) as {
    orders: Array<{
      name: string;
      order_status_url: string | null;
      financial_status: string | null;
      fulfillment_status: string | null;
      created_at: string;
      total_price: string;
      currency: string;
      line_items: Array<{ title: string; quantity: number }>;
    }>;
  };

  return data.orders.map((order) => ({
    name: order.name,
    orderStatusUrl: order.order_status_url,
    financialStatus: order.financial_status,
    fulfillmentStatus: order.fulfillment_status,
    createdAt: order.created_at,
    totalPrice: order.total_price,
    currency: order.currency,
    lineItems: order.line_items.map((item) => ({
      title: item.title,
      quantity: item.quantity,
    })),
  }));
}
