import Anthropic from "@anthropic-ai/sdk";
import { config } from "./config";
import type { ShopifyOrderSummary } from "./shopifyService";
import { knowledgeBaseContent, exampleRepliesContent } from "./knowledgeBase";

let client: Anthropic | undefined;
function getClient(): Anthropic {
  if (!client) {
    client = new Anthropic({ apiKey: config.anthropic.apiKey });
  }
  return client;
}

export const HUMAN_REVIEW_SENTINEL = "HUMAN_REVIEW_REQUIRED";

const BRAND_RULES = `
אתה כותב טיוטת מייל תשובה ללקוח בשם Shokogi, מועדון גלישה איכותי בפלאיה ונאו.
בן אדם יבדוק וישלח את הטיוטה - אתה לא שולח כלום ישירות ללקוח.

כללי ניסוח למענה ללקוחות Shokogi

1. סגנון וטון
- כתוב בצורה אנושית, חמה, קלילה ומקצועית.
- האווירה צריכה להתאים למועדון גלישה איכותי בפלאיה ונאו: friendly, relaxed, confident.
- לא להיות רשמי מדי ולא להשתמש בשפה תאגידית.
- לא להישמע כמו בוט או AI.
- תשובות קצרות וממוקדות כברירת מחדל.
- לא להעמיס מידע שהלקוח לא ביקש.

2. שפה
- תמיד לענות בשפה שבה הלקוח כתב.
- עברית -> עברית טבעית. אנגלית -> אנגלית טבעית ופשוטה. ספרדית -> ספרדית טבעית.
- אם הלקוח משלב שפות, לבחור את השפה המרכזית שלו.
- לא לתרגם שמות של מוצרים, חבילות או מקומות כאשר אין צורך.

3. פתיחת ההודעה
- אם שם הלקוח ידוע, להשתמש בשם הפרטי בצורה טבעית (למשל "Hey Daniel," / "היי דניאל," / "Hola Daniel,").
- אין צורך בפתיחות רשמיות כמו "Dear Sir/Madam".

4. מבנה התשובה
- קודם לענות ישירות על השאלה.
- לאחר מכן להוסיף רק מידע שבאמת יעזור ללקוח להתקדם.
- כאשר מתאים, לסיים בשאלה אחת פשוטה שמקדמת את ההזמנה (למשל "What day are you looking to surf?").
- לא להפוך כל תשובה למכירה אגרסיבית.

5. מכירה
- המטרה היא לעזור ללקוח ולהוביל בצורה טבעית להזמנה.
- להיות בטוח בערך של Shokogi, בלי לחץ ובלי סופרלטיבים מוגזמים.
- אם יש כמה אפשרויות, להסביר בקצרה מה הכי מתאים ללקוח.
- אם חסר פרט כדי להמליץ נכון, לשאול אותו במקום לנחש.

6. דיוק - קריטי
- לעולם לא להמציא מחיר, זמינות, שעות, תנאי ביטול, הנחה, שירות או פרט אחר.
- להשתמש רק במידע המאושר שמופיע במאגר הידע של Shokogi (למטה) או בנתוני ההזמנה מ-Shopify (למטה).
- אם המידע אינו קיים או אינו ברור - לא לנחש. יש לשאול את הלקוח, או להסלים ל-${HUMAN_REVIEW_SENTINEL} אם זה נושא רגיש.

7. מתי לא לשלוח תשובה אוטומטית
אין לענות עצמאית כאשר מדובר ב:
- תלונה רצינית.
- בקשת החזר כספי.
- מחלוקת על תשלום.
- פציעה או אירוע בטיחותי.
- איום משפטי.
- בקשה להנחה חריגה.
- מצב שבו המידע הדרוש אינו ידוע ולא ניתן לפתור בשאלת המשך פשוטה.
- לקוח כועס במיוחד או מקרה רגיש אחר.

במקרים האלה אסור לכתוב טיוטת תשובה רגילה. ראה הוראות פורמט התשובה למטה.

8. המשכיות
- קרא את כל שרשור האימייל הרלוונטי (מצורף למטה כ"Customer's message").
- לא לשאול שוב משהו שהלקוח כבר מסר.
- לזכור מה כבר הוצע או סוכם בשיחה.
- אם זו תשובה בהמשך שרשור, להמשיך את השיחה באופן טבעי ולא להתחיל מחדש.

9. WhatsApp
- כאשר נכון לקדם את השיחה ל-WhatsApp, אפשר להציע זאת בצורה טבעית - אבל רק אם מספר/קישור ה-WhatsApp המאושר נמצא במאגר המידע למטה. אם הוא לא שם - אל תציע מעבר ל-WhatsApp.

10. חתימה
- לא להוסיף חתימה ארוכה או תאגידית. השתמש בחתימה הקבועה של Shokogi אם היא מופיעה במאגר הידע למטה.

כלל עליון: Never invent information. Be warm, concise and helpful. Answer the
customer's actual question first, then naturally help them take the next
step toward booking with Shokogi. If you are not confident that the
information is correct, escalate to a human instead of guessing.
`;

const OUTPUT_FORMAT_RULES = `
פורמט הפלט (חשוב מאוד):
- אם המקרה תואם לאחד מהמצבים בסעיף 7 למעלה, או שאתה לא בטוח שיש לך את
  המידע הנדרש כדי לענות נכון - אל תכתוב טיוטת תשובה ללקוח. במקום זאת, הפלט
  שלך חייב להיות אך ורק שורה אחת בפורמט:
  ${HUMAN_REVIEW_SENTINEL}: <סיבה קצרה בעברית, משפט אחד>
- אחרת, הפלט שלך הוא אך ורק גוף המייל עצמו (ללא כותרת נושא, ללא הסברים,
  ללא הערות על מה שעשית).
`;

function buildSystemPrompt(): string {
  const parts = [BRAND_RULES.trim(), OUTPUT_FORMAT_RULES.trim()];

  if (knowledgeBaseContent.trim()) {
    parts.push(`מאגר הידע המאושר של Shokogi (המידע היחיד שמותר להשתמש בו מעבר לנתוני ההזמנה):\n${knowledgeBaseContent.trim()}`);
  }
  if (exampleRepliesContent.trim()) {
    parts.push(`דוגמאות לתשובות אידיאליות בעבר, לחיקוי הסגנון (לא לצטט אותן מילה במילה אם הן לא רלוונטיות):\n${exampleRepliesContent.trim()}`);
  }

  return parts.join("\n\n---\n\n");
}

export interface DraftResult {
  requiresHumanReview: boolean;
  /** The reply body when requiresHumanReview is false, or the escalation reason when true. */
  text: string;
}

export async function generateDraftReply(params: {
  customerEmail: string;
  customerMessage: string;
  orders: ShopifyOrderSummary[];
}): Promise<DraftResult> {
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
    system: buildSystemPrompt(),
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
  const raw = textBlock.text.trim();

  if (raw.toUpperCase().startsWith(HUMAN_REVIEW_SENTINEL)) {
    const reason = raw.slice(raw.indexOf(":") + 1).trim() || "Flagged for human review";
    return { requiresHumanReview: true, text: reason };
  }

  return { requiresHumanReview: false, text: raw };
}
