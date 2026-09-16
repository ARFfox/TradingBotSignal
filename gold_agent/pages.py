"""Feuille de style et pages d'authentification du tableau de bord.

Separe de web.py (regle 17 : aucun fichier > 500 lignes).
"""

# Le theme complet vit dans theme.py (maquette.html est la source, 8.7)
from .theme import CSS  # noqa: F401  (reexporte pour rendu.py)


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




# JavaScript de navigation (SPEC_SITE_V3 §2-§5). Constante BRUTE, jamais
# interpolee dans une f-string : pleine d'accolades.
NAV_JS = r"""
(() => {
  // --- theme : le CLAIR est le defaut demande (8.7) ; le choix persiste --
  const racine = document.documentElement;
  const btTheme = document.getElementById('bt-theme');
  let theme = 'light';
  try { theme = localStorage.getItem('theme') || 'light'; } catch (e) {}
  const majTheme = t => {
    racine.setAttribute('data-theme', t);
    if (btTheme) btTheme.textContent = t === 'dark' ? '◐ thème clair' : '◐ thème sombre';
    try { localStorage.setItem('theme', t); } catch (e) {}
  };
  majTheme(theme);
  if (btTheme) btTheme.onclick = () => {
    theme = racine.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
    majTheme(theme);
    try { majGraphique(INSTRUMENTS[window.INSTRUMENT_ACTIF]); } catch (e) {}
  };

  const bloc = document.getElementById('donnees-instruments');
  if (!bloc) return;
  const D = JSON.parse(bloc.textContent);
  const INSTRUMENTS = D.instruments, SIGNAUX = D.signaux;
  const TV_INT = {H4:'240', H1:'60', M30:'30', M15:'15', M5:'5'};
  let TF_ACTIF = '30', WS = null;
  window.INSTRUMENT_ACTIF = 'XAUUSD';

  // §4 : les pastilles DERIVENT toutes de la meme liste, par calcul —
  // elles comptent les signaux EN COURS, jamais l'historique (8.5).
  const badgeMarche = m => SIGNAUX.filter(s => s.marche === m).length;
  const badgeInstrument = c => SIGNAUX.filter(s => s.instrument === c).length;
  document.querySelectorAll('.m-btn').forEach(b => {
    const n = badgeMarche(b.dataset.m);
    if (n) { const e = b.querySelector('.pastille'); e.textContent = n; e.hidden = false; }
    b.onclick = () => document.querySelectorAll('.m-grille').forEach(g =>
      g.hidden = (g.id !== 'mg2-' + b.dataset.m) || !g.hidden);
  });
  document.querySelectorAll('.tuile-inst').forEach(t => {
    const n = badgeInstrument(t.dataset.cle);
    if (n) { const e = t.querySelector('.pastille'); e.textContent = n; e.hidden = false; }
    t.onclick = () => location.hash = '#/' + t.dataset.m + '/' + t.dataset.cle;
  });

  // §3 : recreer le widget = changer la source de l'iframe. setSymbol se
  // comporte mal quand l'intervalle change en meme temps.
  function majGraphique(inst) {
    const f = document.getElementById('tv-iframe');
    if (!f || !inst) return;
    const th = racine.getAttribute('data-theme') === 'dark' ? 'dark' : 'light';
    f.src = 'https://s.tradingview.com/widgetembed/?symbol='
      + encodeURIComponent(inst.tv) + '&interval=' + TF_ACTIF
      + '&theme=' + th + '&style=1&locale=fr&hide_side_toolbar=0'
      + '&allow_symbol_change=0&timezone=Etc%2FUTC';
  }
  function fermerFlux() { if (WS) { try { WS.close(); } catch (e) {} WS = null; } }

  function majEnTete(inst) {
    document.getElementById('titre-inst').textContent = inst.libelle;
    const gp = document.getElementById('grand-prix');
    const va = document.getElementById('variation');
    const src = document.getElementById('source-prix');
    fermerFlux();
    if (inst.cle === 'XAUUSD') { if (src) src.textContent = ''; return; }
    if (inst.prix != null) gp.textContent = inst.prix.toFixed(inst.decimales);
    if (inst.variation_pct != null) {
      va.textContent = (inst.variation_pct >= 0 ? '+' : '') + inst.variation_pct.toFixed(2) + '%';
      va.className = 'var ' + (inst.variation_pct >= 0 ? 'hausse' : 'baisse');
    }
    if (inst.binance) {
      // crypto : temps reel gratuit, un seul flux a la fois (§3)
      if (src) src.textContent = 'connexion Binance…';
      try {
        WS = new WebSocket('wss://stream.binance.com:9443/ws/'
                           + inst.binance.toLowerCase() + '@miniTicker');
        WS.onmessage = ev => {
          const t = JSON.parse(ev.data);
          gp.textContent = parseFloat(t.c).toFixed(inst.decimales);
          const v = (parseFloat(t.c) / parseFloat(t.o) - 1) * 100;
          va.textContent = (v >= 0 ? '+' : '') + v.toFixed(2) + '%';
          va.className = 'var ' + (v >= 0 ? 'hausse' : 'baisse');
          if (src) src.textContent = 'prix en direct (Binance)';
        };
        WS.onerror = () => { if (src) src.textContent = 'différé (cache 6 h)'; };
      } catch (e) { if (src) src.textContent = 'différé (cache 6 h)'; }
    } else if (src) src.textContent = 'différé (cache 6 h)';
    // Bug 1 (16/09) : l'ancien bandeau « l'analyse reste celle de XAU/USD »
    // etait perime et mentait — la grille analyse bien l'instrument clique.
    // Un bandeau faux apprend a ne plus lire les bandeaux : supprime.
    const note = document.getElementById('note-instrument');
    if (note) note.hidden = true;
  }

  // 8.2 : la fiche par instrument — deux blocs (stats+timeframes en haut,
  // onglets d'historique en bas), calcules par vue_instrument.
  function placerRisque() {
    const hote = document.getElementById('hote-risque');
    const bloc = document.getElementById('bloc-risque');
    if (hote && bloc) { hote.appendChild(bloc); bloc.hidden = false; }
  }
  function majFiche(cle) {
    const haut = document.getElementById('fiche-haut');
    const bas = document.getElementById('fiche-bas');
    if (!haut || !bas) return;
    haut.dataset.cle = cle;
    fetch('/api/instrument/' + cle, {cache: 'no-store'})
      .then(r => r.json())
      .then(d => {
        if (haut.dataset.cle !== cle) return;
        // le bloc Risque vit dans l'onglet 3 : on le sort avant d'ecraser
        const risque = document.getElementById('bloc-risque');
        if (risque) { risque.hidden = true; document.body.appendChild(risque); }
        haut.innerHTML = d.html_haut || '';
        bas.innerHTML = d.html_bas || '';
        placerRisque();
        const ch = document.getElementById('chapeau-signal');
        if (ch) ch.textContent = (d.tf_signal && d.tf_signal.length)
          ? '🔴 ' + d.tf_signal.length + ' signal(aux) sur ' + d.tf_signal.join(', ') : '';
        window.appliquerTf && window.appliquerTf();
      })
      .catch(() => {});
  }
  placerRisque();

  // Onglets de la fiche + filtres — par DELEGATION : le contenu est
  // reinjecte a chaque changement d'instrument.
  document.addEventListener('click', e => {
    const o = e.target.closest('#onglets-fiche .onglet');
    if (o) {
      document.querySelectorAll('#onglets-fiche .onglet').forEach(x =>
        x.classList.toggle('actif', x === o));
      ['pf1', 'pf2', 'pf3'].forEach(id => {
        const p = document.getElementById(id);
        if (p) p.classList.toggle('actif', id === o.dataset.pf);
      });
      return;
    }
    const puce = e.target.closest('.puce');
    if (puce) {
      const panneau = puce.closest('.panneau');
      panneau.querySelectorAll('.puce').forEach(x =>
        x.setAttribute('aria-pressed', x === puce));
      const ftf = puce.dataset.ftf, fet = puce.dataset.fet;
      panneau.querySelectorAll('tbody tr').forEach(tr => {
        let ok = true;
        if (ftf && ftf !== 'TOUS') ok = tr.dataset.tf === ftf;
        if (fet && fet !== 'TOUS')
          ok = (fet === 'resolu') ? (tr.dataset.etat === 'TP' || tr.dataset.etat === 'SL')
                                  : tr.dataset.etat === fet;
        tr.style.display = ok ? '' : 'none';
      });
    }
  });

  // §2 : un seul etat, dans le hash — retour navigateur et lien partageable.
  function appliquerHash() {
    const p = location.hash.split('/');
    if (p.length < 3) return;
    const inst = INSTRUMENTS[p[2]];
    if (!inst) return;
    window.INSTRUMENT_ACTIF = inst.cle;
    majEnTete(inst); majGraphique(inst);
    majAnalyse(inst); majFiche(inst.cle);
    document.querySelectorAll('.tuile-inst').forEach(t =>
      t.classList.toggle('actif', t.dataset.cle === inst.cle));
    if (inst.cle === 'XAUUSD') {
      const note = document.getElementById('note-instrument');
      if (note) note.hidden = true;
    }
  }
  let ANALYSE_EN_COURS = null;
  function majAnalyse(inst) {
    const grille = document.querySelector('.grille');
    if (!grille) return;
    if (inst.cle === 'XAUUSD') {
      // retour a l'or : le rafraichissement normal reprend la main
      if (window.rafraichir) rafraichir(true);
      return;
    }
    grille.innerHTML = '<div class="bandeau">Analyse de ' + inst.libelle
      + ' en cours (données ' + (inst.binance ? 'Binance' : 'Yahoo, différées')
      + ')…</div>';
    const jeton = inst.cle;
    ANALYSE_EN_COURS = jeton;
    fetch('/api/instruments/' + jeton, {cache: 'no-store'})
      .then(r => r.json())
      .then(d => {
        if (ANALYSE_EN_COURS !== jeton || window.INSTRUMENT_ACTIF !== jeton) return;
        grille.innerHTML = d.html || ('<div class="bandeau">analyse indisponible : '
                                      + (d.erreur || '?') + '</div>');
      })
      .catch(() => {
        if (window.INSTRUMENT_ACTIF === jeton)
          grille.innerHTML = '<div class="bandeau">analyse indisponible (réseau)</div>';
      });
  }

  addEventListener('hashchange', appliquerHash);
  if (location.hash) appliquerHash();
  else majFiche('XAUUSD');   // l'or est l'instrument par defaut : sa fiche aussi

  // §5 : un clic timeframe met aussi a jour l'intervalle TradingView.
  document.addEventListener('click', e => {
    const b = e.target.closest('.tfx');
    if (!b || !b.dataset.tf || !TV_INT[b.dataset.tf]) return;
    TF_ACTIF = TV_INT[b.dataset.tf];
    majGraphique(INSTRUMENTS[window.INSTRUMENT_ACTIF] || INSTRUMENTS['XAUUSD']);
  });
  // premier chargement : le cadre TradingView suit le theme choisi
  majGraphique(INSTRUMENTS['XAUUSD']);
})();
"""
