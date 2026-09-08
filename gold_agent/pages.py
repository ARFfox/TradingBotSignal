"""Feuille de style et pages d'authentification du tableau de bord.

Separe de web.py (regle 17 : aucun fichier > 500 lignes).
"""

CSS = """
*{box-sizing:border-box;margin:0;padding:0}
body{background:#0d1117;color:#e6edf3;font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;padding:24px}
.wrap{max-width:1400px;margin:0 auto}
header{display:flex;align-items:baseline;gap:18px;flex-wrap:wrap;margin-bottom:6px}
h1{font-size:22px;font-weight:650;letter-spacing:-.3px}
.prix{font-size:30px;font-weight:700;color:#e3b341;font-variant-numeric:tabular-nums}
.meta{color:#8b949e;font-size:13px}
.bandeau{background:#161b22;border:1px solid #30363d;border-left:3px solid #d29922;border-radius:8px;padding:12px 16px;margin:16px 0 24px;font-size:13.5px;color:#c9d1d9}
.grille{display:grid;grid-template-columns:repeat(auto-fit,minmax(330px,1fr));gap:18px}
.carte{background:#161b22;border:1px solid #30363d;border-radius:10px;overflow:hidden;display:flex;flex-direction:column}
.carte.actif{border-color:#2f81f7}
.tete{padding:14px 16px;border-bottom:1px solid #30363d;display:flex;align-items:center;justify-content:space-between;gap:10px}
.tf{font-size:17px;font-weight:650}
.role{color:#8b949e;font-size:12px;text-transform:uppercase;letter-spacing:.6px}
.badge{font-size:11px;padding:3px 9px;border-radius:99px;font-weight:600;white-space:nowrap}
.b-mesure{background:#12341f;color:#3fb950;border:1px solid #238636}
.b-indicatif{background:#3a2e12;color:#d29922;border:1px solid #9e6a03}
.b-nonmesure{background:#3d1d1d;color:#f85149;border:1px solid #b62324}
.corps{padding:16px;flex:1}
.aucun{color:#8b949e;font-size:13.5px;padding:10px 0}
.aucun b{color:#c9d1d9;display:block;margin-bottom:4px;font-weight:600}
.zones{display:flex;flex-direction:column;gap:8px;margin-bottom:14px}
.zone{display:flex;align-items:center;justify-content:space-between;padding:9px 12px;border-radius:6px;font-variant-numeric:tabular-nums}
.z-entree{background:rgba(47,129,247,.13);border-left:3px solid #2f81f7}
.z-stop{background:rgba(248,81,73,.12);border-left:3px solid #f85149}
.z-obj{background:rgba(63,185,80,.12);border-left:3px solid #3fb950}
.zl{font-size:12px;color:#8b949e;text-transform:uppercase;letter-spacing:.5px}
.zv{font-size:17px;font-weight:650}
.zd{font-size:11.5px;color:#8b949e;margin-top:2px}
.stats{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-top:12px;padding-top:12px;border-top:1px solid #30363d}
.st{text-align:center}
.sl{font-size:10.5px;color:#8b949e;text-transform:uppercase;letter-spacing:.5px}
.sv{font-size:15px;font-weight:600;font-variant-numeric:tabular-nums;margin-top:2px}
.chart{background:#0d1117;border-top:1px solid #30363d}
.alertes{margin-top:12px;display:flex;flex-direction:column;gap:6px}
.al{font-size:12.5px;padding:7px 10px;border-radius:5px;background:#21262d;color:#c9d1d9;border-left:2px solid #8b949e}
.al.chaud{border-left-color:#f85149;color:#ffa198}
.al.tiede{border-left-color:#d29922;color:#e3b341}
footer{margin-top:28px;padding-top:18px;border-top:1px solid #30363d;color:#8b949e;font-size:12.5px;line-height:1.7}
.rr{font-size:13px;color:#8b949e}
.rr b{color:#e6edf3;font-size:15px}
.age{font-size:11px;color:#6e7681;margin-left:auto}
.age.perime{color:#f85149}
.barre{display:flex;align-items:center;gap:14px;flex-wrap:wrap;margin-left:auto}
.pastille{width:8px;height:8px;border-radius:50%;background:#3fb950;display:inline-block;margin-right:6px}
.pastille.charge{background:#d29922;animation:clign 1s infinite}
@keyframes clign{50%{opacity:.3}}
.compteur{font-size:12.5px;color:#8b949e;font-variant-numeric:tabular-nums}
#notif-etat{font-size:12px;color:#8b949e}
.rondelle{display:flex;flex-direction:column;align-items:center;gap:3px}
.btn-rond{width:42px;height:42px;border-radius:50%;background:#21262d;border:1px solid #30363d;
color:#c9d1d9;display:flex;align-items:center;justify-content:center;cursor:pointer;padding:0;
transition:background .15s,transform .1s;position:relative}
.btn-rond:hover{background:#30363d;transform:scale(1.06)}
.btn-rond svg{width:19px;height:19px;fill:none;stroke:currentColor;stroke-width:1.8;
stroke-linecap:round;stroke-linejoin:round}
.btn-rond.on{border-color:#238636;color:#3fb950}
.btn-rond .point{position:absolute;top:2px;right:2px;width:9px;height:9px;border-radius:50%;
background:#3fb950;border:2px solid #161b22;display:none}
.btn-rond.on .point{display:block}
.mini-lib{font-size:10px;color:#6e7681;letter-spacing:.2px;font-variant-numeric:tabular-nums}
.anneau{position:relative;width:54px;height:54px}
.anneau svg{transform:rotate(-90deg)}
.anneau .pctq{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;
font-size:12.5px;font-weight:700;font-variant-numeric:tabular-nums}
.on{color:#3fb950}
.flash{animation:flash 1.4s ease-out}
.news{background:#161b22;border:1px solid #30363d;border-radius:10px;padding:14px 16px;margin:0 0 18px;display:grid;grid-template-columns:1fr 1fr;gap:16px}
@media(max-width:800px){.news{grid-template-columns:1fr}}
.news h3{font-size:12px;color:#8b949e;text-transform:uppercase;letter-spacing:.6px;margin-bottom:8px}
.evt{display:flex;justify-content:space-between;gap:10px;font-size:13px;padding:5px 0;border-bottom:1px solid #21262d}
.evt:last-child{border-bottom:none}
.evt .t{color:#c9d1d9}.evt .q{color:#8b949e;white-space:nowrap;font-variant-numeric:tabular-nums}
.risque{padding:8px 12px;border-radius:6px;font-size:13px;margin-bottom:10px}
.risque.veto{background:#3d1d1d;color:#ffa198;border-left:3px solid #f85149}
.risque.reserve{background:#3a2e12;color:#e3b341;border-left:3px solid #d29922}
.risque.ok{background:#12341f;color:#3fb950;border-left:3px solid #238636}
.risque.inconnu{background:#21262d;color:#8b949e;border-left:3px solid #8b949e}
.macrol{font-size:13px;color:#c9d1d9;padding:4px 0}
.macrol b{font-variant-numeric:tabular-nums}
.haut-page{display:grid;grid-template-columns:340px 1fr;gap:18px;margin:0 0 18px}
@media(max-width:900px){.haut-page{grid-template-columns:1fr}}
.boule{background:#161b22;border:1px solid #30363d;border-radius:10px;padding:18px;display:flex;flex-direction:column;align-items:center;gap:10px}
.boule h3{font-size:12px;color:#8b949e;text-transform:uppercase;letter-spacing:.6px;align-self:flex-start}
.verdict-b{font-size:20px;font-weight:700}
.verdict-b.h{color:#3fb950}.verdict-b.b{color:#f85149}.verdict-b.n{color:#d29922}
.legende{display:flex;gap:16px;font-size:12.5px;color:#c9d1d9}
.legende i{display:inline-block;width:9px;height:9px;border-radius:50%;margin-right:5px}
.contribs{width:100%;font-size:11.5px;color:#8b949e;max-height:150px;overflow-y:auto;border-top:1px solid #21262d;padding-top:8px}
.contribs div{display:flex;justify-content:space-between;padding:2px 0}
.tv-cadre{background:#161b22;border:1px solid #30363d;border-radius:10px;overflow:hidden;min-height:460px}
.tv-cadre h3{font-size:12px;color:#8b949e;text-transform:uppercase;letter-spacing:.6px;padding:14px 16px 0}
.onglets{display:flex;gap:8px;margin:0 0 14px;flex-wrap:wrap}
.onglet{background:#21262d;color:#c9d1d9;border:1px solid #30363d;border-radius:8px;padding:9px 18px;font-size:13.5px;cursor:pointer;font-family:inherit;font-weight:600}
.onglet.actif{background:#1f6feb;border-color:#1f6feb;color:#fff}
.panneau{display:none}.panneau.actif{display:block}
.tf-btns{display:flex;gap:6px;margin:0 0 10px}
.tf-btn{background:#21262d;color:#c9d1d9;border:1px solid #30363d;border-radius:6px;padding:5px 14px;font-size:12.5px;cursor:pointer;font-family:inherit}
.tf-btn.actif{background:#238636;border-color:#238636;color:#fff}
.grand-chart{display:none;background:#161b22;border:1px solid #30363d;border-radius:10px;padding:12px}
.grand-chart.actif{display:block}
.strats{background:#161b22;border:1px solid #30363d;border-radius:10px;padding:16px;overflow-x:auto}
.strats table{width:100%;border-collapse:collapse;font-size:13px}
.strats th{text-align:left;color:#8b949e;font-size:11px;text-transform:uppercase;letter-spacing:.5px;padding:6px 10px;border-bottom:1px solid #30363d}
.strats td{padding:7px 10px;border-bottom:1px solid #21262d;color:#c9d1d9;font-variant-numeric:tabular-nums}
.strats .ok{color:#3fb950}.strats .ko{color:#f85149}
.jauge-tf{position:relative;width:44px;height:44px;flex-shrink:0}
.jauge-tf svg{transform:rotate(-90deg)}
.jauge-tf span{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;font-size:11px;font-weight:700;font-variant-numeric:tabular-nums}
.ict-ligne{font-size:12px;color:#8b949e;padding:6px 0;border-top:1px solid #21262d;margin-top:8px}
.ict-ligne b{color:#c9d1d9}
.cerveau{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:12px}
.ag{background:#161b22;border:1px solid #30363d;border-radius:10px;padding:14px}
.ag h4{font-size:13.5px;color:#e6edf3;display:flex;align-items:center;gap:8px}
.ag .pt{width:9px;height:9px;border-radius:50%;flex-shrink:0}
.ag .pt.ok{background:#3fb950}.ag .pt.ko{background:#f85149}
.ag p{font-size:12px;color:#8b949e;margin-top:4px}
.superviseur{grid-column:1/-1;background:#161b22;border:1px solid #30363d;border-left:3px solid #1f6feb;border-radius:10px;padding:14px;font-size:13px;color:#c9d1d9}
.sys{display:grid;grid-template-columns:1fr 340px;gap:14px;margin-bottom:16px}
@media(max-width:1000px){.sys{grid-template-columns:1fr}}
.ag-grille{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:12px}
.agc{background:#0e1524;border:1px solid #1f2b45;border-radius:10px;padding:12px 14px;position:relative;overflow:hidden}
.agc .code{position:absolute;top:8px;right:10px;font-size:10px;color:#4a5878;font-family:monospace}
.agc h4{display:flex;align-items:center;gap:8px;font-size:14.5px;letter-spacing:.3px}
.agc .ico{width:30px;height:30px;border-radius:7px;display:flex;align-items:center;justify-content:center;font-size:15px;background:#0d1117;border:1px solid currentColor}
.agc .rl{font-size:11px;color:#8b949e;margin:2px 0 8px 38px}
.chip{font-size:9.5px;font-weight:700;letter-spacing:1px;border:1px solid currentColor;border-radius:4px;padding:2px 7px;margin-left:auto;animation:pulse-chip 1.6s infinite}
@keyframes pulse-chip{50%{opacity:.45}}
.barp{height:4px;background:#1a2440;border-radius:99px;overflow:hidden;margin:6px 0 8px}
.barp i{display:block;height:100%;width:40%;border-radius:99px;background:currentColor;animation:flux 2.2s ease-in-out infinite}
@keyframes flux{0%{margin-left:-40%}100%{margin-left:100%}}
.act{font-size:12px;color:#c9d1d9;min-height:34px;font-family:ui-monospace,monospace;line-height:1.45}
.act .lg{display:none}.act .lg.on{display:block}
.agc .pied{display:flex;justify-content:space-between;align-items:center;margin-top:8px;font-size:10.5px;color:#6e7681;border-top:1px solid #1a2440;padding-top:7px}
.mini-conv{display:flex;align-items:center;gap:5px;font-variant-numeric:tabular-nums}
.console{background:#05080f;border:1px solid #1f2b45;border-radius:10px;padding:10px 12px;font-family:ui-monospace,monospace;font-size:11px;line-height:1.6;overflow-y:auto;max-height:520px}
.console h5{color:#4a5878;font-size:10px;letter-spacing:1.5px;margin-bottom:6px}
.cl{color:#8b949e;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.cl b{color:#58a6ff;font-weight:600}
.cl.signal{color:#3fb950}.cl.veto{color:#f85149}.cl.alerte{color:#d29922}
.tf-nav{display:flex;gap:8px;margin:0 0 12px;flex-wrap:wrap}
.tfb{position:relative;background:#21262d;color:#c9d1d9;border:1px solid #30363d;border-radius:8px;
padding:10px 22px;font-size:14px;font-weight:700;cursor:pointer;font-family:inherit}
.tfb.actif{background:#1f6feb;border-color:#1f6feb;color:#fff}
.tfb .bip{position:absolute;top:-5px;right:-5px;min-width:17px;height:17px;border-radius:99px;
background:#f85149;color:#fff;font-size:10px;display:flex;align-items:center;justify-content:center;
padding:0 4px;border:2px solid #0d1117;animation:pulse-chip 1.2s infinite}
.tfb .bip.ok{background:#3fb950}
.carte[data-tf]{display:none}.carte[data-tf].vue{display:flex}
.convs{grid-column:1/-1;display:flex;gap:18px;flex-wrap:wrap;background:#0e1524;border:1px solid #1f2b45;border-radius:10px;padding:12px 16px;margin-bottom:14px}
.convs .cvx{display:flex;flex-direction:column;align-items:center;gap:3px;font-size:10px;color:#8b949e}
.var{font-size:15px;font-weight:600;font-variant-numeric:tabular-nums}
.var.hausse{color:#3fb950}.var.baisse{color:#f85149}
.direct{font-size:11.5px;color:#6e7681}
.direct .vif{color:#3fb950}
.quota{display:flex;align-items:center;gap:10px;font-size:12.5px;color:#8b949e}
.jauge{width:120px;height:6px;background:#21262d;border-radius:99px;overflow:hidden}
.jauge span{display:block;height:100%;background:#3fb950;transition:width .4s}
.jauge span.moyen{background:#d29922}.jauge span.haut{background:#f85149}
@keyframes flash{0%{box-shadow:0 0 0 0 rgba(47,129,247,.7)}100%{box-shadow:0 0 0 22px rgba(47,129,247,0)}}
button{background:#21262d;color:#c9d1d9;border:1px solid #30363d;border-radius:6px;padding:7px 14px;font-size:13px;cursor:pointer;font-family:inherit}
button:hover{background:#30363d}
"""


