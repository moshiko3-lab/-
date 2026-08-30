# Connecting the school's WhatsApp

What this gets you: the conversation inside the manager, a reminder before
every session, a brief on the day's board each morning to whoever is working,
and a bot that answers the questions that get asked forty times a week.

Read the two limits first. They are WhatsApp's, not ours, and both of them
change what is worth building.

### 1. A number connected to the API leaves the WhatsApp Business app

A phone number can be on the Cloud API **or** in the WhatsApp Business app on a
phone. Never both. Registering the school's existing number for the API signs it
out of the app on the phone, and the chat history on that phone does not come
across.

So there are two ways in, and the school has to pick one:

* **A second number for the API.** The existing number keeps working exactly as
  it does today, on the phone, with its history. The new number is what sends
  reminders and briefs and what the bot answers on. Nothing is lost, and it can
  be undone by ignoring it. This is the recommendation.
* **Move the existing number over.** Everything then lives in the manager, which
  is tidier, and the day it goes wrong nobody at the school has WhatsApp on
  their phone for the business at all. Only worth it once the setup below has
  been proved on a test number.

### 2. There is no group

The Cloud API cannot post into a WhatsApp group. There is no endpoint for it,
and no permission that unlocks one — group messaging is only possible through
unofficial libraries that drive a logged-in WhatsApp Web session, which is
against Meta's terms and gets business numbers banned.

So "a message to the Shokogi group every morning at seven" is built as the same
message to each person on a list, sent individually and at the same moment. In
practice that is better: an instructor who is not working today can be left off
the list, and nobody can reply into a thread the whole school reads.

If it has to be the actual group, the WhatsApp screen has **Send to a group by
hand** beside the brief: WhatsApp opens with today's board already written and
you pick the group. A person still presses send, but nobody types the day out.

### 3. Free-form messages only inside 24 hours

The school may write freely to somebody for 24 hours after **their** last
message. Outside that window nothing goes but a **template** Meta approved
beforehand. Reminders and briefs are almost always outside it, which is why
both are templates and why the two below have to be submitted and approved
before either automation does anything.

---

## What goes where

```
the page  ──asks──▶  the Edge Function  ──sends──▶  Meta  ──▶  the customer
   │                        │
   └── reads the ───────────┴── writes the conversation ──▶ Postgres
       conversation
```

The Meta token can message anyone in the world as the school. It lives as a
secret on the function and nowhere else — not in the page, which anyone can
open, and not in the database, which every signed-in device can read. A browser
can *ask* for a message to be sent; it can never send one.

---

## Setting it up

### Step 1 — the database

In the Supabase SQL editor, run `supabase/schema.sql` (if it has not been run),
then `supabase/whatsapp.sql`. Both are safe to run twice.

### Step 2 — Meta

1. **A business portfolio** at <https://business.facebook.com>, with the
   school's legal name and website.
2. **An app**: <https://developers.facebook.com/apps> → Create app → *Business*
   → add the **WhatsApp** product. This creates a WhatsApp Business Account
   (WABA) and gives you a free test number.
3. **The number.** WhatsApp Manager → *Phone numbers* → add the number the
   school will use, and verify it by SMS or call. Re-read limit 1 above before
   you use the number that is in the phone app today.
4. **The ids.** In the WhatsApp → API setup panel, copy the **Phone number ID**
   (a long number, not the phone number itself) and the **WhatsApp Business
   Account ID**.
5. **A permanent token.** Business settings → *Users* → **System users** → add
   one with the Admin role → *Assign assets* → the app and the WABA → *Generate
   token* → tick `whatsapp_business_messaging` and
   `whatsapp_business_management`. Set no expiry. Copy it once; it is not shown
   again.
6. **The app secret**: App settings → Basic → *App secret* → Show.

### Step 3 — the function

Set the secrets, then deploy. None of these ever go in the repository.

```
supabase login
supabase link --project-ref bxjwqvoscbzhetuwhyvk

supabase secrets set \
  WA_TOKEN="<the permanent token>" \
  WA_PHONE_ID="<the phone number id>" \
  WA_VERIFY_TOKEN="<any long random string you invent>" \
  WA_APP_SECRET="<the app secret>" \
  WA_TICK_SECRET="<another long random string you invent>"

supabase functions deploy whatsapp --no-verify-jwt
```

