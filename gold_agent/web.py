"""Tableau de bord local : python3 -m gold_agent.web

Serveur HTTP minimal (bibliothèque standard, aucune dépendance). Les données
sont recalculées à chaque chargement — un tableau de bord de trading qui
affiche des prix périmés est pire qu'inutile.
"""
from __future__ import annotations

import argparse
import http.server
import json
import shutil
import socket
import socketserver
import subprocess
import threading
import time
import webbrowser
from datetime import datetime, timezone

from . import auth, datasource as ds, notify, tableau

PORT = 8787

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
.on{color:#3fb950}
.flash{animation:flash 1.4s ease-out}
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
<title>Connexion — Or</title><style>
*{box-sizing:border-box;margin:0;padding:0}
body{background:#0d1117;color:#e6edf3;font:15px/1.5 -apple-system,sans-serif;
display:flex;align-items:center;justify-content:center;min-height:100vh}
form{background:#161b22;border:1px solid #30363d;border-radius:12px;padding:32px;width:340px}
h1{font-size:19px;margin-bottom:6px}
p{color:#8b949e;font-size:13px;margin-bottom:20px}
label{display:block;font-size:12.5px;color:#8b949e;margin:12px 0 5px}
input{width:100%;background:#0d1117;border:1px solid #30363d;border-radius:6px;
color:#e6edf3;padding:9px 12px;font-size:14px}
input:focus{outline:none;border-color:#2f81f7}
button{width:100%;margin-top:20px;background:#238636;color:#fff;border:none;
border-radius:6px;padding:10px;font-size:14px;font-weight:600;cursor:pointer}
button:hover{background:#2ea043}
.err{background:#3d1d1d;border:1px solid #b62324;color:#ffa198;border-radius:6px;
padding:9px 12px;font-size:13px;margin-bottom:14px}
.note{margin-top:16px;font-size:11.5px;color:#6e7681;line-height:1.5}
</style></head><body><form method="POST" action="/connexion">
<h1>Or — Tableau de bord</h1><p>XAU/USD · analyse multi-timeframe</p>
{erreur}
<label>Identifiant</label><input name="nom" autocomplete="username" autofocus required>
<label>Mot de passe</label><input name="motdepasse" type="password" autocomplete="current-password" required>
<button>Se connecter</button>
<div class="note">Comptes geres en local :<br>
<code>python3 -m gold_agent.auth ajouter &lt;nom&gt;</code></div>
</form></body></html>"""


def _chandeliers(bougies: list, setup: dict, largeur=560, hauteur=200) -> str:
    """Graphique en chandeliers SVG, avec les zones du setup superposées."""
    if not bougies:
        return ""
    marge_d, marge_h = 52, 8
    zone_l = largeur - marge_d
    zone_h = hauteur - marge_h * 2

    prix = [b["h"] for b in bougies] + [b["l"] for b in bougies]
    for cle in ("entree", "stop", "objectif"):
        v = (setup or {}).get(cle)
        if v:
            prix.append(v)
    pmin, pmax = min(prix), max(prix)
    if pmax == pmin:
        pmax = pmin + 1
    marge_p = (pmax - pmin) * 0.06
    pmin, pmax = pmin - marge_p, pmax + marge_p

    def y(p):
        return marge_h + (pmax - p) / (pmax - pmin) * zone_h

    pas = zone_l / max(len(bougies), 1)
    corps = max(1.4, pas * 0.6)
    out = [f'<svg viewBox="0 0 {largeur} {hauteur}" width="100%" height="{hauteur}" '
           f'xmlns="http://www.w3.org/2000/svg">']

    # Zones du setup
    for cle, couleur in (("entree", "#2f81f7"), ("stop", "#f85149"), ("objectif", "#3fb950")):
        z = (setup or {}).get(f"{cle}_zone")
        if not z:
            continue
        y1, y2 = y(z[1]), y(z[0])
        out.append(f'<rect x="0" y="{y1:.1f}" width="{zone_l:.1f}" height="{max(abs(y2-y1),1.5):.1f}" '
                   f'fill="{couleur}" fill-opacity="0.16"/>')
        out.append(f'<line x1="0" y1="{y(( z[0]+z[1])/2):.1f}" x2="{zone_l:.1f}" '
                   f'y2="{y((z[0]+z[1])/2):.1f}" stroke="{couleur}" stroke-width="1.2" stroke-dasharray="4 3"/>')

    # Chandeliers
    for i, b in enumerate(bougies):
        x = i * pas + pas / 2
        hausse = b["c"] >= b["o"]
        col = "#3fb950" if hausse else "#f85149"
        out.append(f'<line x1="{x:.1f}" y1="{y(b["h"]):.1f}" x2="{x:.1f}" y2="{y(b["l"]):.1f}" '
                   f'stroke="{col}" stroke-width="1"/>')
        yo, yc = y(b["o"]), y(b["c"])
        out.append(f'<rect x="{x - corps/2:.1f}" y="{min(yo,yc):.1f}" width="{corps:.1f}" '
                   f'height="{max(abs(yc-yo),1):.1f}" fill="{col}"/>')

    # Echelle de prix
    for frac in (0, 0.5, 1):
        p = pmin + (pmax - pmin) * frac
        yy = y(p)
        out.append(f'<line x1="0" y1="{yy:.1f}" x2="{zone_l:.1f}" y2="{yy:.1f}" '
                   f'stroke="#30363d" stroke-width="0.5"/>')
        out.append(f'<text x="{zone_l + 6}" y="{yy + 3.5:.1f}" fill="#8b949e" '
                   f'font-size="10.5" font-family="monospace">{p:.0f}</text>')
    out.append("</svg>")
    return "".join(out)


def _carte(r: dict) -> str:
    s = r.get("setup") or {}
    fi = r.get("fiabilite") or {}
    niveau = fi.get("niveau", "non mesuré")
    cls = {"mesuré": "b-mesure", "indicatif": "b-indicatif"}.get(niveau, "b-nonmesure")
    actif = " actif" if s.get("setup") else ""

    h = [f'<div class="carte{actif}">',
         f'<div class="tete"><div><div class="tf">{r["nom"]}</div>'
         f'<div class="role">{r["role"]}</div></div>'
         f'<span class="badge {cls}">{niveau} · {fi.get("note","")}</span></div>',
         '<div class="corps">']

    if s.get("setup"):
        sens = "ACHAT" if s["setup"] == "achat" else "VENTE"
        etat = "déclenché" if s.get("declenche") else f"à {s['distance_a_entree']} pts"
        h.append(f'<div class="rr">{sens} · {etat} · R:R <b>{s["rr"]}</b></div>')
        h.append('<div class="zones" style="margin-top:10px">')
        for cle, lib, klass, extra in (
            ("entree", "Entrée", "z-entree", f"zone {s['entree_zone'][0]} – {s['entree_zone'][1]}"),
            ("stop", "Stop loss", "z-stop", f"risque {s['risque_pts']} pts"),
            ("objectif", "Take profit", "z-obj", f"gain {s['gain_pts']} pts"),
        ):
            h.append(f'<div class="zone {klass}"><div><div class="zl">{lib}</div>'
                     f'<div class="zd">{extra}</div></div><div class="zv">{s[cle]}</div></div>')
        h.append("</div>")
    else:
        h.append(f'<div class="aucun"><b>Aucun signal</b>{s.get("raison","")}</div>')

    ext = r.get("extension") or {}
    vol = r.get("volatilite") or {}
    h.append('<div class="stats">')
    for lib, val in (("RSI", f'{r.get("rsi"):.1f}' if r.get("rsi") else "—"),
                     ("ATR", f'{r.get("atr"):.2f}' if r.get("atr") else "—"),
                     ("Extension", f'{ext.get("score","—")}')):
        h.append(f'<div class="st"><div class="sl">{lib}</div><div class="sv">{val}</div></div>')
    h.append("</div>")

    alertes = []
    if ext.get("niveau") in ("extreme", "marquee"):
        cl = "chaud" if ext["niveau"] == "extreme" else "tiede"
        alertes.append((cl, f'Extension {ext["sens"]} {ext["niveau"]} — score {ext["score"]}/100, '
                            f'prix à {ext["ecart_pct"]:+.1f}% de son EMA'))
    if vol.get("regime") in ("expansion_forte", "expansion"):
        cl = "chaud" if vol["regime"] == "expansion_forte" else "tiede"
        alertes.append((cl, f'Volatilité ×{vol["ratio"]} — {vol["note"]}'))
    rev = r.get("renversement") or {}
    if rev.get("renversement"):
        alertes.append(("tiede", rev["note"]))
    if alertes:
        h.append('<div class="alertes">')
        for cl, txt in alertes:
            h.append(f'<div class="al {cl}">{txt}</div>')
        h.append("</div>")

    age = r.get("age_secondes")
    if age is not None:
        perime = " perime" if r.get("perime") else ""
        libelle = f"donnees figees depuis {age}s" if r.get("perime") else (
            "en direct" if age == 0 else f"il y a {age}s")
        h.append(f'<div class="al{perime}" style="margin-top:10px;font-size:11.5px;'
                 f'border-left-color:#30363d;background:transparent;padding:4px 0">{libelle}</div>')
    if r.get("erreur"):
        h.append(f'<div class="al chaud" style="margin-top:6px">{r["erreur"]}</div>')

    h.append("</div>")
    h.append(f'<div class="chart">{_chandeliers(r.get("bougies", []), s)}</div>')
    h.append("</div>")
    return "".join(h)


def rendre(d: dict) -> str:
    gen = datetime.fromisoformat(d["genere_le"]).astimezone()
    cartes = "".join(_carte(r) for r in d["timeframes"])

    # Valeurs rendues cote serveur : sans cela, variation et quota restent
    # vides jusqu'au premier sondage, 30 s apres l'ouverture de la page.
    q = d.get("quote") or {}
    v = q.get("variation_pct")
    var_txt = f"{v:+.2f}%" if v is not None else ""
    var_cls = "hausse" if (v or 0) >= 0 else "baisse"
    age = q.get("age", 0)
    frais = ('<span class="vif">prix en direct</span>' if age <= 20
             else f"prix il y a {age}s") if q else ""

    u = d.get("usage") or {}
    if u.get("limite"):
        quota_txt = f"{u['restant']} / {u['limite']} requêtes restantes"
        pct = u.get("part_pct") or 0
        jauge_cls = "haut" if pct > 85 else ("moyen" if pct > 60 else "")
        jauge_w = min(pct, 100)
    else:
        quota_txt, jauge_cls, jauge_w = "quota —", "", 0
    return f"""<!doctype html><html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Or — Tableau de bord</title><style>{CSS}</style></head><body><div class="wrap">
<header><h1>XAU/USD</h1><div class="prix">{d.get('prix') or '—'}</div>
<div class="var {var_cls}" id="variation">{var_txt}</div>
<div class="meta"><span class="pastille" id="pastille"></span><span id="horodatage">{gen:%d/%m/%Y %H:%M:%S}</span>
 · <span id="compte">{d['nb_setups']}</span> signal(aux) actif(s)
 · <span class="direct" id="fraicheur">{frais}</span></div>
<div class="barre">
<div class="quota" id="quota" title="quota Twelve Data restant aujourd'hui">
  <span id="quota-txt">{quota_txt}</span><span class="jauge"><span id="jauge" class="{jauge_cls}" style="width:{jauge_w}%"></span></span></div>
<span class="compteur">prochain contrôle dans <span id="compteur">10</span>s</span>
<button id="btn-notif">Activer les notifications</button>
<span id="notif-etat"></span>
<button onclick="rafraichir(true)">Actualiser</button>
<a href="/deconnexion" style="color:#8b949e;font-size:12.5px">Déconnexion</a>
</div></header>
<div class="bandeau"><b>Sortie mécanique d'une règle, pas une recommandation.</b>
Les niveaux découlent des paramètres de la règle : support confirmé = entrée, −1&nbsp;ATR = stop,
première résistance = objectif. Le badge de chaque carte indique ce que le backtest a réellement
mesuré sur ce timeframe. Un signal «&nbsp;non mesuré&nbsp;» n'a aucune preuve derrière lui.</div>
<div class="grille">{cartes}</div>
<footer>
<span id="etat-cles"></span>Données Twelve Data · filtres : RSI max 70 à l'achat,
RSI min 30 à la vente, R:R minimum 1,5, contexte du timeframe supérieur.<br>
Le côté vendeur reste non validé (5&nbsp;trades d'historique, espérance négative).
Résultats hors spread réel et glissement. Aucun ordre n'est passé.
</footer></div>
<script>
const INTERVALLE = 10;              // secondes entre deux controles
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

    // Quota restant
    if (d.usage && d.usage.limite) {{
      const u = d.usage, pct = u.part_pct ?? 0;
      document.getElementById("quota-txt").textContent =
        `${{u.restant}} / ${{u.limite}} requêtes restantes`;
      const j = document.getElementById("jauge");
      j.style.width = Math.min(pct, 100) + "%";
      j.className = pct > 85 ? "haut" : (pct > 60 ? "moyen" : "");
      document.getElementById("quota").title =
        u.detail.map(c => c.erreur ? `clé ${{c.cle}} : ${{c.erreur}}`
          : `clé ${{c.cle}} : ${{c.restant}} restantes (minute ${{c.par_minute}})`).join("\n");
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
  if (p === "granted") {{ el.innerHTML = '<span class="on">notifications actives</span>'; btn.style.display = "none"; }}
  else if (p === "denied") {{ el.textContent = "refusées — à réactiver dans les réglages du navigateur"; btn.style.display = "none"; }}
  else el.textContent = "";
}}

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
                if not s.get("setup"):
                    continue
                cle = _cle_signal(r)
                actuels.add(cle)
                if premier or cle in connus:
                    continue
                fi = (r.get("fiabilite") or {}).get("niveau", "?")
                envoye = notify.diffuser(r["nom"], s, d.get("prix"), fi)
                canaux = ", ".join(k for k, v in envoye.items() if v) or "aucun canal"
                print(f"[{datetime.now():%H:%M:%S}] signal {r['nom']} {s['setup']} "
                      f"entree {s['entree']} (fiabilite: {fi}) -> {canaux}", flush=True)
            connus = actuels
            premier = False
        except Exception as e:
            print(f"[{datetime.now():%H:%M:%S}] surveillance : {str(e)[:120]}", flush=True)
        arret.wait(intervalle)


class Handler(http.server.BaseHTTPRequestHandler):

    def _jeton(self) -> str | None:
        brut = self.headers.get("Cookie", "")
        for morceau in brut.split(";"):
            k, _, v = morceau.strip().partition("=")
            if k == "session":
                return v
        return None

    def _repondre(self, corps: bytes, ctype: str, entetes: list | None = None,
                  code: int = 200) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(corps)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (entetes or []):
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(corps)

    def do_POST(self):
        if self.path != "/connexion":
            self._repondre(b"introuvable", "text/plain", code=404)
            return
        import urllib.parse
        taille = min(int(self.headers.get("Content-Length", 0) or 0), 4096)
        champs = urllib.parse.parse_qs(self.rfile.read(taille).decode("utf-8", "replace"))
        nom = (champs.get("nom") or [""])[0].strip()
        mdp = (champs.get("motdepasse") or [""])[0]
        if nom and auth.verifier(nom, mdp):
            jeton = auth.ouvrir_session(nom)
            # HttpOnly : inaccessible au JavaScript de la page. SameSite=Strict :
            # le cookie ne part jamais depuis un autre site.
            self._repondre(b"", "text/plain", code=303, entetes=[
                ("Location", "/"),
                ("Set-Cookie", f"session={jeton}; HttpOnly; SameSite=Strict; Path=/"),
            ])
        else:
            page = PAGE_CONNEXION.replace("{erreur}",
                '<div class="err">Identifiant ou mot de passe incorrect.</div>')
            self._repondre(page.encode(), "text/html; charset=utf-8", code=401)

    def do_GET(self):
        # Deconnexion
        if self.path == "/deconnexion":
            auth.fermer_session(self._jeton())
            self._repondre(b"", "text/plain", code=303, entetes=[
                ("Location", "/"),
                ("Set-Cookie", "session=; Max-Age=0; Path=/"),
            ])
            return

        # Tant qu'aucun compte n'existe, pas d'ecran de connexion : exiger un
        # mot de passe inexistant reviendrait a verrouiller l'utilisateur dehors.
        if auth.comptes_existent() and not auth.session_valide(self._jeton()):
            if self.path.startswith("/json"):
                self._repondre(b'{"erreur":"non authentifie"}',
                               "application/json; charset=utf-8", code=401)
            else:
                self._repondre(PAGE_CONNEXION.replace("{erreur}", "").encode(),
                               "text/html; charset=utf-8", code=401)
            return

        if self.path.startswith("/json"):
            # On renvoie les donnees ET le HTML des cartes dans la meme reponse :
            # une seule requete, et le rendu reste ecrit a un seul endroit
            # (pas de duplication de la mise en page en JavaScript).
            try:
                d = tableau.collecter()
                charge = {
                    "prix": d.get("prix"),
                    "genere_le": d["genere_le"],
                    "nb_setups": d["nb_setups"],
                    "signaux": [
                        {"tf": r["nom"],
                         "sens": (r.get("setup") or {}).get("setup"),
                         "entree": (r.get("setup") or {}).get("entree"),
                         "stop": (r.get("setup") or {}).get("stop"),
                         "objectif": (r.get("setup") or {}).get("objectif"),
                         "rr": (r.get("setup") or {}).get("rr"),
                         "declenche": (r.get("setup") or {}).get("declenche"),
                         "fiabilite": (r.get("fiabilite") or {}).get("niveau")}
                        for r in d["timeframes"] if (r.get("setup") or {}).get("setup")
                    ],
                    "html": "".join(_carte(r) for r in d["timeframes"]),
                    "quota": ds.COMPTEUR["twelvedata"],
                    "rotation": ds.etat_rotation(),
                    "quote": d.get("quote"),
                    "usage": d.get("usage"),
                }
                corps = json.dumps(charge, ensure_ascii=False).encode()
            except Exception as e:
                corps = json.dumps({"erreur": str(e)[:200]}).encode()
            ctype = "application/json; charset=utf-8"
        else:
            try:
                d = tableau.collecter()
                corps = rendre(d).encode()
            except Exception as e:
                corps = (f"<body style='background:#0d1117;color:#f85149;"
                         f"font-family:sans-serif;padding:40px'>"
                         f"<h2>Erreur de collecte</h2><pre>{e}</pre></body>").encode()
            ctype = "text/html; charset=utf-8"
        self._repondre(corps, ctype)

    def log_message(self, *a):
        pass


class _ServeurIPv6(socketserver.TCPServer):
    address_family = socket.AF_INET6
    allow_reuse_address = True


def _expliquer_port_occupe(port: int) -> None:
    """Message lisible plutot qu'une pile d'appels Python.

    On distingue deux cas tres differents : un tableau de bord deja lance
    (il suffit de l'ouvrir) et un autre programme sur le port (il faut en
    choisir un autre).
    """
    print(f"\nLe port {port} est deja occupe.\n", flush=True)

    deja_le_notre = False
    try:
        r = subprocess.run(["curl", "-s", "-m", "5", f"http://127.0.0.1:{port}/json"],
                           capture_output=True, text=True, timeout=10)
        deja_le_notre = '"rotation"' in r.stdout or '"nb_setups"' in r.stdout
    except Exception:
        pass

    if deja_le_notre:
        print("  C'est un tableau de bord deja en route — pas besoin d'en lancer un second.", flush=True)
        print(f"  Ouvre simplement : http://127.0.0.1:{port}\n", flush=True)
        print("  Pour le remplacer, arrete-le d'abord :", flush=True)
        print("    pkill -f gold_agent.web", flush=True)
    else:
        print("  Un autre programme utilise ce port. Deux options :\n", flush=True)
        print(f"    python3 -m gold_agent.web --port {port + 1}    # en choisir un autre", flush=True)
        print(f"    lsof -nP -iTCP:{port} -sTCP:LISTEN            # voir qui l'occupe", flush=True)
    print("", flush=True)


def main() -> int:
    ap = argparse.ArgumentParser(prog="gold_agent.web", description="Tableau de bord de l'or.")
    ap.add_argument("--port", type=int, default=PORT)
    ap.add_argument("--surveillance", type=int, default=300, metavar="SECONDES",
                    help="intervalle de surveillance en arriere-plan (0 = desactive, defaut 300)")
    ap.add_argument("--no-open", action="store_true", help="ne pas ouvrir le navigateur")
    a = ap.parse_args()

    arret = threading.Event()
    if a.surveillance > 0:
        tableau.definir_profil("surveillance")
        b = tableau.budget()
        print(f"Surveillance active — controle toutes les {a.surveillance}s", flush=True)
        c = notify.etat_canaux()
        print(f"  notification systeme  : {'oui' if c['systeme'] else 'NON'}", flush=True)
        print(f"  push telephone (ntfy) : {c['sujet'] or 'NON configure'}", flush=True)
        print(f"  volume en lots        : {'calcule' if c['capital_configure'] else 'CAPITAL absent de .env'}", flush=True)
        print(f"  cles Twelve Data : {b['cles']} en rotation — quota cumule {b['quota']}/jour", flush=True)
        print(f"  consommation prevue : ~{b['prevu']}/jour ({b['part_pct']}% du quota)", flush=True)
        print("  caches : " + ", ".join(f"{k}={v}s" for k, v in b["ttl"].items()), flush=True)
        threading.Thread(target=surveiller, args=(a.surveillance, arret), daemon=True).start()
    else:
        print("Surveillance desactivee (profil consultation, caches courts)", flush=True)

    socketserver.TCPServer.allow_reuse_address = True
    try:
        srv = socketserver.TCPServer(("127.0.0.1", a.port), Handler)
    except OSError as e:
        if e.errno != 48:      # EADDRINUSE
            raise
        arret.set()
        _expliquer_port_occupe(a.port)
        return 1

    # Deuxieme ecoute sur la boucle locale IPv6. Sur macOS, "localhost" resout
    # d'abord en ::1 : un serveur qui n'ecoute qu'en 127.0.0.1 est alors
    # injoignable quand on tape localhost dans le navigateur. On reste sur la
    # boucle locale — jamais sur toutes les interfaces, le tableau ne doit pas
    # etre expose au reseau.
    srv6 = None
    try:
        srv6 = _ServeurIPv6(("::1", a.port), Handler)
        threading.Thread(target=srv6.serve_forever, daemon=True).start()
    except OSError:
        pass   # pas d'IPv6 sur cette machine : 127.0.0.1 suffit

    with srv:
        url = f"http://127.0.0.1:{a.port}/"
        print(f"\nTableau de bord : {url}", flush=True)
        if srv6:
            print(f"          ou      http://localhost:{a.port}/   (IPv6 actif)", flush=True)
        if auth.comptes_existent():
            print(f"  acces protege : {len(auth.lister())} compte(s) — python3 -m gold_agent.auth lister", flush=True)
        else:
            print("  ACCES LIBRE — aucun compte defini. Pour proteger :", flush=True)
            print("    python3 -m gold_agent.auth ajouter <ton-nom>", flush=True)
        print("  /json pour les donnees brutes", flush=True)
        print("  Ctrl+C pour arreter", flush=True)
        if not a.no_open:
            threading.Timer(1.0, lambda: webbrowser.open(url)).start()
        try:
            srv.serve_forever()
        except KeyboardInterrupt:
            arret.set()
            if srv6:
                srv6.shutdown()
            print(f"\narret — {ds.COMPTEUR['twelvedata']} requetes consommees cette session", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
