/* ======================================================================
   הבסיס המשותף לשלושת הדפים: היומן של המטפלת, דף קביעת התור, וכתב
   השחרור. שלושתם נבנים לקובץ HTML עצמאי אחד, ושלושתם קוראים ל-lib הזה
   כדי שחישוב הזמן הפנוי ייעשה במקום אחד. אם דף ההזמנה מחשב שעות אחרת
   מהיומן, הלקוחה מקבלת שעה שכבר תפוסה — וזו התקלה שהורגת מערכת תורים.

   הכול כאן מכוון לפנמה: דולר, +507, ומספרי טלפון של תיירות שמגיעים
   מכל מדינה שהיא.
   ====================================================================== */

var DB_KEY = "brows.db";
var CC = "507";                 /* קידומת המדינה שבה העסק יושב */

/* ------------------------------------------------------------------ זמן */
function pad2(n){ return (n < 10 ? "0" : "") + n; }

/* 'YYYY-MM-DD' מתוך Date, לפי השעון המקומי ולא UTC.
   toISOString היה מזיז תאריך אחורה כל אחרי-הצהריים בפנמה. */
function ymd(d){
  return d.getFullYear() + "-" + pad2(d.getMonth() + 1) + "-" + pad2(d.getDate());
}
function parseYmd(s){
  var p = String(s || "").split("-");
  return new Date(+p[0], (+p[1] || 1) - 1, +p[2] || 1);
}
function todayYmd(){ return ymd(new Date()); }
function addDays(s, n){ var d = parseYmd(s); d.setDate(d.getDate() + n); return ymd(d); }
function hm2min(s){
  var p = String(s || "0:0").split(":");
  return (+p[0] || 0) * 60 + (+p[1] || 0);
}
function min2hm(m){
  m = Math.max(0, Math.round(m));
  return pad2(Math.floor(m / 60)) + ":" + pad2(m % 60);
}
/* שעון 12 שעות, כי זה מה שקוראים בפנמה */
function hm12(s){
  var m = typeof s === "number" ? s : hm2min(s);
  var h = Math.floor(m / 60), mm = m % 60;
  var ap = h < 12 ? "AM" : "PM";
  h = h % 12; if (!h) h = 12;
  return h + ":" + pad2(mm) + " " + ap;
}

var DAYS = {
  he: ["ראשון","שני","שלישי","רביעי","חמישי","שישי","שבת"],
  en: ["Sunday","Monday","Tuesday","Wednesday","Thursday","Friday","Saturday"]
};
var DAYS_SHORT = {
  he: ["א׳","ב׳","ג׳","ד׳","ה׳","ו׳","ש׳"],
  en: ["Sun","Mon","Tue","Wed","Thu","Fri","Sat"]
};
var MONTHS = {
  he: ["ינואר","פברואר","מרץ","אפריל","מאי","יוני","יולי","אוגוסט","ספטמבר",
       "אוקטובר","נובמבר","דצמבר"],
  en: ["January","February","March","April","May","June","July","August",
       "September","October","November","December"]
};
/* השפה שבה הדף הנוכחי מדבר. היומן קובע "he" ולא נוגע בזה שוב;
   הדפים הציבוריים מחליפים אותה מתחת לרגליים של הפונקציות האלה. */
var LANG = "he";
function dayOf(s){ return parseYmd(s).getDay(); }          /* 0 = ראשון */
function dayName(i){ return DAYS[LANG][i]; }
function dayShort(i){ return DAYS_SHORT[LANG][i]; }
function niceDate(s){
  var d = parseYmd(s);
  return LANG === "he"
    ? DAYS.he[d.getDay()] + ", " + d.getDate() + " ב" + MONTHS.he[d.getMonth()]
    : DAYS.en[d.getDay()] + ", " + MONTHS.en[d.getMonth()] + " " + d.getDate();
}
function shortDate(s){
  var d = parseYmd(s);
  return d.getDate() + "/" + (d.getMonth() + 1);
}
function nowMinutes(){ var d = new Date(); return d.getHours() * 60 + d.getMinutes(); }
/* חותמת זמן על מסמך חתום נקראת בשעון של מי שקוראת אותו, לא ב-UTC.
   מה שנשמר נשאר ISO — זה מה שממיין נכון; מה שמוצג הוא מקומי. */
