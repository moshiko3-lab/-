/* SHOKOGI home — reveal on scroll + a "clean sand" water sheen on each warm section. Waves are pure CSS. */
(function(){
  var root=document.querySelector('.sk2'); if(!root) return;
  var reduce=matchMedia('(prefers-reduced-motion: reduce)').matches;
  var hasIO='IntersectionObserver' in window;

  /* reveal */
  var items=[].slice.call(root.querySelectorAll('[data-r],[data-rs]'));
  function show(el){
    el.classList.add('is-in');
    if(el.hasAttribute('data-rs')){ var k=el.children;
      for(var i=0;i<k.length;i++){ k[i].style.transitionDelay=(i*85)+'ms'; } }
  }
  if(reduce || !hasIO){ items.forEach(show); return; }
  var io=new IntersectionObserver(function(es){
    es.forEach(function(e){ if(e.isIntersecting){ show(e.target); io.unobserve(e.target); } });
  },{threshold:.12,rootMargin:'0px 0px -8% 0px'});
  items.forEach(function(e){ io.observe(e); });

  /* clean-sand wash: sweep a soft sheen across each warm section once as it enters */
  var sands=[].slice.call(root.querySelectorAll('.sec.tint'));
  if(sands.length){
    var io2=new IntersectionObserver(function(es){
      es.forEach(function(e){ if(e.isIntersecting){ e.target.classList.add('is-wash'); io2.unobserve(e.target); } });
    },{threshold:.2});
    sands.forEach(function(e){ io2.observe(e); });
  }
})();
