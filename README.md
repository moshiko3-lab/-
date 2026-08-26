# google-connect-code

שרת Node.js + Express + TypeScript שמחבר חשבון Google באמצעות **OAuth 2.0
Authorization Code Flow**, עם גישה ל-Gmail כשימוש עיקרי.

## הגדרה ב-Google Cloud Console

1. צרו פרויקט (או השתמשו בקיים) ב-[Google Cloud Console](https://console.cloud.google.com/).
2. הפעילו את **Gmail API** תחת "APIs & Services" > "Library".
3. במסך ההסכמה (OAuth consent screen) הוסיפו את ה-scopes: `gmail.readonly`,
   `gmail.send`, `userinfo.email`.
4. תחת "Credentials" צרו **OAuth client ID** מסוג "Web application".
5. הוסיפו ל-"Authorized redirect URIs" את הכתובת:
   `http://localhost:3000/auth/google/callback`
6. העתיקו את ה-Client ID וה-Client Secret.

## הרצה מקומית

```bash
npm install
cp .env.example .env
# מלאו את GOOGLE_CLIENT_ID ו-GOOGLE_CLIENT_SECRET בקובץ .env
npm run dev
```

## זרימת החיבור

1. גולשים אל `GET /auth/google` — מפנה למסך ההרשאה של Google.
2. לאחר אישור המשתמש, Google מפנה חזרה אל `GET /auth/google/callback?code=...`.
3. השרת מחליף את ה-`code` בטוקנים (`access_token` + `refresh_token`) מול
   Google, שומר אותם (בזיכרון, לפי אימייל) ומחזיר אישור חיבור.
4. `GET /gmail/messages?email=you@example.com` — דוגמה לשימוש בטוקנים
   השמורים כדי לקרוא ל-Gmail API.

## הערה לגבי אחסון טוקנים

הטוקנים נשמרים בקובץ JSON על הדיסק (`src/tokenStore.ts`, נתיב ברירת מחדל
`data/tokens.json`, ניתן לשינוי עם `TOKEN_STORE_PATH`), כדי לשרוד הפעלות
מחדש של השרת. **חשוב**: אם מריצים בענן, ודאו שהנתיב הזה על **דיסק קבוע
(persistent volume)** — אחרת כל דיפלוי חדש ימחק את החיבור ותצטרכו להתחבר
מחדש. הקובץ נשמר כטקסט גלוי (לא מוצפן) — מספיק לשימוש קטן/יחיד, אבל לפני
production אמיתי עם כמה חנויות כדאי להחליף במסד נתונים עם הצפנה של
ה-`refresh_token`.

## טיוטות תשובה אוטומטיות ללקוחות (Shopify + AI)

`POST /automation/draft-replies?email=you@example.com` סורק את תיבת ה-Inbox
של החשבון המחובר, ולכל מייל חדש מלקוח (שעדיין אין לו את התווית
`AI-Drafted`):

1. מחפש הזמנות של הלקוח ב-Shopify לפי כתובת המייל שלו (Admin API).
2. שולח ל-Claude את תוכן הפנייה + נתוני ההזמנה, ומבקש טיוטת תשובה.
3. שומר את הטיוטה כ-**Draft** בג'ימייל, כתגובה לאותה השרשור (thread) — **לא
   שולח שום דבר אוטומטית**.
4. מתייג את המייל המקורי ב-`AI-Drafted` כדי שלא יעובד שוב בהרצה הבאה.

בן אדם צריך לפתוח את הטיוטה בג'ימייל, לבדוק אותה, ואז לשלוח אותה בעצמו.

### הגדרה נוספת נדרשת

- **Shopify**: צרו custom app בחנות (Settings > Apps and sales channels >
  Develop apps), תנו לו הרשאת `read_orders`, והעתיקו את ה-Admin API access
  token אל `SHOPIFY_ADMIN_ACCESS_TOKEN`. את `SHOPIFY_STORE_DOMAIN` (למשל
  `your-store.myshopify.com`) שימו גם כן ב-`.env`.
- **Anthropic**: מפתח API תחת `ANTHROPIC_API_KEY`.
- כדי שהטיוטות ייווצרו, החשבון צריך להתחבר מחדש דרך `/auth/google` אחרי
  שהתווספו ה-scopes `gmail.modify` ו-`gmail.compose`.

### הרצה חוזרת

השרת מריץ את זה **אוטומטית מתוך עצמו** על כל חשבון מחובר, כל
`AUTOMATION_INTERVAL_MINUTES` דקות (ברירת מחדל: 5). אין צורך ב-cron
חיצוני. אפשר לכבות את זה (ולהריץ רק ידנית דרך ה-endpoint) עם
`AUTOMATION_ENABLED=false`.

חשוב: זה טיימר בתוך תהליך ה-Node — אם השרת נופל/מופעל מחדש, הטיימר מתחיל
מחדש מ-0. וכיוון שהחיבורים ל-Google נשמרים בזיכרון (ראו הערה למעלה),
הפעלה מחדש של השרת גם מאבדת את החשבונות המחוברים.

### קול המותג של Shokogi + מתי לא לענות אוטומטית

כללי הניסוח (טון, שפה, מבנה, מכירה, דיוק) מוטמעים ב-system prompt שנשלח
ל-Claude (`src/aiDraft.ts`). בנוסף:

- **`knowledge/shokogi-knowledge-base.md`** — מלאו כאן רק עובדות מאושרות
  (מחירים, שעות, מדיניות ביטול, WhatsApp, חתימה). ה-AI מקבל הוראה מפורשת
  להשתמש רק במידע שמופיע כאן או בנתוני ההזמנה מ-Shopify, ולעולם לא להמציא.
- **`knowledge/example-replies.md`** — הוסיפו כאן 15–20 זוגות אמיתיים של
  (מייל לקוח → התשובה האידיאלית שלכם), כדי שה-AI יחקה את הסגנון המדויק שלכם
  ולא רק את הכללים המילוליים.
  (השרת קורא את שני הקבצים באתחול — יש להפעיל מחדש אחרי עריכה.)
- כאשר הפנייה היא תלונה רצינית, בקשת החזר, מחלוקת תשלום, פציעה/בטיחות,
  איום משפטי, בקשת הנחה חריגה, מידע חסר, או לקוח כועס — Claude **לא**
  יוצר טיוטת תשובה. במקום זאת המייל מתויג בג'ימייל בתווית
  `Needs-Human-Review` (ניתן לשינוי דרך `GMAIL_HUMAN_REVIEW_LABEL`), כדי
  שבן אדם יטפל בו ידנית.

## פריסה בענן, כדי שזה ירוץ גם כשהמחשב/טלפון שלכם סגורים

השרת חייב לרוץ על מכונה שנשארת דלוקה — לא על המחשב או הטלפון האישי שלכם.
הכי פשוט: **Railway** (או **Render**) — מחוברים לריפו ב-GitHub, וזה בונה
ומריץ אוטומטית מה-`Dockerfile` שבפרויקט.

### שלבים ב-Railway

1. Railway.app → New Project → Deploy from GitHub repo → בחרו את הריפו הזה.
2. תחת Variables, הוסיפו את כל המשתנים מ-`.env.example` (עם ערכים
   אמיתיים) — כולל `GOOGLE_REDIRECT_URI` שצריך להצביע על ה-domain שRailway
   ייתן לכם, למשל `https://your-app.up.railway.app/auth/google/callback`
   (עדכנו את אותה כתובת גם ב-Google Cloud Console, ב-Authorized redirect URIs).
3. **חובה**: הוסיפו Volume (Settings → Volumes) ועגנו אותו לנתיב שמוגדר
   ב-`TOKEN_STORE_PATH` (למשל `/data`, ואז `TOKEN_STORE_PATH=/data/tokens.json`).
   בלי זה, כל דיפלוי חדש ימחק את חיבור הג'ימייל.
4. אחרי הדיפלוי, גלשו פעם אחת ל-`https://your-app.up.railway.app/auth/google`
   כדי לחבר את חשבון הג'ימייל. מהנקודה הזו השרת ימשיך לרוץ ולסרוק לבד,
   24/7, גם כשהמחשב שלכם כבוי.

הכלי `docker build` לא היה זמין בסביבת הפיתוח שבה נכתב הקוד, אז מומלץ
לבדוק build אחד מקומי (`docker build -t shokogi-ai .`) לפני הדיפלוי
הראשון, כדי לוודא שהכל תקין אצלכם.
