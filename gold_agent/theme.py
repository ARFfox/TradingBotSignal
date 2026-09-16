"""Le thème du site — maquette.html est la SOURCE des valeurs (8.7).

Clair par défaut, sombre par le bouton (data-theme) et par préférence
système. Le rouge et le vert sont indistinguables en deutéranopie
(ΔE 4,1 mesuré, ~8 % des hommes) : le SIGNE et l'icône portent le sens,
la couleur ne fait qu'accompagner. Deux verts et deux rouges : le vif va
sur les marques (barres, points), le foncé sur le texte (contraste ≥ 4,5:1).
"""

CSS = """
:root{
  color-scheme:light;
  --fond:#ffffff; --surface:#fafaf9; --surface-2:#f4f4f2;
  --bord:#e4e3df; --bord-fort:#cdccc7;
  --encre:#17171a; --encre-2:#52514e; --encre-3:#76746f;
  --perte:#b3261e; --perte-marque:#d03b3b; --perte-fond:#fdf0ef;
  --gain:#006300; --gain-marque:#0ca30c; --gain-fond:#edf7ed;
  --attention:#8a5a00; --attention-marque:#fab219; --attention-fond:#fdf6e6;
  --accent:#1c5cab; --accent-marque:#2a78d6; --accent-fond:#eef4fd;
  --neutre-fond:#f0efec; --r:10px;
  --ombre:0 1px 2px rgba(23,23,26,.05),0 1px 3px rgba(23,23,26,.06);
}
:root[data-theme="dark"]{
  color-scheme:dark;
  --fond:#131316; --surface:#1a1a1e; --surface-2:#232328;
  --bord:#2c2c32; --bord-fort:#3d3d45;
  --encre:#f2f2f0; --encre-2:#b9b8b2; --encre-3:#8d8c86;
  --perte:#ff8a80; --perte-marque:#e66767; --perte-fond:#2a1614;
  --gain:#6ddc6d; --gain-marque:#0ca30c; --gain-fond:#12240f;
  --attention:#f5c451; --attention-marque:#fab219; --attention-fond:#2a2210;
  --accent:#7fb2f5; --accent-marque:#3987e5; --accent-fond:#101d2e;
  --neutre-fond:#26262b; --ombre:0 1px 2px rgba(0,0,0,.4);
}
@media (prefers-color-scheme: dark){
  :root:where(:not([data-theme="light"])){
    color-scheme:dark;
    --fond:#131316; --surface:#1a1a1e; --surface-2:#232328;
    --bord:#2c2c32; --bord-fort:#3d3d45;
    --encre:#f2f2f0; --encre-2:#b9b8b2; --encre-3:#8d8c86;
    --perte:#ff8a80; --perte-marque:#e66767; --perte-fond:#2a1614;
    --gain:#6ddc6d; --gain-marque:#0ca30c; --gain-fond:#12240f;
    --attention:#f5c451; --attention-marque:#fab219; --attention-fond:#2a2210;
    --accent:#7fb2f5; --accent-marque:#3987e5; --accent-fond:#101d2e;
    --neutre-fond:#26262b;
  }
}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--fond);color:var(--encre);
font:14px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Inter,system-ui,sans-serif;
-webkit-font-smoothing:antialiased;padding:20px 16px 60px}
.wrap{max-width:1680px;margin:0 auto}
.mono{font-variant-numeric:tabular-nums;font-feature-settings:"tnum"}
h1,h2,h3{font-weight:650;letter-spacing:-.01em}

/* ---------- chapeau ---------- */
header{display:flex;align-items:center;gap:14px;flex-wrap:wrap;margin-bottom:14px}
h1{font-size:17px;font-weight:700}
.prix{font-size:26px;font-weight:700;letter-spacing:-.02em;font-variant-numeric:tabular-nums}
.meta{color:var(--encre-3);font-size:12.5px}
.var{font-size:13px;font-weight:650;padding:3px 8px;border-radius:99px}
.var.hausse{color:var(--gain);background:var(--gain-fond)}
.var.baisse{color:var(--perte);background:var(--perte-fond)}
.direct{font-size:11.5px;color:var(--encre-3)}
.direct .vif{color:var(--gain)}
#chapeau-signal{font-size:12.5px;color:var(--perte);font-weight:650}
.bt-theme{background:var(--surface);border:1px solid var(--bord);color:var(--encre-2);
border-radius:8px;padding:6px 11px;cursor:pointer;font:inherit;font-size:12px}
.bt-theme:hover{background:var(--surface-2)}
.barre{display:flex;align-items:center;gap:14px;flex-wrap:wrap;margin-left:auto}
.rondelle{display:flex;flex-direction:column;align-items:center;gap:3px}
.btn-rond{width:42px;height:42px;border-radius:50%;background:var(--surface);border:1px solid var(--bord);
color:var(--encre-2);display:flex;align-items:center;justify-content:center;cursor:pointer;padding:0;
transition:background .15s,transform .1s;position:relative}
.btn-rond:hover{background:var(--surface-2);transform:scale(1.06)}
.btn-rond svg{width:19px;height:19px;fill:none;stroke:currentColor;stroke-width:1.8;
stroke-linecap:round;stroke-linejoin:round}
.btn-rond.on{border-color:var(--gain-marque);color:var(--gain)}
.btn-rond .point{position:absolute;top:2px;right:2px;width:9px;height:9px;border-radius:50%;
background:var(--gain-marque);border:2px solid var(--surface);display:none}
.btn-rond.on .point{display:block}
.mini-lib{font-size:10px;color:var(--encre-3);letter-spacing:.2px;font-variant-numeric:tabular-nums}
.anneau{position:relative;width:54px;height:54px}
.anneau svg{transform:rotate(-90deg)}
.anneau .pctq{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;
font-size:12.5px;font-weight:700;font-variant-numeric:tabular-nums}
.pt-etat{width:8px;height:8px;border-radius:50%;background:var(--gain-marque);display:inline-block;margin-right:6px}
.pt-etat.charge{background:var(--attention-marque);animation:clign 1s infinite}
@keyframes clign{50%{opacity:.3}}
#notif-etat{font-size:12px;color:var(--encre-3)}
.on{color:var(--gain)}

/* ---------- pastille compteur (signaux EN COURS) ---------- */
.pastille{background:var(--perte-marque);color:#fff;font-size:11px;font-weight:700;
min-width:18px;height:18px;border-radius:99px;display:inline-flex;align-items:center;
justify-content:center;padding:0 5px;line-height:1}
.pastille[hidden]{display:none}

/* ---------- marchés + instruments ---------- */
.marches-nav{display:flex;gap:8px;flex-wrap:wrap;margin:0 0 10px}
.m-btn{position:relative;background:var(--surface);border:1px solid var(--bord);border-radius:9px;
padding:8px 14px;cursor:pointer;font:inherit;font-weight:600;font-size:13px;color:var(--encre-2);
display:inline-flex;align-items:center;gap:7px}
.m-btn:hover{border-color:var(--bord-fort)}
.m-grille{background:var(--fond);border:1px solid var(--bord);border-radius:var(--r);padding:10px 12px;margin:0 0 12px}
.m-tuiles{display:flex;gap:7px;overflow-x:auto;padding:4px 2px 8px;scrollbar-width:thin}
.tuile-inst{flex:0 0 auto;background:var(--surface);border:1px solid var(--bord);border-radius:9px;
padding:8px 12px;cursor:pointer;font-size:12px;min-width:116px;position:relative;text-align:left}
.tuile-inst:hover{border-color:var(--bord-fort)}
.tuile-inst.actif{border-color:var(--accent-marque);background:var(--accent-fond);
box-shadow:inset 0 0 0 1px var(--accent-marque)}
.tuile-inst .pastille{position:absolute;top:-6px;right:-5px}
.bandeau{background:var(--surface);border:1px solid var(--bord);border-left:3px solid var(--attention-marque);
border-radius:8px;padding:12px 16px;margin:12px 0 18px;font-size:13px;color:var(--encre-2)}

/* ---------- bandeau de stats (4 tuiles, maquette) ---------- */
.stats4{display:grid;grid-template-columns:1.15fr 1.7fr 1fr .85fr;gap:1px;background:var(--bord);
border:1px solid var(--bord);border-radius:var(--r);overflow:hidden;margin:0 0 16px}
.tuile{background:var(--surface);padding:14px 16px;min-width:0}
.tuile .lab{font-size:11px;font-weight:650;text-transform:uppercase;letter-spacing:.06em;
color:var(--encre-3);margin-bottom:5px}
.heros{font-size:38px;font-weight:700;letter-spacing:-.025em;line-height:1.05}
.heros.neg{color:var(--perte)} .heros.pos{color:var(--gain)}
.sous{font-size:11.5px;color:var(--encre-3);margin-top:4px}
.gros{font-size:24px;font-weight:700;letter-spacing:-.02em;line-height:1.15}
.gros.neg{color:var(--perte)} .gros.pos{color:var(--gain)}
.jauge{margin-top:9px}
.jauge .piste{position:relative;height:26px;background:var(--neutre-fond);border-radius:6px;overflow:visible}
.jauge .rempli{position:absolute;inset:0 auto 0 0;background:var(--perte-marque);border-radius:6px 3px 3px 6px}
.jauge .rempli.ok{background:var(--gain-marque)}
.jauge .seuil{position:absolute;top:-5px;bottom:-5px;width:2px;background:var(--encre);border-radius:2px}
.jauge .seuil::after{content:attr(data-l);position:absolute;top:-17px;left:50%;transform:translateX(-50%);
white-space:nowrap;font-size:10.5px;font-weight:650;color:var(--encre-2)}
.jauge .dansbarre{position:absolute;left:9px;top:50%;transform:translateY(-50%);
color:#fff;font-size:13px;font-weight:700}
.manque{font-size:11.5px;color:var(--perte);font-weight:600;margin-top:7px}

/* ---------- timeframes pleine largeur ---------- */
.tfs{display:grid;grid-template-columns:repeat(6,1fr);gap:8px;margin:0 0 16px;overflow:visible}
.tfx{position:relative;background:var(--surface);border:1px solid var(--bord);border-radius:var(--r);
padding:11px 8px;cursor:pointer;font:inherit;text-align:center}
.tfx:hover{border-color:var(--bord-fort)}
.tfx.actif,.tfx[aria-pressed="true"]{border-color:var(--accent-marque);background:var(--accent-fond);
box-shadow:inset 0 0 0 1px var(--accent-marque)}
.tfx .n{font-size:16px;font-weight:700;letter-spacing:-.01em}
.tfx .v{font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.05em;margin-top:3px}
.tfx .e{font-size:10.5px;color:var(--encre-3);margin-top:1px;font-variant-numeric:tabular-nums}
.v.coupe{color:var(--perte)} .v.obs{color:var(--attention)}
.v.autorise{color:var(--gain)} .v.insuf{color:var(--encre-3)}
.tfx.coupe{opacity:.62}
.tfx .pastille{position:absolute;top:-7px;right:-6px}

/* ---------- duo : signal | graphique ---------- */
.duo{display:grid;grid-template-columns:400px minmax(0,1fr);gap:16px;margin:0 0 18px;align-items:stretch}
.carte{background:var(--surface);border:1px solid var(--bord);border-radius:var(--r);
box-shadow:var(--ombre);overflow:hidden;display:flex;flex-direction:column}
.carte[data-tf]{display:none}.carte[data-tf].vue{display:flex}
.tete{padding:13px 15px;border-bottom:1px solid var(--bord);display:flex;align-items:center;gap:11px;flex-wrap:wrap}
.tf{font-size:15px;font-weight:700}
.role{color:var(--encre-3);font-size:11px;text-transform:uppercase;letter-spacing:.6px}
.badge{font-size:11px;font-weight:650;padding:4px 9px;border-radius:99px;display:inline-flex;
align-items:center;gap:5px;white-space:nowrap}
.badge.mesure-pos,.b-mesure{background:var(--gain-fond);color:var(--gain)}
.badge.mesure-neg,.b-nonmesure{background:var(--perte-fond);color:var(--perte)}
.badge.gris,.b-indicatif{background:var(--neutre-fond);color:var(--encre-2)}
.corps{padding:15px;flex:1;overflow-y:auto;max-height:560px}
.aucun{color:var(--encre-3);font-size:13px;padding:6px 0}
.aucun b{color:var(--encre-2);display:block;margin-bottom:4px;font-weight:600}
.avis{border-left:3px solid;border-radius:0 8px 8px 0;padding:10px 13px;font-size:12.5px;
line-height:1.55;margin-bottom:13px}
.avis.stop{border-color:var(--attention-marque);background:var(--attention-fond);color:var(--attention)}
.avis.info{border-color:var(--accent-marque);background:var(--accent-fond);color:var(--accent)}
.zones{display:grid;gap:8px;margin-bottom:14px}
.zone{display:flex;justify-content:space-between;align-items:baseline;gap:10px;
padding:9px 12px;border-radius:8px;border-left:3px solid;font-variant-numeric:tabular-nums}
.z-entree{border-color:var(--accent-marque);background:var(--accent-fond)}
.z-stop{border-color:var(--perte-marque);background:var(--perte-fond)}
.z-obj{border-color:var(--gain-marque);background:var(--gain-fond)}
.zl{font-size:11px;font-weight:650;text-transform:uppercase;letter-spacing:.05em;color:var(--encre-2)}
.zv{font-size:17px;font-weight:700}
.zd{font-size:11px;color:var(--encre-3);margin-top:1px}
.stats{display:grid;grid-template-columns:repeat(3,1fr);gap:9px;margin-top:12px;padding-top:13px;
border-top:1px solid var(--bord)}
.st{text-align:center}
.sl{font-size:10px;font-weight:650;letter-spacing:.05em;color:var(--encre-3);text-transform:uppercase}
.sv{font-size:18px;font-weight:700;font-variant-numeric:tabular-nums;margin-top:2px}
.alertes{margin-top:12px;display:flex;flex-direction:column;gap:6px}
.al{font-size:12.5px;padding:7px 10px;border-radius:5px;background:var(--surface-2);
color:var(--encre-2);border-left:2px solid var(--encre-3)}
.al.chaud{border-left-color:var(--perte-marque);color:var(--perte)}
.al.tiede{border-left-color:var(--attention-marque);color:var(--attention)}
.ict-ligne{font-size:12px;color:var(--encre-3);padding:6px 0;border-top:1px solid var(--bord);margin-top:8px}
.ict-ligne b{color:var(--encre-2)}
.rr{font-size:13px;color:var(--encre-3)}
.rr b{color:var(--encre);font-size:15px}
.age{font-size:11px;color:var(--encre-3);margin-left:auto}
.age.perime{color:var(--perte)}
.chart-tv{position:relative;background:var(--surface-2);min-height:460px;border-radius:var(--r);
border:1px solid var(--bord);overflow:hidden}
.chart-tv iframe{position:absolute;inset:0;width:100%;height:100%;border:0}
.surchart{position:absolute;top:12px;left:12px;background:var(--fond);border:1px solid var(--bord);
border-radius:8px;padding:9px 12px;font-size:12px;box-shadow:var(--ombre);max-width:290px;
text-align:left;color:var(--encre-2);z-index:5;display:none}
.surchart.vue{display:block}
.surchart b{color:var(--encre);display:block;margin-bottom:3px;font-size:12.5px}

/* ---------- onglets + tableaux ---------- */
.onglets{display:flex;gap:6px;border-bottom:1px solid var(--bord);margin:0;flex-wrap:wrap}
.onglet{background:none;border:none;border-bottom:2px solid transparent;padding:9px 14px;
cursor:pointer;font:inherit;font-weight:600;font-size:13.5px;color:var(--encre-3);margin-bottom:-1px}
.onglet:hover{color:var(--encre-2)}
.onglet.actif,.onglet[aria-selected="true"]{color:var(--accent);border-bottom-color:var(--accent-marque)}
.onglet .cpt{font-size:11px;color:var(--encre-3);font-weight:600;margin-left:5px}
.panneau{display:none}
.panneau.actif{display:block;background:var(--surface);border:1px solid var(--bord);border-top:none;
border-radius:0 0 var(--r) var(--r);overflow:hidden;margin-bottom:18px}
.filtres{display:flex;gap:7px;align-items:center;flex-wrap:wrap;padding:11px 14px;
border-bottom:1px solid var(--bord);background:var(--surface-2)}
.puce{background:var(--fond);border:1px solid var(--bord);border-radius:99px;padding:4px 11px;
cursor:pointer;font:inherit;font-size:12px;font-weight:600;color:var(--encre-2)}
.puce[aria-pressed="true"]{background:var(--accent-fond);border-color:var(--accent-marque);color:var(--accent)}
.filtres .info{margin-left:auto;font-size:11.5px;color:var(--encre-3)}
.defile{max-height:252px;overflow-y:auto;overscroll-behavior:contain;
scrollbar-width:thin;scrollbar-color:var(--bord-fort) transparent}
.defile::-webkit-scrollbar{width:11px}
.defile::-webkit-scrollbar-thumb{background:var(--bord-fort);border-radius:99px;border:3px solid var(--surface)}
table{width:100%;border-collapse:collapse;font-size:13px}
thead th{position:sticky;top:0;background:var(--surface-2);text-align:left;font-size:10.5px;
font-weight:700;letter-spacing:.06em;text-transform:uppercase;color:var(--encre-3);
padding:9px 12px;border-bottom:1px solid var(--bord);z-index:1}
tbody td{padding:9px 12px;border-bottom:1px solid var(--bord);white-space:nowrap;color:var(--encre-2);
font-variant-numeric:tabular-nums}
tbody tr:last-child td{border-bottom:none}
tbody tr:hover{background:var(--surface-2)}
td.num{text-align:right}
.res{font-weight:650;font-size:12.5px;display:inline-flex;align-items:center;gap:5px}
.res.tp{color:var(--gain)} .res.sl{color:var(--perte)} .res.at{color:var(--encre-3)}
.cause{font-size:11.5px;color:var(--encre-3)}
.pied{padding:10px 14px;font-size:11.5px;color:var(--encre-3);border-top:1px solid var(--bord);
background:var(--surface-2)}

/* ---------- blocs conservés (risque, boule, cerveau, console, stratégies) */
.news{background:var(--surface);border:1px solid var(--bord);border-radius:var(--r);
padding:14px 16px;margin:0;display:grid;grid-template-columns:1fr 1fr;gap:16px}
@media(max-width:800px){.news{grid-template-columns:1fr}}
.news h3{font-size:12px;color:var(--encre-3);text-transform:uppercase;letter-spacing:.6px;margin-bottom:8px}
.evt{display:flex;justify-content:space-between;gap:10px;font-size:13px;padding:5px 0;
border-bottom:1px solid var(--bord)}
.evt:last-child{border-bottom:none}
.evt .t{color:var(--encre-2)}.evt .q{color:var(--encre-3);white-space:nowrap;font-variant-numeric:tabular-nums}
.risque{padding:8px 12px;border-radius:6px;font-size:13px;margin-bottom:10px}
.risque.veto{background:var(--perte-fond);color:var(--perte);border-left:3px solid var(--perte-marque)}
.risque.reserve{background:var(--attention-fond);color:var(--attention);border-left:3px solid var(--attention-marque)}
.risque.ok{background:var(--gain-fond);color:var(--gain);border-left:3px solid var(--gain-marque)}
.risque.inconnu{background:var(--neutre-fond);color:var(--encre-3);border-left:3px solid var(--encre-3)}
.macrol{font-size:13px;color:var(--encre-2);padding:4px 0}
.haut-page{display:grid;grid-template-columns:340px 1fr;gap:18px;margin:0 0 18px}
@media(max-width:900px){.haut-page{grid-template-columns:1fr}}
.boule{background:var(--surface);border:1px solid var(--bord);border-radius:var(--r);padding:18px;
display:flex;flex-direction:column;align-items:center;gap:10px}
.boule h3{font-size:12px;color:var(--encre-3);text-transform:uppercase;letter-spacing:.6px;align-self:flex-start}
.verdict-b{font-size:20px;font-weight:700}
.verdict-b.h{color:var(--gain)}.verdict-b.b{color:var(--perte)}.verdict-b.n{color:var(--attention)}
.legende{display:flex;gap:16px;font-size:12.5px;color:var(--encre-2)}
.legende i{display:inline-block;width:9px;height:9px;border-radius:50%;margin-right:5px}
.contribs{width:100%;font-size:11.5px;color:var(--encre-3);max-height:150px;overflow-y:auto;
border-top:1px solid var(--bord);padding-top:8px}
.contribs div{display:flex;justify-content:space-between;padding:2px 0}
.tv-cadre{background:var(--surface);border:1px solid var(--bord);border-radius:var(--r);
overflow:hidden;min-height:460px}
.tv-cadre h3{font-size:12px;color:var(--encre-3);text-transform:uppercase;letter-spacing:.6px;padding:14px 16px 0}
.strats{background:var(--surface);border:1px solid var(--bord);border-radius:var(--r);padding:16px;overflow-x:auto}
.strats .ok{color:var(--gain)}.strats .ko{color:var(--perte)}
.grille{display:grid;grid-template-columns:repeat(auto-fit,minmax(330px,1fr));gap:18px}
.grand-chart{display:none;background:var(--surface);border:1px solid var(--bord);border-radius:var(--r);padding:12px}
.grand-chart.actif{display:block}
.chart{background:var(--surface-2);border-top:1px solid var(--bord)}
.cerveau{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:12px}
.ag{background:var(--surface);border:1px solid var(--bord);border-radius:var(--r);padding:14px}
.ag h4{font-size:13.5px;color:var(--encre);display:flex;align-items:center;gap:8px}
.ag .pt{width:9px;height:9px;border-radius:50%;flex-shrink:0}
.ag .pt.ok{background:var(--gain-marque)}.ag .pt.ko{background:var(--perte-marque)}
.ag p{font-size:12px;color:var(--encre-3);margin-top:4px}
.superviseur{grid-column:1/-1;background:var(--surface);border:1px solid var(--bord);
border-left:3px solid var(--accent-marque);border-radius:var(--r);padding:14px;font-size:13px;color:var(--encre-2)}
.sys{display:grid;grid-template-columns:1fr 340px;gap:14px;margin-bottom:16px}
@media(max-width:1000px){.sys{grid-template-columns:1fr}}
.ag-grille{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:12px}
.agc{background:var(--surface);border:1px solid var(--bord);border-radius:var(--r);padding:12px 14px;
position:relative;overflow:hidden}
.agc .code{position:absolute;top:8px;right:10px;font-size:10px;color:var(--encre-3);font-family:monospace}
.agc h4{display:flex;align-items:center;gap:8px;font-size:14.5px;letter-spacing:.3px}
.agc .ico{width:30px;height:30px;border-radius:7px;display:flex;align-items:center;justify-content:center;
font-size:15px;background:var(--surface-2);border:1px solid currentColor}
.agc .rl{font-size:11px;color:var(--encre-3);margin:2px 0 8px 38px}
.chip{font-size:9.5px;font-weight:700;letter-spacing:1px;border:1px solid currentColor;border-radius:4px;
padding:2px 7px;margin-left:auto;animation:pulse-chip 1.6s infinite}
@keyframes pulse-chip{50%{opacity:.45}}
.barp{height:4px;background:var(--neutre-fond);border-radius:99px;overflow:hidden;margin:6px 0 8px}
.barp i{display:block;height:100%;width:40%;border-radius:99px;background:currentColor;animation:flux 2.2s ease-in-out infinite}
@keyframes flux{0%{margin-left:-40%}100%{margin-left:100%}}
.act{font-size:12px;color:var(--encre-2);min-height:34px;font-family:ui-monospace,monospace;line-height:1.45}
.act .lg{display:none}.act .lg.on{display:block}
.agc .pied{display:flex;justify-content:space-between;align-items:center;margin-top:8px;font-size:10.5px;
color:var(--encre-3);border-top:1px solid var(--bord);padding-top:7px}
.mini-conv{display:flex;align-items:center;gap:5px;font-variant-numeric:tabular-nums}
.console{background:var(--surface-2);border:1px solid var(--bord);border-radius:var(--r);padding:10px 12px;
font-family:ui-monospace,monospace;font-size:11px;line-height:1.6;overflow-y:auto;max-height:520px}
.console h5{color:var(--encre-3);font-size:10px;letter-spacing:1.5px;margin-bottom:6px}
.cl{color:var(--encre-3);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.cl b{color:var(--accent);font-weight:600}
.cl.signal{color:var(--gain)}.cl.veto{color:var(--perte)}.cl.alerte{color:var(--attention)}
.convs{grid-column:1/-1;display:flex;gap:18px;flex-wrap:wrap;background:var(--surface);
border:1px solid var(--bord);border-radius:var(--r);padding:12px 16px;margin-bottom:14px}
.convs .cvx{display:flex;flex-direction:column;align-items:center;gap:3px;font-size:10px;color:var(--encre-3)}
.jauge-tf{position:relative;width:44px;height:44px;flex-shrink:0}
.jauge-tf svg{transform:rotate(-90deg)}
.jauge-tf span{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;
font-size:11px;font-weight:700;font-variant-numeric:tabular-nums}
footer{margin-top:28px;padding-top:18px;border-top:1px solid var(--bord);color:var(--encre-3);
font-size:12.5px;line-height:1.7}
.flash{animation:flash 1.4s ease-out}
@keyframes flash{0%{box-shadow:0 0 0 0 rgba(42,120,214,.55)}100%{box-shadow:0 0 0 22px rgba(42,120,214,0)}}
button{font-family:inherit}
.tf-btns{display:flex;gap:6px;margin:0 0 10px}
.tf-btn{background:var(--surface);color:var(--encre-2);border:1px solid var(--bord);border-radius:6px;
padding:5px 14px;font-size:12.5px;cursor:pointer;font-family:inherit}
.tf-btn.actif{background:var(--accent-fond);border-color:var(--accent-marque);color:var(--accent)}
@media (max-width:1100px){
  .duo{grid-template-columns:1fr}
  .stats4{grid-template-columns:1fr 1fr}
  .tfs{grid-template-columns:repeat(3,1fr)}
}
@media (max-width:620px){
  body{padding:14px 12px 40px}
  .stats4{grid-template-columns:1fr}
  .heros{font-size:32px}
}
"""
