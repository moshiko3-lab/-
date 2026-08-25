# SHOKOGI Auto-Reply Bot — הפעלה

בוט שרץ **בתוך חשבון ה-Gmail עצמו** (shokogipanama@gmail.com) דרך Google Apps Script.
פועל בשרתי גוגל, פעם בשעה, לגמרי בלי תלות בצ'אט הזה, בטלפון, או בסשן פתוח.

## מה הוא עושה

כל שעה: מחפש מיילים חדשים מ-`mailer@shopify.com` (פניות מטופס יצירת הקשר באתר),
שולף שם/מייל/הודעה של הלקוח, מושך מוצרים רלוונטיים ומחירים מ-Shopify, מבקש מ-Claude
לכתוב תשובה בסגנון של שוקוגי (כולל אזכור וואטסאפ), **שולח את התשובה ישירות ללקוח**,
ומתייג את הפנייה המקורית כ-`Auto-Replied (AI)` כדי לא לענות עליה שוב. אם כבר יש
התכתבות קודמת עם אותו לקוח — הוא מדלג ושולח לך מייל התראה שזה דורש תשובה אישית.
כל תשובה שנשלחת (או פנייה שדולגה) — אתה מקבל עליה מייל התראה לתיבה שלך.

## שלב 1 — צור את הפרויקט

1. היכנס ל-[script.google.com](https://script.google.com) **כשאתה מחובר לחשבון shokogipanama@gmail.com**.
2. New project.
3. מחק את הקוד שם ותדביק במקומו את כל התוכן של `Code.gs` מהתיקייה הזו.
4. שנה את שם הפרויקט (למשל "SHOKOGI Auto-Reply").

## שלב 2 — מפתחות API (Script Properties)

בתפריט הצד → **Project Settings** (גלגל שיניים) → **Script Properties** → **Add script property**.
הוסף שלושה ערכים:

| Property | Value |
|---|---|
| `ANTHROPIC_API_KEY` | מפתח API של Claude — ראה איך להשיג למטה |
| `SHOPIFY_STORE_DOMAIN` | הדומיין של `*.myshopify.com` של החנות (לא www.shokogi.com!) |
| `SHOPIFY_ADMIN_TOKEN` | Access Token של Shopify Admin API — ראה איך להשיג למטה |

### איך להשיג ANTHROPIC_API_KEY
1. היכנס ל-[console.anthropic.com](https://console.anthropic.com)
2. API Keys → Create Key
3. חייב כרטיס אשראי/חיוב מחובר לחשבון (זו קריאת API בתשלום, עלות נמוכה מאוד לכמות המיילים הזו)

### איך להשיג את SHOPIFY_STORE_DOMAIN
בממשק הניהול של שופיפיי, כתובת ה-URL כשאתה מחובר נראית כמו
`https://admin.shopify.com/store/XXXXX` — או תחת Settings → Domains תראה את
כתובת ה-`.myshopify.com` המקורית. זה מה שצריך להכניס (לדוגמה `shokogi.myshopify.com`).

### איך להשיג SHOPIFY_ADMIN_TOKEN
1. בממשק הניהול של שופיפיי: Settings → Apps and sales channels → Develop apps
2. Create an app → תן שם (למשל "Auto-Reply Bot")
3. Configure Admin API scopes → סמן `read_products` בלבד (לא צריך יותר מזה)
4. Install app → Reveal token once → העתק את ה-Admin API access token

## שלב 3 — הרשאה חד-פעמית

בעורך הסקריפט, בחר את הפונקציה `checkAndReplyToInquiries` מהתפריט העליון ולחץ **Run**.
גוגל תבקש ממך לאשר הרשאות (קריאה/שליחה ב-Gmail, גישה לאינטרנט חיצוני) — אשר.
זו ריצה אחת ידנית כדי לתת לסקריפט הרשאה; מכאן והלאה הוא רץ לבד.

## שלב 4 — הפעל את הטריגר השעתי

בתפריט הצד → **Triggers** (אייקון שעון) → **Add Trigger**:
- Function: `checkAndReplyToInquiries`
- Event source: Time-driven
- Type: Hour timer
- Every hour

שמור. זהו — הבוט פעיל.

## בדיקה ועצירה

- **לבדוק שזה עובד:** תריץ את `checkAndReplyToInquiries` ידנית מהעורך, ותסתכל ב-Executions (בתפריט הצד) לראות לוג.
- **לעצור זמנית:** מחק את הטריגר תחת Triggers.
- **לראות מה נשלח:** תיקיית Sent בג'ימייל, וכן ה-labels `Auto-Replied (AI)` על ההודעות המקוריות.
