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
         retrying forever against a wall */
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
function cloudPull(db,guard){
  var since=cloudRead(CLOUD_SINCE_KEY,"1970-01-01T00:00:00Z");
  var now=outbox(), mine={};
  [guard||{},now].forEach(function(src){
    Object.keys(src).forEach(function(k){
      mine[k]=mine[k]||{};
      Object.keys(src[k]||{}).forEach(function(id){ mine[k][id]=1; });
    });
  });
  var newest=since, touched=0, errs=[];
  var jobs=CLOUD_TABLES.map(function(spec){
    var q="/rest/v1/"+spec.t+"?school=eq."+encodeURIComponent(CLOUD.school)+
          "&updated_at=gt."+encodeURIComponent(since)+
          "&order=updated_at.asc&limit=1000";
    return cloudFetch(q).then(function(rows){
      (rows||[]).forEach(function(row){
        if(row.updated_at>newest) newest=row.updated_at;
        if(mine[spec.k] && mine[spec.k][row.id]) return;   /* ours is newer */
        var list=db[spec.k]=db[spec.k]||[];
        var at=-1;
        for(var i=0;i<list.length;i++) if(list[i] && list[i].id===row.id){at=i;break;}
        if(row.deleted){ if(at>=0){ list.splice(at,1); touched++; } return; }
        if(at>=0) list[at]=row.data; else list.push(row.data);
        touched++;
      });
    }).catch(function(e){ errs.push(spec.t+": "+((e&&e.message)||"failed")); });
  });
  return Promise.all(jobs).then(function(){
    /* the cursor only moves when every table answered, or a table that was
       briefly unreachable would be skipped for good */
    if(!errs.length) cloudWrite(CLOUD_SINCE_KEY,newest);
    return {got:touched,errors:errs};
  });
}

/* One turn of the handle: send what we have, take what they have. */
function cloudSync(db,onDone){
  if(!cloudConfigured() || !cloudSignedIn()){
    if(onDone) onDone(null,{skipped:true});
    return Promise.resolve(null);
  }
  var s=cloudSession(), guard=null;
  var first = (s && s.expires_at && s.expires_at-Date.now()<120000)
    ? cloudRefresh() : Promise.resolve();
  return first
    .then(function(){
      guard=outbox();
      return cloudPush(db);
    })
    .then(function(push){
      return cloudPull(db,guard).then(function(pull){
        var errs=(push.errors||[]).concat(pull.errors||[]);
        var info={sent:push.sent,got:pull.got,errors:errs};
        if(onDone) onDone(errs.length?{message:errs[0]}:null,info);
        return info;
      });
    })
    .catch(function(err){
      if(onDone) onDone(err||{message:"Sync failed"});
      return null;
    });
}
