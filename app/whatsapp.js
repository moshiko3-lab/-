/* ========================== the school's WhatsApp ==========================

   The counter already has the day in front of it. This is the other half of
   the same conversation: what the customer actually reads.

   Three things live here.

     * The conversation. Every message in and out, in one list per number,
       with a box to answer from. The messages are rows in the shared book
       like everything else -- this screen reads them the same way the board
       reads sessions.
     * The automations. A reminder before a session, a brief every morning to
       whoever is working, and a bot that answers the questions that get asked
       forty times a week. All off until somebody turns them on.
     * The setup. What is connected, what is not, and what to do about it.

   Two rules of WhatsApp's own shape this whole screen, and neither is ours:

     1. A free-form message may only be sent within 24 hours of the customer's
        last message. Outside that window nothing goes but a template Meta
        approved beforehand. So the box below a cold conversation is closed,
        with the reason on it, rather than accepting a reply that would be
        refused after the fact.
     2. There is no group. The Cloud API cannot post into a WhatsApp group at
        all, so the morning brief is the same message to each person on the
        list, sent individually.

   Nothing here holds the Meta token. The page asks the Edge Function, the
   function decides and sends. See supabase/WHATSAPP.md. */

var WA={tab:"chats",open:"",cfg:null,contacts:[],recent:[],thread:[],
        health:null,loaded:false,loading:false,err:"",timer:null,busy:false};

var WA_DEFAULTS={
  tz:"America/Panama", bookingUrl:"",
  reminders:{on:false,hoursBefore:18,template:"session_reminder",lang:"en",
             quietFrom:21,quietTo:7},
  brief:{on:false,at:"07:00",days:[0,1,2,3,4,5,6],to:[],
         template:"daily_brief",lang:"en"},
  bot:{on:false,hours:"",greeting:"",handover:"",rules:[]}
};

function waCfg(){
  var c=WA.cfg||{};
  return {
    tz:c.tz||WA_DEFAULTS.tz,
    bookingUrl:c.bookingUrl||"",
    reminders:waMerge(WA_DEFAULTS.reminders,c.reminders),
    brief:waMerge(WA_DEFAULTS.brief,c.brief),
    bot:waMerge(WA_DEFAULTS.bot,c.bot)
  };
}
function waMerge(base,over){
  var out={},k;
  for(k in base) out[k]=base[k];
  for(k in (over||{})) if(over[k]!=null) out[k]=over[k];
  return out;
}

/* Digits, no plus, no spaces -- the way Meta keeps them, so a number typed at
   the counter and the same number arriving from a webhook are one row and not
   two conversations. Kept identical to waId() in the function. */
function waNum(raw){
  var d=String(raw==null?"":raw).replace(/\D+/g,"");
  if(!d) return "";
  d=d.replace(/^00/,"");
  if(d.length<=8) d="507"+d;
  return d;
}
function waPretty(id){
  var s=String(id||"");
  return s?("+"+s):"—";
}
/* The escape hatch, and the reason this screen is useful before a single Meta
   form has been filled in: a link that opens WhatsApp with the message already
   typed, for a person to send with their own thumb. */
function waLink(phone,text){
  return "https://wa.me/"+waNum(phone)+
         (text?("?text="+encodeURIComponent(text)):"");
}
function waWhen(ts){
  var d=new Date(ts);
  if(isNaN(d.getTime())) return "";
  var hh=String(d.getHours()).padStart(2,"0")+":"+
         String(d.getMinutes()).padStart(2,"0");
  return iso(d)===todayISO()?hh:(dmy(iso(d))+" "+hh);
}
function waAgo(ts){
  if(!ts) return "";
  var mins=Math.round((Date.now()-Date.parse(ts))/60000);
  if(isNaN(mins)) return "";
  if(mins<1) return "just now";
  if(mins<60) return mins+"m ago";
  if(mins<1440) return Math.round(mins/60)+"h ago";
  return Math.round(mins/1440)+"d ago";
}
/* The 24-hour window, worked out the same way the function works it out. */
function waWindowOpen(c){
  if(!c||!c.last_in) return false;
  return (Date.now()-Date.parse(c.last_in))<24*3600*1000-60000;
}

/* ------------------------------ the wire ------------------------------
   Reading is ordinary PostgREST, the same as the rest of the book. Sending is
   never that: it goes to the function, which is the only thing holding a token
   that could message the world as the school. */
