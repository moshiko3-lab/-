/* ============================ the shared book ============================
   Until now every browser kept its own copy and that was the end of it. A
   school runs on one book: the counter takes a booking, the instructor opens
   the board on their phone, and both see the same day.

   The shape of it:

   * Supabase is Postgres with an HTTP front (PostgREST) and a login service.
     No SDK is loaded -- these are plain fetch calls, so the page keeps working
     with no CDN, no build step and nothing to go stale.
   * Each collection is a table of rows: id, school, updated_at, deleted, and
     the record itself as jsonb. Rows, not one big document, so two people
     editing different bookings at the same time do not overwrite each other.
   * Local first. Every write lands in this browser immediately and goes into
     an outbox; the outbox drains when there is a network. The till does not
     stop because the wifi in Venao dropped, which it does.
   * Newest write wins per row, by the server's clock.

   The key below is Supabase's publishable key. It is meant to sit in a public
   page -- what protects the data is the login and the row policies, not the
   key. The service key never appears here and must never be committed.
*/
var CLOUD = {
  url: "https://bxjwqvoscbzhetuwhyvk.supabase.co",
  key: "sb_publishable_fqeQ4Nm91QQJRlLYPr8HfA_rsrld1QC",
  school: "shokogi"
};

/* the collections that travel, and the key each row is identified by */
var CLOUD_TABLES = [
  {t:"clients",   k:"clients"},
  {t:"staff",     k:"staff"},
  {t:"products",  k:"products"},
  {t:"gear",      k:"gear"},
  {t:"bookings",  k:"bookings"},
  {t:"sessions",  k:"sessions"},
  {t:"trips",     k:"trips"},
  {t:"docs",      k:"docs"},
  {t:"invoices",  k:"invoices"},
  {t:"tickets",   k:"tickets"},
  {t:"cash",      k:"cash"},
  {t:"pos",       k:"pos"},
  {t:"tides",     k:"tides"},
  {t:"timeoff",   k:"timeOff"},
  {t:"gearblocks",k:"gearBlocks"}
];
function cloudTableFor(key){
  for(var i=0;i<CLOUD_TABLES.length;i++)
    if(CLOUD_TABLES[i].k===key) return CLOUD_TABLES[i].t;
  return null;
}

var CLOUD_SESSION_KEY="shokogi.cloud.session";
var CLOUD_OUTBOX_KEY="shokogi.cloud.outbox";
var CLOUD_SINCE_KEY="shokogi.cloud.since";

/* set the moment the server refuses the token, wherever that happens */
var CLOUD_AUTH_BAD=false;

function cloudConfigured(){ return !!(CLOUD.url && CLOUD.key); }
function cloudRead(k,fallback){
  try{ var v=localStorage.getItem(k); return v?JSON.parse(v):fallback; }
  catch(e){ return fallback; }
}
function cloudWrite(k,v){
  try{ localStorage.setItem(k,JSON.stringify(v)); }catch(e){}
}
function cloudSession(){ return cloudRead(CLOUD_SESSION_KEY,null); }
function cloudSignedIn(){ var s=cloudSession(); return !!(s&&s.access_token); }
function cloudWho(){ var s=cloudSession(); return (s&&s.email)||""; }

/* ---------------------------- the outbox ----------------------------
   {collection: {id: true}} -- what this browser has changed and not yet
   handed over. It survives a reload, a crash and a night with no signal. */
function outbox(){ return cloudRead(CLOUD_OUTBOX_KEY,{}) || {}; }
function outboxCount(){
  var o=outbox(),n=0;
  for(var k in o) n+=Object.keys(o[k]||{}).length;
  return n;
}
function cloudDirty(collection,id){
  if(!cloudTableFor(collection) || !id) return;
  var o=outbox();
  (o[collection]=o[collection]||{})[id]=1;
  cloudWrite(CLOUD_OUTBOX_KEY,o);
}
/* A whole collection at once, for the paths that rewrite a list rather than
   touch one record. */