PAGE_CONNEXION = """<!doctype html><html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Or — Connexion</title><style>*{box-sizing:border-box;margin:0;padding:0}
body{background:radial-gradient(ellipse at top,#141b26 0%,#0d1117 55%);color:#e6edf3;
font:15px/1.5 -apple-system,sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh;padding:20px}
.carte{background:#161b22;border:1px solid #30363d;border-radius:14px;padding:36px;width:380px;box-shadow:0 20px 60px rgba(0,0,0,.45)}
.logo{display:flex;align-items:center;gap:12px;margin-bottom:6px}
.rond{width:40px;height:40px;border-radius:50%;background:conic-gradient(#3fb950 0 62%,#f85149 62% 100%);
display:flex;align-items:center;justify-content:center;font-weight:800;color:#0d1117;font-size:13px}
h1{font-size:20px}
.sous{color:#e3b341;font-size:12.5px;letter-spacing:.4px;margin-bottom:22px}
label{display:block;font-size:12.5px;color:#8b949e;margin:13px 0 5px}
input{width:100%;background:#0d1117;border:1px solid #30363d;border-radius:7px;color:#e6edf3;padding:10px 12px;font-size:14px}
input:focus{outline:none;border-color:#e3b341}
button{width:100%;margin-top:22px;background:#e3b341;color:#1c1c1c;border:none;border-radius:7px;
padding:11px;font-size:14px;font-weight:700;cursor:pointer}
button:hover{background:#f0c65a}
.err{background:#3d1d1d;border:1px solid #b62324;color:#ffa198;border-radius:7px;padding:9px 12px;font-size:13px;margin-bottom:14px}
.note{margin-top:18px;font-size:11.5px;color:#6e7681;line-height:1.6}
.alerte{margin-top:14px;background:#3a2e12;border-left:3px solid #d29922;border-radius:6px;padding:9px 12px;font-size:12px;color:#e3b341;line-height:1.5}</style></head><body>
<form class="carte" method="POST" action="/connexion">
<div class="logo"><div class="rond">OR</div><h1>Tableau de bord Or</h1></div>
<div class="sous">XAU/USD · analyse multi-timeframe · signaux mesurés</div>
{erreur}
<label>Adresse e-mail</label>
<input name="nom" type="email" autocomplete="username" placeholder="toi@gmail.com" autofocus required>
<label>Mot de passe</label>
<input name="motdepasse" type="password" autocomplete="current-password" required>
<button>Se connecter</button>
<div class="note">Session privée sur cette machine (127.0.0.1). Mot de passe stocké
uniquement en condensé scrypt salé — jamais en clair. 5 échecs = blocage temporaire.</div>
</form></body></html>"""


