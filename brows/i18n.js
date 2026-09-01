/* ======================================================================
   המילים של שני הדפים הציבוריים, באנגלית ובעברית.

   השפה נבחרת פעם אחת ונזכרת: ?lang= בכתובת גובר על הכול (כך אפשר לשלוח
   קישור בשפה מסוימת בוואטסאפ), אחרי זה מה שהלקוחה בחרה בפעם הקודמת,
   ואם אין כלום — שפת הדפדפן. ברירת המחדל היא אנגלית: בפנמה זה מה
   שהכי סביר שקוראים.
   ====================================================================== */

var T = {
  en: {
    dir:"ltr",
    /* דף קביעת התור */
    bookTitle:"Book an appointment",
    pickService:"What are we doing today?",
    noServices:"No treatments are open for booking right now.",
    minutes:"min",
    needsForm:"consent form required",
    formOnce:"Before your first treatment you fill in a short health declaration and release. Once, not every visit.",
    backToServices:"Back to treatments",
    changeTime:"Change time",
    pickWhen:"When suits you?",
    noSlots:"No times left that day. Try another one.",
    hoursOnlyNote:"These are opening hours. The final confirmation comes from the studio on WhatsApp.",
    yourDetails:"Your details",
    fullName:"Full name",
    phone:"Phone / WhatsApp",
    phoneHint:"With country code if it is not a Panama number",
    anything:"Anything I should know? (optional)",
    needName:"Please write your name",
    badPhone:"That number does not look right",
    beforeTreat:"Before your treatment",
    beforeTreatBody:"This treatment needs a signed health declaration and release. The link appears right after you book.",
    cancelPolicy:function(h){ return "I have read and agree: cancel or change up to " + h +
      " hours before the appointment. Late cancellations and no-shows may be charged."; },
    mustAgree:"Please agree to the cancellation terms",
    confirmBtn:"Confirm appointment",
    requestBtn:"Send request on WhatsApp",
    working:"One moment…",
    taken:"That time was just taken. Please pick another.",
    saveFailed:"Could not save it: ",
    bookedTitle:"You're booked",
    requestedTitle:"Request sent",
    bookedBody:function(h){ return "See you soon. Cancel or change up to " + h + " hours before."; },
    requestedBody:"The studio will confirm the time on WhatsApp.",
    fillForm:"Fill the health declaration & release",
    fillFormNote:"Takes a minute, and saves time in the studio.",
    bookAnother:"Book another appointment",
    copied:"Details copied — send them to the studio",
    notOnlineFoot:"Appointments are confirmed with the studio",

    /* כתב השחרור */
    formTitle:"Health declaration & release",
    formSub:"Before lash lift, brow lamination and tinting",
    yourInfo:"Your details",
    idnum:"ID / passport",
    birth:"Date of birth",
    email:"Email (optional)",
    treatment:"Treatment",
    pickTreatment:"Please choose at least one treatment",
    health:"Health declaration",
    healthNote:"These answers are what let me know the treatment is safe for you. A “yes” does not rule a treatment out — it just means we talk about it first.",
    yes:"Yes", no:"No", tellMore:"You can add detail",
    knowTitle:"What you should know",
    patchTest:"Patch test:",
    readRisks:"I have read and understood the explanation and the risks.",
    afterTitle:"Aftercare",
    readAfter:"I have received the instructions and undertake to follow them.",
    decTitle:"Release, waiver of liability and informed consent",
    decIntro:"I, the undersigned, declare and agree:",
    readDec:"I have read all of the clauses above, I understand them, and I confirm them with my signature.",
    privacyTitle:"Privacy and photos",
    guardianTitle:"Parent or guardian",
    guardianNote:"Under 18 — a parent or guardian must sign.",
    guardianName:"Parent / guardian name",
    notesLabel:"Anything you want to add (optional)",
    signature:"Signature",
    signHere:"Sign here with your finger",
    clear:"Clear",
    needSign:"Please sign",
    send:"Sign and send",
    sending:"Sending…",
    missing:"Missing: ",
    mName:"name", mPhone:"phone", mTreat:"treatment", mQuestions:"health questions",
    mConsent:"confirmations", mSign:"signature",
    signedTitle:"Signed",
    signedCloud:"It reached the studio. You can close this page.",
    signedWa:"WhatsApp opened with a summary for the studio. If it did not open, print or save as PDF and send it.",
    printBtn:"Print / save as PDF",
    docTitle:"Health declaration, informed consent and release",
    colName:"Full name", colPhone:"Phone", colId:"ID", colBirth:"Date of birth",
    colTreat:"Treatments",
    noFlags:"No contraindications were marked.",
    notesTitle:"Notes:",
    afterOk:"Aftercare instructions: accepted.",
    risksOk:"Explanation of risks: given and read.",
    photoLine:"Photos and posting:",
    agreed:"agreed", declined:"not agreed",
    guardianLine:"Guardian:",
    waIntro:"I filled in the health declaration and release",
    waFlags:"Please note — I answered yes to:",
    waClean:"I did not mark any contraindication.",
    waNote:"Note:"
  },

  he: {
    dir:"rtl",
    bookTitle:"קביעת תור",
    pickService:"מה עושים היום?",
    noServices:"אין כרגע טיפולים פתוחים להזמנה.",
    minutes:"דק׳",
    needsForm:"דורש כתב שחרור חתום",
    formOnce:"לפני הטיפול הראשון ממלאים הצהרת בריאות וכתב שחרור קצר. פעם אחת, לא בכל ביקור.",
    backToServices:"חזרה לטיפולים",
    changeTime:"שינוי מועד",
    pickWhen:"מתי נוח לך?",
    noSlots:"אין שעות פנויות ביום הזה. אפשר לנסות יום אחר.",
    hoursOnlyNote:"השעות כאן הן שעות הפעילות. אישור סופי מגיע מהסטודיו בוואטסאפ.",
    yourDetails:"הפרטים שלך",
    fullName:"שם מלא",
    phone:"טלפון / וואטסאפ",
    phoneHint:"עם קידומת מדינה אם זה לא מספר פנמי",
    anything:"משהו שכדאי לדעת? (לא חובה)",
    needName:"צריך שם",
    badPhone:"המספר לא נראה תקין",
    beforeTreat:"לפני הטיפול",
    beforeTreatBody:"לטיפול הזה צריך הצהרת בריאות וכתב שחרור חתומים. הקישור יופיע מיד אחרי הקביעה.",
    cancelPolicy:function(h){ return "קראתי ואני מאשרת: ביטול או שינוי עד " + h +
      " שעות לפני התור. ביטול מאוחר או אי-הגעה עלולים לחייב בתשלום."; },
    mustAgree:"צריך לאשר את תנאי הביטול",
    confirmBtn:"אישור התור",
    requestBtn:"שליחת בקשה בוואטסאפ",
    working:"רגע…",
    taken:"השעה הזאת בדיוק נתפסה. בחרי שעה אחרת.",
    saveFailed:"לא הצלחנו לשמור: ",
    bookedTitle:"התור נקבע",
    requestedTitle:"הבקשה נשלחה",
    bookedBody:function(h){ return "נתראה! ביטול או שינוי עד " + h + " שעות לפני."; },
    requestedBody:"הסטודיו יאשר את המועד בוואטסאפ.",
    fillForm:"מילוי הצהרת בריאות וכתב שחרור",
    fillFormNote:"לוקח דקה, וחוסך זמן בסטודיו.",
    bookAnother:"קביעת תור נוסף",
    copied:"הפרטים הועתקו — אפשר לשלוח אותם לסטודיו",
    notOnlineFoot:"התור נקבע בתיאום עם הסטודיו",

    formTitle:"הצהרת בריאות וכתב שחרור",
    formSub:"לפני הרמת ריסים, הרמת גבות וצביעה",
    yourInfo:"הפרטים שלך",
    idnum:"תעודת זהות / דרכון",
    birth:"תאריך לידה",
    email:"אימייל (לא חובה)",
    treatment:"הטיפול",
    pickTreatment:"צריך לבחור לפחות טיפול אחד",
    health:"הצהרת בריאות",
    healthNote:"התשובות כאן הן מה שמאפשר לי לדעת אם הטיפול בטוח עבורך. תשובת “כן” לא פוסלת טיפול — היא רק אומרת שנדבר על זה קודם.",
    yes:"כן", no:"לא", tellMore:"אפשר לפרט",
    knowTitle:"מה חשוב לדעת על הטיפול",
    patchTest:"בדיקת רגישות:",
    readRisks:"קראתי והבנתי את ההסבר ואת הסיכונים.",
    afterTitle:"הוראות לאחר הטיפול",
    readAfter:"קיבלתי את ההוראות ואני מתחייבת להקפיד עליהן.",
    decTitle:"כתב שחרור, פטור מאחריות והסכמה מדעת",
    decIntro:"אני, החתומה מטה, מצהירה ומאשרת:",
    readDec:"קראתי את כל הסעיפים לעיל, הבנתי אותם, ואני מאשרת אותם בחתימתי.",
    privacyTitle:"פרטיות וצילום",
    guardianTitle:"חתימת הורה או אפוטרופוס",
    guardianNote:"מתחת לגיל 18 — נדרשת חתימת הורה או אפוטרופוס.",
    guardianName:"שם ההורה/אפוטרופוס",
    notesLabel:"הערות שתרצי להוסיף (לא חובה)",
    signature:"חתימה",
    signHere:"חתמי כאן באצבע",
    clear:"ניקוי",
    needSign:"צריך לחתום",
    send:"חתימה ושליחה",
    sending:"שולח…",
    missing:"חסר: ",
    mName:"שם", mPhone:"טלפון", mTreat:"טיפול", mQuestions:"שאלון",
    mConsent:"אישורים", mSign:"חתימה",
    signedTitle:"הטופס נחתם",
    signedCloud:"הטופס הגיע לסטודיו. אפשר לסגור את הדף.",
    signedWa:"נפתח וואטסאפ עם סיכום לסטודיו. אם הוא לא נפתח — אפשר להדפיס או לשמור PDF ולשלוח.",
    printBtn:"הדפסה / שמירה כ־PDF",
    docTitle:"הצהרת בריאות, הסכמה מדעת וכתב שחרור",
    colName:"שם מלא", colPhone:"טלפון", colId:"תעודת זהות", colBirth:"תאריך לידה",
    colTreat:"טיפולים",
    noFlags:"לא סומנה אף התוויית נגד.",
    notesTitle:"הערות:",
    afterOk:"הוראות לאחר הטיפול: אושרו.",
    risksOk:"הסבר על הסיכונים: נמסר ונקרא.",
    photoLine:"צילום ופרסום:",
    agreed:"אושר", declined:"לא אושר",
    guardianLine:"אפוטרופוס:",
    waIntro:"מילאתי את הצהרת הבריאות וכתב השחרור",
    waFlags:"לתשומת לבך — עניתי כן על:",
    waClean:"לא סימנתי אף התוויית נגד.",
    waNote:"הערה:"
  }
};

