/* ======================================================================
   תוכן המסמך שהלקוחה חותמת עליו: כתב שחרור ופטור מאחריות, ולצידו
   הצהרת הבריאות וההסכמה מדעת שנותנות לו על מה לעמוד.

   הכול יושב כאן ולא מפוזר בקוד, כדי שאפשר יהיה לתקן נוסח בלי לגעת
   בדף. ארבע הערות למי שיעדכן:

   * הסעיפים שמסומנים flag הם התוויות נגד. "כן" בהם לא חוסם את הטופס —
     הוא מסמן אותו ליד המטפלת, כי ההחלטה אם לטפל היא שלה.
   * סעיף 8 בהצהרה — שאין במסמך כדי לפטור מרשלנות — נמצא שם בכוונה.
     פטור גורף מאחריות הוא בדיוק הסוג שנוטים לפסול; סעיף שמודה בגבול
     שלו עומד טוב יותר מסעיף שמתיימר לבטל כל אחריות.
   * סעיף 9 מחזיק את הטופס תקף גם לטיפולים הבאים מאותו סוג, כדי שלא
     צריך יהיה להחתים מחדש בכל ביקור — בתנאי שהלקוחה מעדכנת על שינוי.
   * זו נקודת פתיחה מקצועית, לא ייעוץ משפטי. העסק בפנמה; עורך דין
     מקומי צריך לעבור על הנוסח לפני שמשתמשים בו מול לקוחות.
   ====================================================================== */

/* הטיפולים שהמסמך מכסה, ואיזה חלק בשאלון כל אחד מהם פותח */
var TREATMENTS = [
  {id:"lift", groups:["eyes"],
   he:"הרמת ריסים (Lash Lift)",      en:"Lash lift"},
  {id:"lam",  groups:["brows"],
   he:"הרמת גבות / למינציה",         en:"Brow lamination"},
  {id:"tint", groups:["eyes","brows"],
   he:"צביעת גבות או ריסים",          en:"Brow or lash tint"},
  {id:"wax",  groups:["brows","hair"],
   he:"עיצוב גבות / שפם / שעווה בפנים", en:"Brows, upper lip or facial waxing"},
  {id:"bodywax", groups:["hair"],
   he:"שעווה בגוף (רגליים, ידיים, בית שחי)", en:"Body waxing (legs, arms, underarms)"},
  {id:"ext",  groups:["eyes"],
   he:"תוספות ריסים",                 en:"Lash extensions"}
];

