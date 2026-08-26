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

לצורך פשטות הדוגמה שומרת טוקנים בזיכרון התהליך (`src/tokenStore.ts`) — הם
נמחקים באתחול מחדש של השרת. לפני שימוש בפרודקשן יש להחליף זאת באחסון קבוע
(מסד נתונים) עם הצפנה של ה-`refresh_token`.