/* טווח שעות בתוך משפט עברי: "12:30 PM – 1:30 PM" הוא רצף של קטעים
   לטיניים עם מקף ניטרלי ביניהם, וההקשר הימני-לשמאלי מסדר אותם מחדש —
   על המסך זה יוצא "PM – 1:30 PM 12:30". span עם dir=ltr נועל את הסדר. */
function ltr(text){ return '<span dir="ltr">' + text + "</span>"; }
/* התאריך שרשום על מסמך חתום, קצר וקריא: 28/8 ולא 2026-08-28 */
function stampDate(iso){
  var d = new Date(iso);
  if (isNaN(d.getTime())) return String(iso || "").slice(0, 10);
  return d.getDate() + "/" + (d.getMonth() + 1);
}
function localStamp(iso){
  var d = new Date(iso);
  if (isNaN(d.getTime())) return String(iso || "");
  return niceDate(ymd(d)) + " · " + hm12(d.getHours() * 60 + d.getMinutes());
}

/* ---------------------------------------------------------------- מזהים */
function uid(){ return Date.now().toString(36) + Math.random().toString(36).slice(2, 8); }

/* ------------------------------------------------------------- טלפונים
   בוונאו חצי מהלקוחות מקומיות עם מספר פנמי בן שמונה ספרות, וחצי תיירות
   עם מספר מכל מקום בעולם. לכן: מספר שנראה מקומי מקבל את קידומת 507,
   וכל דבר עם + נשמר כפי שהוא. בדיקה רופפת בכוונה — עדיף לקבל מספר זר
   מוזר מאשר לחסום לקוחה אמיתית. */
function digits(s){ return String(s || "").replace(/\D+/g, ""); }
function normPhone(s){
  var raw = String(s || "").trim();
  var d = digits(raw);
  if (!d) return "";
  if (raw.charAt(0) === "+" || d.length > 8) return d;   /* כבר בינלאומי */
  return CC + d;                                          /* מקומי */
}
function validPhone(s){
  var d = normPhone(s);
  return d.length >= 8 && d.length <= 15;
}
function showPhone(s){
  var d = normPhone(s);
  if (d.indexOf(CC) === 0 && d.length === CC.length + 8)
    return d.slice(3, 7) + "-" + d.slice(7);              /* 6123-4567 */
  return "+" + d;
}
function waLink(phone, text){
  return "https://wa.me/" + normPhone(phone) + "?text=" + encodeURIComponent(text || "");
}

/* ---------------------------------------------------------------- כסף
   פנמה עובדת בדולר (הבלבואה צמודה 1:1 ובפועל משלמים בשטרות דולר). */
function money(n){
  var v = Math.round((+n || 0) * 100) / 100;
  return "$" + (v === Math.round(v) ? v : v.toFixed(2));
}

/* --------------------------------------------------------- ברירות מחדל */
/* השירותים והמחירים הם נקודת פתיחה סבירה לסטודיו גבות וריסים בפנמה.
   הם נערכים במסך ההגדרות, ושם הם אמורים להשתנות. */
