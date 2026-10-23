/* SHOKOGI home — reveal on scroll (gentle, staggered). The sand grain + water wash and the logo wash are pure CSS. */
(function(){
  var root=document.querySelector('.sk2'); if(!root) return;
  var reduce=matchMedia('(prefers-reduced-motion: reduce)').matches;
  var items=[].slice.call(root.querySelectorAll('[data-r],[data-rs]'));
  function show(el){
    el.classList.add('is-in');
    if(el.hasAttribute('data-rs')){ var k=el.children;
      for(var i=0;i<k.length;i++){ k[i].style.transitionDelay=(i*85)+'ms'; } }
  }
  if(reduce || !('IntersectionObserver' in window)){ items.forEach(show); return; }
  var io=new IntersectionObserver(function(es){
    es.forEach(function(e){ if(e.isIntersecting){ show(e.target); io.unobserve(e.target); } });
  },{threshold:.12,rootMargin:'0px 0px -8% 0px'});
  items.forEach(function(e){ io.observe(e); });
})();