function waCall(path,body){
  var url=CLOUD.url+"/functions/v1/whatsapp/"+path;
  return fetch(url,{method:body?"POST":"GET",headers:cloudHeaders(),
                    body:body?JSON.stringify(body):undefined})
    .then(function(r){
      return r.text().then(function(t){
        var j=null; try{ j=t?JSON.parse(t):null; }catch(e){}
        if(!r.ok) throw {status:r.status,
          message:(j&&j.error)||t||("HTTP "+r.status)};
        return j;
      });
    });
}
function waWhere(){ return "school=eq."+encodeURIComponent(CLOUD.school); }

function waRefresh(quiet){
  if(!cloudConfigured()||!cloudSignedIn()){ WA.loaded=true; return; }
  if(WA.loading) return;
  WA.loading=true;
  if(!quiet) WA.err="";
  var jobs=[
    cloudFetch("/rest/v1/wa_config?"+waWhere()+"&select=data&limit=1")
      .then(function(r){ WA.cfg=(r&&r[0]&&r[0].data)||{}; }),
    cloudFetch("/rest/v1/wa_contacts?"+waWhere()+
               "&order=last_in.desc.nullslast&limit=200")
      .then(function(r){ WA.contacts=r||[]; }),
    cloudFetch("/rest/v1/wa_messages?"+waWhere()+
               "&order=created_at.desc&limit=200")
      .then(function(r){ WA.recent=r||[]; })
  ];
  if(WA.open){
    jobs.push(cloudFetch("/rest/v1/wa_messages?"+waWhere()+
        "&wa_id=eq."+encodeURIComponent(WA.open)+
        "&order=created_at.desc&limit=80")
      .then(function(r){ WA.thread=(r||[]).slice().reverse(); }));
  }
  Promise.all(jobs).then(function(){
    WA.loaded=true; WA.loading=false; WA.err="";
    if(cur==="whatsapp") render();
  }).catch(function(e){
    WA.loading=false; WA.loaded=true;
    WA.err=(e&&e.message)||"could not read the conversation";
    /* the tables are added by supabase/whatsapp.sql; say so rather than
       leaving a raw PostgREST complaint on the screen */
    if(/does not exist|relation|schema cache/i.test(WA.err))
      WA.err="the WhatsApp tables are not in the database yet — "+
             "run supabase/whatsapp.sql once, then come back";
    if(cur==="whatsapp") render();
  });
}
function waHealth(){
  waCall("health").then(function(h){
    WA.health=h||{};
    if(h&&h.config) WA.cfg=h.config;
    if(cur==="whatsapp") render();
  }).catch(function(e){
    WA.health={error:(e&&e.message)||"the function did not answer"};
    if(cur==="whatsapp") render();
  });
}
function waSaveCfg(next,note){
  WA.cfg=next;
  return cloudFetch("/rest/v1/wa_config?on_conflict=school",{
    method:"POST",
    headers:{"Prefer":"resolution=merge-duplicates,return=minimal"},
    body:[{school:CLOUD.school,data:next}]
  }).then(function(){
    toast(note||"Saved");
    if(cur==="whatsapp") render();
  }).catch(function(e){
    toast("Could not save: "+((e&&e.message)||"refused"));
  });
}

/* Every fifteen seconds while somebody is looking at this screen, and never
   when they are not: a school with the board open all day should not be
   polling a conversation nobody is reading. */
function waPulse(){
  if(WA.timer) return;
  WA.timer=setInterval(function(){
    if(cur==="whatsapp" && !WA.busy) waRefresh(true);
  },15000);
}

/* ------------------------------ the screen ------------------------------ */
function renderWhatsapp(){
  var host=document.getElementById("p-whatsapp"); host.textContent="";
  waPulse();
  if(!WA.loaded && !WA.loading) waRefresh();
  if(WA.health===null && cloudSignedIn()){ WA.health={}; waHealth(); }

  var unread=WA.contacts.reduce(function(a,c){return a+(c.unread||0);},0);
  var waiting=WA.contacts.filter(function(c){return c.needs_human;}).length;
  secHeader(host,"WhatsApp",
    [WA.contacts.length?(WA.contacts.length+" conversation"+
       (WA.contacts.length===1?"":"s")):"",
     unread?(unread+" unread"):"",
     waiting?(waiting+" waiting on a person"):""].filter(Boolean).join(" · "),
    "New message",function(){ waComposeForm(""); });

  var strip=el("div","panel");
  strip.style.cssText="padding:10px 12px;display:flex;gap:8px;align-items:center;flex-wrap:wrap";
  var h=WA.health||{};
  var state=h.error?"critc":(h.connected?"ok":"warnc");
  strip.appendChild(el("span","chip "+state,
    h.error?"the function did not answer":(h.connected?"Connected":"Not connected")));
  if(h.number&&h.number.display_phone_number)
    strip.appendChild(el("span","lab",h.number.display_phone_number+
      (h.number.verified_name?(" · "+h.number.verified_name):"")));
  if(h.queued) strip.appendChild(el("span","chip neutral",h.queued+" queued"));
  var sp=el("span","spacer"); strip.appendChild(sp);
  var rf=el("button","btn sm","Refresh");
  rf.addEventListener("click",function(){ WA.health=null; waRefresh(); toast("Reading…"); });
  strip.appendChild(rf);
  host.appendChild(strip);

  if(WA.err){
    var bad=el("div","panel");
    bad.style.cssText="padding:12px;border-left:3px solid var(--crit)";
    bad.appendChild(el("div","strong","The conversation could not be read"));
    bad.appendChild(el("div","muted",WA.err));
    host.appendChild(bad);
  }

  var tabs=el("div","pos-tabs"); tabs.style.margin="12px 0";
  [{k:"chats",l:"Chats"},{k:"auto",l:"Automations"},{k:"setup",l:"Setup"}]
    .forEach(function(t){
      var b=el("button",null,t.l);
      b.setAttribute("aria-pressed",WA.tab===t.k?"true":"false");
      b.addEventListener("click",function(){ WA.tab=t.k; render(); });
      tabs.appendChild(b);
    });
  host.appendChild(tabs);

  if(WA.tab==="chats") waChats(host);
  else if(WA.tab==="auto") waAutomations(host);
  else waSetup(host);
}

