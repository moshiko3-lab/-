/* ======================================================================
   כתב השחרור והפטור, ולצידו הצהרת הבריאות וההסכמה מדעת — המסמך
   שהלקוחה חותמת עליו. אנגלית או עברית, ולנייד בלבד.

   מסמך, לא אשף: הכול על עמוד אחד שאפשר לגלול, כי אדם שחותם על מסמך
   צריך לראות אותו שלם. השאלון נפתח לפי הטיפול שנבחר — מי שבאה לשעוות
   שפם לא נשאלת על ניתוחי עיניים.
   ====================================================================== */

var db = null;
var sig = null;        /* מצב לוח החתימה */
var answers = {};      /* id -> {yes, note} */
var chosen = {};       /* id של טיפול -> true */
/* מה שכבר הוקלד. החלפת שפה מציירת את הטופס מחדש, ואישה שמילאה חצי
   מסמך ואז לחצה על EN לא אמורה למצוא אותו ריק — החתימה כלולה. */
var draft = {};

var TEXT_FIELDS = ["p-name","p-phone","p-id","p-birth","p-mail","p-notes","g-name","g-id"];
var TICKS = ["c-risk","c-after","c-dec","c-photo"];

function snapshot(){
  TEXT_FIELDS.forEach(function(id){ var e = $("#" + id); if (e) draft[id] = e.value; });
  TICKS.forEach(function(id){ var e = $("#" + id); if (e) draft[id] = e.checked; });
  if (sig && sig.drawn) draft.sig = sig.canvas.toDataURL("image/png");
}
function restore(){
  TEXT_FIELDS.forEach(function(id){
    var e = $("#" + id);
    if (e && draft[id]) e.value = draft[id];
  });
  TICKS.forEach(function(id){
    var e = $("#" + id);
    if (e && draft[id]) e.checked = true;
  });
  if (answers.minor && answers.minor.yes) $("#minor-box").classList.remove("hidden");
}