function cloudDirtyAll(collection,list){
  (list||[]).forEach(function(r){ if(r&&r.id) cloudDirty(collection,r.id); });
}
function outboxClear(collection,ids){
  var o=outbox();
  if(!o[collection]) return;
  ids.forEach(function(id){ delete o[collection][id]; });
  if(!Object.keys(o[collection]).length) delete o[collection];
  cloudWrite(CLOUD_OUTBOX_KEY,o);
}

/* ---------------------------- the wire ---------------------------- */
function cloudHeaders(extra){
  var s=cloudSession();
  var h={"apikey":CLOUD.key,"Content-Type":"application/json"};
  h["Authorization"]="Bearer "+((s&&s.access_token)||CLOUD.key);
  for(var k in (extra||{})) h[k]=extra[k];
  return h;
}
function cloudFetch(path,opts){
  opts=opts||{};
  return fetch(CLOUD.url+path,{
    method:opts.method||"GET",
    headers:cloudHeaders(opts.headers),
    body:opts.body?JSON.stringify(opts.body):undefined
  }).then(function(r){
    if(r.status===401 || r.status===403){
      /* the token expired or the policies refused: say so rather than
         retrying forever against a wall. The flag is how a sync that
         collects errors per table rather than throwing still finds out the
         session itself is the problem. */
      CLOUD_AUTH_BAD=true;
      return r.text().then(function(t){
        throw {status:r.status,message:t||"Not allowed"};
      });
    }
    if(!r.ok) return r.text().then(function(t){
      throw {status:r.status,message:t||("HTTP "+r.status)}; });
    return r.status===204?null:r.json();
  });
}

function cloudSignIn(email,password){
  return fetch(CLOUD.url+"/auth/v1/token?grant_type=password",{
    method:"POST",
    headers:{"apikey":CLOUD.key,"Content-Type":"application/json"},
    body:JSON.stringify({email:email,password:password})
  }).then(function(r){
    return r.json().then(function(j){
      if(!r.ok) throw {status:r.status,
        message:(j&&(j.error_description||j.msg||j.message))||"Sign-in failed"};
      cloudWrite(CLOUD_SESSION_KEY,{
        access_token:j.access_token,refresh_token:j.refresh_token,
        email:(j.user&&j.user.email)||email,
        expires_at:Date.now()+((j.expires_in||3600)*1000)});
      return j;
    });
  });
}
function cloudRefresh(){
  var s=cloudSession();
  if(!s||!s.refresh_token) return Promise.reject({message:"Not signed in"});
  return fetch(CLOUD.url+"/auth/v1/token?grant_type=refresh_token",{
    method:"POST",
    headers:{"apikey":CLOUD.key,"Content-Type":"application/json"},
    body:JSON.stringify({refresh_token:s.refresh_token})
  }).then(function(r){
    return r.json().then(function(j){
      if(!r.ok) throw {status:r.status,message:"Session expired"};
      cloudWrite(CLOUD_SESSION_KEY,{
        access_token:j.access_token,refresh_token:j.refresh_token,
        email:s.email,expires_at:Date.now()+((j.expires_in||3600)*1000)});
      return j;
    });
  });
}
function cloudSignOut(){
  try{ localStorage.removeItem(CLOUD_SESSION_KEY); }catch(e){}
}

/* ---------------------------- push ----------------------------
   Everything this browser changed, upserted a collection at a time. A row
   the app deleted is sent as deleted rather than vanishing, or the other
   browsers would hand it straight back. */
function cloudPush(db){
  var o=outbox(), jobs=[], sent=0, errs=[];
  Object.keys(o).forEach(function(coll){
    var table=cloudTableFor(coll);
    if(!table) return;
    var ids=Object.keys(o[coll]||{});
    if(!ids.length) return;
    var have={};
    (db[coll]||[]).forEach(function(r){ if(r&&r.id) have[r.id]=r; });
    var rows=ids.map(function(id){
      var rec=have[id];
      return {id:id,school:CLOUD.school,deleted:!rec,
              data:rec||{id:id},updated_at:new Date().toISOString()};
    });
    /* one table refusing is one table's problem: the rest of the day still
       goes over, and what failed stays in the outbox for the next turn */
    jobs.push(cloudFetch("/rest/v1/"+table+"?on_conflict=id",{
      method:"POST",
      headers:{"Prefer":"resolution=merge-duplicates,return=minimal"},
      body:rows
    }).then(function(){ outboxClear(coll,ids); sent+=rows.length; })
      .catch(function(e){ errs.push(table+": "+((e&&e.message)||"failed")); }));
  });
  if(!jobs.length) return Promise.resolve({sent:0,errors:[]});
  return Promise.all(jobs).then(function(){ return {sent:sent,errors:errs}; });
}

