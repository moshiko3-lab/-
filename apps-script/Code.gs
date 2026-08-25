/**
 * SHOKOGI auto-reply bot.
 * Runs entirely inside the shokogipanama@gmail.com Google account via a
 * time-driven trigger — no dependency on any external session being open.
 *
 * Setup: see apps-script/README.md
 */

var LABEL_NAME = 'Auto-Replied (AI)'; // same label already used/created earlier via the Gmail connector
var WHATSAPP_NUMBER = '+507 62596666';
var STORE_PUBLIC_DOMAIN = 'www.shokogi.com';
var CLAUDE_MODEL = 'claude-sonnet-5';
var NOTIFY_EMAIL = 'shokogipanama@gmail.com'; // change if you want notifications elsewhere

function checkAndReplyToInquiries() {
  var label = GmailApp.getUserLabelByName(LABEL_NAME) || GmailApp.createLabel(LABEL_NAME);
  var query = 'from:mailer@shopify.com subject:"New customer message" -label:"' + LABEL_NAME + '"';
  var threads = GmailApp.search(query, 0, 50);

  if (threads.length === 0) return;

  var products = getShopifyProducts();
  var productsContext = products.map(function (p) {
    var priceRange = p.minPrice === p.maxPrice ? ('$' + p.minPrice) : ('$' + p.minPrice + '-' + p.maxPrice);
    return '- ' + p.title + ' (' + priceRange + '): https://' + STORE_PUBLIC_DOMAIN + '/products/' + p.handle;
  }).join('\n');

  threads.forEach(function (thread) {
    try {
      handleThread(thread, label, productsContext);
    } catch (err) {
      // Never let one bad thread kill the whole run.
      Logger.log('Error handling thread ' + thread.getId() + ': ' + err);
      notifyOwner('SHOKOGI bot error', 'Failed on thread ' + thread.getId() + ':\n' + err);
    }
  });
}

function handleThread(thread, label, productsContext) {
  var firstMsg = thread.getMessages()[0];
  var body = firstMsg.getPlainBody();

  var name = extractField(body, 'Name');
  var email = extractField(body, 'Email');
  var comment = extractField(body, 'Comment');

  if (!email || !comment) {
    thread.addLabel(label);
    return;
  }

  // First-contact check: skip if we already have a sent conversation with
  // this address — an existing thread needs a human, not a bot.
  var priorSent = GmailApp.search('to:' + email + ' in:sent', 0, 1);
  if (priorSent.length > 0) {
    thread.addLabel(label);
    notifyOwner(
      'Skipped auto-reply — existing conversation',
      'Skipped ' + name + ' (' + email + ') — found a prior sent email to this address. Needs your personal reply.\n\nOriginal message:\n' + comment
    );
    return;
  }

  var replyBody = callClaude(name, comment, productsContext);

  if (!replyBody || replyBody.trim() === 'SKIP_SPAM') {
    thread.addLabel(label);
    return;
  }

  GmailApp.sendEmail(email, 'Re: ' + firstMsg.getSubject(), replyBody, {
    name: 'SHOKOGI',
  });

  thread.addLabel(label);

  notifyOwner(
    'Auto-replied to ' + name + ' (' + email + ')',
    replyBody
  );
}

function extractField(body, fieldName) {
  var regex = new RegExp(fieldName + ':\\s*\\n?([^\\n]+)');
  var match = body.match(regex);
  return match ? match[1].trim() : '';
}

function notifyOwner(subject, body) {
  MailApp.sendEmail(NOTIFY_EMAIL, '[SHOKOGI bot] ' + subject, body);
}

/** ---------- Shopify ---------- */