function $(s){ return document.querySelector(s); }
function $$(s){ return Array.prototype.slice.call(document.querySelectorAll(s)); }
function esc(s){
  return String(s == null ? "" : s).replace(/[&<>"']/g, function(c){
    return {"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c];
  });
}
var toastTimer = null;
function toast(msg){
  var el = $("#toast");
  el.firstElementChild.textContent = msg;
  el.classList.remove("hidden");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(function(){ el.classList.add("hidden"); }, 3000);
}
function qs(name){
  var m = new RegExp("[?&]" + name + "=([^&]*)").exec(location.search);
  return m ? decodeURIComponent(m[1].replace(/\+/g, " ")) : "";
}
function txt(o){ return LANG === "he" ? (o.he || o.en) : (o.en || o.he); }

function bootData(){
  if (cloudConfigured())
    return cloudPublicLoad().then(function(d){ db = d; }, function(){ db = local(); });
  db = local();
  return Promise.resolve();
}
function local(){
  var saved = null;
  try { saved = localStorage.getItem(DB_KEY); } catch (e) {}
  if (saved) return loadDb();
  var d = blankDb();
  if (SALON) d.settings = Object.assign(d.settings, SALON.settings || {});
  return d;
}

/* אילו קבוצות שאלות פתוחות לפי הטיפולים שסומנו. עוד לא סומן כלום —
   מציגים הכול, כדי שאף אחת לא תחשוב שהטופס קצר משהוא. */
function openGroups(){
  var g = {all: true}, any = false;
  TREATMENTS.forEach(function(tr){
    if (chosen[tr.id]) { any = true; tr.groups.forEach(function(x){ g[x] = true; }); }
  });
  /* עוד לא סומן כלום — מציגים את הכול, כדי שאף אחת לא תחשוב שהטופס
     קצר משהוא. הקבוצות נספרות מהטיפולים עצמם, כך שטיפול חדש לא נשאר
     בלי השאלות שלו. */
  if (!any) TREATMENTS.forEach(function(tr){
    tr.groups.forEach(function(x){ g[x] = true; });
  });
  return g;
}
function visibleQuestions(){
  var g = openGroups();
  return QUESTIONS.filter(function(q){ return g[q.g]; });
}

/* =============================== הטופס =============================== */
function drawForm(){
  document.title = t("formTitle");
  $("#bizname").textContent = (db.settings.name ? db.settings.name + " · " : "") + t("formTitle");
  $("#bizsub").textContent = t("formSub");

  $("#stage").innerHTML =
    '<div class="card"><h2>' + esc(t("yourInfo")) + "</h2>" +
      '<div class="field"><label>' + esc(t("fullName")) + "</label>" +
        '<input id="p-name" autocomplete="name" value="' + esc(qs("n")) + '">' +
        '<div class="errmsg">' + esc(t("needName")) + "</div></div>" +
      '<div class="field"><label>' + esc(t("phone")) + "</label>" +
        '<input id="p-phone" type="tel" inputmode="tel" autocomplete="tel" value="' +
        esc(qs("p")) + '"><div class="errmsg">' + esc(t("badPhone")) + "</div></div>" +
      '<div class="row"><div class="field grow"><label>' + esc(t("idnum")) + "</label>" +
        '<input id="p-id"></div>' +
        '<div class="field grow"><label>' + esc(t("birth")) + "</label>" +
        '<input id="p-birth" type="date"></div></div>' +
      '<div class="field"><label>' + esc(t("email")) + "</label>" +
        '<input id="p-mail" type="email" autocomplete="email" dir="ltr"></div>' +
    "</div>" +

    '<div class="card"><h2>' + esc(t("treatment")) + "</h2><div id=\"t-box\">" +
      TREATMENTS.map(function(tr){
        return '<label class="row" style="font-weight:400;padding:8px 0;gap:9px">' +
          '<input type="checkbox" data-t="' + tr.id + '"' +
          (chosen[tr.id] ? " checked" : "") + "><span>" + esc(txt(tr)) + "</span></label>";
      }).join("") + "</div>" +
      '<div class="errmsg" id="t-err">' + esc(t("pickTreatment")) + "</div></div>" +

    '<div class="card"><h2>' + esc(t("health")) + "</h2>" +
      '<p class="small muted">' + esc(t("healthNote")) + "</p>" +
      '<div id="q-box"></div></div>' +

    '<div class="card"><h2>' + esc(t("knowTitle")) + "</h2>" +
      '<div class="legal"><ul>' + RISKS[LANG].map(function(r){
        return "<li>" + esc(r) + "</li>"; }).join("") + "</ul>" +
      "<p><b>" + esc(t("patchTest")) + "</b> " + esc(TXT_PATCH[LANG]) + "</p></div>" +
      '<label class="agree" id="ag-risk"><input type="checkbox" id="c-risk"><span>' +
        esc(t("readRisks")) + "</span></label></div>" +

    '<div class="card"><h2>' + esc(t("afterTitle")) + "</h2>" +
      '<div class="legal"><ul>' + AFTERCARE[LANG].map(function(r){
        return "<li>" + esc(r) + "</li>"; }).join("") + "</ul></div>" +
      '<label class="agree" id="ag-after"><input type="checkbox" id="c-after"><span>' +
        esc(t("readAfter")) + "</span></label></div>" +

    '<div class="card"><h2>' + esc(t("decTitle")) + "</h2>" +
      '<div class="legal"><p>' + esc(t("decIntro")) + "</p><ol>" +
      DECLARATION[LANG].map(function(d){ return "<li>" + esc(d) + "</li>"; }).join("") +
      "</ol></div>" +
      '<label class="agree" id="ag-dec"><input type="checkbox" id="c-dec"><span>' +
        esc(t("readDec")) + "</span></label></div>" +

    '<div class="card"><h2>' + esc(t("privacyTitle")) + "</h2>" +
      '<div class="legal"><p>' + esc(TXT_PRIVACY[LANG]) + "</p></div>" +
      '<label class="agree" style="background:#fff;border:1px solid var(--line)">' +
        '<input type="checkbox" id="c-photo"><span>' + esc(TXT_PHOTO[LANG]) +
        "</span></label></div>" +

    '<div class="card hidden" id="minor-box"><h2>' + esc(t("guardianTitle")) + "</h2>" +
      '<p class="small muted">' + esc(t("guardianNote")) + "</p>" +
      '<div class="field"><label>' + esc(t("guardianName")) + '</label><input id="g-name"></div>' +
      '<div class="field"><label>' + esc(t("idnum")) + '</label><input id="g-id"></div></div>' +

    '<div class="card"><h2>' + esc(t("signature")) + "</h2>" +
      '<div class="field"><label>' + esc(t("notesLabel")) + "</label>" +
        '<textarea id="p-notes" rows="2"></textarea></div>' +
      '<div class="sigwrap"><canvas id="sig" class="sig"></canvas>' +
        '<div class="sighint" id="sighint">' + esc(t("signHere")) + "</div></div>" +
      '<div class="row between" style="margin-top:8px">' +
        '<span class="small muted" id="sigdate"></span>' +
        '<button class="mini ghost" id="sigclear">' + esc(t("clear")) + "</button></div>" +
      '<div class="errmsg" id="sig-err">' + esc(t("needSign")) + "</div></div>" +

    '<button class="primary block" id="send">' + esc(t("send")) + "</button>" +
    '<p class="small muted" id="sendmsg" style="text-align:center;margin:10px 0 24px"></p>';

  drawQuestions();
  restore();
  $("#sigdate").textContent = niceDate(todayYmd());
  $$("#t-box input").forEach(function(c){
    c.onchange = function(){ chosen[c.dataset.t] = c.checked; drawQuestions(); };
  });
  initSig();
  $("#send").onclick = submit;
}

function drawQuestions(){
  $("#q-box").innerHTML = visibleQuestions().map(function(q){
    var a = answers[q.id] || {};
    return '<div class="q" data-q="' + q.id + '"><div class="qt">' + esc(txt(q)) + "</div>" +
      '<div class="yn">' +
        '<label class="' + (a.yes === true ? "on-yes" : "") + '"><input type="radio" name="q-' +
          q.id + '" value="yes"' + (a.yes === true ? " checked" : "") + "><span>" +
          esc(t("yes")) + "</span></label>" +
        '<label class="' + (a.yes === false ? "on-no" : "") + '"><input type="radio" name="q-' +
          q.id + '" value="no"' + (a.yes === false ? " checked" : "") + "><span>" +
          esc(t("no")) + "</span></label></div>" +
      '<div class="field" style="margin:8px 0 0;' + (a.yes === true ? "" : "display:none") +
        '" data-note="' + q.id + '"><input placeholder="' +
        esc(LANG === "he" ? (q.askHe || t("tellMore")) : (q.askEn || t("tellMore"))) +
        '" value="' + esc(a.note || "") + '"></div></div>';
  }).join("");
  $$("#q-box input[type=radio]").forEach(function(r){
    r.onchange = function(){
      var box = r.closest(".q"), id = box.dataset.q, yes = r.value === "yes";
      answers[id] = {yes: yes, note: (answers[id] || {}).note || ""};
      box.classList.remove("err");
      box.querySelectorAll(".yn label").forEach(function(l){
        l.className = l.querySelector("input").checked ? (yes ? "on-yes" : "on-no") : "";
      });
      box.querySelector("[data-note]").style.display = yes ? "" : "none";
      if (id === "minor") $("#minor-box").classList.toggle("hidden", !yes);
    };
  });
  $$("#q-box [data-note] input").forEach(function(inp){
    inp.oninput = function(){
      var id = inp.closest("[data-note]").dataset.note;
      answers[id] = answers[id] || {yes: true, note: ""};
      answers[id].note = inp.value;
    };
  });
}

/* ------------------------------------------------------------ חתימה */
function initSig(){
  var c = $("#sig");
  var ratio = window.devicePixelRatio || 1;
  var ctx;
  function size(){
    var r = c.getBoundingClientRect();
    var keep = sig && sig.drawn ? c.toDataURL() : null;
    c.width = Math.max(1, Math.round(r.width * ratio));
    c.height = Math.max(1, Math.round(r.height * ratio));
    var x = c.getContext("2d");
    x.scale(ratio, ratio);
    x.lineWidth = 2.2; x.lineCap = "round"; x.lineJoin = "round"; x.strokeStyle = "#2f2622";
    if (keep) {
      var img = new Image();
      img.onload = function(){ x.drawImage(img, 0, 0, r.width, r.height); };
      img.src = keep;
    }
    return x;
  }
  ctx = size();
  sig = {drawn: false, canvas: c};
  if (draft.sig) {
    var back = new Image();
    back.onload = function(){
      var r = c.getBoundingClientRect();
      ctx.drawImage(back, 0, 0, r.width, r.height);
      sig.drawn = true;
      $("#sighint").style.display = "none";
    };
    back.src = draft.sig;
  }
  window.addEventListener("resize", function(){ ctx = size(); });

  var down = false;
  function pos(e){
    var r = c.getBoundingClientRect();
    return {x: e.clientX - r.left, y: e.clientY - r.top};
  }
  c.addEventListener("pointerdown", function(e){
    down = true;
    try { c.setPointerCapture(e.pointerId); } catch (err) {}
    var p = pos(e); ctx.beginPath(); ctx.moveTo(p.x, p.y);
    /* נקודה אחת היא עדיין חתימה: מי שרק נוגעת לא נשארת עם לוח ריק */
    ctx.lineTo(p.x + 0.1, p.y); ctx.stroke();
    sig.drawn = true;
    $("#sighint").style.display = "none";
    $("#sig-err").style.display = "none";
    e.preventDefault();
  });
  c.addEventListener("pointermove", function(e){
    if (!down) return;
    var p = pos(e); ctx.lineTo(p.x, p.y); ctx.stroke(); e.preventDefault();
  });
  ["pointerup", "pointercancel", "pointerleave"].forEach(function(ev){
    c.addEventListener(ev, function(){ down = false; });
  });
  $("#sigclear").onclick = function(){
    ctx.clearRect(0, 0, c.width, c.height);
    sig.drawn = false;
    delete draft.sig;
    $("#sighint").style.display = "";
  };
}

/* ------------------------------------------------------------ שליחה */
function submit(){
  var missing = [];
  var name = $("#p-name").value.trim();
  var phone = $("#p-phone").value.trim();
  $("#p-name").closest(".field").classList.toggle("err", !name);
  if (!name) missing.push(t("mName"));
  var pbad = !validPhone(phone);
  $("#p-phone").closest(".field").classList.toggle("err", pbad);
  if (pbad) missing.push(t("mPhone"));

  var treats = TREATMENTS.filter(function(tr){ return chosen[tr.id]; });
  $("#t-err").style.display = treats.length ? "none" : "block";
  if (!treats.length) missing.push(t("mTreat"));

  var unanswered = visibleQuestions().filter(function(q){ return !(q.id in answers); });
  unanswered.forEach(function(q){
    var el = document.querySelector('[data-q="' + q.id + '"]');
    if (el) el.classList.add("err");
  });
  if (unanswered.length) missing.push(t("mQuestions"));

  var consentOk = true;
  [["c-risk","ag-risk"], ["c-after","ag-after"], ["c-dec","ag-dec"]].forEach(function(p){
    var ok = $("#" + p[0]).checked;
    $("#" + p[1]).classList.toggle("err", !ok);
    if (!ok) consentOk = false;
  });
  if (!consentOk) missing.push(t("mConsent"));

  $("#sig-err").style.display = sig.drawn ? "none" : "block";
  if (!sig.drawn) missing.push(t("mSign"));

  if (missing.length) {
    $("#sendmsg").textContent = t("missing") + missing.join(", ");
    var first = document.querySelector(".err, #t-err[style*='block']");
    if (first) first.scrollIntoView({behavior: "smooth", block: "center"});
    return;
  }
  $("#sendmsg").textContent = "";

  var isMinor = !!(answers.minor && answers.minor.yes);
  var rec = {
    id: uid(),
    name: name,
    phone: normPhone(phone),
    idnum: $("#p-id").value.trim(),
    birth: $("#p-birth").value,
    email: $("#p-mail").value.trim(),
    lang: LANG,
    treatments: treats.map(function(tr){ return txt(tr); }),
    treatmentIds: treats.map(function(tr){ return tr.id; }),
    answers: visibleQuestions().map(function(q){
      var a = answers[q.id] || {};
      return {id: q.id, q: txt(q), yes: !!a.yes, note: a.note || "", flag: !!q.flag};
    }),
    notes: $("#p-notes").value.trim(),
    photos: $("#c-photo").checked,
    guardian: isMinor ? ($("#g-name").value.trim() + " · " + $("#g-id").value.trim()) : "",
    signature: sig.canvas.toDataURL("image/png"),
    signedAt: new Date().toISOString(),
    consent: {risks: true, aftercare: true, declaration: true},
    version: 1
  };

  $("#send").disabled = true;
  $("#send").textContent = t("sending");

  if (cloudConfigured()) {
    cloudSubmitForm(rec).then(function(){ drawDone(rec, "cloud"); },
      function(){ saveLocal(rec); whatsapp(rec); drawDone(rec, "wa"); });
    return;
  }
  saveLocal(rec);
  whatsapp(rec);
  drawDone(rec, "wa");
}
function saveLocal(rec){
  try {
    var d = loadDb();
    var c = findClient(d, rec.phone);
    if (c) rec.clientId = c.id;
    d.forms.push(rec);
    saveDb(d);
    cloudDirty("forms", rec.id);
  } catch (e) {}
}
/* בלי ענן, המסמך החתום נשאר על המכשיר שמילא אותו. מה שנוסע בוואטסאפ
   הוא הסיכום שהמטפלת צריכה כדי להחליט אם לטפל — לא התמונה של החתימה. */
function whatsapp(rec){
  var to = db.settings.phone || "";
  if (!to) return;
  var flags = rec.answers.filter(function(a){ return a.yes; });
  var text = t("waIntro") + " ✅\n" + rec.name + " · " + showPhone(rec.phone) + "\n" +
    rec.treatments.join(", ") + "\n" +
    (flags.length
      ? t("waFlags") + "\n" + flags.map(function(f){
          return "· " + f.q + (f.note ? " (" + f.note + ")" : ""); }).join("\n")
      : t("waClean")) +
    (rec.notes ? "\n" + t("waNote") + " " + rec.notes : "");
  window.open(waLink(to, text), "_blank");
}

/* ------------------------------------------ המסמך החתום, להדפסה */
function drawDone(rec, where){
  var yes = rec.answers.filter(function(a){ return a.yes; });
  $("#stage").innerHTML =
    '<div class="card noprint" style="text-align:center">' +
      '<div style="font-size:1.9rem">✓</div><h2>' + esc(t("signedTitle")) + "</h2>" +
      '<p class="small muted">' + esc(where === "cloud" ? t("signedCloud") : t("signedWa")) +
      "</p><button class=\"mini\" onclick=\"window.print()\">" + esc(t("printBtn")) +
      "</button></div>" +

    '<div class="card doc"><h2 style="margin-top:0">' +
      esc(db.settings.name ? db.settings.name + " — " : "") + esc(t("docTitle")) + "</h2>" +
    "<table>" +
      "<tr><td>" + esc(t("colName")) + "</td><td>" + esc(rec.name) + "</td></tr>" +
      "<tr><td>" + esc(t("colPhone")) + "</td><td>" + esc(showPhone(rec.phone)) + "</td></tr>" +
      (rec.idnum ? "<tr><td>" + esc(t("colId")) + "</td><td>" + esc(rec.idnum) + "</td></tr>" : "") +
      (rec.birth ? "<tr><td>" + esc(t("colBirth")) + "</td><td>" + esc(rec.birth) + "</td></tr>" : "") +
      "<tr><td>" + esc(t("colTreat")) + "</td><td>" + esc(rec.treatments.join(", ")) +
      "</td></tr></table>" +

    "<h2>" + esc(t("health")) + "</h2><table>" +
    rec.answers.map(function(a){
      return "<tr><td>" + esc(a.q) + "</td><td" + (a.yes ? ' class="yesmark"' : "") + ">" +
        esc(a.yes ? t("yes") : t("no")) + (a.note ? " — " + esc(a.note) : "") + "</td></tr>";
    }).join("") + "</table>" +
    (yes.length ? "" : '<p class="small muted">' + esc(t("noFlags")) + "</p>") +
    (rec.notes ? "<p><b>" + esc(t("notesTitle")) + "</b> " + esc(rec.notes) + "</p>" : "") +

    "<h2>" + esc(t("decTitle")) + '</h2><div class="legal"><p>' + esc(t("decIntro")) +
    "</p><ol>" + DECLARATION[LANG].map(function(d){
      return "<li>" + esc(d) + "</li>"; }).join("") + "</ol></div>" +
    '<p class="small">' + esc(t("afterOk")) + "<br>" + esc(t("risksOk")) + "<br>" +
      esc(t("photoLine")) + " " + esc(rec.photos ? t("agreed") : t("declined")) + "</p>" +
    '<p class="small muted">' + esc(TXT_PRIVACY[LANG]) + "</p>" +
    (rec.guardian ? "<p><b>" + esc(t("guardianLine")) + "</b> " + esc(rec.guardian) + "</p>" : "") +

    '<div style="margin-top:16px"><b>' + esc(t("signature")) + ":</b><br>" +
      '<img src="' + rec.signature + '" alt="signature" style="max-width:250px;' +
      'border:1px solid var(--line);border-radius:10px"><br>' +
      '<span class="small muted">' + esc(rec.name) + " · " +
      esc(localStamp(rec.signedAt)) + "</span></div></div>";
  window.scrollTo(0, 0);
}

/* ------------------------------------------------------------- הפעלה */
setLang(pickLang());
qs("t").split(",").forEach(function(id){ if (id) chosen[id] = true; });
langPick("#lang", function(){ snapshot(); drawForm(); });
bootData().then(drawForm);
