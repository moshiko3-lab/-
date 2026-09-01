/* ======================================================================
   הספר המשותף.

   בלי החלק הזה כל דפדפן שומר לעצמו, וזה מספיק ליומן על טלפון אחד — אבל
   תור שלקוחה קובעת מהטלפון שלה לא מגיע לשום מקום. עם החלק הזה יש
   Postgres אחד (Supabase) שכולם מדברים איתו: הלקוחה כותבת אליו תור,
   והיומן מוריד אותו.

   שלושה כללים שמחזיקים את זה:

   * הכתובת והמפתח שלמטה נועדו לשבת בדף ציבורי. מה ששומר על המידע הוא
     כללי ההרשאה במסד (supabase.sql), לא סודיות המפתח.
   * אורחת לא קוראת תורים ולא קוראת טפסים. כדי להציג שעות פנויות היא
     מקבלת רק טווחים תפוסים, בלי שם ובלי טלפון.
   * הטפסים הם מידע רפואי. אורחת יכולה רק לכתוב טופס, לעולם לא לקרוא.
   ====================================================================== */

/* הבנייה מחליפה את השורה הזאת בשלמותה בתוכן cloud.json */
var CLOUD = {url: "", key: ""};

var CL_SESSION = "brows.session";
var CL_OUTBOX  = "brows.outbox";
var CL_SINCE   = "brows.since";
var CL_TABLES  = ["settings", "services", "clients", "appointments", "blocks", "forms"];
/* איך כל טבלה יושבת בתוך ה-db המקומי */
var CL_KEY = {settings:"settings", services:"services", clients:"clients",
              appointments:"appointments", blocks:"blocks", forms:"forms"};

function cloudConfigured(){ return !!(CLOUD.url && CLOUD.key); }
function jread(k, d){ try { var v = localStorage.getItem(k); return v ? JSON.parse(v) : d; }
                      catch (e) { return d; } }
function jwrite(k, v){ try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) {} }
function cloudSession(){ return jread(CL_SESSION, null); }
function cloudSignedIn(){ var s = cloudSession(); return !!(s && s.access_token); }
function cloudWho(){ var s = cloudSession(); return (s && s.email) || ""; }

/* ------------------------------------------------------------- החוט */
function clHeaders(auth){
  var s = cloudSession();
  var h = {"apikey": CLOUD.key, "Content-Type": "application/json"};
  h.Authorization = "Bearer " + ((auth !== false && s && s.access_token) || CLOUD.key);
  return h;
}
function clFetch(path, opts){
  opts = opts || {};
  return fetch(CLOUD.url + path, {
    method: opts.method || "GET",
    headers: Object.assign(clHeaders(opts.auth), opts.headers || {}),
    body: opts.body ? JSON.stringify(opts.body) : undefined
  }).then(function(r){
    if (r.status === 204) return null;
    return r.text().then(function(t){
      var j = null;
      try { j = t ? JSON.parse(t) : null; } catch (e) { j = t; }
      if (!r.ok) {
        var msg = (j && (j.message || j.error_description || j.error)) || ("HTTP " + r.status);
        var err = new Error(msg); err.status = r.status; throw err;
      }
      return j;
    });
  });
}

/* ------------------------------------------------------------ כניסה */
function cloudSignIn(email, password){
  return clFetch("/auth/v1/token?grant_type=password",
                 {method: "POST", auth: false, body: {email: email, password: password}})
    .then(function(j){
      jwrite(CL_SESSION, {access_token: j.access_token, refresh_token: j.refresh_token,
                          email: email, expires_at: Date.now() + (j.expires_in || 3600) * 1000});
      return true;
    });
}
function cloudSignOut(){
  try { localStorage.removeItem(CL_SESSION); localStorage.removeItem(CL_SINCE); } catch (e) {}
}
function cloudRefresh(){
  var s = cloudSession();
  if (!s || !s.refresh_token) return Promise.reject(new Error("no session"));
  return clFetch("/auth/v1/token?grant_type=refresh_token",
                 {method: "POST", auth: false, body: {refresh_token: s.refresh_token}})
    .then(function(j){
      jwrite(CL_SESSION, {access_token: j.access_token, refresh_token: j.refresh_token,
                          email: s.email, expires_at: Date.now() + (j.expires_in || 3600) * 1000});
    });
}

/* ------------------------------------------------------------ תיבת יוצא
   מה ששונה כאן ועוד לא נמסר. שורד רענון, קריסה ולילה בלי קליטה. */
