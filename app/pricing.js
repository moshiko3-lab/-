/* Shared by the manager and the public booking site. Both must price a
   product identically -- a customer quoted one number and billed another is
   the worst kind of bug -- so this lives in one file and is inlined into both
   pages at build time rather than copied.
*/
/* ============================ pricing ============================
   A product does not have "a price". A lesson is priced per head by how many
   share it; a rental by how long the board is out. all_prices in Bloowatch is
   that matrix, and this is the same thing: tiers, and the rule for picking one. */
function tiersOf(p){ return (p && p.prices && p.prices.length) ? p.prices : null; }

/* Their price_unit says what a tier's number means: by_closing_time is the
   whole hire until closing, from_pickup counts from the moment it goes out,
   hourly is a rate. Six of the imported rentals carry one from_pickup tier at
   the top of a by_closing_time ladder -- 60h at $10 where 30h is $285 -- so
   these are not one ladder and must not be compared as if they were. The
   ladder is whichever unit most of the tiers use; the odd ones out are left
   for the school to price deliberately rather than silently undercutting. */
function tierUnit(x){ return x && x.unit ? x.unit : ""; }
/* The unit only tells two ladders apart where the tiers are *durations*. On a
   ladder of head counts it is noise: three of their lessons carry "hourly" on
   the one-person tier and nothing on the pair and the group, and splitting
   those apart drops the full price -- a single surfer was quoted the pair's
   $120 for the 3X course instead of $180. So the split applies to hour tiers
   only. */
function durationLadder(p){
  var t=tiersOf(p);
  return !!(t && t.some(function(x){return x.hours;}));
}
function ladderUnit(p){
  var t=tiersOf(p); if(!t || !durationLadder(p)) return "";
  var n={},best="",bn=-1;
  t.forEach(function(x){
    var u=tierUnit(x);
    n[u]=(n[u]||0)+1;
    if(n[u]>bn){ bn=n[u]; best=u; }
  });
  return best;
}
function ladderTiers(p){
  var t=tiersOf(p); if(!t) return [];
  if(!durationLadder(p)) return t;
  var u=ladderUnit(p);
  return t.filter(function(x){return tierUnit(x)===u;});
}
function oddTiers(p){
  var t=tiersOf(p); if(!t || !durationLadder(p)) return [];
  var u=ladderUnit(p);
  return t.filter(function(x){return tierUnit(x)!==u;});
}
function unitLabel(u){
  return u==="by_closing_time" ? "until closing"
       : u==="from_pickup" ? "from pickup"
       : u==="hourly" ? "per hour"
       : u || "";
}

function hasPaxTiers(p){
  var t=ladderTiers(p); if(!t.length) return false;
  return t.some(function(x){return (x.minPax||1)>1;});
}
function hasHourTiers(p){
  var t=ladderTiers(p); if(!t.length) return false;
  return t.some(function(x){return x.hours;});
}
function priceFor(p,pax,hours){
  /* the applicable tier is the most generous one the request still clears */
  var t=ladderTiers(p);
  if(!t.length) return Number(p&&p.price)||0;
  var cands=t;
  if(hasHourTiers(p)){
    var h=Number(hours)||1;
    var fit=t.filter(function(x){return x.hours && x.hours<=h;});
    /* below the smallest tier, charge the smallest tier */
    cands=fit.length?fit:t.filter(function(x){return x.hours;});
    cands=[cands.reduce(function(a,b){
      if(fit.length) return (a.hours>b.hours)?a:b;
      return (a.hours<b.hours)?a:b;
    })];
  }
  if(hasPaxTiers(p)){
    var n=Math.max(1,Number(pax)||1);
    var ok=cands.filter(function(x){return (x.minPax||1)<=n;});
    if(ok.length) cands=[ok.reduce(function(a,b){
      return ((a.minPax||1)>(b.minPax||1))?a:b;})];
  }
  var chosen=cands[0]||t[0];
  return Number(chosen.price)||0;
}
function priceSummary(p){
  var t=ladderTiers(p);
  if(t.length<2) return "";
  var extra=oddTiers(p).length;
  var tail=extra?(" · "+extra+" tier"+(extra===1?"":"s")+" priced another way"):"";
  if(hasHourTiers(p)){
    var hs=t.filter(function(x){return x.hours;}).sort(function(a,b){return a.hours-b.hours;});
    return hs.length+" duration tiers · "+hs[0].hours+"h $"+money(hs[0].price,0)+
      " … "+hs[hs.length-1].hours+"h $"+money(hs[hs.length-1].price,0)+tail;
  }
  if(hasPaxTiers(p)){
    var ps=t.slice().sort(function(a,b){return (a.minPax||1)-(b.minPax||1);});
    return ps.map(function(x){return (x.minPax||1)+"p $"+money(x.price,0);}).join(" · ")+tail;
  }
  return "";
}