/* ---------------------------- pull ----------------------------
   Whatever changed since we last looked, merged row by row. A row we have a
   pending change for is left alone -- ours has not been sent yet, and the
   push that follows settles it. */
/* `guard` is the outbox as it stood before the push. A row that was ours a
   moment ago -- or that somebody typed while the sync was in the air -- is
   left alone: the copy in this browser is the newer one, and the next push
   settles it. Without this, an edit made during a sync is lost to whatever
   the pull happens to carry. */
var CLOUD_EPOCH="1970-01-01T00:00:00Z";
var CLOUD_PAGE=1000;

/* A cursor per table, not one shared between them.

   Shared, it lost rows: a page is a thousand rows at most, so a busy table
   hands back its first thousand and stops at nine in the morning while a
   quiet table hands back its three and reaches this afternoon. One cursor
   takes the later of the two and the busy table's whole day is stepped over,
   for good. Each table now remembers its own place. */
function cloudSince(){
  var v=cloudRead(CLOUD_SINCE_KEY,null);
  if(typeof v==="string"){          /* the single cursor this replaces */
    var o={};
    CLOUD_TABLES.forEach(function(s){ o[s.t]=v; });
    return o;
  }
  return v||{};
}
/* Come back a couple of seconds before where we stopped. Two rows written in
   the same instant can become visible to a reader in either order, and a
   record handed over twice costs nothing -- the merge is by id -- while one
   missed is a booking nobody sees. */
function cloudBack(ts,floor){
  var t=Date.parse(ts);
  if(isNaN(t)) return ts;
  var back=new Date(t-2000).toISOString();
  return back<floor?floor:back;
}

function cloudPull(db,guard){
  var since=cloudSince();
  var now=outbox(), mine={};
  [guard||{},now].forEach(function(src){
    Object.keys(src).forEach(function(k){
      mine[k]=mine[k]||{};
      Object.keys(src[k]||{}).forEach(function(id){ mine[k][id]=1; });
    });
  });
  var next={}, touched=0, errs=[], more=false;
  var jobs=CLOUD_TABLES.map(function(spec){
    var from=since[spec.t]||CLOUD_EPOCH;
    next[spec.t]=from;
    var q="/rest/v1/"+spec.t+"?school=eq."+encodeURIComponent(CLOUD.school)+
          "&updated_at=gt."+encodeURIComponent(from)+
          "&order=updated_at.asc&limit="+CLOUD_PAGE;
    return cloudFetch(q).then(function(rows){
      rows=rows||[];
      var top=from;
      rows.forEach(function(row){
        if(row.updated_at>top) top=row.updated_at;
        if(mine[spec.k] && mine[spec.k][row.id]) return;   /* ours is newer */
        var list=db[spec.k]=db[spec.k]||[];
        var at=-1;
        for(var i=0;i<list.length;i++) if(list[i] && list[i].id===row.id){at=i;break;}
        if(row.deleted){ if(at>=0){ list.splice(at,1); touched++; } return; }
        if(at>=0) list[at]=row.data; else list.push(row.data);
        touched++;
      });
      /* this table's own place, moved only because this table answered */
      if(rows.length) next[spec.t]=cloudBack(top,from);
      /* a full page means there is more of it behind: say so, and the sync
         comes straight back rather than leaving it until the next poll */
      if(rows.length>=CLOUD_PAGE) more=true;
    }).catch(function(e){ errs.push(spec.t+": "+((e&&e.message)||"failed")); });
  });
  return Promise.all(jobs).then(function(){
    cloudWrite(CLOUD_SINCE_KEY,next);
    return {got:touched,errors:errs,more:more};
  });
}

