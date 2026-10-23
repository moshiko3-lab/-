/* SHOKOGI scroll-craft — compact engine for Shopify. Reads data-sc-* off the
   markup and drives it; it never builds DOM. Devices: pin + cue, reveal + stagger,
   kinetic lines, pan rail, parallax planes, pointer spotlight + magnet, and a
   scroll-driven wash (the "tide" signature). */
(function(){
  var root = document.querySelector('[data-sc-root]'); if(!root) return;
  var reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
  var de = document.documentElement;

  /* ---- kinetic: split a heading into word spans for a line-by-line rise ---- */
  [].forEach.call(root.querySelectorAll('[data-sc-kinetic]'), function(h){
    var words = h.textContent.trim().split(/\s+/);
    h.textContent = '';
    words.forEach(function(w,i){
      var s = document.createElement('span'); s.className = 'k-w';
      var inner = document.createElement('span'); inner.className = 'k-i'; inner.textContent = w;
      inner.style.transitionDelay = (i*55) + 'ms';
      s.appendChild(inner); h.appendChild(s);
      h.appendChild(document.createTextNode(' '));
    });
  });

  /* ---- reveal on enter (+ kinetic trigger) ---- */
  function show(el){
    el.classList.add('is-in');
    var st = +(el.getAttribute('data-sc-stagger')||0);
    if(st){ var k=el.children; for(var i=0;i<k.length;i++){ k[i].style.transitionDelay=(i*st)+'ms'; } }
  }
  var ins = [].slice.call(root.querySelectorAll('[data-sc-in],[data-sc-kinetic]'));
  if(reduce || !('IntersectionObserver' in window)){ ins.forEach(show); }
  else{
    var io = new IntersectionObserver(function(es){
      es.forEach(function(e){ if(e.isIntersecting){ show(e.target); io.unobserve(e.target); } });
    }, {threshold:.16, rootMargin:'0px 0px -8% 0px'});
    ins.forEach(function(e){ io.observe(e); });
  }

  /* ---- acts: give every pinned/pan act a scroll span, then drive per frame ---- */
  var acts = [].slice.call(root.querySelectorAll('[data-sc-act]')).map(function(a){
    var span = +(a.getAttribute('data-sc-span')||1);
    if(a.getAttribute('data-sc-act') !== 'flow') a.style.setProperty('--span', span);
    return {
      el:a, span:span,
      pan: a.querySelector('[data-sc-pan]'),
      cues: [].slice.call(a.querySelectorAll('[data-sc-cue]')).map(function(c){
        var n=(c.getAttribute('data-sc-cue')||'0 1').trim().split(/\s+/).map(Number);
        return {el:c, from:n[0]||0, to:(n.length>1?n[1]:1)};
      }),
      wash: a.querySelector('[data-sc-wash]')
    };
  });
  var planes = [].slice.call(root.querySelectorAll('[data-sc-plane]'));

  var mx=0, my=0, raf=0;
  function sched(){ if(!raf) raf=requestAnimationFrame(tick); }
  function cueOpacity(p, from, to){
    var ri = Math.min(0.14, (to-from)*0.4), ro = Math.min(0.14, (to-from)*0.4);
    if(p < from || p > to) return 0;
    if(p < from+ri) return (p-from)/ri;
    if(to < 0.999 && p > to-ro) return (to-p)/ro;
    return 1;
  }
  function tick(){
    raf=0; var vh=innerHeight;
    acts.forEach(function(a){
      var r=a.el.getBoundingClientRect();
      var denom=a.el.offsetHeight-vh;
      var p = denom>0 ? Math.min(1,Math.max(0,(-r.top)/denom)) : (r.top<vh?1:0);
      a.el.style.setProperty('--p', p.toFixed(4));
      a.cues.forEach(function(c){ c.el.style.opacity = cueOpacity(p, c.from, c.to).toFixed(3);
        if(!reduce){ var o=+c.el.style.opacity; c.el.style.transform='translateY('+((1-o)*14).toFixed(1)+'px)'; } });
      if(a.pan){ var host=a.pan.parentElement||a.el; var ov=a.pan.scrollWidth-host.clientWidth; if(ov>0) a.pan.style.transform='translate3d('+(-ov*p).toFixed(1)+'px,0,0)'; }
      /* wash: the tide rises up the stage as the act scrubs (the signature move).
         Starts already covering the lower band so the words never sit on raw video. */
      if(a.wash){ var y=52-Math.min(1,p/0.72)*38; a.wash.style.transform='translate3d(0,'+y.toFixed(2)+'%,0)'; }
    });
    if(!reduce){
      planes.forEach(function(pl){
        var rate=parseFloat(pl.getAttribute('data-sc-plane'))||0;
        var r=pl.getBoundingClientRect(); var centre=r.top+r.height/2-vh/2;
        pl.style.transform='translate3d('+(mx*rate*80).toFixed(1)+'px,'+(-centre*rate).toFixed(1)+'px,0)';
      });
    }
  }
  addEventListener('scroll', sched, {passive:true});
  addEventListener('resize', sched);

  /* ---- pointer: spotlight + magnet + plane drift ---- */
  if(!reduce && matchMedia('(hover:hover) and (pointer:fine)').matches){
    var spots=[].slice.call(root.querySelectorAll('[data-sc-spotlight]'));
    var mags=[].slice.call(root.querySelectorAll('[data-sc-magnet]'));
    addEventListener('mousemove', function(e){
      mx=(e.clientX/innerWidth-.5); my=(e.clientY/innerHeight-.5);
      spots.forEach(function(s){ var r=s.getBoundingClientRect();
        s.style.setProperty('--mx',((e.clientX-r.left)/r.width).toFixed(3));
        s.style.setProperty('--my',((e.clientY-r.top)/r.height).toFixed(3)); });
      mags.forEach(function(m){ var r=m.getBoundingClientRect(), k=+(m.getAttribute('data-sc-magnet')||.2),
        dx=e.clientX-(r.left+r.width/2), dy=e.clientY-(r.top+r.height/2);
        m.style.transform = Math.hypot(dx,dy)<180 ? 'translate('+(dx*k).toFixed(1)+'px,'+(dy*k).toFixed(1)+'px)' : ''; });
      sched();
    }, {passive:true});
  }

  tick();
})();