/* ------------------------------ the chats ------------------------------ */
function waPreview(id){
  for(var i=0;i<WA.recent.length;i++)
    if(WA.recent[i].wa_id===id) return WA.recent[i];
  return null;
}
function waWho(c){
  if(c.name) return c.name;
  var m=null;
  DB.clients.forEach(function(x){
    if(x.phone && waNum(x.phone)===c.wa_id) m=x.name;
  });
  if(!m) DB.staff.forEach(function(x){
    if(x.phone && waNum(x.phone)===c.wa_id) m=x.name+" (crew)";
  });
  return m||waPretty(c.wa_id);
}

function waChats(host){
  if(!WA.contacts.length){
    host.appendChild(emptyState("💬","No conversations yet",
      "Every message the school's number sends or receives lands here, in one "+
      "thread per person. Nothing arrives until the number is connected and "+
      "the webhook is pointed at the function — the Setup tab says what is "+
      "still missing. In the meantime, New message opens WhatsApp with the "+
      "text ready to send by hand.",
      "Send a message",function(){ waComposeForm(""); }));
    return;
  }
  var grid=el("div");
  grid.style.cssText="display:grid;grid-template-columns:minmax(220px,300px) 1fr;"+
    "gap:12px;align-items:start";
  if(window.innerWidth<860) grid.style.gridTemplateColumns="1fr";

  var list=el("div","panel");
  list.style.cssText="max-height:70vh;overflow:auto;padding:4px";
  WA.contacts.forEach(function(c){
    var row=el("button");
    var on=WA.open===c.wa_id;
    row.style.cssText="appearance:none;border:0;width:100%;text-align:left;"+
      "font:inherit;cursor:pointer;padding:9px 10px;border-radius:8px;"+
      "display:block;background:"+(on?"var(--line)":"none");
    var top=el("div");
    top.style.cssText="display:flex;gap:6px;align-items:center";
    var nm=el("span","strong",waWho(c));
    nm.style.cssText="flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap";
    top.appendChild(nm);
    if(c.unread) top.appendChild(el("span","chip warnc",String(c.unread)));
    if(c.needs_human) top.appendChild(el("span","chip critc","person"));
    if(c.opted_out) top.appendChild(el("span","chip neutral","stopped"));
    row.appendChild(top);
    var last=waPreview(c.wa_id);
    var sub=el("div","muted",(last?((last.direction==="out"?"→ ":"")+
      String(last.body||"").slice(0,44)):waPretty(c.wa_id)));
    sub.style.cssText="font-size:12px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap";
    row.appendChild(sub);
    row.appendChild(el("div","muted",waAgo(c.last_in||c.last_out)));
    row.addEventListener("click",function(){
      WA.open=c.wa_id; WA.thread=[]; waRefresh(); waSeen(c);
    });
    list.appendChild(row);
  });
  grid.appendChild(list);
  grid.appendChild(waThread());
  host.appendChild(grid);
}

/* Opening a thread is reading it. The count is the school's own, not Meta's --
   nothing here marks anything read on the customer's phone. */
function waSeen(c){
  if(!c.unread) return;
  cloudFetch("/rest/v1/wa_contacts?"+waWhere()+
             "&wa_id=eq."+encodeURIComponent(c.wa_id),{
    method:"PATCH",headers:{"Prefer":"return=minimal"},body:{unread:0}
  }).then(function(){ c.unread=0; }).catch(function(){});
}