PAGE_CREATION = """<!doctype html><html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Or — Créer le compte</title><style>*{box-sizing:border-box;margin:0;padding:0}
body{background:radial-gradient(ellipse at top,#141b26 0%,#0d1117 55%);color:#e6edf3;
font:15px/1.5 -apple-system,sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh;padding:20px}
.carte{background:#161b22;border:1px solid #30363d;border-radius:14px;padding:36px;width:380px;box-shadow:0 20px 60px rgba(0,0,0,.45)}
.logo{display:flex;align-items:center;gap:12px;margin-bottom:6px}
.rond{width:40px;height:40px;border-radius:50%;background:conic-gradient(#3fb950 0 62%,#f85149 62% 100%);
display:flex;align-items:center;justify-content:center;font-weight:800;color:#0d1117;font-size:13px}
h1{font-size:20px}
.sous{color:#e3b341;font-size:12.5px;letter-spacing:.4px;margin-bottom:22px}
label{display:block;font-size:12.5px;color:#8b949e;margin:13px 0 5px}
input{width:100%;background:#0d1117;border:1px solid #30363d;border-radius:7px;color:#e6edf3;padding:10px 12px;font-size:14px}
input:focus{outline:none;border-color:#e3b341}
button{width:100%;margin-top:22px;background:#e3b341;color:#1c1c1c;border:none;border-radius:7px;
padding:11px;font-size:14px;font-weight:700;cursor:pointer}
button:hover{background:#f0c65a}
.err{background:#3d1d1d;border:1px solid #b62324;color:#ffa198;border-radius:7px;padding:9px 12px;font-size:13px;margin-bottom:14px}
.note{margin-top:18px;font-size:11.5px;color:#6e7681;line-height:1.6}
.alerte{margin-top:14px;background:#3a2e12;border-left:3px solid #d29922;border-radius:6px;padding:9px 12px;font-size:12px;color:#e3b341;line-height:1.5}</style></head><body>
<form class="carte" method="POST" action="/creer">
<div class="logo"><div class="rond">OR</div><h1>Bienvenue</h1></div>
<div class="sous">Première utilisation — crée le compte administrateur</div>
{erreur}
<label>Adresse e-mail (ton identifiant)</label>
<input name="nom" type="email" autocomplete="username" placeholder="toi@gmail.com" autofocus required>
<label>Mot de passe (10 caractères minimum)</label>
<input name="motdepasse" type="password" autocomplete="new-password" minlength="10" required>
<label>Confirme le mot de passe</label>
<input name="motdepasse2" type="password" autocomplete="new-password" minlength="10" required>
<button>Créer le compte et protéger le site</button>
<div class="alerte">N'utilise JAMAIS ton vrai mot de passe Google ici. Choisis un mot
de passe dédié à ce site — ton adresse Gmail ne sert que d'identifiant.</div>
<div class="note">Dès la création, tout accès au site exigera cette connexion.</div>
</form></body></html>"""