var QUESTIONS = [
  /* ---- כללי: נשאל תמיד ---- */
  {id:"preg", g:"all", flag:true,
   he:"האם את בהיריון או מניקה?",
   en:"Are you pregnant or breastfeeding?"},
  {id:"allerg", g:"all", flag:true, askHe:"למה בדיוק?", askEn:"To what?",
   he:"האם ידועה לך רגישות או אלרגיה לחומרים כמו קרטין, אמוניום תיוגליקולט, צבע שיער/PPD, דבק, לטקס או שעווה?",
   en:"Do you have any known sensitivity or allergy to keratin, ammonium thioglycolate, hair dye/PPD, adhesive, latex or wax?"},
  {id:"react", g:"all", flag:true, askHe:"מה קרה?", askEn:"What happened?",
   he:"האם היתה לך בעבר תגובה, גירוי או כוויה בעקבות טיפול דומה?",
   en:"Have you ever had a reaction, irritation or burn from a similar treatment?"},
  {id:"skin", g:"all", flag:true,
   he:"האם יש כרגע באזור הטיפול מחלת עור פעילה, פצע פתוח, הרפס, אקזמה או פסוריאזיס?",
   en:"Is there any active skin condition, open wound, herpes, eczema or psoriasis in the treatment area?"},
  {id:"roacc", g:"all", flag:true,
   he:"האם נטלת בשנה האחרונה רואקוטן (איזוטרטינואין) או תכשיר דומה?",
   en:"Have you taken Accutane (isotretinoin) or a similar medication in the past year?"},
  {id:"onco", g:"all", flag:true,
   he:"האם את מטופלת כעת בכימותרפיה, בהקרנות או בתרופות מדכאות חיסון?",
   en:"Are you currently undergoing chemotherapy, radiotherapy, or taking immunosuppressants?"},
  {id:"meds", g:"all", flag:false, askHe:"אילו?", askEn:"Which ones?",
   he:"האם את נוטלת תרופות קבועות — סטרואידים, מדללי דם, הורמונים או אחרות?",
   en:"Do you take any regular medication — steroids, blood thinners, hormones or others?"},
  {id:"chronic", g:"all", flag:true, askHe:"איזו?", askEn:"Which?",
   he:"האם יש מחלה כרונית שכדאי שאדע עליה — אוטואימונית, בלוטת התריס, סוכרת, אפילפסיה?",
   en:"Do you have a chronic condition I should know about — autoimmune, thyroid, diabetes, epilepsy?"},
  {id:"aesth", g:"all", flag:true,
   he:"האם עברת באזור הטיפול בוטוקס, חומצה היאלורונית, פילינג, מיקרונידלינג או לייזר בשבועיים האחרונים?",
   en:"Have you had Botox, fillers, a peel, microneedling or laser in this area in the last two weeks?"},
  {id:"minor", g:"all", flag:true,
   he:"האם את מתחת לגיל 18?",
   en:"Are you under 18 years old?"},

  /* ---- עיניים: ריסים וצביעה ---- */
  {id:"eyesurg", g:"eyes", flag:true,
   he:"האם עברת ניתוח עיניים או תיקון לייזר בראייה בחצי השנה האחרונה?",
   en:"Have you had eye surgery or laser vision correction in the last six months?"},
  {id:"eyeinf", g:"eyes", flag:true,
   he:"האם יש כעת דלקת עיניים, לחמית, שעורה, יובש כרוני או רגישות מוגברת בעיניים?",
   en:"Do you currently have an eye infection, conjunctivitis, a stye, chronic dryness or unusually sensitive eyes?"},
  {id:"lens", g:"eyes", flag:false,
   he:"האם את מרכיבה עדשות מגע?",
   en:"Do you wear contact lenses?"},
  {id:"exts", g:"eyes", flag:true,
   he:"האם יש כרגע תוספות ריסים או שאריות של תוספות?",
   en:"Do you currently have lash extensions, or any leftover extensions?"},
  {id:"drops", g:"eyes", flag:true, askHe:"מה?", askEn:"What?",
   he:"האם את משתמשת בטיפות עיניים, בתרופה לגלאוקומה או בסרום להארכת ריסים?",
   en:"Do you use eye drops, glaucoma medication or a lash growth serum?"},

  /* ---- גבות ---- */
  {id:"hairrem", g:"brows", flag:true,
   he:"האם הסרת שיער באזור הגבות (שעווה, חוט, לייזר) ב-48 השעות האחרונות?",
   en:"Have you removed brow hair (wax, thread, laser) in the last 48 hours?"},
  {id:"loss", g:"brows", flag:true,
   he:"האם יש נשירה, אזורים דלילים או מריטה של שיער הגבות?",
   en:"Is there hair loss, thinning or plucking damage in your brows?"},
  {id:"pmu", g:"brows", flag:true,
   he:"האם יש איפור קבוע, מיקרובליידינג או שרטוט שבוצע בחודש האחרון?",
   en:"Do you have permanent makeup, microblading or brow tattooing done in the last month?"},

  /* ---- הסרת שיער, בפנים ובגוף ---- */
  {id:"sun", g:"hair", flag:true,
   he:"האם באזור יש כוויית שמש, שיזוף טרי, גירוי או עור פגום?",
   en:"Is the area sunburnt, freshly tanned, irritated or broken?"},
  {id:"laser", g:"hair", flag:true,
   he:"האם עברת באזור לייזר להסרת שיער, אלקטרוליזה או פילינג בשבועיים האחרונים?",
   en:"Have you had laser hair removal, electrolysis or a peel on this area in the last two weeks?"},
  {id:"veins", g:"hair", flag:false,
   he:"האם יש באזור דליות, שומות בולטות או ורידים מורחבים?",
   en:"Are there varicose veins, raised moles or broken capillaries in the area?"}
];

