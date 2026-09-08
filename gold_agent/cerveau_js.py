"""Le script du reseau 3D de demonstration (onglet Cerveau).
"""

CERVEAU_JS = r"""
(function(){
  const cv = document.getElementById('cerveau3d');
  if (!cv) return;
  const ctx = cv.getContext('2d');
  let W, H; const DPR = window.devicePixelRatio || 1;
  function dim(){ W = cv.clientWidth; H = cv.clientHeight;
    cv.width = W*DPR; cv.height = H*DPR; ctx.setTransform(DPR,0,0,DPR,0,0); }
  dim(); addEventListener('resize', dim);

  let donnees = {agents:[]};
  try { donnees = JSON.parse(document.getElementById('donnees-cerveau').textContent); } catch(e){}

  // Disposition : superviseur au centre, sources de donnees sur l'anneau
  // exterieur, analyse a mi-distance, sorties (site, telephone) en dessous.
  const noeuds = [{id:'sup', nom:'Superviseur', emoji:'\u{1F9E0}', x:0, y:0, z:0, r:26, type:'centre', ok:true}];
  const sorties = [
    {id:'site', nom:'Site 8787', emoji:'\u{1F5A5}', x:0, y:170, z:60, r:18, type:'sortie', ok:true},
    {id:'tel', nom:'Téléphone (ntfy)', emoji:'\u{1F4F1}', x:150, y:150, z:-40, r:14, type:'sortie', ok:true},
    {id:'toi', nom:'TOI — décision', emoji:'\u{1F464}', x:-150, y:150, z:-40, r:16, type:'humain', ok:true},
  ];
  const ags = donnees.agents || [];
  const n = ags.length;
  ags.forEach((a,i)=>{
    const ang = i/n*Math.PI*2, ray = 200;
    noeuds.push({id:'a'+i, nom:a.nom, ok:a.ok, detail:a.detail, type:'agent',
      emoji:a.emoji||'\u{1F916}', cible:a.cible, coul:a.coul,
      x:Math.cos(ang)*ray, y:-40+Math.sin(ang*2)*38, z:Math.sin(ang)*ray, r:16});
  });
  noeuds.push(...sorties);

  const liens = [];
  ags.forEach((a,i)=>liens.push(['a'+i,'sup']));
  liens.push(['sup','site'],['site','tel'],['site','toi']);

  const parts = liens.map(()=>Math.random());   // particules de flux
  const idx = Object.fromEntries(noeuds.map((nd,i)=>[nd.id,i]));

  let ang = 0, survol = -1, tourne = true;
  const btnRot = document.getElementById('btn-rotation');
  if (btnRot) btnRot.onclick = () => {
    tourne = !tourne;
    btnRot.textContent = tourne ? '\u23F8 figer' : '\u25B6 animer';
  };
  cv.addEventListener('mousemove', e=>{
    const rc = cv.getBoundingClientRect();
    const mx = e.clientX-rc.left, my = e.clientY-rc.top;
    survol = -1;
    for (let i=0;i<noeuds.length;i++){
      const pn = noeuds[i]._p;
      if (pn && Math.hypot(mx-pn[0],my-pn[1]) < pn[2]+8) { survol=i; break; }
    }
    cv.style.cursor = (survol>=0 && (noeuds[survol].cible || noeuds[survol].id==='sup'))
      ? 'pointer' : 'default';
  });
  cv.addEventListener('click', ()=>{
    if (survol < 0) return;
    const nd = noeuds[survol];
    if (nd.id === 'sup') {
      document.querySelector('.superviseur')?.scrollIntoView({behavior:'smooth'});
    } else if (nd.cible && window.allerOnglet) {
      window.allerOnglet(nd.cible);
    }
  });

  function proj(nd, a){
    const cx=Math.cos(a), sx=Math.sin(a);
    const x = nd.x*cx - nd.z*sx, z = nd.x*sx + nd.z*cx;
    const persp = 560/(560+z);
    return [W/2 + x*persp, H/2 - 20 + nd.y*persp, nd.r*persp, persp, z];
  }

  function boucle(){
    // Le canvas nait dans un onglet masque (largeur 0) : on se recale des
    // que l'onglet devient visible ou que la fenetre change.
    if (W !== cv.clientWidth || H !== cv.clientHeight) dim();
    if (!W || !H) { requestAnimationFrame(boucle); return; }
    if (tourne) ang += 0.0035;
    ctx.clearRect(0,0,W,H);
    noeuds.forEach(nd=>nd._p = proj(nd, nd.type==='sortie'||nd.type==='humain' ? 0 : ang));

    // Liens + particules de donnees
    liens.forEach((ln,i)=>{
      const A = noeuds[idx[ln[0]]]._p, B = noeuds[idx[ln[1]]]._p;
      const g = ctx.createLinearGradient(A[0],A[1],B[0],B[1]);
      g.addColorStop(0,'rgba(120,140,180,0.10)'); g.addColorStop(1,'rgba(120,140,180,0.28)');
      ctx.strokeStyle=g; ctx.lineWidth=0.8;
      ctx.beginPath(); ctx.moveTo(A[0],A[1]); ctx.lineTo(B[0],B[1]); ctx.stroke();
      parts[i]=(parts[i]+0.006+Math.random()*0.002)%1;
      const t=parts[i], px=A[0]+(B[0]-A[0])*t, py=A[1]+(B[1]-A[1])*t;
      ctx.fillStyle='rgba(227,179,65,0.9)';
      ctx.beginPath(); ctx.arc(px,py,1.6,0,7); ctx.fill();
    });

    // Noeuds, tries par profondeur
    [...noeuds].sort((a,b)=>b._p[4]-a._p[4]).forEach(nd=>{
      const [x,y,r] = nd._p;
      const coul = nd.type==='centre' ? '#1f6feb'
                 : nd.type==='humain' ? '#a371f7'
                 : nd.type==='sortie' ? '#e3b341'
                 : (nd.coul || (nd.ok ? '#3fb950' : '#f85149'));
      const halo = ctx.createRadialGradient(x,y,0,x,y,r*2.4);
      halo.addColorStop(0, coul+'55'); halo.addColorStop(1,'transparent');
      ctx.fillStyle=halo; ctx.beginPath(); ctx.arc(x,y,r*2.4,0,7); ctx.fill();
      ctx.fillStyle=coul+'22'; ctx.beginPath(); ctx.arc(x,y,r*0.95,0,7); ctx.fill();
      ctx.strokeStyle=coul; ctx.lineWidth=1.6;
      ctx.beginPath(); ctx.arc(x,y,r*0.95,0,7); ctx.stroke();
      ctx.font = Math.max(12, r*1.05) + 'px serif';
      ctx.textAlign='center'; ctx.textBaseline='middle';
      ctx.fillText(nd.emoji || '\u{1F916}', x, y+1);
      ctx.textBaseline='alphabetic';
      ctx.fillStyle='#c9d1d9'; ctx.font='11px -apple-system,sans-serif';
      ctx.textAlign='center';
      ctx.fillText(nd.nom, x, y + r*0.95 + 14);
    });

    // Infobulle de survol
    if (survol>=0){
      const nd=noeuds[survol];
      if (nd.detail){
        const [x,y]=nd._p;
        ctx.fillStyle='rgba(13,17,23,0.92)'; ctx.strokeStyle='#30363d';
        const txt=nd.detail.slice(0,60), w=ctx.measureText(txt).width+16;
        ctx.beginPath(); ctx.roundRect(x-w/2, y-46, w, 24, 5); ctx.fill(); ctx.stroke();
        ctx.fillStyle='#e6edf3'; ctx.fillText(txt, x, y-30);
      }
    }
    requestAnimationFrame(boucle);
  }
  boucle();

  // Recoloration en direct quand /json rafraichit la sante
  window.majCerveau = sante => {
    (sante.agents||[]).forEach((a,i)=>{
      const nd = noeuds.find(x=>x.id==='a'+i);
      if (nd){ nd.ok = a.ok; nd.detail = a.detail; }
    });
  };
})();
"""