`--no-verify-jwt` is required: Meta's webhook cannot carry a Supabase token, and
the gate would refuse every message the school is sent. The function checks each
door itself — a signed-in member for `/send` and `/health`, Meta's signature for
`/webhook`, the tick secret for `/tick`.

### Step 4 — the webhook

In the app: WhatsApp → *Configuration* → Webhook → Edit.

* **Callback URL**
  `https://bxjwqvoscbzhetuwhyvk.supabase.co/functions/v1/whatsapp/webhook`
* **Verify token** — the `WA_VERIFY_TOKEN` you set above, character for
  character.

Verify and save, then **Manage** the fields and subscribe to **messages**.
Nothing arrives without that subscription, and the panel does not say so.

### Step 5 — the two templates

WhatsApp Manager → *Message templates* → Create. Both are **Utility**, both in
the language you set on the automation (`en` unless you change it). The names
have to match what the WhatsApp screen has in *Automations*.

**`session_reminder`** — three variables, in this order: the person's name,
what they booked, and when it is.

> Hi {{1}}, a reminder from Shokogi Surf School: {{2}} is on {{3}}. Reply here
> if anything has changed. See you on the water.

**`daily_brief`** — two variables: the date, and the day in one line.

> Shokogi, {{1}}. Today: {{2}}

Approval usually takes minutes and occasionally a day. A template parameter may
not contain a newline or a tab — Meta refuses the whole message — which is why
the brief goes out as one line of stops through a template, and as a proper
list when it is sent inside the open window.

### Step 6 — the clock

Reminders and the brief are worked out and queued by `/tick`. Something has to
call it. In the Supabase SQL editor, switch on the `pg_cron` and `pg_net`
extensions (Database → Extensions), then run the block at the bottom of
`supabase/whatsapp.sql` with the two placeholders filled in.

Until that is scheduled, **Run now** on the WhatsApp screen does one turn of it
by hand, which is enough to test with.

### Step 7 — turn it on

Open the manager → **WhatsApp** → *Setup*. Every line should say `set`. Then in
*Automations*, switch on what the school actually wants, one at a time:

* **Reminders** — hours before, and the quiet hours nothing goes out inside.
* **The morning brief** — the time, the days, and who is on the list. Preview
  shows exactly what will be sent.
* **The bot** — the booking page link, what it says when it recognises nothing,
  and a rule per question worth answering. Keep it short and hand over early: a
  wrong answer sent in the school's name is worse than no answer.

---

## What it costs

Meta charges per template message, by category and by the country of the
person receiving it; replies sent inside the 24-hour window are free. Utility
templates — which is what both of ours are — are the cheapest category. The
current price list is on Meta's own pricing page; there is no point in a number
here that will be wrong in six months.

---

## When it does not work

**The webhook will not verify.** The verify token has to match exactly, and the
function has to be deployed before Meta calls it. Try it yourself:

```
curl "https://bxjwqvoscbzhetuwhyvk.supabase.co/functions/v1/whatsapp/webhook?hub.mode=subscribe&hub.verify_token=<yours>&hub.challenge=hello"
```

It should answer `hello`.

**Messages arrive but nothing shows in the manager.** Either the *messages*
field was never subscribed (step 4), or `whatsapp.sql` has not been run. The
Chats tab says which.

**Everything is refused with "outside the 24-hour window".** That is the rule
working. Approve the templates, or open the chat and send it by hand — the
button is on the thread.

**A reminder went out twice.** It cannot: the queue's dedupe key is unique per
session and per number. Two rows in `wa_jobs` with the same `dedupe` is a
database that was not created by `whatsapp.sql`.

**Nothing is being sent at the right time.** `select * from cron.job_run_details
order by start_time desc limit 20;` says whether the tick is running at all.

## The doors, if you ever need them directly

| | |
| --- | --- |
| `GET /whatsapp/webhook` | Meta's handshake |
| `POST /whatsapp/webhook` | messages and delivery reports, signed by Meta |
| `POST /whatsapp/send` | `{to, text}` or `{to, template, lang, params}` — signed-in members only |
| `POST /whatsapp/tick` | queue what is due, then send it — the tick secret, or a signed-in member |
| `GET /whatsapp/health` | what is configured and what is missing |
