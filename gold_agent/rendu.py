"""Assemblage de la page complete et surveillance des signaux.

Separe de web.py (regle 17) : web.py garde le serveur HTTP, ce module
garde le rendu et la boucle de notification.
"""
from __future__ import annotations

import threading
import time
from datetime import datetime

from . import config as _cfg, datasource as ds, notify, tableau
from .blocs import (_boule, _carte, _fragment_graphe, _grille,
                    _panneau_agents, WIDGET_TV)
from .cerveau_js import CERVEAU_JS  # noqa: F401
from .onglets import _bloc_constellation, _bloc_marches, _blocs_onglets
from .pages import CSS


def rendre(d: dict) -> str:
    gen = datetime.fromisoformat(d["genere_le"]).astimezone()
    cartes = _grille(d)

    # Valeurs rendues cote serveur : sans cela, variation et quota restent
    # vides jusqu'au premier sondage, 30 s apres l'ouverture de la page.
    q = d.get("quote") or {}
    v = q.get("variation_pct")
    var_txt = f"{v:+.2f}%" if v is not None else ""
    var_cls = "hausse" if (v or 0) >= 0 else "baisse"
    age = q.get("age", 0)
    frais = ('<span class="vif">prix en direct</span>' if age <= 20
             else f"prix il y a {age}s") if q else ""

    _onglets = _blocs_onglets(d)
    bloc_news, bloc_graph = _onglets["news"], _onglets["graph"]
    bloc_strats, bloc_histo = _onglets["strats"], _onglets["histo"]
    boule, widget = _onglets["boule"], _onglets["widget"]
    bloc_constel = _bloc_constellation(d)
    bloc_marches = _bloc_marches(d)

    sa = d.get("sante") or {}
    ags = ""
    for a in sa.get("agents", []):
        pt = "ok" if a["ok"] else "ko"
        clic = (f''' onclick="allerOnglet('{a["cible"]}')" style="cursor:pointer"'''
                if a.get("cible") else "")
        emo = a.get("emoji", "")
        ags += (f'<div class="ag"{clic}><h4><span class="pt {pt}"></span>{emo} {a["nom"]}</h4>'
                f'<p>{a["role"]}</p><p>Source : {a["source"]}</p><p>{a["detail"]}</p></div>')
    probs = sa.get("problemes", [])
    diag = ("<b>Superviseur — problèmes détectés :</b><br>" + "<br>".join(f"• {x}" for x in probs))         if probs else "<b>Superviseur :</b> tous les agents répondent, aucun problème détecté."
    reps = sa.get("reparations") or []
    if reps:
        boutons = "".join(
            f'<button class="tf-btn" style="margin:4px 6px 0 0" '
            f'onclick="reparer(&#39;{r["action"]}&#39;, this)" '
            f'title="{r["contexte"]}">&#128295; {r["libelle"]}</button>'
            for r in reps)
        diag += f'<br><br><b>Corrections disponibles</b> (liste blanche, un clic) :<br>{boutons}'
    tfs_on = ", ".join(sa.get("tf_emission") or []) or "aucun"
    diag += (f'<br><br><span style="color:#8b949e;font-size:12px">Timeframes émetteurs : '
             f'<b style="color:#c9d1d9">{tfs_on}</b> — fondé sur les backtests '
             f'(H4 +0,76R · H1 +0,52R · M30 +0,63R ; M15 ~0R et creux −11R : coupé ; '
             f'M5 : 17 j de données, coupé)</span>')

    recos = sa.get("recommandations") or []
    if recos:
        diag += ('<br><br><b>Recommandations</b> (à mesurer avant application — le système '
                 'ne se modifie jamais seul) :<br>' + "<br>".join(f"→ {x}" for x in recos))
    import json as _json
    EMO = {"AG-01": "📡", "AG-02": "📈", "AG-03": "♟️", "AG-04": "✏️",
           "AG-05": "⛏️", "AG-06": "🎲", "AG-07": "💡", "AG-00": "🧠",
           "AG-09": "🌌", "AG-10": "🪞", "AG-16": "😈", "AG-11": "💱",
           "AG-12": "🪙", "AG-13": "🥇", "AG-14": "📊", "AG-15": "🕸️"}
    donnees_cerveau = _json.dumps({"agents": [
        {"nom": a["nom"], "ok": True, "detail": a["activites"][0][:80],
         "emoji": EMO.get(a["code"], "🤖"), "cible": None, "coul": a["coul"]}
        for a in (d.get("agents") or []) if a["code"] != "AG-00"]}, ensure_ascii=False)
    canvas = (f'<div style="background:#0d1117;border:1px solid #30363d;border-radius:10px;'
              f'margin-bottom:14px;overflow:hidden;position:relative">'
              f'<button id="btn-rotation" class="tf-btn" '
              f'style="position:absolute;top:10px;right:10px;z-index:2">&#9208; figer</button>'
              f'<div style="position:absolute;top:12px;left:14px;font-size:11.5px;color:#6e7681">'
              f'clique un agent pour ouvrir sa page</div>'
              f'<canvas id="cerveau3d" style="width:100%;height:440px;display:block"></canvas></div>'
              f'<script id="donnees-cerveau" type="application/json">{donnees_cerveau}</script>'
              f'<script src="/cerveau.js" defer></script>')
    panneau = _panneau_agents(d)
    # Anciennes cartes + bloc superviseur retires : les agents live couvrent
    # tout, et le superviseur notifie ses corrections.
    bloc_cerveau = (panneau
                    + '<div style="font-size:11px;color:#6e7681;margin:10px 0 6px">'
                      'Le réseau des agents — tout ce qui est visible est mesuré '
                      'à l&#39;instant du rendu (taille = conviction, rouge animé = blocage, '
                      'gris = agent muet) :</div>'
                    + _fragment_graphe()
                    + '<div style="font-size:11px;color:#6e7681;margin:14px 0 6px">'
                      'Démonstration — les agents et leurs liaisons en 3D :</div>'
                    + canvas)

    u = d.get("usage") or {}
    if u.get("limite"):
        pct_rest = max(0.0, 100.0 - (u.get("part_pct") or 0))
        anneau_coul = "#3fb950" if pct_rest > 40 else ("#d29922" if pct_rest > 15 else "#f85149")
        anneau_arc = 144.5 * pct_rest / 100          # circonference r=23
        quota_pct_txt = f"{pct_rest:.0f}%"
        quota_detail = f"{u['restant']} / {u['limite']}"
    else:
        anneau_coul, anneau_arc, quota_pct_txt, quota_detail = "#8b949e", 0.0, "—", "quota inconnu"
    return f"""<!doctype html><html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Or — Tableau de bord</title><style>{CSS}</style></head><body><div class="wrap">
<header><h1>XAU/USD</h1><div class="prix">{d.get('prix') or '—'}</div>
<div class="var {var_cls}" id="variation">{var_txt}</div>
<div class="meta"><span class="pastille" id="pastille"></span><span id="horodatage">{gen:%d/%m/%Y %H:%M:%S}</span>
 · <span id="compte">{d['nb_setups']}</span> signal(aux) actif(s)
 · <span class="direct" id="fraicheur">{frais}</span></div>
<div class="barre">
<div class="rondelle" id="quota" title="quota Twelve Data restant aujourd'hui">
  <div class="anneau">
    <svg width="54" height="54" viewBox="0 0 54 54">
      <circle cx="27" cy="27" r="23" fill="none" stroke="#21262d" stroke-width="5"/>
      <circle id="anneau-quota" cx="27" cy="27" r="23" fill="none" stroke="{anneau_coul}"
        stroke-width="5" stroke-linecap="round" stroke-dasharray="{anneau_arc:.1f} 144.5"/>
    </svg>
    <span class="pctq" id="quota-pct" style="color:{anneau_coul}">{quota_pct_txt}</span>
  </div>
  <span class="mini-lib" id="quota-detail">{quota_detail}</span>
</div>
<div class="rondelle"><button class="btn-rond" onclick="rafraichir(true)" title="Actualiser maintenant">
  <svg viewBox="0 0 24 24"><path d="M21 12a9 9 0 1 1-2.6-6.4M21 3v6h-6"/></svg></button>
  <span class="mini-lib">dans <span id="compteur">10</span>s</span></div>
<div class="rondelle"><button class="btn-rond" id="btn-notif" title="Notifications du navigateur">
  <svg viewBox="0 0 24 24"><path d="M18 8a6 6 0 0 0-12 0c0 7-3 9-3 9h18s-3-2-3-9M13.7 21a2 2 0 0 1-3.4 0"/></svg>
  <span class="point"></span></button>
  <span class="mini-lib" id="notif-etat">notifs</span></div>
<div class="rondelle"><button class="btn-rond" onclick="allerOnglet('p-cerveau')"
  title="Cerveau — agents, santé, superviseur" style="font-size:19px">&#129504;</button>
  <span class="mini-lib">cerveau</span></div>
<div class="rondelle"><a class="btn-rond" href="/deconnexion" title="Déconnexion">
  <svg viewBox="0 0 24 24"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9"/></svg></a>
  <span class="mini-lib">sortie</span></div>
</div></header>
<div class="bandeau"><b>Sortie mécanique d'une règle, pas une recommandation.</b>
Les niveaux découlent des paramètres de la règle : support confirmé = entrée, −1&nbsp;ATR = stop,
première résistance = objectif. Le badge de chaque carte indique ce que le backtest a réellement
mesuré sur ce timeframe. Un signal «&nbsp;non mesuré&nbsp;» n'a aucune preuve derrière lui.</div>
<div class="haut-page">{boule}{widget}</div>
<div class="onglets">
<button class="onglet actif" data-p="p-risque">Risque événementiel</button>
<button class="onglet" data-p="p-graph">Analyse graphique</button>
<button class="onglet" data-p="p-strats">Stratégies</button>
<button class="onglet" data-p="p-histo">Historique</button>
<button class="onglet" data-p="p-constel">Constellation</button>
<button class="onglet" data-p="p-marches">Marchés</button>
</div>
<div id="p-risque" class="panneau actif">{bloc_news}</div>
<div id="p-graph" class="panneau">{bloc_graph}</div>
<div id="p-strats" class="panneau">{bloc_strats}</div>
<div id="p-histo" class="panneau">{bloc_histo}</div>
<div id="p-constel" class="panneau">{bloc_constel}</div>
<div id="p-marches" class="panneau">{bloc_marches}</div>
<div id="p-cerveau" class="panneau">{bloc_cerveau}</div>
<div class="grille">{cartes}</div>
<footer>
<span id="etat-cles"></span>Données Twelve Data · filtres : RSI max 70 à l'achat,
RSI min 30 à la vente, R:R minimum 1,5, contexte du timeframe supérieur.<br>
Le côté vendeur reste non validé (5&nbsp;trades d'historique, espérance négative).
Résultats hors spread réel et glissement. Aucun ordre n'est passé.
</footer></div>
<script>
const INTERVALLE = 3;              // secondes entre deux controles
let restant = INTERVALLE, enCours = false;
let connus = new Set();             // signaux deja notifies
let sonActif = true;

// Identite d'un signal : notifier une fois par configuration, pas a chaque
// sondage. Le prix d'entree fait partie de la cle — si la regle deplace son
// niveau, c'est un nouveau signal.
const cle = s => `${{s.tf}}|${{s.sens}}|${{s.entree}}|${{s.declenche}}`;

function bip() {{
  if (!sonActif) return;
  try {{
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    const o = ctx.createOscillator(), g = ctx.createGain();
    o.connect(g); g.connect(ctx.destination);
    o.frequency.value = 880; o.type = "sine";
    g.gain.setValueAtTime(0.0001, ctx.currentTime);
    g.gain.exponentialRampToValueAtTime(0.25, ctx.currentTime + 0.02);
    g.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + 0.5);
    o.start(); o.stop(ctx.currentTime + 0.5);
  }} catch (e) {{}}
}}

function notifier(s) {{
  const etat = s.declenche ? "DÉCLENCHÉ" : "en attente";
  const titre = `${{s.sens.toUpperCase()}} ${{s.tf}} — ${{etat}}`;
  const corps = `Entrée ${{s.entree}} · Stop ${{s.stop}} · TP ${{s.objectif}} · R:R ${{s.rr}}`
              + `\nFiabilité : ${{s.fiabilite}}`;
  if (window.Notification && Notification.permission === "granted") {{
    new Notification(titre, {{ body: corps, tag: cle(s), requireInteraction: s.declenche }});
  }}
  bip();
  document.title = `(${{s.sens === "achat" ? "▲" : "▼"}}) ${{s.tf}} — XAU/USD`;
}}

async function rafraichir(manuel) {{
  if (enCours) return;
  enCours = true;
  document.getElementById("pastille").classList.add("charge");
  try {{
    const r = await fetch("/json", {{ cache: "no-store" }});
    const d = await r.json();
    if (d.erreur) throw new Error(d.erreur);

    document.querySelector(".grille").innerHTML = d.html;
    window.appliquerTf && window.appliquerTf();
    if (d.boule) document.querySelector(".boule").outerHTML = d.boule;
    if (d.sante && window.majCerveau) window.majCerveau(d.sante);
    if (d.sys_agents) {{
      const sys = document.getElementById("sys-agents");
      if (sys) {{ const sc = sys.querySelector(".console"); const pos = sc ? sc.scrollTop : 0;
        sys.outerHTML = d.sys_agents;
        const nc = document.querySelector("#sys-agents .console");
        if (nc) nc.scrollTop = nc.scrollHeight; }}
    }}
    document.querySelector(".prix").textContent = d.prix ?? "—";
    document.getElementById("compte").textContent = d.nb_setups;
    document.getElementById("horodatage").textContent =
      new Date(d.genere_le).toLocaleString("fr-FR");
    // Prix en direct : age et variation du jour
    if (d.quote) {{
      const v = d.quote.variation_pct ?? 0;
      const el = document.getElementById("variation");
      el.textContent = (v >= 0 ? "+" : "") + v.toFixed(2) + "%";
      el.className = "var " + (v >= 0 ? "hausse" : "baisse");
      const age = d.quote.age ?? 0;
      document.getElementById("fraicheur").innerHTML = age <= 20
        ? '<span class="vif">prix en direct</span>'
        : `prix il y a ${{age}}s`;
    }}

    // Quota restant : anneau circulaire, pourcentage au centre
    if (d.usage && d.usage.limite) {{
      const u = d.usage, pctRest = Math.max(0, 100 - (u.part_pct ?? 0));
      const coul = pctRest > 40 ? "#3fb950" : (pctRest > 15 ? "#d29922" : "#f85149");
      const an = document.getElementById("anneau-quota");
      an.setAttribute("stroke-dasharray", (144.5 * pctRest / 100).toFixed(1) + " 144.5");
      an.setAttribute("stroke", coul);
      const pc = document.getElementById("quota-pct");
      pc.textContent = pctRest.toFixed(0) + "%";
      pc.style.color = coul;
      document.getElementById("quota-detail").textContent = `${{u.restant}} / ${{u.limite}}`;
      document.getElementById("quota").title =
        u.detail.map(c => c.erreur ? `clé ${{c.cle}} : ${{c.erreur}}`
          : `clé ${{c.cle}} : ${{c.restant}} restantes (minute ${{c.par_minute}})`).join(" | ");
    }}

    if (d.rotation && d.rotation.cles) {{
      const r = d.rotation;
      const repos = r.au_repos.length ? ` · ${{r.au_repos.length}} au repos` : "";
      document.getElementById("etat-cles").innerHTML =
        `${{r.cles}} clés en rotation · ${{r.total}} requêtes cette session${{repos}}<br>`;
    }}

    const actuels = new Set(d.signaux.map(cle));
    for (const s of d.signaux) {{
      if (!connus.has(cle(s))) {{
        notifier(s);
        document.querySelector(".grille").classList.add("flash");
        setTimeout(() => document.querySelector(".grille").classList.remove("flash"), 1500);
      }}
    }}
    // Un signal disparu doit pouvoir re-notifier s'il revient
    connus = actuels;
    if (d.nb_setups === 0) document.title = "Or — Tableau de bord";
  }} catch (e) {{
    console.error("rafraichissement echoue :", e);
  }} finally {{
    enCours = false;
    restant = INTERVALLE;
    document.getElementById("pastille").classList.remove("charge");
  }}
}}

window.reparer = async (action, btn) => {{
  btn.disabled = true; btn.textContent = "...";
  try {{
    const r = await fetch("/reparer", {{ method: "POST",
      headers: {{ "Content-Type": "application/x-www-form-urlencoded" }},
      body: "action=" + encodeURIComponent(action) }});
    const d = await r.json();
    btn.textContent = d.ok ? "\u2713 " + d.message.slice(0, 60) : "\u2717 " + d.message;
    btn.style.borderColor = d.ok ? "#238636" : "#b62324";
    if (d.ok) setTimeout(() => location.reload(), 1200);
  }} catch (e) {{ btn.textContent = "\u2717 erreur reseau"; btn.disabled = false; }}
}};
window.allerOnglet = id => {{
  const p = document.getElementById(id);
  if (!p) return;
  document.querySelectorAll(".onglet").forEach(x => x.classList.remove("actif"));
  document.querySelectorAll(".panneau").forEach(x => x.classList.remove("actif"));
  p.classList.add("actif");
  const btn = document.querySelector(`.onglet[data-p="${{id}}"]`);
  if (btn) btn.classList.add("actif");
  p.scrollIntoView({{behavior:"smooth", block:"start"}});
}};
document.querySelectorAll(".onglet").forEach(b => b.onclick = () => {{
  document.querySelectorAll(".onglet").forEach(x => x.classList.remove("actif"));
  document.querySelectorAll(".panneau").forEach(x => x.classList.remove("actif"));
  b.classList.add("actif");
  document.getElementById(b.dataset.p).classList.add("actif");
}});
document.querySelectorAll(".tf-btn").forEach(b => b.onclick = () => {{
  document.querySelectorAll(".tf-btn").forEach(x => x.classList.remove("actif"));
  document.querySelectorAll(".grand-chart").forEach(x => x.classList.remove("actif"));
  b.classList.add("actif");
  document.getElementById(b.dataset.c).classList.add("actif");
}});

document.getElementById("btn-notif").onclick = async () => {{
  if (!window.Notification) {{
    document.getElementById("notif-etat").textContent = "non supporté par ce navigateur";
    return;
  }}
  const p = await Notification.requestPermission();
  majEtatNotif(p);
  if (p === "granted") new Notification("Notifications activées",
    {{ body: "Tu seras prévenu dès qu'un signal apparaît." }});
}};

function majEtatNotif(p) {{
  const el = document.getElementById("notif-etat");
  const btn = document.getElementById("btn-notif");
  if (p === "granted") {{ btn.classList.add("on"); el.textContent = "notifs actives"; el.style.color = "#3fb950"; }}
  else if (p === "denied") {{ el.textContent = "refusées"; el.style.color = "#f85149"; btn.disabled = true; }}
  else el.textContent = "activer";
}}

window.tfActif = window.tfActif || null;
window.appliquerTf = () => {{
  const cartes = document.querySelectorAll(".carte[data-tf]");
  if (!cartes.length) return;
  let choix = window.tfActif;
  if (!choix || ![...cartes].some(c => c.dataset.tf === choix)) {{
    // par defaut : premier TF avec signal actif, sinon H4
    const avec = [...document.querySelectorAll(".tfb .bip.ok")];
    choix = avec.length ? avec[0].parentElement.dataset.tf : "H4";
  }}
  cartes.forEach(c => c.classList.toggle("vue", c.dataset.tf === choix));
  document.querySelectorAll(".tfb").forEach(b =>
    b.classList.toggle("actif", b.dataset.tf === choix));
}};
document.addEventListener("click", e => {{
  const b = e.target.closest(".tfb");
  if (b) {{ window.tfActif = b.dataset.tf; window.appliquerTf(); }}
}});
window.appliquerTf();

setInterval(() => {{
  document.querySelectorAll("#sys-agents .act").forEach(a => {{
    const l = a.querySelectorAll(".lg");
    if (l.length < 2) return;
    let i = [...l].findIndex(x => x.classList.contains("on"));
    l[i].classList.remove("on");
    l[(i + 1) % l.length].classList.add("on");
  }});
}}, 1500);

setInterval(() => {{
  restant--;
  document.getElementById("compteur").textContent = Math.max(restant, 0);
  if (restant <= 0) rafraichir(false);
}}, 1000);

if (window.Notification) majEtatNotif(Notification.permission);
// Premier sondage immediat : il amorce la liste des signaux connus sans
// notifier ceux qui etaient deja la au chargement.
fetch("/json", {{ cache: "no-store" }}).then(r => r.json()).then(d => {{
  if (d.signaux) connus = new Set(d.signaux.map(cle));
}}).catch(() => {{}});
</script>
</body></html>"""