/* ---------------------------- live ----------------------------
   Asking every twenty seconds is not the same as being told. Postgres already
   knows the moment a row changes, and Supabase will hold a socket open and say
   so; the page answers by pulling, which is the same code path the poll uses
   and therefore obeys the same rules about whose copy is newer.

   No SDK for this either. It is the Phoenix channel protocol underneath: join
   a topic, name the tables, keep a heartbeat going. Four message shapes.

   It is an improvement, never a dependency. If the socket cannot open -- an
   old browser, a captive-portal wifi that eats websockets, a project where
   replication was never switched on -- nothing breaks: the poll behind it
   carries the day as before, just less promptly. */
var CLOUD_LIVE={ws:null,ref:0,joined:false,beat:null,retry:0,timer:null,
                token:null,onChange:null,onState:null};
function cloudLiveState(){ if(CLOUD_LIVE.onState) CLOUD_LIVE.onState(); }

function cloudLiveSend(msg){
  var w=CLOUD_LIVE.ws;
  if(!w || w.readyState!==1) return;
  msg.ref=String(++CLOUD_LIVE.ref);
  try{ w.send(JSON.stringify(msg)); }catch(e){}
}

function cloudLiveStart(onChange){
  if(onChange) CLOUD_LIVE.onChange=onChange;
  if(!cloudConfigured() || !cloudSignedIn()) return;
  if(typeof WebSocket==="undefined") return;
  if(CLOUD_LIVE.ws) return;
  var w;
  try{
    w=new WebSocket(CLOUD.url.replace(/^http/,"ws")+
      "/realtime/v1/websocket?apikey="+encodeURIComponent(CLOUD.key)+"&vsn=1.0.0");
  }catch(e){ return; }
  CLOUD_LIVE.ws=w;
  w.onopen=function(){
    CLOUD_LIVE.retry=0;
    var s=cloudSession();
    CLOUD_LIVE.token=(s&&s.access_token)||null;
    /* every table, this school only: an instructor's phone is told about this
       school's day and nothing else, and the row policies say the same */
    cloudLiveSend({topic:"realtime:"+CLOUD.school,event:"phx_join",payload:{
      config:{
        broadcast:{self:false},
        postgres_changes:CLOUD_TABLES.map(function(spec){
          return {event:"*",schema:"public",table:spec.t,
                  filter:"school=eq."+CLOUD.school};
        })
      },
      access_token:CLOUD_LIVE.token
    }});
    CLOUD_LIVE.beat=setInterval(function(){
      cloudLiveSend({topic:"phoenix",event:"heartbeat",payload:{}});
      /* a refreshed token has to reach the socket too, or the server drops
         the channel an hour in and the day quietly stops being live */
      var s2=cloudSession(), tok=(s2&&s2.access_token)||null;
      if(tok && tok!==CLOUD_LIVE.token){
        CLOUD_LIVE.token=tok;
        cloudLiveSend({topic:"realtime:"+CLOUD.school,event:"access_token",
                       payload:{access_token:tok}});
      }
    },25000);
  };
  w.onmessage=function(ev){
    var m; try{ m=JSON.parse(ev.data); }catch(e){ return; }
    if(m.event==="phx_reply" && m.payload && m.payload.status==="ok" &&
       !CLOUD_LIVE.joined){
      CLOUD_LIVE.joined=true;
      cloudLiveState();      /* the corner can say so now */
    }
    if(m.event==="postgres_changes" && CLOUD_LIVE.onChange) CLOUD_LIVE.onChange();
  };
  w.onclose=function(){ cloudLiveStop(true); };
  w.onerror=function(){ /* onclose follows and does the work */ };
}

function cloudLiveStop(reconnect){
  if(CLOUD_LIVE.beat){ clearInterval(CLOUD_LIVE.beat); CLOUD_LIVE.beat=null; }
  var w=CLOUD_LIVE.ws, was=CLOUD_LIVE.joined;
  CLOUD_LIVE.ws=null; CLOUD_LIVE.joined=false;
  if(w){ try{ w.onclose=null; w.close(); }catch(e){} }
  clearTimeout(CLOUD_LIVE.timer);
  if(was) cloudLiveState();    /* and say so when it drops, too */
  if(reconnect && cloudSignedIn()){
    /* back off: a server having a bad minute should not be met by fifteen
       tills reconnecting in a loop */
    var wait=Math.min(30000,1000*Math.pow(2,CLOUD_LIVE.retry++));
    CLOUD_LIVE.timer=setTimeout(function(){ cloudLiveStart(); },wait);
  }
}
function cloudLiveUp(){ return !!(CLOUD_LIVE.ws && CLOUD_LIVE.joined); }

