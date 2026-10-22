/* SHOKOGI home — compact scroll engine: day-cycle, in/stagger, pin+cue, pan, parallax, pointer. */
(function(){
  var sec=document.getElementById('schome-sc'); if(!sec) return;
  var de=document.documentElement;
  var reduce=matchMedia('(prefers-reduced-motion: reduce)').matches;

  /* reveal on entry */
  function reveal(el){ el.classList.add('is-in'); var k=el.children, st=+(el.getAttribute('data-sc-stagger')||0);
    for(var i=0;i<k.length;i++){ k[i].style.transitionDelay=(i*st)+'ms'; } }
  var ins=[].slice.call(sec.querySelectorAll('[data-sc-in]'));
  if('IntersectionObserver' in window){
    var io=new IntersectionObserver(function(es){ es.forEach(function(e){ if(e.isIntersecting){ reveal(e.target); io.unobserve(e.target); } }); },{threshold:.14,rootMargin:'0px 0px -7% 0px'});
    ins.forEach(function(e){ io.observe(e); });
  } else { ins.forEach(reveal); }

  /* parse cues */
  function parseCue(el){ var n=(el.getAttribute('data-sc-cue')||'').trim().split(/\s+/).map(Number);
    var multi=n.length>1;
    return { el:el, from:n[0]||0, to:multi?n[1]:1,
      ri:n.length>2?n[2]:(multi?0.3:0.25), ro:n.length>3?n[3]:(multi?0.3:0),
      rise: el.getAttribute('data-sc-rise')==='0'?0:12 }; }
  function cueOpacity(c,p){ var win=Math.max(c.to-c.from,1e-4), ie=c.from+c.ri*win, os=c.to-c.ro*win;
    if(p<c.from) return 0; if(p>c.to) return c.ro===0?1:0;
    if(c.ri>0&&p<ie) return (p-c.from)/(ie-c.from); if(c.ro>0&&p>os) return (c.to-p)/(c.to-os); return 1; }

  /* collect acts */
  var acts=[].slice.call(sec.querySelectorAll('[data-sc-act]')).map(function(a){
    var span=+(a.getAttribute('data-sc-span')||1);
    a.style.height=(span*100)+'vh';
    return { el:a, span:span,
      pan:a.querySelector('[data-sc-pan]'),
      par:[].slice.call(a.querySelectorAll('[data-sc-parallax]')),
      cues:[].slice.call(a.querySelectorAll('[data-sc-cue]')).map(parseCue) };
  });

  var raf=0, dayCur=0;
  function tick(){
    raf=0; var vh=innerHeight, y=window.pageYOffset||0;
    var top=sec.getBoundingClientRect().top+y, span=sec.offsetHeight-vh;
    var day=span>0?Math.min(1,Math.max(0,(y-top)/span)):0;
    dayCur+= (day-dayCur)*(reduce?1:0.12); if(Math.abs(day-dayCur)<4e-4) dayCur=day;
    de.style.setProperty('--day', dayCur.toFixed(4));
    acts.forEach(function(a){
      var at=a.el.getBoundingClientRect().top+y;
      var p=Math.min(1,Math.max(0,(y-at)/Math.max(a.el.offsetHeight-vh,1)));
      a.el.style.setProperty('--sc-p',p.toFixed(4));
      a.cues.forEach(function(c){ var o=cueOpacity(c,p); c.el.style.opacity=o;
        if(!reduce&&c.rise) c.el.style.transform='translateY('+((1-o)*c.rise).toFixed(1)+'px)'; });
      if(a.pan){ var ov=a.pan.scrollWidth-a.pan.clientWidth; a.pan.style.transform='translateX('+(-(ov>0?ov:0)*p).toFixed(1)+'px)'; }
      if(!reduce) a.par.forEach(function(pe){ var r=+(pe.getAttribute('data-sc-parallax')||0); pe.style.transform='translateY('+(r*(p-.5)*100).toFixed(1)+'px)'; });
    });
    if(dayCur!==day) sched();
  }
  function sched(){ if(!raf) raf=requestAnimationFrame(tick); }
  addEventListener('scroll',sched,{passive:true}); addEventListener('resize',sched);

  /* pointer: spotlight + magnet */
  if(!reduce && matchMedia('(hover:hover) and (pointer:fine)').matches){
    var spot=sec.querySelector('[data-sc-spotlight]'), mags=[].slice.call(sec.querySelectorAll('[data-sc-magnet]'));
    addEventListener('mousemove',function(e){
      if(spot){ var r=spot.getBoundingClientRect(); spot.style.setProperty('--sc-mx',((e.clientX-r.left)/r.width).toFixed(3)); spot.style.setProperty('--sc-my',((e.clientY-r.top)/r.height).toFixed(3)); }
      mags.forEach(function(m){ var r=m.getBoundingClientRect(), s=+(m.getAttribute('data-sc-magnet')||.25),
        dx=e.clientX-(r.left+r.width/2), dy=e.clientY-(r.top+r.height/2);
        if(Math.hypot(dx,dy)<170){ m.style.transform='translate('+(dx*s).toFixed(1)+'px,'+(dy*s).toFixed(1)+'px)'; } else { m.style.transform=''; } });
    },{passive:true});
  }
  tick();
})();