function waThread(){
  var box=el("div","panel");
  box.style.cssText="padding:12px;min-height:320px;display:flex;flex-direction:column";
  if(!WA.open){
    box.appendChild(el("p","muted","Pick a conversation on the left."));
    return box;
  }
  var c=null;
  WA.contacts.forEach(function(x){ if(x.wa_id===WA.open) c=x; });
  c=c||{wa_id:WA.open};

  var head=el("div");
  head.style.cssText="display:flex;gap:8px;align-items:center;flex-wrap:wrap;"+
    "border-bottom:1px solid var(--line);padding-bottom:8px;margin-bottom:8px";
  head.appendChild(el("span","strong",waWho(c)));
  head.appendChild(el("span","lab",waPretty(c.wa_id)));
  var hsp=el("span","spacer"); head.appendChild(hsp);
  if(c.needs_human){
    var done=el("button","btn sm","Handled");
    done.addEventListener("click",function(){
      cloudFetch("/rest/v1/wa_contacts?"+waWhere()+
                 "&wa_id=eq."+encodeURIComponent(c.wa_id),{
        method:"PATCH",headers:{"Prefer":"return=minimal"},
        body:{needs_human:false,bot_until:null}
      }).then(function(){ waRefresh(); toast("Back to the bot"); })
        .catch(function(e){ toast((e&&e.message)||"Refused"); });
    });
    head.appendChild(done);
  }
  var open=el("a","btn sm","Open in WhatsApp");
  open.href=waLink(c.wa_id,""); open.target="_blank"; open.rel="noopener";
  head.appendChild(open);
  box.appendChild(head);

  var log=el("div");
  log.style.cssText="flex:1;overflow:auto;max-height:52vh;display:flex;"+
    "flex-direction:column;gap:6px;padding:2px";
  if(!WA.thread.length) log.appendChild(el("p","muted","Nothing in this thread yet."));
  WA.thread.forEach(function(m){
    var out=m.direction==="out";
    var b=el("div");
    b.style.cssText="max-width:78%;padding:7px 10px;border-radius:10px;"+
      "white-space:pre-wrap;word-break:break-word;font-size:13px;"+
      (out?"align-self:flex-end;background:var(--accent);color:#fff"
         :"align-self:flex-start;background:var(--line)");
    b.appendChild(el("div",null,m.body||("("+(m.kind||"message")+")")));
    var meta=el("div",null,waWhen(m.created_at)+
      (m.template?(" · "+m.template):"")+
      (out&&m.status?(" · "+m.status):""));
    meta.style.cssText="font-size:10px;opacity:.75;margin-top:3px";
    b.appendChild(meta);
    if(m.error){
      var er=el("div",null,m.error);
      er.style.cssText="font-size:10px;margin-top:3px;color:var(--crit);"+
        (out?"color:#ffd7d7":"");
      b.appendChild(er);
    }
    log.appendChild(b);
  });
  box.appendChild(log);

  var foot=el("div");
  foot.style.cssText="border-top:1px solid var(--line);padding-top:8px;margin-top:8px";
  if(c.opted_out){
    foot.appendChild(el("div","muted",
      "This number asked us to stop writing. Nothing will be sent to it."));
  } else if(!waWindowOpen(c)){
    foot.appendChild(el("div","muted",
      "More than 24 hours since their last message. WhatsApp only allows an "+
      "approved template here, so the box is closed — open the chat and send "+
      "it by hand, or let a template go from the automations."));
    var a=el("a","btn sm primary","Open in WhatsApp");
    a.href=waLink(c.wa_id,""); a.target="_blank"; a.rel="noopener";
    a.style.marginTop="8px"; foot.appendChild(a);
  } else {
    var row=el("div");
    row.style.cssText="display:flex;gap:8px;align-items:flex-end";
    var ta=el("textarea"); ta.rows=2;
    ta.style.cssText="flex:1;font:inherit;padding:8px;border-radius:8px;"+
      "border:1px solid var(--line);background:var(--panel);color:inherit";
    ta.placeholder="Write a reply…";
    var sendb=el("button","btn primary","Send");
    sendb.addEventListener("click",function(){
      var text=ta.value.trim();
      if(!text) return;
      sendb.disabled=true; WA.busy=true;
      waSend(c.wa_id,text).then(function(){ ta.value=""; })
        .catch(function(){})
        .then(function(){ sendb.disabled=false; WA.busy=false; });
    });
    ta.addEventListener("keydown",function(e){
      if(e.key==="Enter"&&(e.ctrlKey||e.metaKey)) sendb.click();
    });
    row.appendChild(ta); row.appendChild(sendb);
    foot.appendChild(row);
    foot.appendChild(el("div","hint","Ctrl+Enter sends. The window closes 24 "+
      "hours after their last message."));
  }
  box.appendChild(foot);
  return box;
}