function outbox(){ return jread(CL_OUTBOX, {}) || {}; }
function cloudDirty(table, id){
  if (!id || CL_TABLES.indexOf(table) < 0) return;
  var o = outbox(); (o[table] = o[table] || {})[id] = 1; jwrite(CL_OUTBOX, o);
}
function cloudDelete(table, id){
  if (!id || CL_TABLES.indexOf(table) < 0) return;
  var o = outbox(); (o[table] = o[table] || {})[id] = "del"; jwrite(CL_OUTBOX, o);
}
function outboxCount(){
  var o = outbox(), n = 0;
  for (var k in o) n += Object.keys(o[k] || {}).length;
  return n;
}
function outboxClear(table, ids){
  var o = outbox();
  if (!o[table]) return;
  ids.forEach(function(id){ delete o[table][id]; });
  if (!Object.keys(o[table]).length) delete o[table];
  jwrite(CL_OUTBOX, o);
}

/* --------------------------------------------------- מקומי מול השרת */
function localRow(local, table, id){
  if (table === "settings") return {id: "settings", data: local.settings};
  var list = local[CL_KEY[table]] || [];
  for (var i = 0; i < list.length; i++) if (list[i].id === id) return {id: id, data: list[i]};
  return null;
}
function applyRow(local, table, row){
  if (table === "settings") {
    if (row.data) local.settings = Object.assign(local.settings, row.data);
    return;
  }
  var key = CL_KEY[table];
  var list = local[key] || (local[key] = []);
  var at = -1;
  for (var i = 0; i < list.length; i++) if (list[i].id === row.id) { at = i; break; }
  if (row.deleted) { if (at >= 0) list.splice(at, 1); return; }
  var rec = Object.assign({}, row.data, {id: row.id});
  if (at >= 0) list[at] = rec; else list.push(rec);
}

var CL_BUSY = false;
var CL_STATE = {at: 0, error: "", live: false};

function cloudSync(){
  if (!cloudConfigured() || !cloudSignedIn() || CL_BUSY) return Promise.resolve(false);
  CL_BUSY = true;
  var since = jread(CL_SINCE, "1970-01-01T00:00:00Z");
  var stamp = new Date().toISOString();
  var local = loadDb();
  var changed = false;

  /* קודם מוסרים מה ששלנו, ואז מושכים — כדי שמה שנכתב כאן לא יידרס
     מיד על ידי גרסה ישנה יותר שהשרת עוד מחזיק */
  var box = outbox();
  var pushes = Object.keys(box).map(function(table){
    var ids = Object.keys(box[table]);
    var rows = [], dels = [];
    ids.forEach(function(id){
      if (box[table][id] === "del") { dels.push(id); return; }
      var r = localRow(local, table, id);
      if (r) rows.push({id: r.id, data: r.data, deleted: false});
      else dels.push(id);
    });
    var jobs = [];
    if (rows.length)
      jobs.push(clFetch("/rest/v1/" + table + "?on_conflict=id",
        {method: "POST", headers: {Prefer: "resolution=merge-duplicates"}, body: rows}));
    if (dels.length)
      jobs.push(clFetch("/rest/v1/" + table + "?id=in.(" +
        dels.map(encodeURIComponent).join(",") + ")",
        {method: "PATCH", body: {deleted: true}}));
    return Promise.all(jobs).then(function(){ outboxClear(table, ids); });
  });

  return Promise.all(pushes).then(function(){
    return Promise.all(CL_TABLES.map(function(table){
      return clFetch("/rest/v1/" + table + "?select=id,data,deleted,updated_at&updated_at=gt." +
                     encodeURIComponent(since) + "&order=updated_at.asc&limit=1000")
        .then(function(rows){
          (rows || []).forEach(function(row){ applyRow(local, table, row); changed = true; });
        });
    }));
  }).then(function(){
    if (changed) saveDb(local);
    jwrite(CL_SINCE, stamp);
    CL_STATE = {at: Date.now(), error: "", live: true};
    CL_BUSY = false;
    if (changed && typeof window !== "undefined")
      window.dispatchEvent(new Event("brows-cloud"));
    return changed;
  }).catch(function(e){
    CL_BUSY = false;
    if (e.status === 401) {
      return cloudRefresh().then(function(){ return cloudSync(); },
        function(){ cloudSignOut(); CL_STATE = {at: 0, error: "צריך להתחבר מחדש", live: false};
                    if (typeof window !== "undefined") window.dispatchEvent(new Event("brows-cloud")); });
    }
    CL_STATE = {at: Date.now(), error: e.message || "שגיאת סנכרון", live: false};
    return false;
  });
}