var RISKS = {
  he: [
    "הטיפול הוא טיפול קוסמטי. הוא אינו טיפול רפואי ואינו מחליף בדיקה או ייעוץ של רופא.",
    "ייתכנו אדמומיות, גירוד, צריבה קלה, נפיחות או יובש באזור הטיפול, בדרך כלל למשך שעות עד יממה.",
    "החומרים משנים את מבנה השערה. שיער דק, צבוע או פגום עלול להתייבש, להישבר או להגיב אחרת מהצפוי.",
    "התוצאה משתנה מאדם לאדם לפי סוג השערה, צפיפותה, כיוון הצמיחה ומצבה — ואינה ניתנת להבטחה מראש.",
    "משך התוצאה נע בדרך כלל בין ארבעה לשמונה שבועות, לפי מחזור צמיחת השערה והטיפוח שאחרי.",
    "במקרים נדירים תיתכן תגובה אלרגית. בדיקת רגישות מקטינה את הסיכון אך אינה מאפסת אותו.",
    "בטיפולי עיניים תיתכן צריבה או דמעת. אם חומר נכנס לעין — לשטוף מיד במים ולומר לי."
  ],
  en: [
    "This is a cosmetic treatment. It is not medical treatment or advice, and does not replace being seen by a doctor.",
    "Redness, itching, mild stinging, swelling or dryness in the treated area are possible, usually for a few hours up to a day.",
    "The products change the structure of the hair. Fine, coloured or damaged hair may dry out, break, or react differently than expected.",
    "Results vary from person to person with hair type, density, growth direction and condition — they cannot be guaranteed in advance.",
    "Results normally last four to eight weeks, depending on your hair growth cycle and the aftercare you follow.",
    "In rare cases an allergic reaction is possible. A patch test lowers that risk but does not remove it.",
    "Eye treatments can sting or make the eyes water. If any product enters the eye, rinse with water immediately and tell me."
  ]
};

var AFTERCARE = {
  he: [
    "24 שעות בלי מים, קיטור, סאונה, בריכה או ים באזור הטיפול.",
    "24 שעות בלי איפור, מסקרה, סרומים או חומצות באזור.",
    "לא לשפשף, לא לגרד ולא למשוך את השערות; אחרי הרמת ריסים — להימנע משינה עם הפנים בכרית.",
    "בלי שיזוף, מיטת שיזוף או חשיפה ממושכת לשמש ב-48 השעות הראשונות.",
    "להזין את השערות בשמן או בסרום שהומלץ, לפי ההנחיה שקיבלתי.",
    "אדמומיות שאינה חולפת, נפיחות, כאב, הפרשה או שינוי בראייה — להפסיק כל שימוש, לומר לי, ולפנות לרופא."
  ],
  en: [
    "No water, steam, sauna, pool or sea on the treated area for 24 hours.",
    "No makeup, mascara, serums or acids on the area for 24 hours.",
    "Do not rub, scratch or pull the hairs; after a lash lift, avoid sleeping face-down on the pillow.",
    "No tanning, tanning beds or long sun exposure for the first 48 hours.",
    "Nourish the hairs with the oil or serum recommended to you, as instructed.",
    "Redness that does not settle, swelling, pain, discharge or any change in vision — stop using everything, tell me, and see a doctor."
  ]
};

