/* ======================================================================
   דף קביעת התור שהלקוחה רואה. אנגלית או עברית, ולנייד בלבד.

   הוא עובד בשני מצבים, ואומר ללקוחה באיזה מהם הוא נמצא:

   * מחובר לענן — השעות שמוצגות הן השעות שבאמת פנויות, והתור נתפס ברגע
     שנלחץ. השרת הוא זה שבודק שאין חפיפה, לא הדפדפן.
   * בלי ענן — הדף מכיר את שעות העבודה ואת הטיפולים, אבל לא את התורים
     שכבר נקבעו. לכן הוא שולח בקשת תור בוואטסאפ, והמטפלת מאשרת. לומר
     "התור נקבע" במצב הזה זה לשקר ללקוחה.
   ====================================================================== */

var db = null;
var online = false;
var step = 1;
var pick = {service: null, date: null, time: null};
/* השם והטלפון ששכבר הוקלדו, כדי שהחלפת שפה במסך האחרון לא תמחק אותם */
var draft = {};

function $(s){ return document.querySelector(s); }
function esc(s){
  return String(s == null ? "" : s).replace(/[&<>"']/g, function(c){
    return {"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c];
  });
}
var toastTimer = null;
function toast(msg){
  var t = $("#toast");
  t.firstElementChild.textContent = msg;
  t.classList.remove("hidden");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(function(){ t.classList.add("hidden"); }, 3000);
}

/* מאיפה מגיעים הנתונים: ענן, ואם אין — מה שנצרב לדף בבנייה, ואם אין גם
   זה, ברירות המחדל. על הטלפון של המטפלת עצמה יש כאן ספר מקומי, והוא קודם. */
function bootData(){
  if (cloudConfigured()) {
    return cloudPublicLoad().then(function(d){
      db = d; online = true;
      return loadBusy();
    }).catch(function(){ db = fallbackDb(); online = false; });
  }
  db = fallbackDb();
  return Promise.resolve();
}
function fallbackDb(){
  var saved = null;
  try { saved = localStorage.getItem(DB_KEY); } catch (e) {}
  if (saved) return loadDb();
  var d = blankDb();
  if (SALON) {
    d.settings = Object.assign(d.settings, SALON.settings || {});
    if (SALON.services) d.services = SALON.services;
  }
  return d;
}
/* בענן, הזמן התפוס מגיע כטווחים בלי שם — ונכנס ליומן המקומי כחסימות,
   כדי שחישוב השעות הפנויות יהיה בדיוק אותו קוד שהיומן מריץ. */
function loadBusy(){
  var from = todayYmd(), to = addDays(from, +db.settings.horizon || 45);
  return cloudBusy(from, to).then(function(rows){
    db.appointments = [];
    db.blocks = (db.blocks || []).concat(rows.map(function(r){
      return {id: uid(), date: r.date, from: min2hm(r.from), to: min2hm(r.to), reason: "busy"};
    }));
  }).catch(function(){ online = false; });
}

function activeServices(){
  return db.services.filter(function(s){ return s.active !== false; });
}
function svc(){ return serviceById(db, pick.service); }
function note(){ return LANG === "he" ? db.settings.noteHe : db.settings.noteEn; }

function setStep(n){
  step = n;
  ["#s1","#s2","#s3"].forEach(function(sel, i){ $(sel).classList.toggle("on", i < n); });
  window.scrollTo(0, 0);
  draw();
}

/* ------------------------------------------------------------- מסכים */
function draw(){
  $("#bizname").textContent = db.settings.name || t("bookTitle");
  $("#mark").textContent = (db.settings.name || "✦").trim().charAt(0);
  var sub = [];
  if (db.settings.address) sub.push(db.settings.address);
  if (db.settings.phone) sub.push(showPhone(db.settings.phone));
  $("#bizsub").textContent = sub.join(" · ");
  $("#note-box").innerHTML = note()
    ? '<div class="card tight" style="background:var(--rose-soft);border-color:#eddad6">' +
      esc(note()) + "</div>" : "";
  var ig = (db.settings.instagram || "").replace(/^@/, "");
  $("#foot").innerHTML =
    (ig ? '<a href="https://instagram.com/' + esc(ig) + '" target="_blank" rel="noopener">@' +
          esc(ig) + "</a><br>" : "") +
    (online ? "" : esc(t("notOnlineFoot")));
  if (step === 1) drawServices();
  if (step === 2) drawWhen();
  if (step === 3) drawDetails();
  if (step === 4) drawDone();
}

function drawServices(){
  var list = activeServices();
  /* כשכל הטיפולים דורשים כתב שחרור, שורה זהה מתחת לכל אחד מהם היא רעש
     שמפסיק להיקרא. אז היא נאמרת פעם אחת למעלה, ומופיעה ליד טיפול בודד
     רק כשהיא באמת מבדילה אותו מהשאר. */
  var allNeed = list.length > 0 && list.every(function(s){ return s.form; });
  $("#stage").innerHTML = "<h2>" + esc(t("pickService")) + "</h2>" +
    (allNeed ? '<p class="policy" style="margin:-6px 0 14px">' +
               esc(t("formOnce")) + "</p>" : "") +
    (list.length ? list.map(function(s){
      return '<button class="pick" data-s="' + s.id + '"><div class="svc">' +
        "<b>" + esc(svcName(s)) + "</b></div>" +
        '<div class="dur">' + s.minutes + " " + esc(t("minutes")) +
        (s.form && !allNeed ? " · " + esc(t("needsForm")) : "") + "</div></button>";
    }).join("") : "<p class=\"muted\">" + esc(t("noServices")) + "</p>");
  $("#stage").querySelectorAll("[data-s]").forEach(function(b){
    b.onclick = function(){
      pick.service = b.dataset.s; pick.date = null; pick.time = null; setStep(2);
    };
  });
}

function bookableDays(){
  var out = [], n = +db.settings.horizon || 45;
  for (var i = 0; i <= n; i++) {
    var d = addDays(todayYmd(), i);
    out.push({date: d, open: freeSlots(db, d, svc().minutes).length > 0});
  }
  return out;
}
function drawWhen(){
  var s = svc(), days = bookableDays();
  if (!pick.date) {
    var first = days.filter(function(d){ return d.open; })[0];
    pick.date = first ? first.date : todayYmd();
  }
  var slots = freeSlots(db, pick.date, s.minutes);
  $("#stage").innerHTML =
    '<button class="back">‹ ' + esc(t("backToServices")) + "</button>" +
    '<div class="recap"><div><b>' + esc(svcName(s)) + "</b></div>" +
    '<div class="small">' + s.minutes + " " + esc(t("minutes")) + "</div></div>" +
    "<h2>" + esc(t("pickWhen")) + "</h2>" +
    '<div class="days">' + days.slice(0, 21).map(function(d){
      var dt = parseYmd(d.date);
      return '<button class="day' + (d.open ? "" : " off") +
        (d.date === pick.date ? " on" : "") + '" data-d="' + d.date + '"' +
        (d.open ? "" : " disabled") + "><b>" + dt.getDate() + "</b><span>" +
        esc(dayShort(dt.getDay())) + "</span></button>";
    }).join("") + "</div>" +
    '<h3 style="margin-top:16px">' + esc(niceDate(pick.date)) + "</h3>" +
    (slots.length
      ? '<div class="slots">' + slots.map(function(m){
          return '<button class="slot" data-t="' + min2hm(m) + '">' + hm12(m) + "</button>";
        }).join("") + "</div>"
      : '<p class="muted">' + esc(t("noSlots")) + "</p>") +
    (online ? "" : '<p class="policy" style="margin-top:16px">' + esc(t("hoursOnlyNote")) + "</p>");
  $("#stage").querySelector(".back").onclick = function(){ setStep(1); };
  $("#stage").querySelectorAll("[data-d]").forEach(function(b){
    b.onclick = function(){ pick.date = b.dataset.d; pick.time = null; draw(); };
  });
  $("#stage").querySelectorAll("[data-t]").forEach(function(b){
    b.onclick = function(){ pick.time = b.dataset.t; setStep(3); };
  });
}

function drawDetails(){
  var s = svc();
  var hrs = +db.settings.cancelHours || 24;
  $("#stage").innerHTML =
    '<button class="back">‹ ' + esc(t("changeTime")) + "</button>" +
    '<div class="recap"><div><b>' + esc(svcName(s)) + "</b></div>" +
    "<div>" + esc(niceDate(pick.date)) + " · " + hm12(pick.time) + "</div>" +
    '<div class="small">' + s.minutes + " " + esc(t("minutes")) + "</div></div>" +
    "<h2>" + esc(t("yourDetails")) + "</h2>" +
    '<div class="field"><label>' + esc(t("fullName")) + "</label>" +
      '<input id="b-name" autocomplete="name"><div class="errmsg">' +
      esc(t("needName")) + "</div></div>" +
    '<div class="field"><label>' + esc(t("phone")) + "</label>" +
      '<input id="b-phone" type="tel" inputmode="tel" autocomplete="tel" placeholder="6123-4567">' +
      '<div class="errmsg">' + esc(t("badPhone")) + "</div>" +
      '<div class="small muted" style="margin-top:4px">' + esc(t("phoneHint")) + "</div></div>" +
    '<div class="field"><label>' + esc(t("anything")) + '</label><input id="b-note"></div>' +
    (s.form ? '<div class="card tight" style="background:var(--warn-soft);border-color:#e8cba6">' +
      "<b>" + esc(t("beforeTreat")) + '</b><div class="small">' +
      esc(t("beforeTreatBody")) + "</div></div>" : "") +
    '<label class="row" style="font-weight:400;margin:12px 0;align-items:flex-start;gap:9px">' +
      '<input type="checkbox" id="b-ok"><span class="policy">' +
      esc(t("cancelPolicy")(hrs)) + "</span></label>" +
    '<button class="primary block" id="b-go">' +
      esc(online ? t("confirmBtn") : t("requestBtn")) + "</button>" +
    '<div class="small muted" id="b-msg" style="margin:10px 0 20px"></div>';
  ["b-name", "b-phone", "b-note"].forEach(function(id){
    if (draft[id]) $("#" + id).value = draft[id];
    $("#" + id).oninput = function(){ draft[id] = $("#" + id).value; };
  });
  if (draft.ok) $("#b-ok").checked = true;
  $("#b-ok").onchange = function(){ draft.ok = $("#b-ok").checked; };
  $("#stage").querySelector(".back").onclick = function(){ setStep(2); };
  $("#b-go").onclick = submit;
}

function submit(){
  var name = $("#b-name").value.trim();
  var phone = $("#b-phone").value.trim();
  var bad = !name;
  $("#b-name").closest(".field").classList.toggle("err", !name);
  var pbad = !validPhone(phone);
  $("#b-phone").closest(".field").classList.toggle("err", pbad);
  bad = bad || pbad;
  if (bad) return;
  if (!$("#b-ok").checked) { toast(t("mustAgree")); return; }

  var s = svc();
  var appt = {
    id: uid(), clientName: name, phone: normPhone(phone),
    serviceId: s.id, serviceName: svcName(s), date: pick.date, time: pick.time,
    minutes: s.minutes, note: $("#b-note").value.trim(),
    status: db.settings.autoConfirm ? "confirmed" : "pending",
    source: "online", lang: LANG, created: new Date().toISOString()
  };
  pick.appt = appt;

  var btn = $("#b-go");
  btn.disabled = true;
  btn.textContent = t("working");

  if (online) {
    cloudBook(appt).then(function(){ setStep(4); }, function(e){
      btn.disabled = false;
      btn.textContent = t("confirmBtn");
      if (/taken|clash/i.test(e.message || "")) {
        $("#b-msg").textContent = t("taken");
        pick.time = null;
        loadBusy().then(function(){ setStep(2); });
      } else {
        $("#b-msg").textContent = t("saveFailed") + (e.message || "");
      }
    });
    return;
  }

  /* בלי ענן: הבקשה נוסעת בוואטסאפ. על הטלפון של המטפלת היא גם נכנסת
     ליומן, כך שדף ההזמנה הפתוח אצלה עדיין שימושי. */
  try {
    if (localStorage.getItem(DB_KEY)) {
      var localDb = loadDb();
      appt.status = "pending";
      appt.clientId = upsertClient(localDb, name, phone, {lang: LANG}).id;
      localDb.appointments.push(appt);
      saveDb(localDb);
    }
  } catch (e) {}
  var to = db.settings.phone || "";
  var text = (LANG === "he" ? "היי! אשמח לתור 💛" : "Hi! I'd love to book 💛") + "\n" +
    (LANG === "he" ? "שם" : "Name") + ": " + name + "\n" +
    (LANG === "he" ? "טלפון" : "Phone") + ": " + showPhone(phone) + "\n" +
    (LANG === "he" ? "טיפול" : "Treatment") + ": " + svcName(s) + "\n" +
    (LANG === "he" ? "מועד" : "When") + ": " + niceDate(pick.date) + ", " + hm12(pick.time) +
    (appt.note ? "\n" + (LANG === "he" ? "הערה" : "Note") + ": " + appt.note : "");
  if (to) window.open(waLink(to, text), "_blank");
  else if (navigator.clipboard) { navigator.clipboard.writeText(text); toast(t("copied")); }
  setStep(4);
}

function drawDone(){
  var s = svc(), a = pick.appt;
  var hrs = +db.settings.cancelHours || 24;
  var booked = online && a.status === "confirmed";
  $("#stage").innerHTML =
    '<div class="card done"><div class="tick">✓</div>' +
    "<h2>" + esc(booked ? t("bookedTitle") : t("requestedTitle")) + "</h2>" +
    '<div class="recap" style="text-align:start"><div><b>' + esc(svcName(s)) + "</b></div>" +
    "<div>" + esc(niceDate(pick.date)) + " · " + hm12(pick.time) + "</div>" +
    '<div class="small">' + esc(a.clientName) + " · " + esc(showPhone(a.phone)) + "</div></div>" +
    '<p class="small muted">' + esc(booked ? t("bookedBody")(hrs) : t("requestedBody")) + "</p>" +
    (s.form
      ? '<a class="btn primary block" href="form.html?lang=' + LANG +
        "&t=" + encodeURIComponent(treatmentsFor(s).join(",")) +
        "&n=" + encodeURIComponent(a.clientName) +
        "&p=" + encodeURIComponent(a.phone) + '">' + esc(t("fillForm")) + "</a>" +
        '<p class="small muted" style="margin-top:8px">' + esc(t("fillFormNote")) + "</p>"
      : "") +
    '<button class="mini ghost" id="again" style="margin-top:8px">' +
      esc(t("bookAnother")) + "</button></div>";
  $("#again").onclick = function(){
    pick = {service: null, date: null, time: null};
    if (online) loadBusy().then(function(){ setStep(1); }); else setStep(1);
  };
}

setLang(pickLang());
langPick("#lang", draw);
bootData().then(function(){ draw(); });
