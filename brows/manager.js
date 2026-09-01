/* ====================================================================
   היומן של המטפלת. עברית, ולנייד בלבד.

   כל מה שנרשם כאן נשמר בדפדפן הזה. אם הוגדר חיבור לענן (ראו cloud.js)
   אותו מידע גם עולה לשרת ויורד ממנו — וזה מה שמאפשר לתור שנקבע באתר
   להגיע לטלפון. בלי חיבור, היומן עובד במלואו על מכשיר אחד.
   ==================================================================== */

LANG = "he";                      /* היומן תמיד בעברית */
var db = loadDb();
var day = todayYmd();
var tab = "today";

function persist(){ if (!saveDb(db)) toast("אין מקום לשמור — ייצאי גיבוי"); }
function esc(s){
  return String(s == null ? "" : s).replace(/[&<>"']/g, function(c){
    return {"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c];
  });
}
function $(s){ return document.querySelector(s); }
function $$(s){ return Array.prototype.slice.call(document.querySelectorAll(s)); }

var toastTimer = null;
function toast(msg){
  var t = $("#toast");
  t.firstElementChild.textContent = msg;
  t.classList.remove("hidden");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(function(){ t.classList.add("hidden"); }, 2600);
}
function openModal(html){
  $("#modal-box").innerHTML = html;
  $("#modal").classList.remove("hidden");
  document.body.style.overflow = "hidden";
}
function closeModal(){
  $("#modal").classList.add("hidden");
  $("#modal-box").innerHTML = "";
  document.body.style.overflow = "";
}
$("#modal").addEventListener("click", function(e){
  if (e.target.id === "modal" || e.target.dataset.close !== undefined) closeModal();
});

/* הכתובת של דף ההזמנה ושל כתב השחרור, לפי היכן שהיומן עצמו יושב */
function siteUrl(file, lang){
  var u = location.href.split("#")[0].split("?")[0];
  return u.replace(/[^\/]*$/, file) + (lang ? "?lang=" + lang : "");
}
function copy(text, said){
  function fallback(){
    var ta = document.createElement("textarea");
    ta.value = text; ta.style.position = "fixed"; ta.style.opacity = "0";
    document.body.appendChild(ta); ta.select();
    try { document.execCommand("copy"); } catch (e) {}
    document.body.removeChild(ta);
    toast(said || "הועתק");
  }
  if (navigator.clipboard && navigator.clipboard.writeText)
    navigator.clipboard.writeText(text).then(function(){ toast(said || "הועתק"); }, fallback);
  else fallback();
}

/* -------------------------------------------------- הודעות ללקוחה
   נכתבות בשפה שהלקוחה בחרה כשקבעה את התור. לקוחה שקבעה באנגלית לא
   אמורה לקבל תזכורת בעברית. */
function langOf(a){ return a && a.lang === "he" ? "he" : "en"; }
function svcLabel(a, lang){
  var s = serviceById(db, a.serviceId);
  if (s) return (lang === "he" ? (s.he || s.en) : (s.en || s.he)) || "";
  return a.serviceName || "";
}
function whenLine(a, lang){
  var save = LANG; LANG = lang;
  var out = niceDate(a.date) + " · " + hm12(a.time);
  LANG = save;
  return out;
}
function confirmText(a){
  var l = langOf(a);
  if (l === "he")
    return "היי " + (a.clientName || "") + " 💛\nהתור שלך ב" + db.settings.name +
      " נקבע:\n🗓️ " + whenLine(a, "he") + "\n💅 " + svcLabel(a, "he") +
      (db.settings.address ? "\n📍 " + db.settings.address : "") +
      "\n\nביטול או שינוי — עד " + db.settings.cancelHours + " שעות לפני התור.";
  return "Hi " + (a.clientName || "") + " 💛\nYour appointment at " + db.settings.name +
    " is confirmed:\n🗓️ " + whenLine(a, "en") + "\n💅 " + svcLabel(a, "en") +
    (db.settings.address ? "\n📍 " + db.settings.address : "") +
    "\n\nCancel or change up to " + db.settings.cancelHours + " hours before.";
}
function reminderText(a){
  var l = langOf(a);
  if (l === "he")
    return "היי " + (a.clientName || "") + " 💛 מזכירה לך את התור מחר, " +
      whenLine(a, "he") + " ל" + svcLabel(a, "he") + ".\nנתראה! " + db.settings.name;
  return "Hi " + (a.clientName || "") + " 💛 just a reminder about tomorrow, " +
    whenLine(a, "en") + " for " + svcLabel(a, "en") + ".\nSee you! " + db.settings.name;
}
function formInvite(a){
  var l = langOf(a);
  if (l === "he")
    return "היי " + (a.clientName || "") + " 💛 לפני הטיפול צריך למלא הצהרת בריאות " +
      "וכתב שחרור, זה לוקח דקה:\n" + siteUrl("form.html", "he");
  return "Hi " + (a.clientName || "") + " 💛 before your treatment please fill in the " +
    "health declaration and release, it takes a minute:\n" + siteUrl("form.html", "en");
}

/* ---------------------------------------------------------- ניווט */
$$("#tabs button").forEach(function(b){
  b.addEventListener("click", function(){
    tab = b.dataset.tab;
    $$("#tabs button").forEach(function(x){ x.classList.toggle("on", x === b); });
    ["today","agenda","clients","forms","settings"].forEach(function(t){
      $("#tab-" + t).classList.toggle("hidden", t !== tab);
    });
    window.scrollTo(0, 0);
    render();
  });
});
$("#d-prev").onclick  = function(){ day = addDays(day, -1); renderDay(); };
$("#d-next").onclick  = function(){ day = addDays(day,  1); renderDay(); };
$("#d-today").onclick = function(){ day = todayYmd(); renderDay(); };
$("#d-block").onclick = function(){ blockEditor(); };
$("#btn-new").onclick = function(){ apptEditor(null); };

function render(){
  $("#bizname").textContent = db.settings.name || "היומן";
  $("#subline").textContent = cloudLine();
  if (tab === "today")    renderDay();
  if (tab === "agenda")   renderAgenda();
  if (tab === "clients")  renderClients();
  if (tab === "forms")    renderForms();
  if (tab === "settings") renderSettings();
  renderPending();
}

/* ------------------------------------------------------ בקשות ממתינות */
function pendingList(){
  return db.appointments.filter(function(a){ return a.status === "pending"; })
    .sort(function(a, b){ return (a.date + a.time).localeCompare(b.date + b.time); });
}
function renderPending(){
  var p = pendingList(), box = $("#pending-box");
  var n = document.querySelector('#tabs button[data-tab="today"]');
  var old = n.querySelector(".badge");
  if (old) old.remove();
  if (p.length) {
    var b = document.createElement("span");
    b.className = "badge"; b.textContent = p.length;
    n.appendChild(b);
  }
  if (!p.length) { box.innerHTML = ""; return; }
  box.innerHTML =
    '<div class="card" style="border-color:#e8cba6;background:#fffaf3">' +
    "<b>ממתינות לאישור (" + p.length + ")</b>" +
    p.map(function(a){
      return '<div class="row between" style="margin-top:10px;gap:7px">' +
        '<div class="grow"><div class="name">' + esc(a.clientName) + "</div>" +
        '<div class="small muted">' + shortDate(a.date) + " · " + hm12(a.time) + " · " +
        esc(svcLabel(a, "he")) + "</div></div>" +
        '<button class="mini primary" data-ok="' + a.id + '">אישור</button>' +
        '<button class="mini danger" data-no="' + a.id + '">דחייה</button></div>';
    }).join("") + "</div>";
  box.querySelectorAll("[data-ok]").forEach(function(b){
    b.onclick = function(){ setStatus(b.dataset.ok, "confirmed"); };
  });
  box.querySelectorAll("[data-no]").forEach(function(b){
    b.onclick = function(){ setStatus(b.dataset.no, "cancelled"); };
  });
}
function apptById(id){
  for (var i = 0; i < db.appointments.length; i++)
    if (db.appointments[i].id === id) return db.appointments[i];
  return null;
}
function setStatus(id, st){
  var a = apptById(id);
  if (!a) return;
  a.status = st;
  persist(); cloudDirty("appointments", id); cloudSync();
  if (st === "confirmed") {
    toast("אושר");
    if (a.phone) window.open(waLink(a.phone, confirmText(a)), "_blank");
  } else toast("בוטל");
  render();
}

/* ============================== היום ============================== */
function dayAppts(d){
  return db.appointments.filter(function(a){ return a.date === d; })
    .sort(function(x, y){ return x.time.localeCompare(y.time); });
}
function renderDay(){
  $("#d-title").textContent = niceDate(day) + (day === todayYmd() ? " · היום" : "");
  var list = dayAppts(day);
  var live = list.filter(ACTIVE);
  var m = live.reduce(function(t, a){ return t + (+a.price || 0); }, 0);
  var mins = live.reduce(function(t, a){ return t + (+a.minutes || 0); }, 0);
  $("#d-sum").textContent = live.length
    ? live.length + " תורים · " + (Math.round(mins / 6) / 10) + " שעות · " + money(m) : "";

  var blocks = db.blocks.filter(function(b){ return b.date === day; });
  var html;
  if (!list.length && !blocks.length) {
    html = '<div class="empty">' +
      (workWindows(db, day).length ? "אין תורים ביום הזה." : "יום סגור לפי שעות העבודה.") +
      '<div style="margin-top:12px"><button class="mini primary" id="d-add">+ תור חדש</button></div></div>';
  } else {
    html = list.map(apptCard).join("") + blocks.map(function(b){
      return '<button class="appt" data-block="' + b.id + '" style="background:#f6f3f1">' +
        '<div class="time">' + hm12(b.from) + "</div>" +
        '<div class="grow"><div class="name">' + esc(b.reason || "חסום") + "</div>" +
        '<div class="small muted">' + hm12(b.from) + " – " + hm12(b.to) + "</div></div></button>";
    }).join("");
  }
  $("#d-list").innerHTML = html;
  var add = $("#d-add"); if (add) add.onclick = function(){ apptEditor(null); };
  wireCards("#d-list");
}
function wireCards(root){
  $(root).querySelectorAll("[data-appt]").forEach(function(el){
    el.onclick = function(){ apptSheet(el.dataset.appt); };
  });
  $(root).querySelectorAll("[data-block]").forEach(function(el){
    el.onclick = function(){ blockEditor(el.dataset.block); };
  });
}
function apptCard(a){
  var chip = a.status === "pending" ? '<span class="chip warn">ממתין</span>' :
             a.status === "done"    ? '<span class="chip ok">בוצע</span>'   :
             a.status === "cancelled" ? '<span class="chip bad">בוטל</span>' : "";
  return '<button class="appt ' + (a.status || "confirmed") + '" data-appt="' + a.id + '">' +
    '<div class="time">' + hm12(a.time) +
      '<div class="small muted" style="font-weight:400">' + hm12(apptEnd(db, a)) + "</div></div>" +
    '<div class="grow"><div class="row between"><span class="name">' +
      esc(a.clientName || "ללא שם") + "</span>" + chip + "</div>" +
    '<div class="small muted">' + esc(svcLabel(a, "he")) + " · " + money(a.price) +
      (a.source === "online" ? " · מהאתר" : "") + "</div>" +
    (a.note ? '<div class="small" style="color:#8a544f">' + esc(a.note) + "</div>" : "") +
    "</div></button>";
}

function apptSheet(id){
  var a = apptById(id);
  if (!a) return;
  var s = serviceById(db, a.serviceId);
  var c = a.clientId ? db.clients.filter(function(x){ return x.id === a.clientId; })[0] : null;
  var f = db.forms.filter(function(x){
    return (a.clientId && x.clientId === a.clientId) ||
           (a.phone && normPhone(x.phone) === normPhone(a.phone)); })[0];
  openModal(
    '<div class="row between"><h2>' + esc(a.clientName) + "</h2>" +
      '<button class="ghost mini" data-close>סגירה</button></div>' +
    '<p class="muted small">' + niceDate(a.date) + " · " + hm12(a.time) + " – " +
      hm12(apptEnd(db, a)) + " · " + esc(svcLabel(a, "he")) + " · " + money(a.price) + "</p>" +
    (s && s.form && !f ? '<div class="chip warn" style="margin-bottom:10px">עוד לא חתמה על כתב שחרור</div>' : "") +
    (f ? '<div class="chip ok" style="margin-bottom:10px">חתמה · ' +
         esc(String(f.signedAt || "").slice(0, 10)) + "</div>" : "") +
    (a.note ? "<p>" + esc(a.note) + "</p>" : "") +
    '<div class="row wrapped" style="margin:12px 0">' +
      (a.phone ? '<a class="btn mini" href="tel:+' + esc(normPhone(a.phone)) + '">חיוג</a>' +
                 '<a class="btn mini" target="_blank" href="' +
                   esc(waLink(a.phone, confirmText(a))) + '">אישור</a>' +
                 '<a class="btn mini" target="_blank" href="' +
                   esc(waLink(a.phone, reminderText(a))) + '">תזכורת</a>' +
                 '<a class="btn mini" target="_blank" href="' +
                   esc(waLink(a.phone, formInvite(a))) + '">שליחת טופס</a>' : "") +
    "</div>" +
    '<div class="row wrapped">' +
      (a.status !== "done" ? '<button class="mini primary" id="m-done">בוצע</button>' : "") +
      '<button class="mini" id="m-edit">עריכה</button>' +
      (a.status !== "cancelled" ? '<button class="mini danger" id="m-cancel">ביטול</button>' : "") +
      (c ? '<button class="mini ghost" id="m-client">כרטיס לקוחה</button>' : "") +
      (f ? '<button class="mini ghost" id="m-form">הטופס שלה</button>' : "") +
    "</div>"
  );
  var d = $("#m-done");   if (d) d.onclick = function(){ closeModal(); setStatus(id, "done"); };
  var x = $("#m-cancel"); if (x) x.onclick = function(){
    if (confirm("לבטל את התור?")) { closeModal(); setStatus(id, "cancelled"); }
  };
  $("#m-edit").onclick = function(){ apptEditor(id); };
  var cl = $("#m-client"); if (cl) cl.onclick = function(){ clientSheet(c.id); };
  var fm = $("#m-form");   if (fm) fm.onclick = function(){ formSheet(f.id); };
}

/* ------------------------------------------------------- עריכת תור */
function apptEditor(id){
  var a = id ? apptById(id) : null;
  var isNew = !a;
  if (isNew) {
    var w = workWindows(db, day)[0];
    a = {id: uid(), date: day, time: min2hm(w ? w.from : 540), status: "confirmed",
         clientName: "", phone: "", serviceId: (db.services[0] || {}).id,
         minutes: 30, price: 0, note: "", source: "owner", lang: "en"};
  }
  var opts = db.services.map(function(s){
    return '<option value="' + s.id + '"' + (s.id === a.serviceId ? " selected" : "") +
           ">" + esc(svcName(s)) + " · " + s.minutes + "׳ · " + money(s.price) + "</option>";
  }).join("");
  openModal(
    '<div class="row between"><h2>' + (isNew ? "תור חדש" : "עריכת תור") + "</h2>" +
      '<button class="ghost mini" data-close>סגירה</button></div>' +
    '<div class="field"><label>שם הלקוחה</label>' +
      '<input id="e-name" autocomplete="off" value="' + esc(a.clientName) + '">' +
      '<div class="errmsg">צריך שם</div></div>' +
    '<div class="sugg hidden" id="e-sugg"></div>' +
    '<div class="field"><label>טלפון (עם קידומת אם לא פנמי)</label>' +
      '<input id="e-phone" type="tel" inputmode="tel" value="' + esc(a.phone) + '">' +
      '<div class="errmsg">מספר לא תקין</div></div>' +
    '<div class="field"><label>טיפול</label><select id="e-svc">' + opts + "</select></div>" +
    '<div class="row"><div class="field grow"><label>תאריך</label>' +
      '<input id="e-date" type="date" value="' + a.date + '"></div>' +
      '<div class="field grow"><label>שעה</label>' +
      '<input id="e-time" type="time" step="300" value="' + a.time + '"></div></div>' +
    '<div class="row"><div class="field grow"><label>דקות</label>' +
      '<input id="e-min" type="number" min="5" step="5" value="' + (a.minutes || 30) + '"></div>' +
      '<div class="field grow"><label>מחיר ($)</label>' +
      '<input id="e-price" type="number" min="0" step="1" value="' + (a.price || 0) + '"></div></div>' +
    '<div class="field"><label>שפת הלקוחה</label><select id="e-lang">' +
      '<option value="en"' + (langOf(a) === "en" ? " selected" : "") + ">English</option>" +
      '<option value="he"' + (langOf(a) === "he" ? " selected" : "") + ">עברית</option>" +
      "</select></div>" +
    '<div class="field"><label>הערה</label><input id="e-note" value="' + esc(a.note || "") + '"></div>' +
    '<div id="e-clash"></div>' +
    '<div class="row" style="margin-top:8px">' +
      '<button class="primary grow" id="e-save">שמירה</button>' +
      (isNew ? "" : '<button class="danger mini" id="e-del">מחיקה</button>') + "</div>"
  );

  function svcNow(){ return serviceById(db, $("#e-svc").value); }
  $("#e-svc").onchange = function(){
    var s = svcNow();
    if (s) { $("#e-min").value = s.minutes; $("#e-price").value = s.price; }
    checkClash();
  };
  if (isNew) $("#e-svc").onchange();
  ["#e-date", "#e-time", "#e-min"].forEach(function(sel){
    $(sel).onchange = checkClash; $(sel).oninput = checkClash;
  });
  function checkClash(){
    var hit = conflictAt(db, $("#e-date").value, $("#e-time").value,
                         +$("#e-min").value || 30, a.id);
    var out = $("#e-clash");
    if (!hit) { out.innerHTML = ""; return; }
    var who = hit.appt ? (hit.appt.clientName || "תור") : (hit.block.reason || "חסימה");
    out.innerHTML = '<div class="chip warn" style="margin-bottom:8px">חופף ל' +
      esc(who) + " (" + hm12(hit.from) + " – " + hm12(hit.to) + ")</div>";
  }
  checkClash();

  /* השלמת שם מתוך הלקוחות הקיימות — כדי שלא ייווצר כרטיס כפול */
  $("#e-name").oninput = function(){
    var q = $("#e-name").value.trim(), box = $("#e-sugg");
    if (q.length < 2) { box.classList.add("hidden"); return; }
    var hits = db.clients.filter(function(c){
      return (c.name || "").toLowerCase().indexOf(q.toLowerCase()) >= 0 ||
             (digits(q) && normPhone(c.phone).indexOf(digits(q)) >= 0);
    }).slice(0, 6);
    if (!hits.length) { box.classList.add("hidden"); return; }
    box.innerHTML = hits.map(function(c){
      return '<button data-c="' + c.id + '">' + esc(c.name) +
             ' <span class="muted small">' + esc(showPhone(c.phone)) + "</span></button>";
    }).join("");
    box.classList.remove("hidden");
    box.querySelectorAll("[data-c]").forEach(function(b){
      b.onclick = function(){
        var c = db.clients.filter(function(x){ return x.id === b.dataset.c; })[0];
        $("#e-name").value = c.name; $("#e-phone").value = showPhone(c.phone);
        if (c.lang) $("#e-lang").value = c.lang;
        a.clientId = c.id; box.classList.add("hidden");
      };
    });
  };

  $("#e-save").onclick = function(){
    var name = $("#e-name").value.trim(), phone = $("#e-phone").value.trim();
    $("#e-name").closest(".field").classList.toggle("err", !name);
    if (!name) return;
    if (phone && !validPhone(phone)) {
      $("#e-phone").closest(".field").classList.add("err"); return;
    }
    var s = svcNow();
    a.clientName = name;
    a.phone = phone ? normPhone(phone) : "";
    a.serviceId = $("#e-svc").value;
    a.serviceName = s ? svcName(s) : "";
    a.date = $("#e-date").value;
    a.time = $("#e-time").value;
    a.minutes = +$("#e-min").value || 30;
    a.price = +$("#e-price").value || 0;
    a.lang = $("#e-lang").value;
    a.note = $("#e-note").value.trim();
    if (phone) a.clientId = upsertClient(db, name, phone, {lang: a.lang}).id;
    if (isNew) { a.created = new Date().toISOString(); db.appointments.push(a); }
    persist(); cloudDirty("appointments", a.id);
    if (a.clientId) cloudDirty("clients", a.clientId);
    cloudSync();
    day = a.date;
    closeModal(); toast(isNew ? "נקבע" : "נשמר"); render();
  };
  var del = $("#e-del");
  if (del) del.onclick = function(){
    if (!confirm("למחוק את התור לגמרי? (ביטול עדיף — הוא נשאר בהיסטוריה)")) return;
    db.appointments = db.appointments.filter(function(x){ return x.id !== a.id; });
    persist(); cloudDelete("appointments", a.id); cloudSync();
    closeModal(); toast("נמחק"); render();
  };
}

/* ---------------------------------------------------- חסימת זמן */
function blockEditor(id){
  var b = id ? db.blocks.filter(function(x){ return x.id === id; })[0] : null;
  var isNew = !b;
  if (isNew) b = {id: uid(), date: day, from: "12:00", to: "13:00", reason: ""};
  openModal(
    '<div class="row between"><h2>' + (isNew ? "חסימת זמן" : "עריכת חסימה") + "</h2>" +
      '<button class="ghost mini" data-close>סגירה</button></div>' +
    '<p class="small muted">שעות שלא יוצעו ללקוחות: הפסקה, סידורים, חופשה.</p>' +
    '<div class="field"><label>תאריך</label><input id="b-date" type="date" value="' + b.date + '"></div>' +
    '<div class="row"><div class="field grow"><label>משעה</label>' +
      '<input id="b-from" type="time" step="300" value="' + b.from + '"></div>' +
      '<div class="field grow"><label>עד</label>' +
      '<input id="b-to" type="time" step="300" value="' + b.to + '"></div></div>' +
    '<div class="field"><label>סיבה</label><input id="b-why" value="' + esc(b.reason) + '"></div>' +
    '<div class="row"><button class="primary grow" id="b-save">שמירה</button>' +
      (isNew ? "" : '<button class="danger mini" id="b-del">מחיקה</button>') + "</div>"
  );
  $("#b-save").onclick = function(){
    b.date = $("#b-date").value; b.from = $("#b-from").value;
    b.to = $("#b-to").value; b.reason = $("#b-why").value.trim();
    if (hm2min(b.to) <= hm2min(b.from)) { toast("שעת הסיום מוקדמת מדי"); return; }
    if (isNew) db.blocks.push(b);
    persist(); cloudDirty("blocks", b.id); cloudSync();
    day = b.date; closeModal(); toast("נחסם"); render();
  };
  var d = $("#b-del");
  if (d) d.onclick = function(){
    db.blocks = db.blocks.filter(function(x){ return x.id !== b.id; });
    persist(); cloudDelete("blocks", b.id); cloudSync();
    closeModal(); toast("נמחק"); render();
  };
}

/* ============================== יומן ============================== */
function renderAgenda(){
  var html = "", any = false;
  for (var i = 0; i < 14; i++) {
    var d = addDays(todayYmd(), i);
    var list = dayAppts(d).filter(ACTIVE);
    if (!list.length) continue;
    any = true;
    html += '<div class="agday"><h3>' + niceDate(d) + " · " + list.length + " תורים</h3>" +
            list.map(apptCard).join("") + "</div>";
  }
  $("#a-list").innerHTML = any ? html : '<div class="empty">אין תורים בשבועיים הקרובים.</div>';
  wireCards("#a-list");
}
$("#a-remind").onclick = function(){
  var t = addDays(todayYmd(), 1);
  var list = dayAppts(t).filter(function(a){ return ACTIVE(a) && a.phone; });
  if (!list.length) { toast("אין למי לשלוח תזכורת מחר"); return; }
  openModal(
    '<div class="row between"><h2>תזכורות ל' + niceDate(t) + "</h2>" +
      '<button class="ghost mini" data-close>סגירה</button></div>' +
    '<p class="small muted">כל שליחה פותחת וואטסאפ עם ההודעה מוכנה, בשפה של הלקוחה.</p>' +
    '<ul class="list">' + list.map(function(a){
      return '<li><div class="row between"><div class="grow"><b>' + esc(a.clientName) +
        '</b><div class="small muted">' + hm12(a.time) + " · " + langOf(a) + "</div></div>" +
        '<a class="btn mini primary" target="_blank" href="' +
        esc(waLink(a.phone, reminderText(a))) + '">שליחה</a></div></li>';
    }).join("") + "</ul>"
  );
};

/* ============================= לקוחות ============================= */
function clientStats(c){
  var list = apptsOf(db, c.id).filter(function(a){ return a.status !== "cancelled"; });
  var past = list.filter(function(a){ return a.date <= todayYmd(); });
  var next = db.appointments.filter(function(a){
    return a.clientId === c.id && ACTIVE(a) && a.date >= todayYmd();
  }).sort(function(a, b){ return (a.date + a.time).localeCompare(b.date + b.time); })[0];
  return {visits: past.length, next: next,
          spent: past.reduce(function(t, a){ return t + (+a.price || 0); }, 0)};
}
function renderClients(){
  var q = ($("#c-search").value || "").trim();
  var list = db.clients.slice();
  if (q) list = list.filter(function(c){
    return (c.name || "").toLowerCase().indexOf(q.toLowerCase()) >= 0 ||
           (digits(q) && normPhone(c.phone).indexOf(digits(q)) >= 0);
  });
  list.sort(function(a, b){ return (a.name || "").localeCompare(b.name || "", "he"); });
  $("#c-sum").textContent = db.clients.length + " לקוחות" +
    (q ? " · " + list.length + " תואמות" : "");
  $("#c-list").innerHTML = list.length ? '<ul class="list">' + list.map(function(c){
    var s = clientStats(c);
    return '<li data-cl="' + c.id + '"><div class="row between">' +
      '<div class="grow"><div class="name">' + esc(c.name || "ללא שם") + "</div>" +
      '<div class="small muted">' + esc(showPhone(c.phone)) + " · " + s.visits + " ביקורים" +
      (s.next ? " · הבא: " + shortDate(s.next.date) : "") + "</div></div>" +
      (s.next ? '<span class="chip ok">תור קבוע</span>' : "") + "</div></li>";
  }).join("") + "</ul>" : '<div class="empty">אין עדיין לקוחות.</div>';
  $("#c-list").querySelectorAll("[data-cl]").forEach(function(el){
    el.onclick = function(){ clientSheet(el.dataset.cl); };
  });
}
$("#c-search").oninput = renderClients;

function clientSheet(id){
  var c = db.clients.filter(function(x){ return x.id === id; })[0];
  if (!c) return;
  var s = clientStats(c);
  var hist = apptsOf(db, c.id);
  var forms = db.forms.filter(function(f){
    return f.clientId === c.id || normPhone(f.phone) === normPhone(c.phone); });
  openModal(
    '<div class="row between"><h2>' + esc(c.name) + "</h2>" +
      '<button class="ghost mini" data-close>סגירה</button></div>' +
    '<p class="muted small">' + esc(showPhone(c.phone)) + " · " + s.visits + " ביקורים · " +
      money(s.spent) + " בסך הכול</p>" +
    '<div class="row wrapped" style="margin:10px 0">' +
      '<a class="btn mini" href="tel:+' + esc(normPhone(c.phone)) + '">חיוג</a>' +
      '<a class="btn mini" target="_blank" href="' + esc(waLink(c.phone, "")) + '">וואטסאפ</a>' +
      '<button class="mini primary" id="cl-new">תור חדש</button>' +
      '<button class="mini" id="cl-form">שליחת טופס</button></div>' +
    '<div class="field"><label>הערות</label>' +
      '<textarea id="cl-notes">' + esc(c.notes || "") + "</textarea>" +
      '<button class="mini" id="cl-save" style="margin-top:6px">שמירת הערות</button></div>' +
    (forms.length
      ? '<button class="chip ok" id="cl-doc" style="border:none;margin-bottom:8px">חתמה על כתב שחרור · ' +
        esc(String(forms[0].signedAt || "").slice(0, 10)) + "</button>"
      : '<div class="chip warn" style="margin-bottom:8px">אין כתב שחרור חתום</div>') +
    "<h3>היסטוריה</h3>" +
    (hist.length ? '<ul class="list">' + hist.map(function(a){
      return "<li>" + shortDate(a.date) + " · " + esc(svcLabel(a, "he")) + " · " +
        money(a.price) +
        (a.status === "cancelled" ? ' <span class="chip bad">בוטל</span>' : "") + "</li>";
    }).join("") + "</ul>" : '<p class="muted small">עדיין לא הייתה.</p>')
  );
  $("#cl-save").onclick = function(){
    c.notes = $("#cl-notes").value;
    persist(); cloudDirty("clients", c.id); cloudSync(); toast("נשמר");
  };
  $("#cl-new").onclick = function(){
    closeModal(); apptEditor(null);
    $("#e-name").value = c.name; $("#e-phone").value = showPhone(c.phone);
    if (c.lang) $("#e-lang").value = c.lang;
  };
  $("#cl-form").onclick = function(){
    window.open(waLink(c.phone, formInvite({clientName: c.name, lang: c.lang})), "_blank");
  };
  var doc = $("#cl-doc");
  if (doc) doc.onclick = function(){ formSheet(forms[0].id); };
}

/* ============================== טפסים ============================== */
$("#f-link-en").onclick = function(){ copy(siteUrl("form.html", "en"), "הקישור באנגלית הועתק"); };
$("#f-link-he").onclick = function(){ copy(siteUrl("form.html", "he"), "הקישור בעברית הועתק"); };
$("#f-open").onclick    = function(){ window.open(siteUrl("form.html"), "_blank"); };

function renderForms(){
  var list = db.forms.slice().sort(function(a, b){
    return String(b.signedAt || "").localeCompare(String(a.signedAt || ""));
  });
  $("#f-list").innerHTML = list.length ? '<ul class="list">' + list.map(function(f){
    return '<li data-f="' + f.id + '"><div class="row between">' +
      '<div class="grow"><div class="name">' + esc(f.name) + "</div>" +
      '<div class="small muted">' + esc((f.treatments || []).join(", ")) + " · " +
      esc(String(f.signedAt || "").slice(0, 10)) + "</div></div>" +
      (flagged(f).length ? '<span class="chip warn">לשים לב</span>'
                         : '<span class="chip ok">תקין</span>') + "</div></li>";
  }).join("") + "</ul>" : '<div class="empty">עדיין לא הגיעו טפסים.</div>';
  $("#f-list").querySelectorAll("[data-f]").forEach(function(el){
    el.onclick = function(){ formSheet(el.dataset.f); };
  });
}
function flagged(f){
  return (f.answers || []).filter(function(x){ return x.yes && x.flag; });
}
function formSheet(id){
  var f = db.forms.filter(function(x){ return x.id === id; })[0];
  if (!f) return;
  var yes = (f.answers || []).filter(function(x){ return x.yes; });
  openModal(
    '<div class="row between noprint"><h2>' + esc(f.name) + "</h2>" +
      '<button class="ghost mini" data-close>סגירה</button></div>' +
    '<div class="formdoc small">' +
    "<p><b>" + esc(f.name) + "</b><br><span class=\"muted\">" + esc(showPhone(f.phone)) +
      (f.idnum ? " · " + esc(f.idnum) : "") + (f.birth ? " · " + esc(f.birth) : "") +
      "</span></p>" +
    "<p><b>טיפולים:</b> " + esc((f.treatments || []).join(", ")) + "</p>" +
    (yes.length
      ? '<div class="card tight" style="background:var(--warn-soft);border-color:#e8cba6">' +
        "<b>ענתה כן ב־" + yes.length + " סעיפים</b>" +
        '<ul style="margin:6px 0 0;padding-inline-start:18px">' +
        yes.map(function(x){
          return "<li>" + esc(x.q) + (x.note ? " — " + esc(x.note) : "") + "</li>"; }).join("") +
        "</ul></div>"
      : '<div class="chip ok">לא סומנה אף התוויית נגד</div>') +
    (f.notes ? "<p><b>הערות הלקוחה:</b> " + esc(f.notes) + "</p>" : "") +
    "<p><b>צילום ופרסום:</b> " + (f.photos ? "אישרה" : "לא אישרה") + "</p>" +
    (f.guardian ? "<p><b>חתימת אפוטרופוס:</b> " + esc(f.guardian) + "</p>" : "") +
    "<p><b>נחתם:</b> " + esc(localStamp(f.signedAt)) + "</p>" +
    (f.signature ? '<img src="' + f.signature + '" alt="חתימה" ' +
      'style="max-width:240px;border:1px solid var(--line);border-radius:10px">' : "") +
    "</div>" +
    '<div class="row noprint" style="margin-top:12px">' +
      '<button class="mini danger" id="fd">מחיקה</button></div>'
  );
  $("#fd").onclick = function(){
    if (!confirm("למחוק את הטופס? זה מסמך חתום שהלקוחה מסרה.")) return;
    db.forms = db.forms.filter(function(x){ return x.id !== id; });
    persist(); cloudDelete("forms", id); cloudSync(); closeModal(); render();
  };
}

/* ============================= הגדרות ============================= */
function renderSettings(){
  var s = db.settings;
  function f(label, id, val, type){
    return '<div class="field"><label>' + label + '</label><input id="' + id +
           '" ' + (type ? 'type="' + type + '" ' : "") + 'value="' + esc(val || "") + '"></div>';
  }
  function n(label, id, val){
    return '<div class="field" style="flex:1;min-width:104px"><label>' + label +
           '</label><input id="' + id + '" type="number" min="0" value="' + (+val || 0) + '"></div>';
  }
  $("#tab-settings").innerHTML =
    '<div class="card"><h2>העסק</h2>' +
      f("שם", "st-name", s.name) + f("שם המטפלת", "st-owner", s.owner) +
      f("וואטסאפ (עם קידומת)", "st-phone", s.phone, "tel") +
      f("כתובת", "st-addr", s.address) + f("אינסטגרם", "st-ig", s.instagram) +
      '<div class="field"><label>הודעה ללקוחה בדף ההזמנה — English</label>' +
        '<textarea id="st-note-en" rows="2">' + esc(s.noteEn) + "</textarea></div>" +
      '<div class="field"><label>אותה הודעה בעברית</label>' +
        '<textarea id="st-note-he" rows="2">' + esc(s.noteHe) + "</textarea></div>" +
    "</div>" +

    '<div class="card"><h2>הטיפולים</h2><div id="st-svc"></div>' +
      '<button class="mini" id="st-svc-add">+ טיפול</button>' +
      '<p class="small muted" style="margin-top:8px">' +
        '"טופס" = טיפול שדורש כתב שחרור חתום לפני שמתחילים.</p></div>' +

    '<div class="card"><h2>שעות עבודה</h2><div id="st-hours"></div></div>' +

    '<div class="card"><h2>כללי ההזמנה</h2><div class="row wrapped">' +
      n("קפיצות (דק׳)", "st-step", s.step) +
      n("סידור בין תורים", "st-buffer", s.buffer) +
      n("מראש (שעות)", "st-lead", s.leadHours) +
      n("ימים קדימה", "st-horizon", s.horizon) +
      n("ביטול עד (שעות)", "st-cancel", s.cancelHours) + "</div>" +
      '<label class="row" style="margin-top:6px;font-weight:400">' +
        '<input type="checkbox" id="st-auto"' + (s.autoConfirm ? " checked" : "") + ">" +
        "<span class=\"small\">תור מהאתר נכנס מאושר מיד (אחרת ממתין לאישור שלך)</span></label>" +
    "</div>" +

    '<div class="card"><h2>הקישורים ללקוחות</h2>' +
      '<p class="small muted">אלה מה ששמים בביו של האינסטגרם ושולחים בוואטסאפ.</p>' +
      '<div class="row wrapped">' +
        '<button class="mini" id="lk-book-en">הזמנת תור · EN</button>' +
        '<button class="mini" id="lk-book-he">הזמנת תור · עברית</button></div>' +
      '<div class="small muted" style="word-break:break-all;margin-top:8px">' +
        esc(siteUrl("book.html")) + "</div></div>" +

    '<div class="card"><h2>הענן</h2><div id="st-cloud"></div></div>' +

    '<div class="card"><h2>גיבוי</h2>' +
      '<p class="small muted">הכול יושב בטלפון הזה. אם הוא אובד — הוא אובד איתו. ' +
        "גיבוי פעם בשבוע לוקח שתי שניות.</p>" +
      '<div class="row wrapped"><button class="mini primary" id="bk-out">ייצוא גיבוי</button>' +
        '<button class="mini" id="bk-in">שחזור</button>' +
        '<button class="mini ghost" id="bk-site">ייצוא לאתר</button>' +
        '<input type="file" id="bk-file" accept="application/json" class="hidden"></div>' +
      '<p class="small muted" style="margin-top:8px">"ייצוא לאתר" יוצר את הקובץ ' +
        "<code>salon.json</code> — הטיפולים והשעות שהדפים הציבוריים מציגים כשאין ענן.</p>" +
    "</div>";

  renderSvcEditor(); renderHoursEditor(); renderCloudBox();

  [["st-name","name"],["st-owner","owner"],["st-phone","phone"],["st-addr","address"],
   ["st-ig","instagram"],["st-note-en","noteEn"],["st-note-he","noteHe"]].forEach(function(p){
    $("#" + p[0]).onchange = function(){
      db.settings[p[1]] = $("#" + p[0]).value.trim();
      persist(); cloudDirty("settings", "settings"); cloudSync();
      $("#bizname").textContent = db.settings.name || "היומן";
    };
  });
  [["st-step","step"],["st-buffer","buffer"],["st-lead","leadHours"],
   ["st-horizon","horizon"],["st-cancel","cancelHours"]].forEach(function(p){
    $("#" + p[0]).onchange = function(){
      db.settings[p[1]] = +$("#" + p[0]).value || 0;
      persist(); cloudDirty("settings", "settings"); cloudSync();
    };
  });
  $("#st-auto").onchange = function(){
    db.settings.autoConfirm = $("#st-auto").checked;
    persist(); cloudDirty("settings", "settings"); cloudSync();
  };
  $("#lk-book-en").onclick = function(){ copy(siteUrl("book.html", "en"), "הקישור הועתק"); };
  $("#lk-book-he").onclick = function(){ copy(siteUrl("book.html", "he"), "הקישור הועתק"); };
  $("#st-svc-add").onclick = function(){
    db.services.push({id: uid(), he: "טיפול חדש", en: "New treatment", minutes: 30,
                      price: 0, form: false, active: true});
    persist(); renderSvcEditor();
  };
  $("#bk-out").onclick = backup;
  $("#bk-in").onclick = function(){ $("#bk-file").click(); };
  $("#bk-site").onclick = exportSite;
  $("#bk-file").onchange = restore;
}
function renderSvcEditor(){
  var host = $("#st-svc");
  host.innerHTML = db.services.map(function(s, i){
    return '<div class="svccard" data-i="' + i + '">' +
      '<div class="two"><input data-k="he" value="' + esc(s.he || "") + '" placeholder="שם בעברית">' +
      '<input data-k="en" value="' + esc(s.en || "") + '" placeholder="Name in English" dir="ltr"></div>' +
      '<div class="nums"><input data-k="minutes" type="number" min="5" step="5" value="' +
        s.minutes + '"><span class="small muted">דק׳</span>' +
      '<input data-k="price" type="number" min="0" step="1" value="' + s.price + '">' +
      '<span class="small muted">$</span>' +
      '<label class="inline"><input data-k="form" type="checkbox"' + (s.form ? " checked" : "") +
        ">טופס</label>" +
      '<label class="inline"><input data-k="active" type="checkbox"' +
        (s.active !== false ? " checked" : "") + ">פעיל</label>" +
      '<button class="mini ghost" data-del="' + i + '" style="margin-inline-start:auto">✕</button>' +
      "</div></div>";
  }).join("");
  host.querySelectorAll("input").forEach(function(inp){
    inp.onchange = function(){
      var i = +inp.closest(".svccard").dataset.i, k = inp.dataset.k;
      db.services[i][k] = (k === "form" || k === "active") ? inp.checked
                        : (k === "minutes" || k === "price") ? (+inp.value || 0) : inp.value;
      persist(); cloudDirty("services", db.services[i].id); cloudSync();
    };
  });
  host.querySelectorAll("[data-del]").forEach(function(b){
    b.onclick = function(){
      var s = db.services[+b.dataset.del];
      if (!confirm("למחוק את " + svcName(s) + "?")) return;
      db.services.splice(+b.dataset.del, 1);
      persist(); cloudDelete("services", s.id); cloudSync(); renderSvcEditor();
    };
  });
}
function renderHoursEditor(){
  var host = $("#st-hours");
  host.innerHTML = [0,1,2,3,4,5,6].map(function(d){
    var wins = db.settings.hours[String(d)] || [];
    return '<div class="daybox"><div class="dn">' + dayName(d) + "</div>" +
      '<div class="grow" data-d="' + d + '">' +
      (wins.length ? wins.map(function(w, i){
        return '<div class="hourrow"><input type="time" step="900" data-w="' + i +
          '" data-k="from" value="' + w.from + '"><span>–</span>' +
          '<input type="time" step="900" data-w="' + i + '" data-k="to" value="' + w.to + '">' +
          '<button class="mini ghost" data-rm="' + i + '">✕</button></div>';
      }).join("") : '<div class="small muted" style="padding:9px 0">סגור</div>') +
      '<button class="mini ghost" data-add="' + d + '">+ שעות</button></div></div>';
  }).join("");
  host.querySelectorAll("input").forEach(function(inp){
    inp.onchange = function(){
      var d = inp.closest("[data-d]").dataset.d;
      db.settings.hours[d][+inp.dataset.w][inp.dataset.k] = inp.value;
      persist(); cloudDirty("settings", "settings"); cloudSync();
    };
  });
  host.querySelectorAll("[data-add]").forEach(function(b){
    b.onclick = function(){
      var d = b.dataset.add;
      (db.settings.hours[d] = db.settings.hours[d] || []).push({from:"09:00", to:"17:00"});
      persist(); cloudDirty("settings", "settings"); cloudSync(); renderHoursEditor();
    };
  });
  host.querySelectorAll("[data-rm]").forEach(function(b){
    b.onclick = function(){
      var d = b.closest("[data-d]").dataset.d;
      db.settings.hours[d].splice(+b.dataset.rm, 1);
      persist(); cloudDirty("settings", "settings"); cloudSync(); renderHoursEditor();
    };
  });
}

/* ------------------------------------------------------------ גיבוי */
function download(name, text){
  var blob = new Blob([text], {type: "application/json"});
  var a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = name;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  setTimeout(function(){ URL.revokeObjectURL(a.href); }, 4000);
}
function backup(){
  download("brows-backup-" + todayYmd() + ".json", JSON.stringify(db, null, 1));
  toast("הגיבוי ירד");
}
/* מה שהדפים הציבוריים צריכים לדעת, ורק זה: שום לקוחה ושום טופס. */
function exportSite(){
  download("salon.json", JSON.stringify({
    settings: db.settings,
    services: db.services.filter(function(s){ return s.active !== false; })
  }, null, 1));
  toast("salon.json ירד — להחליף אותו בתיקיית brows ולדחוף");
}
function restore(e){
  var file = e.target.files[0];
  if (!file) return;
  var r = new FileReader();
  r.onload = function(){
    try {
      var incoming = JSON.parse(r.result);
      if (!incoming || !Array.isArray(incoming.appointments)) throw new Error("bad");
      if (!confirm("לשחזר? כל מה שרשום כאן עכשיו יוחלף.")) return;
      /* גיבוי ישן עלול לחסר מבנה; ברירות המחדל ממלאות אותו */
      db = Object.assign(blankDb(), incoming);
      persist(); toast("שוחזר"); render();
    } catch (err) { toast("הקובץ לא נקרא"); }
  };
  r.readAsText(file);
  e.target.value = "";
}

/* ------------------------------------------------------------- הפעלה */
window.addEventListener("brows-cloud", function(){ db = loadDb(); render(); });
render();
cloudBoot();
