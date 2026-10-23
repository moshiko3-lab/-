/* SHOKOGI home — reveal on scroll + subtle hero/foil parallax. Clean, restrained. */
(function(){
  var root=document.querySelector('.sk2'); if(!root) return;
  var reduce=matchMedia('(prefers-reduced-motion: reduce)').matches;

  /* reveal */
  var items=[].slice.call(root.querySelectorAll('[data-r],[data-rs]'));
  function show(el){
    el.classList.add('is-in');
    if(el.hasAttribute('data-rs')){ var k=el.children;
      for(var i=0;i<k.length;i++){ k[i].style.transitionDelay=(i*80)+'ms'; } }
  }
  if(reduce || !('IntersectionObserver' in window)){ items.forEach(show); }
  else{
    var io=new IntersectionObserver(function(es){
      es.forEach(function(e){ if(e.isIntersecting){ show(e.target); io.unobserve(e.target); } });
    },{threshold:.12,rootMargin:'0px 0px -8% 0px'});
    items.forEach(function(e){ io.observe(e); });
  }

  /* subtle parallax: video stages drift, hero/foil copy lags + fades */
  if(!reduce){
    var pars=[].slice.call(root.querySelectorAll('[data-par]'));
    var pcs=[].slice.call(root.querySelectorAll('.sk2-hero .in,.sk2-foil .in'));
    if(pars.length || pcs.length){
      var raf=0;
      function tick(){ raf=0; var vh=innerHeight;
        pars.forEach(function(p){ var r=p.getBoundingClientRect();
          if(r.bottom<0||r.top>vh) return;
          var prog=(r.top+r.height/2-vh/2)/vh;      /* -~1 .. ~1 */
          p.style.transform='translate3d(0,'+(prog*-22).toFixed(1)+'px,0) scale(1.06)';
        });
        pcs.forEach(function(c){ var s=c.closest('section'); if(!s) return; var r=s.getBoundingClientRect();
          if(r.bottom<0||r.top>vh) return;
          var prog=Math.min(1,Math.max(0,-r.top/vh));   /* 0 at rest, 1 after one viewport up */
          c.style.transform='translate3d(0,'+(prog*34).toFixed(1)+'px,0)';
          c.style.opacity=(1-prog*1.15).toFixed(3);
        });
      }
      function sched(){ if(!raf) raf=requestAnimationFrame(tick); }
      addEventListener('scroll',sched,{passive:true}); addEventListener('resize',sched); tick();
    }
  }
})();