function getShopifyProducts() {
  var cache = CacheService.getScriptCache();
  var cached = cache.get('shopify_products');
  if (cached) return JSON.parse(cached);

  var props = PropertiesService.getScriptProperties();
  var domain = props.getProperty('SHOPIFY_STORE_DOMAIN'); // e.g. your-store.myshopify.com
  var token = props.getProperty('SHOPIFY_ADMIN_TOKEN');

  var url = 'https://' + domain + '/admin/api/2024-01/products.json?status=active&limit=250&fields=title,handle,variants';
  var options = {
    method: 'get',
    headers: { 'X-Shopify-Access-Token': token },
    muteHttpExceptions: true,
  };
  var resp = UrlFetchApp.fetch(url, options);
  var data = JSON.parse(resp.getContentText());

  var products = (data.products || []).map(function (p) {
    var prices = p.variants.map(function (v) { return parseFloat(v.price); });
    return {
      title: p.title,
      handle: p.handle,
      minPrice: Math.min.apply(null, prices),
      maxPrice: Math.max.apply(null, prices),
    };
  });

  cache.put('shopify_products', JSON.stringify(products), 3600); // 1 hour
  return products;
}

/** ---------- Claude ---------- */

function callClaude(customerName, customerComment, productsContext) {
  var apiKey = PropertiesService.getScriptProperties().getProperty('ANTHROPIC_API_KEY');

  var systemPrompt = [
    'You are drafting a customer-service email reply for SHOKOGI, a surf/foil school & shop in Playa Venao, Panama (www.shokogi.com).',
    '',
    'If the customer message is spam/junk/bot text with no real question, respond with EXACTLY the text: SKIP_SPAM (nothing else, no explanation).',
    '',
    'Otherwise, write ONLY the reply email body (no subject line, no preamble, no explanation) in the SAME language the customer wrote in (Hebrew, English, Spanish, whatever they used).',
    '',
    "Match SHOKOGI's real, established writing style: casual, warm, friendly, personal — never corporate/robotic boilerplate. Real examples of this shop's past replies, for tone calibration only (do not copy verbatim):",
    '- "Hi Jose, Welcome to Panama! I understand you\'re interested in joining one of our foil camps, and we\'d be very happy to host you..."',
    '- "Hello, welcome to our paradise foil spot foil camps private room for 7 days 4250 USD Including all services- boat, jet sky, 2 meals a day..."',
    '- "Hi Kylie How are you? ... we got all kinds of surf boards with a quiver of 200 surfboards..."',
    '- "Hiii we were gonna update about december next month. you can see in the website soon shokogi.com"',
    '',
    'Keep it short and concrete: mention the specific relevant package(s), price, and product link(s) from the product list below. Invite them to reply with more questions (dates, number of people) or to book via the link.',
    '',
    'Only use facts from the product list below — never invent policies, discounts, exact availability, or dates that are not in that data. For a support/service request that does not map to a purchasable product (e.g. "where are my photos from my session", a complaint, a logistics question), do NOT invent a product or a process — just write a warm, honest acknowledgment that the team will look into it and follow up.',
    '',
    'ALWAYS also mention, naturally worked into the reply (near the end, before the sign-off), that they are welcome to reach out on WhatsApp at ' + WHATSAPP_NUMBER + ' for faster/direct contact, phrased in the reply\'s language.',
    '',
    'Sign off as "צוות SHOKOGI" when replying in Hebrew, or "SHOKOGI Team" when replying in any other language.',
    '',
    'Available SHOKOGI products (use only these facts):',
    productsContext,
  ].join('\n');

  var userPrompt = 'Customer name: ' + customerName + '\nCustomer message:\n' + customerComment;

  var payload = {
    model: CLAUDE_MODEL,
    max_tokens: 800,
    system: systemPrompt,
    messages: [{ role: 'user', content: userPrompt }],
  };

  var options = {
    method: 'post',
    contentType: 'application/json',
    headers: {
      'x-api-key': apiKey,
      'anthropic-version': '2023-06-01',
    },
    payload: JSON.stringify(payload),
    muteHttpExceptions: true,
  };

  var resp = UrlFetchApp.fetch('https://api.anthropic.com/v1/messages', options);
  var json = JSON.parse(resp.getContentText());

  if (json.error) {
    throw new Error('Claude API error: ' + JSON.stringify(json.error));
  }

  return json.content[0].text;
}