function defaultServices(){
  return [
    {id:"s-brows-lip", he:"עיצוב גבות + שפם", en:"Brow shaping + upper lip",
     minutes:30, price:0, form:true, active:true, treat:["wax"]},
    {id:"s-lift",      he:"הרמת ריסים",       en:"Lash lift",
     minutes:60, price:0, form:true, active:true, treat:["lift"]},
    {id:"s-lam",       he:"הרמת גבות",        en:"Brow lamination",
     minutes:45, price:0, form:true, active:true, treat:["lam"]},
    {id:"s-leg",       he:"שעווה חצי רגל",    en:"Half leg wax",
     minutes:30, price:0, form:true, active:true, treat:["bodywax"]},
    {id:"s-arm",       he:"שעווה חצי יד",     en:"Half arm wax",
     minutes:30, price:0, form:true, active:true, treat:["bodywax"]},
    {id:"s-pit",       he:"שעווה בית שחי",    en:"Underarm wax",
     minutes:10, price:0, form:true, active:true, treat:["bodywax"]}
  ];
}
/* ראשון עד חמישי מלא, שישי קצר, שבת סגור. משנים בהגדרות. */
function defaultHours(){
  return {
    "0":[{from:"09:00", to:"18:00"}],
    "1":[{from:"09:00", to:"18:00"}],
    "2":[{from:"09:00", to:"18:00"}],
    "3":[{from:"09:00", to:"18:00"}],
    "4":[{from:"09:00", to:"18:00"}],
    "5":[{from:"09:00", to:"14:00"}],
    "6":[]
  };
}
function defaultSettings(){
  return {
    name:      "Brows & Lashes",
    owner:     "",
    phone:     "",
    address:   "",
    instagram: "",
    maps:      "",
    hours:     defaultHours(),
    step:      30,      /* כל כמה דקות מוצעת שעה */
    buffer:    10,      /* דקות סידור בין לקוחה ללקוחה */
    leadHours: 2,       /* כמה זמן מראש אפשר עוד לתפוס תור להיום */
    horizon:   45,      /* עד כמה ימים קדימה אפשר להזמין */
    cancelHours: 24,    /* מדיניות ביטול, מוצגת ללקוחה */
    autoConfirm: true,  /* תור מהאתר נכנס מאושר, או ממתין לאישור */
    showPrices: false,  /* האם דף ההזמנה מציג מחירים ללקוחה. ביומן הם
                           תמיד מוצגים — שם זה הכסף שלה, לא שיווק */
    noteHe:    "",      /* הודעה ללקוחה בדף ההזמנה */
    noteEn:    ""
  };
}
function blankDb(){
  return {v:1, settings: defaultSettings(), services: defaultServices(),
          clients: [], appointments: [], blocks: [], forms: []};
}
/* שם הטיפול בשפה של הדף. שירות שנוצר ביומן מקבל שם אחד, וזה בסדר. */
function svcName(s){
  if (!s) return "";
  return (LANG === "en" ? (s.en || s.he) : (s.he || s.en)) || s.name || "";
}

/* איזה חלק בכתב השחרור נפתח לטיפול הזה. שירות שנוצר ביד יכול לשאת
   treat משלו; ברירת המחדל מכסה את הקטלוג שהמערכת מגיעה איתו. */
var SERVICE_TREATMENTS = {
  "s-lift":["lift"], "s-lam":["lam"], "s-both":["lift","lam"], "s-tint":["tint"],
  "s-brows":["wax"], "s-fix":["wax"], "s-bl":["wax"], "s-face":["wax"],
  "s-brows-lip":["wax"], "s-leg":["bodywax"], "s-arm":["bodywax"], "s-pit":["bodywax"]
};
function treatmentsFor(s){
  if (!s) return [];
  if (Array.isArray(s.treat)) return s.treat;
  return SERVICE_TREATMENTS[s.id] || [];
}

/* ------------------------------------------------------------- אחסון */
function loadDb(){
  var db;
  try { db = JSON.parse(localStorage.getItem(DB_KEY) || "null"); } catch (e) { db = null; }
  if (!db || typeof db !== "object") return blankDb();
  var base = blankDb();
  ["services","clients","appointments","blocks","forms"].forEach(function(k){
    if (!Array.isArray(db[k])) db[k] = base[k];
  });
  db.settings = Object.assign({}, base.settings, db.settings || {});
  db.settings.hours = Object.assign({}, base.settings.hours, db.settings.hours || {});
  return db;
}
function saveDb(db){
  try { localStorage.setItem(DB_KEY, JSON.stringify(db)); return true; }
  catch (e) { return false; }
}