function waSend(id,text){
  return waCall("send",{to:id,text:text}).then(function(r){
    if(r&&r.ok){ toast("Sent"); waRefresh(); return r; }
    toast((r&&r.error)||"It was not sent");
    throw {message:(r&&r.error)||"not sent"};
  }).catch(function(e){
    toast((e&&e.message)||"It was not sent");
    throw e;
  });
}

/* ------------------------ a message to anyone ------------------------
   Works whether or not the number is connected: with the connection it goes
   through the function, without it the button hands the text to WhatsApp on
   this device. The second is how the school can use this screen today. */
function waComposeForm(phone){
  var b=el("div");
  var to=input("tel",phone||"",{placeholder:"+507 …"});
  var ta=el("textarea"); ta.rows=5; ta.style.width="100%";
  b.appendChild(field("To",to,"Any number, with its country code."));
  b.appendChild(field("Message",ta));
  var note=el("div","hint","");
  b.appendChild(note);
  function refreshNote(){
    var id=waNum(to.value);
    var c=null;
    WA.contacts.forEach(function(x){ if(x.wa_id===id) c=x; });
    note.textContent = !id ? "" :
      (c&&c.opted_out) ? "This number asked us to stop writing." :
      waWindowOpen(c) ? "Inside the 24-hour window — this will send from the school's number."
      : "Outside the 24-hour window — WhatsApp will refuse a free-form message. "+
        "Use Open in WhatsApp and send it by hand.";
  }
  to.addEventListener("input",refreshNote); refreshNote();

  openModal("New message",b,[
    {label:"Close",on:closeModal},
    {label:"Open in WhatsApp",on:function(){
      var id=waNum(to.value);
      if(!id){ toast("A number first."); return; }
      var a=el("a"); a.href=waLink(id,ta.value); a.target="_blank";
      a.rel="noopener"; document.body.appendChild(a); a.click(); a.remove();
      closeModal();
    }},
    {label:"Send",cls:"primary",on:function(){
      var id=waNum(to.value), text=ta.value.trim();
      if(!id||!text){ toast("A number and something to say."); return; }
      waSend(id,text).then(function(){ closeModal(); }).catch(function(){});
    }}
  ]);
}