var LANG_KEY = "brows.lang";
function pickLang(){
  var q = /[?&]lang=(he|en)/.exec(location.search);
  if (q) { try { localStorage.setItem(LANG_KEY, q[1]); } catch (e) {} return q[1]; }
  var saved = null;
  try { saved = localStorage.getItem(LANG_KEY); } catch (e) {}
  if (saved === "he" || saved === "en") return saved;
  return /^he/i.test(navigator.language || "") ? "he" : "en";
}
function setLang(l){
  LANG = l;
  try { localStorage.setItem(LANG_KEY, l); } catch (e) {}
  document.documentElement.lang = l;
  document.documentElement.dir = T[l].dir;
}
function t(k){ return T[LANG][k]; }

/* ------------------------------------------------------- מתג השפה
   שני מקטעים ולא כפתור אחד: לקוחה שרואה "עברית" על דף אנגלי צריכה
   לנחש אם זה מה שהיא מקבלת או מה שהיא תקבל. כאן רואים את שתיהן ואיזו
   מהן דולקת. הפקד עצמו נשאר LTR תמיד, כך שהוא לא מתהפך מתחת לאצבע
   ברגע שמחליפים. */
var GLOBE = '<svg class="globe" viewBox="0 0 24 24" fill="none" ' +
  'stroke="currentColor" stroke-width="1.7" stroke-linecap="round" aria-hidden="true">' +
  '<circle cx="12" cy="12" r="9"/><path d="M3 12h18"/>' +
  '<path d="M12 3c2.6 2.7 2.6 15.3 0 18C9.4 18.3 9.4 5.7 12 3z"/></svg>';

function langPick(host, onChange){
  var el = typeof host === "string" ? document.querySelector(host) : host;
  if (!el) return;
  el.className = "langpick";
  el.setAttribute("dir", "ltr");
  el.setAttribute("role", "group");
  el.setAttribute("aria-label", "Language");
  el.innerHTML = GLOBE +
    '<button type="button" data-l="en">EN</button>' +
    '<button type="button" data-l="he">עב</button>';
  function paint(){
    Array.prototype.forEach.call(el.querySelectorAll("button"), function(b){
      var on = b.dataset.l === LANG;
      b.classList.toggle("on", on);
      b.setAttribute("aria-pressed", on ? "true" : "false");
    });
  }
  Array.prototype.forEach.call(el.querySelectorAll("button"), function(b){
    b.onclick = function(){
      if (b.dataset.l === LANG) return;
      setLang(b.dataset.l);
      paint();
      onChange();
    };
  });
  paint();
}