def _cle_signal(r: dict) -> str:
    s = r.get("setup") or {}
    return f"{r['nom']}|{s.get('setup')}|{s.get('entree')}|{s.get('declenche')}"


def surveiller(intervalle: int, arret: threading.Event) -> None:
    """Boucle de surveillance : notifie a l'apparition d'un signal.

    Elle amorce sa liste au premier passage sans notifier — sinon un signal
    deja present au demarrage declencherait une alerte trompeuse.
    """
    connus: set = set()
    premier = True
    while not arret.is_set():
        try:
            d = tableau.collecter()
            actuels = set()
            for r in d["timeframes"]:
                s = r.get("setup") or {}
                if not s.get("setup") or s.get("suspendu"):
                    continue
                cle = _cle_signal(r)
                actuels.add(cle)
                if premier or cle in connus:
                    continue
                fi = (r.get("fiabilite") or {}).get("niveau", "?")
                try:
                    svg = _grand_graphique(r)
                except Exception:
                    svg = None
                envoye = notify.diffuser(r["nom"], s, d.get("prix"), fi, svg=svg)
                canaux = ", ".join(k for k, v in envoye.items() if v) or "aucun canal"
                print(f"[{datetime.now():%H:%M:%S}] signal {r['nom']} {s['setup']} "
                      f"entree {s['entree']} (fiabilite: {fi}) -> {canaux}", flush=True)
            connus = actuels
            premier = False
        except Exception as e:
            print(f"[{datetime.now():%H:%M:%S}] surveillance : {str(e)[:120]}", flush=True)
        arret.wait(intervalle)


# Reseau 3D du Cerveau — canvas autonome, aucune bibliotheque externe.
# Servi en fichier separe pour garder les accolades JS hors des f-strings.