/* ------------------------ the first hand-over ------------------------
   A school starts with its whole book inside one browser. Getting it up there
   was a button in a menu -- which is a thing somebody has to know about, and
   if nobody presses it a second device signs in, finds nothing, and the two
   sit there disagreeing about what the school has.

   So each table is checked once per device: if the server has never held a
   single row of it and this browser has rows, then this browser is holding
   the only copy and hands it over. A table the server does have is left
   alone. Taking what is there stays the normal path, and nothing here
   overwrites anything -- the check is "has this ever been uploaded at all",
   not "is mine newer".

   Once a table is accounted for it is never checked again: from then on a
   record written here goes into the outbox by the ordinary route. */
var CLOUD_SEEDED_KEY="shokogi.cloud.seeded";
function cloudSeedCheck(db){
  var seen=cloudRead(CLOUD_SEEDED_KEY,{}) || {};
  var todo=CLOUD_TABLES.filter(function(s){ return !seen[s.t]; });
  if(!todo.length) return Promise.resolve({seeded:[]});
  var seeded=[];
  return Promise.all(todo.map(function(spec){
    return cloudFetch("/rest/v1/"+spec.t+"?school=eq."+
        encodeURIComponent(CLOUD.school)+"&select=id&limit=1")
      .then(function(rows){
        seen[spec.t]=true;
        if((rows||[]).length) return;      /* the server already has this one */
        var list=db[spec.k]||[];
        if(!list.length) return;           /* nothing here to give it */
        list.forEach(function(r){ if(r&&r.id) cloudDirty(spec.k,r.id); });
        seeded.push(spec.t);
      })
      /* unreachable: leave it unmarked and ask again next time round */
      .catch(function(){});
  })).then(function(){
    cloudWrite(CLOUD_SEEDED_KEY,seen);
    return {seeded:seeded};
  });
}

/* One turn of the handle: send what we have, take what they have. */
function cloudSync(db,onDone){
  if(!cloudConfigured() || !cloudSignedIn()){
    if(onDone) onDone(null,{skipped:true});
    return Promise.resolve(null);
  }
  var s=cloudSession(), guard=null;
  /* an hour into a nine-hour day the token is stale; renew a little early
     rather than finding out by being refused */
  var first = (s && s.expires_at && s.expires_at-Date.now()<300000)
    ? cloudRefresh().catch(function(){})   /* the calls below say if it failed */
    : Promise.resolve();
  CLOUD_AUTH_BAD=false;
  return first
    /* before the first push on this device: is any of this book up there at
       all? Whatever is not gets marked, and goes over in the push below. */
    .then(function(){ return cloudSeedCheck(db); })
    .then(function(){
      guard=outbox();
      return cloudPush(db);
    })
    .then(function(push){
      return cloudPull(db,guard).then(function(pull){
        var errs=(push.errors||[]).concat(pull.errors||[]);
        var info={sent:push.sent,got:pull.got,errors:errs,more:pull.more};
        /* The token was refused somewhere in there. One renewal, then either
           it works from here or this device has to be let in again -- rather
           than a corner that says "sync error" all afternoon while the day's
           bookings pile up in a browser nobody thinks to check. */
        if(CLOUD_AUTH_BAD){
          return cloudRefresh().then(function(){
            if(onDone) onDone(null,info);
            return info;
          }).catch(function(){
            cloudSignOut();
            if(onDone) onDone({message:"Signed out — please sign in again",
                               gone:true});
            return null;
          });
        }
        if(onDone) onDone(errs.length?{message:errs[0]}:null,info);
        return info;
      });
    })
    .catch(function(err){
      if(onDone) onDone(err||{message:"Sync failed"});
      return null;
    });
}