/* ------------------------------ automations ------------------------------ */
function waAutomations(host){
  var cfg=waCfg();

  /* ---- the reminder ---- */
  var p1=el("div","panel"); p1.style.padding="14px";
  p1.appendChild(el("h3",null,"Reminder before a session"));
  p1.appendChild(el("p","muted",
    "Every person seated in a session, so many hours before it starts. One "+
    "message per person per session, ever — a reminder cannot go twice."));
  var r=cfg.reminders;
  var rOn=input("checkbox"); rOn.checked=!!r.on; rOn.style.width="auto";
  var rHrs=input("number",r.hoursBefore,{min:"1",max:"96"});
  var rTpl=input("text",r.template,{placeholder:"session_reminder"});
  var rLang=input("text",r.lang,{placeholder:"en"});
  var rQF=input("number",r.quietFrom,{min:"0",max:"23"});
  var rQT=input("number",r.quietTo,{min:"0",max:"23"});
  var g1=el("div","grid2");
  g1.appendChild(field("On",rOn));
  g1.appendChild(field("Hours before",rHrs));
  g1.appendChild(field("Template name",rTpl,
    "Approved in Meta, with three variables: name, what, when."));
  g1.appendChild(field("Template language",rLang));
  g1.appendChild(field("Quiet from",rQF,"Nothing goes out between these hours."));
  g1.appendChild(field("Quiet until",rQT));
  p1.appendChild(g1);
  var s1=el("button","btn primary","Save reminders");
  s1.addEventListener("click",function(){
    var next=waCfg();
    next.reminders={on:rOn.checked,hoursBefore:Number(rHrs.value)||18,
      template:rTpl.value.trim(),lang:rLang.value.trim()||"en",
      quietFrom:Number(rQF.value),quietTo:Number(rQT.value)};
    waSaveCfg(next,"Reminders saved");
  });
  p1.appendChild(s1);
  host.appendChild(p1);

  /* ---- the morning brief ---- */
  var p2=el("div","panel"); p2.style.padding="14px"; p2.style.marginTop="12px";
  p2.appendChild(el("h3",null,"The morning brief"));
  p2.appendChild(el("p","muted",
    "The day's board — every session with its time, its instructors and how "+
    "many are on it — at a fixed hour, to each person on the list. WhatsApp's "+
    "API cannot post into a group, so this is sent to each of them "+
    "individually; an instructor not working today can simply be left off. "+
    "For the real group there is Send to a group by hand: WhatsApp opens with "+
    "today's board already written, and you pick the group."));
  var b2=cfg.brief;
  var bOn=input("checkbox"); bOn.checked=!!b2.on; bOn.style.width="auto";
  var bAt=input("time",b2.at||"07:00");
  var bTpl=input("text",b2.template,{placeholder:"daily_brief"});
  var bLang=input("text",b2.lang,{placeholder:"en"});
  var g2=el("div","grid2");
  g2.appendChild(field("On",bOn));
  g2.appendChild(field("At",bAt));
  g2.appendChild(field("Template name",bTpl,
    "Two variables: the date, and the day in one line."));
  g2.appendChild(field("Template language",bLang));
  p2.appendChild(g2);

  var days=(b2.days||[]).slice();
  var dw=el("div"); dw.style.cssText="display:flex;gap:6px;flex-wrap:wrap;margin:8px 0";
  ["Sun","Mon","Tue","Wed","Thu","Fri","Sat"].forEach(function(d,i){
    var b=el("button","btn sm",d);
    b.setAttribute("aria-pressed",days.indexOf(i)>=0?"true":"false");
    if(days.indexOf(i)>=0) b.classList.add("primary");
    b.addEventListener("click",function(){
      var at=days.indexOf(i);
      if(at>=0) days.splice(at,1); else days.push(i);
      b.classList.toggle("primary");
      b.setAttribute("aria-pressed",days.indexOf(i)>=0?"true":"false");
    });
    dw.appendChild(b);
  });
  p2.appendChild(field("Days",dw));

  var to=(b2.to||[]).slice();
  var tw=el("div"); tw.style.cssText="display:flex;gap:6px;flex-wrap:wrap;margin:6px 0";
  function paintTo(){
    tw.textContent="";
    if(!to.length) tw.appendChild(el("span","muted","Nobody yet."));
    to.forEach(function(n,i){
      var chip=el("span","chip neutral");
      chip.appendChild(document.createTextNode(waNameFor(n)+" "));
      var x=el("button",null,"×");
      x.style.cssText="appearance:none;border:0;background:none;cursor:pointer;font:inherit";
      x.addEventListener("click",function(){ to.splice(i,1); paintTo(); });
      chip.appendChild(x);
      tw.appendChild(chip);
    });
  }
  paintTo();
  var add=el("div"); add.style.cssText="display:flex;gap:6px;flex-wrap:wrap";
  var crew=select([{v:"",l:"Add from crew…"}].concat(
    DB.staff.filter(function(s){return s.phone;}).map(function(s){
      return {v:waNum(s.phone),l:s.name};})),"");
  crew.addEventListener("change",function(){
    if(crew.value && to.indexOf(crew.value)<0){ to.push(crew.value); paintTo(); }
    crew.value="";
  });
  var manual=input("tel","",{placeholder:"or a number"});
  var addb=el("button","btn sm","Add");
  addb.addEventListener("click",function(){
    var n=waNum(manual.value);
    if(n && to.indexOf(n)<0){ to.push(n); paintTo(); manual.value=""; }
  });
  add.appendChild(crew); add.appendChild(manual); add.appendChild(addb);
  p2.appendChild(field("To",tw)); p2.appendChild(add);

  var prev=el("button","btn sm","Preview today's brief");
  prev.style.marginTop="10px";
  prev.addEventListener("click",function(){
    var pb=el("div");
    var pre=el("pre",null,waBriefText(todayISO()));
    pre.style.cssText="white-space:pre-wrap;font:inherit;background:var(--line);"+
      "padding:10px;border-radius:8px";
    pb.appendChild(pre);
    openModal("The brief, as it would go out",pb,[{label:"Close",on:closeModal}]);
  });
  /* The one thing the API cannot do, done by hand in one tap: WhatsApp with
     no number in the link opens its own chooser with the text already
     written, so the real Shokogi group is one pick away. This is the honest
     answer to "post it in the group" -- a person still presses send, but
     nobody types the day out. */
  var group=el("a","btn sm","Send to a group by hand");
  group.href=waLink("",waBriefText(todayISO()));
  group.target="_blank"; group.rel="noopener";
  group.style.marginLeft="8px";
  var s2=el("button","btn primary","Save the brief");
  s2.style.marginLeft="8px";
  s2.addEventListener("click",function(){
    var next=waCfg();
    next.brief={on:bOn.checked,at:bAt.value||"07:00",days:days.slice(),
      to:to.slice(),template:bTpl.value.trim(),lang:bLang.value.trim()||"en"};
    waSaveCfg(next,"Brief saved");
  });
  var brow=el("div"); brow.style.marginTop="10px";
  brow.appendChild(s2); brow.appendChild(prev); brow.appendChild(group);
  p2.appendChild(brow);
  host.appendChild(p2);

  /* ---- the bot ---- */
  var p3=el("div","panel"); p3.style.padding="14px"; p3.style.marginTop="12px";
  p3.appendChild(el("h3",null,"The bot"));
  p3.appendChild(el("p","muted",
    "Answers what it recognises and hands over what it does not. Anyone who "+
    "writes HUMAN stops it for twelve hours and shows up in Chats as waiting "+
    "on a person; anyone who writes STOP is never written to again."));
  var bot=cfg.bot;
  var xOn=input("checkbox"); xOn.checked=!!bot.on; xOn.style.width="auto";
  var xGreet=el("textarea"); xGreet.rows=2; xGreet.value=bot.greeting||"";
  var xHours=el("textarea"); xHours.rows=2; xHours.value=bot.hours||"";
  var xHand=el("textarea"); xHand.rows=2; xHand.value=bot.handover||"";
  var xUrl=input("url",cfg.bookingUrl||"",{placeholder:"https://…/book.html"});
  p3.appendChild(field("On",xOn));
  p3.appendChild(field("Booking page",xUrl,
    "Sent to anyone asking to book. The public page, not the manager."));
  p3.appendChild(field("Anything else it hears",xGreet,
    "The answer when nothing matches. Say what it can be asked."));
  p3.appendChild(field("Opening hours",xHours));
  p3.appendChild(field("When it hands over",xHand));

  var rules=(bot.rules||[]).map(function(x){
    return {match:(x.match||[]).slice(),reply:x.reply||""};});
  var rw=el("div"); rw.style.marginTop="8px";
  function paintRules(){
    rw.textContent="";
    if(!rules.length) rw.appendChild(el("p","muted",
      "No rules. Every message gets the fallback above."));
    rules.forEach(function(rule,i){
      var row=el("div");
      row.style.cssText="display:flex;gap:6px;align-items:flex-start;margin-bottom:6px";
      var words=input("text",rule.match.join(", "),{placeholder:"price, precio, cost"});
      words.style.flex="0 0 30%";
      words.addEventListener("input",function(){
        rule.match=words.value.split(",").map(function(s){return s.trim();})
          .filter(Boolean);
      });
      var rep=el("textarea"); rep.rows=2; rep.style.flex="1"; rep.value=rule.reply;
      rep.addEventListener("input",function(){ rule.reply=rep.value; });
      var del=el("button","btn sm danger","×");
      del.addEventListener("click",function(){ rules.splice(i,1); paintRules(); });
      row.appendChild(words); row.appendChild(rep); row.appendChild(del);
      rw.appendChild(row);
    });
    var addr=el("button","btn sm","Add a rule");
    addr.addEventListener("click",function(){
      rules.push({match:[],reply:""}); paintRules(); });
    rw.appendChild(addr);
  }
  paintRules();
  p3.appendChild(field("Rules — words heard, and the answer",rw));

  var s3=el("button","btn primary","Save the bot");
  s3.style.marginTop="10px";
  s3.addEventListener("click",function(){
    var next=waCfg();
    next.bookingUrl=xUrl.value.trim();
    next.bot={on:xOn.checked,greeting:xGreet.value.trim(),
      hours:xHours.value.trim(),handover:xHand.value.trim(),
      rules:rules.filter(function(x){return x.match.length&&x.reply;})};
    waSaveCfg(next,"Bot saved");
  });
  p3.appendChild(s3);
  host.appendChild(p3);

  /* ---- what is waiting to go ---- */
  var p4=el("div","panel"); p4.style.padding="14px"; p4.style.marginTop="12px";
  p4.appendChild(el("h3",null,"What is queued"));
  p4.appendChild(el("p","muted",
    "Nothing is sent the moment it is worked out: it is written down here and "+
    "sent when it is due. The clock that does the sending is pg_cron — see "+
    "supabase/whatsapp.sql. Run now does one turn of it by hand."));
  var runb=el("button","btn","Run now");
  runb.addEventListener("click",function(){
    runb.disabled=true;
    waCall("tick",{}).then(function(r){
      toast("Queued "+(((r&&r.queued)||{}).reminders||0)+" reminders, sent "+
            ((r&&r.sent)||0));
      waRefresh();
    }).catch(function(e){ toast((e&&e.message)||"The tick was refused"); })
      .then(function(){ runb.disabled=false; });
  });
  p4.appendChild(runb);
  host.appendChild(p4);
}