/* --------------------------------------------------------- זמן פנוי
   תור תופס את השעה שלו ועוד דקות הסידור אחריו. הפער הזה הוא ההבדל בין
   יום שאפשר לעבוד בו ליום שבו כל תור מתחיל באיחור. */
function serviceById(db, id){
  for (var i = 0; i < db.services.length; i++)
    if (db.services[i].id === id) return db.services[i];
  return null;
}
function apptEnd(db, a){
  var m = a.minutes;
  if (!m) { var s = serviceById(db, a.serviceId); m = (s && s.minutes) || 30; }
  return hm2min(a.time) + m;
}
function ACTIVE(a){ return a.status !== "cancelled"; }

/* דקות הסידור נספרות לשני הכיוונים: תור תופס את השעה שלו ועוד הסידור
   אחריו, וגם תור חדש נבדק עם הסידור שלו. בלי זה אפשר לתפוס 10:30–11:00
   ממש בצמוד לתור של 11:00, ואז אין רגע לנקות בין השתיים. היומן עצמו
   בודק בלי הסידור — הוא מזהיר על חפיפה אמיתית, לא על צמידות. */
function busyRanges(db, date, withBuffer){
  var buf = withBuffer === false ? 0 : (+db.settings.buffer || 0), out = [];
  db.appointments.forEach(function(a){
    if (a.date !== date || !ACTIVE(a)) return;
    out.push({from: hm2min(a.time), to: apptEnd(db, a) + buf, appt: a});
  });
  db.blocks.forEach(function(b){
    if (b.date !== date) return;
    out.push({from: hm2min(b.from), to: hm2min(b.to), block: b});
  });
  return out.sort(function(x, y){ return x.from - y.from; });
}
function workWindows(db, date){
  var list = db.settings.hours[String(dayOf(date))] || [];
  return list.map(function(w){ return {from: hm2min(w.from), to: hm2min(w.to)}; })
             .filter(function(w){ return w.to > w.from; });
}
function freeSlots(db, date, minutes){
  var step = +db.settings.step || 30;
  var buf = +db.settings.buffer || 0;
  var busy = busyRanges(db, date);
  var out = [], floor = -1;
  if (date === todayYmd()) floor = nowMinutes() + (+db.settings.leadHours || 0) * 60;
  workWindows(db, date).forEach(function(w){
    var start = Math.ceil(w.from / step) * step;
    /* התור עצמו חייב להיכנס לפני הסגירה; הסידור שאחריו כבר לא, אחרת
       התור האחרון של היום נעלם בכל יום */
    for (var t = start; t + minutes <= w.to; t += step){
      if (t < floor) continue;
      var end = t + minutes + buf;
      var clash = busy.some(function(r){ return t < r.to && end > r.from; });
      if (!clash) out.push(t);
    }
  });
  return out;
}
/* היומן משתמש בזה כדי להזהיר על חפיפה, ומתעלם מהתור שהוא עצמו עורך */
function conflictAt(db, date, time, minutes, ignoreId){
  var from = hm2min(time), to = from + minutes, hit = null;
  busyRanges(db, date, false).forEach(function(r){
    if (r.appt && r.appt.id === ignoreId) return;
    if (from < r.to && to > r.from && !hit) hit = r;
  });
  return hit;
}

/* -------------------------------------------------------- לקוחות */
function findClient(db, phone){
  var p = normPhone(phone);
  if (!p) return null;
  for (var i = 0; i < db.clients.length; i++)
    if (normPhone(db.clients[i].phone) === p) return db.clients[i];
  return null;
}
function upsertClient(db, name, phone, extra){
  var c = findClient(db, phone);
  if (!c) {
    c = {id: uid(), name: name || "", phone: normPhone(phone), notes: "",
         created: new Date().toISOString()};
    db.clients.push(c);
  }
  if (name && !c.name) c.name = name;
  Object.assign(c, extra || {});
  return c;
}
function apptsOf(db, clientId){
  return db.appointments.filter(function(a){ return a.clientId === clientId; })
    .sort(function(a, b){ return (b.date + b.time).localeCompare(a.date + a.time); });
}