var DECLARATION = {
  he: [
    "כל הפרטים שמסרתי בטופס זה נכונים, מלאים ומעודכנים, ולא העלמתי מידע רפואי או בריאותי שעשוי להשפיע על הטיפול או על בטיחותו.",
    "קיבלתי הסבר מלא על מהות הטיפול, על מהלכו, על מה שהוא יכול ואינו יכול להשיג ועל הסיכונים הכרוכים בו; ניתנה לי הזדמנות לשאול שאלות וקיבלתי עליהן מענה.",
    "ידוע לי שהטיפול הוא טיפול קוסמטי בלבד, שאינו מהווה טיפול רפואי או ייעוץ רפואי ואינו מחליף אותם.",
    "אני בוחרת לקבל את הטיפול מרצוני החופשי ובהסכמה מדעת, ומקבלת על עצמי את הסיכונים שתוארו לעיל.",
    "ידוע לי שהתוצאה משתנה מאדם לאדם ואינה מובטחת, ושאי-שביעות רצון מהתוצאה האסתטית אינה כשלעצמה עילה להחזר או לפיצוי.",
    "אני מתחייבת להקפיד על הוראות הטיפול שנמסרו לי, ופוטרת את המטפלת מאחריות לכל נזק שנגרם כתוצאה מאי-הקפדה עליהן, או כתוצאה ממידע שמסרתי בטופס זה באופן שגוי או חלקי, או שלא מסרתי כלל.",
    "אני מתחייבת לדווח למטפלת על כל תגובה חריגה, ולפנות לרופא במידת הצורך.",
    "אין באמור במסמך זה כדי לפטור את המטפלת מאחריות לנזק שנגרם ברשלנותה או במעשה מכוון שלה.",
    "הצהרה זו תקפה גם לטיפולים נוספים מאותו סוג אצל אותה מטפלת, ואני מתחייבת לעדכן אותה בכל שינוי במצבי הבריאותי."
  ],
  en: [
    "Everything I have written in this form is true, complete and current. I have not withheld any medical or health information that could affect the treatment or its safety.",
    "I have received a full explanation of the treatment, how it is carried out, what it can and cannot achieve, and the risks involved. I was given the chance to ask questions and they were answered.",
    "I understand that this is a cosmetic treatment only. It is not medical treatment or medical advice and does not replace them.",
    "I choose to receive the treatment of my own free will and with informed consent, and I accept the risks described above.",
    "I understand that results vary from person to person and cannot be guaranteed, and that dissatisfaction with an aesthetic result is not in itself grounds for a refund or compensation.",
    "I undertake to follow the aftercare instructions given to me, and I release the therapist from liability for any harm caused by my failure to follow them, or caused by information I gave in this form incorrectly, partially, or not at all.",
    "I undertake to tell the therapist about any unusual reaction, and to seek medical attention if needed.",
    "Nothing in this document releases the therapist from liability for harm caused by her own negligence or wilful misconduct.",
    "This declaration also applies to further treatments of the same kind with the same therapist, and I undertake to inform her of any change in my health."
  ]
};

var TXT_PRIVACY = {
  he: "הפרטים והמידע הבריאותי שמסרתי נשמרים אצל המטפלת לצורך מתן הטיפול ובטיחותו בלבד, " +
      "לא יימסרו לצד שלישי אלא אם קיימת חובה שבדין, וניתן לפנות בכל עת כדי לעיין בהם, " +
      "לתקן אותם או לבקש את מחיקתם.",
  en: "The details and health information I have given are kept by the therapist solely to " +
      "provide the treatment safely. They will not be passed to anyone else unless the law " +
      "requires it, and I may ask at any time to see them, correct them or have them deleted."
};
var TXT_PHOTO = {
  he: "אני מאשרת צילום של אזור הטיפול לפני ואחרי, ופרסום הצילום בעמודי הסטודיו ברשתות " +
      "החברתיות. האישור אינו תנאי לקבלת הטיפול, וניתן לחזור בי ממנו בכל עת בהודעה למטפלת.",
  en: "I agree to before-and-after photos of the treated area being taken and posted on the " +
      "studio's social media. This is not a condition of the treatment, and I can withdraw " +
      "my agreement at any time by telling the therapist."
};
var TXT_PATCH = {
  he: "מומלץ לבצע בדיקת רגישות 48 שעות לפני הטיפול הראשון, ובכל מקרה שבו ידועה נטייה לאלרגיה.",
  en: "A patch test 48 hours before your first treatment is recommended, and in any case where " +
      "you know you are prone to allergies."
};