function waNameFor(num){
  var id=waNum(num), out=null;
  DB.staff.forEach(function(s){ if(s.phone&&waNum(s.phone)===id) out=s.name; });
  if(!out) DB.clients.forEach(function(c){ if(c.phone&&waNum(c.phone)===id) out=c.name; });
  return out||waPretty(id);
}

/* The brief, worked out in the page exactly as the function works it out, so
   Preview shows what will actually be sent rather than something like it. */
function waBriefText(dateStr){
  var day=DB.sessions.filter(function(s){
    return s&&s.date===dateStr&&!s.cancelled;
  }).sort(function(a,b){
    return String(a.time||"")<String(b.time||"")?-1:1;});
  if(!day.length) return dateStr+" — nothing on the board today.";
  var pax=day.reduce(function(a,s){return a+(s.participants||[]).length;},0);
  var lines=day.map(function(s){
    var crew=(s.staffIds||[]).map(function(id){return staffName(id);})
      .filter(function(n){return n&&n!=="Unassigned";}).join(", ");
    return (s.time||"--:--")+" "+(s.title||s.category||"Session")+" · "+
           (s.participants||[]).length+"/"+(s.capacity||0)+
           (crew?(" · "+crew):" · unassigned");
  });
  return dateStr+" — "+day.length+" session"+(day.length===1?"":"s")+", "+
         pax+" on the water\n"+lines.join("\n");
}