/* --------------------------------------------- מה שדף ציבורי מבקש */
/* הגדרות, טיפולים וחסימות — מידע פומבי ממילא. */
function cloudPublicLoad(){
  if (!cloudConfigured()) return Promise.reject(new Error("no cloud"));
  return Promise.all([
    clFetch("/rest/v1/settings?select=data&id=eq.settings", {auth: false}),
    clFetch("/rest/v1/services?select=id,data&deleted=is.false", {auth: false}),
    clFetch("/rest/v1/blocks?select=id,data&deleted=is.false", {auth: false})
  ]).then(function(r){
    var db = blankDb();
    if (r[0] && r[0][0] && r[0][0].data) db.settings = Object.assign(db.settings, r[0][0].data);
    db.services = (r[1] || []).map(function(x){ return Object.assign({}, x.data, {id: x.id}); });
    db.blocks   = (r[2] || []).map(function(x){ return Object.assign({}, x.data, {id: x.id}); });
    return db;
  });
}
/* טווחים תפוסים בלבד: מתי, לא מי. */
function cloudBusy(from, to){
  return clFetch("/rest/v1/rpc/free_busy",
                 {method: "POST", auth: false, body: {p_from: from, p_to: to}})
    .then(function(rows){
      return (rows || []).map(function(r){ return {date: r.d, from: r.f, to: r.t}; });
    });
}
/* הזמנת התור נבדקת בשרת, לא כאן: שני טלפונים שלוחצים על אותה שעה
   באותה שנייה מקבלים שם תשובה אחת חיובית ואחת שלילית. */
function cloudBook(a){
  return clFetch("/rest/v1/rpc/book_slot", {method: "POST", auth: false, body: {
    p_name: a.clientName, p_phone: a.phone, p_service: a.serviceId,
    p_service_name: a.serviceName, p_date: a.date, p_time: a.time,
    p_minutes: a.minutes, p_note: a.note || "",
    p_lang: a.lang || "en"
  }});
}
/* גם זה עובר דרך פונקציה ולא דרך הטבלה: כך לאורחת יש רשות לכתוב מסמך
   ואין לה שום רשות לקרוא אחד. */
function cloudSubmitForm(f){
  return clFetch("/rest/v1/rpc/submit_form",
                 {method: "POST", auth: false, body: {p_form: f}});
}

/* ------------------------------------------------- מה שהיומן מציג */
function cloudLine(){
  if (!cloudConfigured()) return "היומן שמור בטלפון הזה";
  if (!cloudSignedIn()) return "לא מחוברת";
  var n = outboxCount();
  if (CL_STATE.error) return CL_STATE.error;
  return n ? n + " ממתינים לשליחה" : "מסונכרן · " + cloudWho();
}
function renderCloudBox(){
  var host = document.getElementById("st-cloud");
  if (!host) return;
  if (!cloudConfigured()) {
    host.innerHTML = '<p class="small muted">היומן עובד עכשיו על המכשיר הזה בלבד: ' +
      "מה שנרשם כאן נשאר כאן, ותור שלקוחה קובעת באתר לא מגיע לכאן אלא בוואטסאפ. " +
      "כדי לחבר ספר משותף — ראו <code>brows/README.md</code>.</p>";
    return;
  }
  if (!cloudSignedIn()) {
    host.innerHTML =
      '<div class="field"><label>אימייל</label><input id="cl-email" type="email"></div>' +
      '<div class="field"><label>סיסמה</label><input id="cl-pass" type="password"></div>' +
      '<button class="primary block" id="cl-in">כניסה</button>' +
      '<div class="small muted" id="cl-err" style="margin-top:8px"></div>';
    document.getElementById("cl-in").onclick = function(){
      var e = document.getElementById("cl-email").value.trim();
      var p = document.getElementById("cl-pass").value;
      document.getElementById("cl-err").textContent = "רגע…";
      cloudSignIn(e, p).then(function(){
        return cloudSync();
      }).then(function(){
        window.dispatchEvent(new Event("brows-cloud"));
      }, function(err){
        document.getElementById("cl-err").textContent = err.message || "לא הצליח";
      });
    };
    return;
  }
  host.innerHTML = '<p class="small">מחוברת כ־<b>' + cloudWho() + "</b><br>" +
    '<span class="muted">' + cloudLine() + "</span></p>" +
    '<div class="row"><button class="mini" id="cl-now">סנכרון עכשיו</button>' +
    '<button class="mini ghost" id="cl-out">יציאה</button></div>';
  document.getElementById("cl-now").onclick = function(){
    cloudSync().then(function(){ window.dispatchEvent(new Event("brows-cloud")); });
  };
  document.getElementById("cl-out").onclick = function(){
    cloudSignOut(); window.dispatchEvent(new Event("brows-cloud"));
  };
}
function cloudBoot(){
  if (!cloudConfigured()) return;
  cloudSync();
  setInterval(cloudSync, 30000);
  document.addEventListener("visibilitychange", function(){
    if (!document.hidden) cloudSync();
  });
}