/* ------------------------------ the setup ------------------------------ */
function waSetup(host){
  var h=WA.health||{};
  var p=el("div","panel"); p.style.padding="14px";
  p.appendChild(el("h3",null,"What is connected"));
  if(h.error){
    p.appendChild(el("p","muted",
      "The function did not answer: "+h.error+". Until it is deployed, this "+
      "screen can still open WhatsApp with a message ready to send by hand."));
  }
  var items=[
    ["The function answers",!h.error,
     "supabase functions deploy whatsapp --no-verify-jwt"],
    ["Access token",!!h.token,"WA_TOKEN — a permanent System User token from Meta"],
    ["Phone number",!!h.phoneId,"WA_PHONE_ID — the number's id, not the number"],
    ["Webhook verify token",!!h.verifyToken,"WA_VERIFY_TOKEN — the same string you type into Meta"],
    ["Webhook signature",!!h.appSecret,"WA_APP_SECRET — so nobody else can post to the webhook"],
    ["The clock",!!h.tickSecret,"WA_TICK_SECRET — what pg_cron sends with the tick"]
  ];
  var t=el("table"); var tb=el("tbody");
  items.forEach(function(row){
    var tr=el("tr");
    var c1=el("td");
    c1.appendChild(el("span","chip "+(row[1]?"ok":"warnc"),row[1]?"set":"missing"));
    tr.appendChild(c1);
    tr.appendChild(el("td","strong",row[0]));
    tr.appendChild(el("td","muted",row[2]));
    tb.appendChild(tr);
  });
  t.appendChild(tb);
  var w=el("div","panel tbl-wrap"); w.style.marginTop="10px";
  w.appendChild(t); p.appendChild(w);

  if(h.number){
    p.appendChild(el("p","muted","Connected as "+
      (h.number.display_phone_number||"")+" "+
      (h.number.verified_name?("("+h.number.verified_name+")"):"")+
      (h.number.quality_rating?(" · quality "+h.number.quality_rating):"")));
  }
  if(h.numberError) p.appendChild(el("p","muted","Meta says: "+h.numberError));

  p.appendChild(el("h3",null,"The order it has to be done in"));
  var ol=el("ol");
  [ "Run supabase/schema.sql, then supabase/whatsapp.sql, in the Supabase SQL editor.",
    "In Meta Business, add WhatsApp to an app and connect a number. A number "+
    "connected to the API leaves the WhatsApp Business phone app — it cannot "+
    "be in both, so use a second number unless the school is ready to give "+
    "the first one up.",
    "Set WA_TOKEN, WA_PHONE_ID, WA_VERIFY_TOKEN, WA_APP_SECRET and "+
    "WA_TICK_SECRET as secrets on the function, then deploy it.",
    "Point Meta's webhook at .../functions/v1/whatsapp/webhook with the same "+
    "verify token, and subscribe it to messages.",
    "Submit the two templates for approval, then turn the automations on.",
    "Schedule the tick with pg_cron — the SQL is at the bottom of "+
    "supabase/whatsapp.sql."
  ].forEach(function(s){ ol.appendChild(el("li",null,s)); });
  p.appendChild(ol);
  p.appendChild(el("p","muted",
    "The whole of it, with the exact values and the two template texts, is in "+
    "supabase/WHATSAPP.md in the repository."));
  host.appendChild(p);
}
