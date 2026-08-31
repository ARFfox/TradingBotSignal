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

    pct = r.get("pct_haussier", 50)
    circ = 2 * 3.14159 * 18
    coul = "#3fb950" if pct >= 55 else ("#f85149" if pct <= 45 else "#d29922")
    jauge = (f'<div class="jauge-tf"><svg width="44" height="44">'
             f'<circle cx="22" cy="22" r="18" fill="none" stroke="#21262d" stroke-width="5"/>'
             f'<circle cx="22" cy="22" r="18" fill="none" stroke="{coul}" stroke-width="5" '
             f'stroke-dasharray="{circ*pct/100:.1f} {circ:.1f}"/></svg>'
             f'<span style="color:{coul}">{pct}%</span></div>')

    h = [f'<div class="carte{actif}">',
         f'<div class="tete"><div style="display:flex;gap:10px;align-items:center">{jauge}'
         f'<div><div class="tf">{r["nom"]}</div>'
         f'<div class="role">{r["role"]}</div></div></div>'
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

    ic = r.get("ict") or {}
    pd_ = ic.get("premium_discount") or {}
    amd = ic.get("amd") or {}
    if pd_.get("zone"):
        kz = ic.get("killzone")
        h.append(f'<div class="ict-ligne">ICT : <b>{pd_["zone"]}</b> '
                 f'({pd_["position_pct"]}% du range) · AMD : <b>{amd.get("phase","—")}</b>'
                 + (f' · killzone <b>{kz}</b>' if kz else "")
                 + '</div>')

    abc = r.get("abc") or {}
    if abc.get("scenario"):
        h.append(f'<div class="ict-ligne">Vagues : <b>{abc["scenario"]}</b> — {abc["stade"]} · '
                 f'cible C <b>{abc["cible_C"]}</b> (zone {abc["zone_C"][0]}–{abc["zone_C"][1]}) · '
                 f'invalidé au-delà de {abc["invalidation"]}</div>')

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


def _boule(c: dict) -> str:
    """Donut de consensus, façon TipRanks — mais décomposable ligne par ligne."""
    if not c:
        return ""
    pct = c["pct_haussier"]
    r, circ = 62, 2 * 3.14159 * 62
    arc_h = circ * pct / 100
    cls = "h" if c["verdict"] == "HAUSSIER" else ("b" if c["verdict"] == "BAISSIER" else "n")
    lignes = "".join(
        f'<div><span>{"▲" if x["camp"]=="haussier" else "▼"} {x["source"]}</span>'
        f'<span>{x["poids"]}</span></div>'
        for x in c.get("contributions", []))
    return f"""<div class="boule">
<h3>Consensus des couches d'analyse</h3>
<svg width="160" height="160" viewBox="0 0 160 160">
<circle cx="80" cy="80" r="{r}" fill="none" stroke="#f85149" stroke-width="17"/>
<circle cx="80" cy="80" r="{r}" fill="none" stroke="#3fb950" stroke-width="17"
 stroke-dasharray="{arc_h:.1f} {circ - arc_h:.1f}" stroke-dashoffset="{circ/4:.1f}"
 transform="rotate(0 80 80)" stroke-linecap="butt"/>
<text x="80" y="76" text-anchor="middle" fill="#e6edf3" font-size="24" font-weight="700">{pct:.0f}%</text>
<text x="80" y="96" text-anchor="middle" fill="#8b949e" font-size="11">haussier</text>
</svg>
<div class="verdict-b {cls}">{c["verdict"]}</div>
<div class="legende">
<span><i style="background:#3fb950"></i>{c["nb_haussier"]} haussiers · {c["haussier"]} pts</span>
<span><i style="background:#f85149"></i>{c["nb_baissier"]} baissiers · {c["baissier"]} pts</span>
</div>
<div class="contribs">{lignes}</div>
</div>"""


# Widget officiel TradingView — construit HORS f-string : son JSON de config
# est plein d'accolades qui entreraient en collision avec le gabarit.
WIDGET_TV = """<div class="tv-cadre"><h3>Graphique en direct — TradingView</h3>
<iframe src="https://s.tradingview.com/widgetembed/?symbol=OANDA%3AXAUUSD&interval=30&theme=dark&style=1&locale=fr&hide_side_toolbar=0&allow_symbol_change=0&timezone=Etc%2FUTC"
 style="width:100%;height:430px;border:0;display:block" loading="lazy"
 title="TradingView XAUUSD"></iframe>
<div style="padding:8px 16px;font-size:11.5px;color:#6e7681">Si ce cadre reste noir,
un bloqueur de publicité filtre probablement tradingview.com — ajoute une exception
pour 127.0.0.1.</div></div>"""


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

    n = d.get("news") or {}
    risque = n.get("risque") or {}
    et = risque.get("etat", "inconnu")
    lignes_agenda = ""
    for e in (n.get("agenda") or [])[:5]:
        h = e["dans_minutes"] / 60
        quand = f"dans {e['dans_minutes']} min" if h < 1.5 else f"dans {h:.1f} h"
        prevu = f" · prévu {e['prevu']}" if e.get("prevu") else ""
        lignes_agenda += (f'<div class="evt"><span class="t">{e["titre"]}{prevu}</span>'
                          f'<span class="q">{quand}</span></div>')
    if not lignes_agenda:
        lignes_agenda = '<div class="evt"><span class="t">aucun événement USD à fort impact sous 48 h</span></div>'

    ma = (n.get("macro") or {})
    lignes_macro = ""
    if ma.get("disponible"):
        tr = ma["taux_reel_10a"]; dl = ma["dollar_large"]
        v1 = tr.get("tendance_1m") or {}
        v2 = dl.get("tendance_1m") or {}
        lignes_macro = (
            f'<div class="macrol">Taux réel 10 ans : <b>{tr["dernier"]}%</b>'
            f' ({v1.get("variation", 0):+.2f} sur 1 mois)</div>'
            f'<div class="macrol">Dollar pondéré : <b>{dl["dernier"]}</b>'
            f' ({v2.get("variation", 0):+.2f} sur 1 mois)</div>')
        for camp, poids, txt in ma.get("arguments", []):
            fleche = "▲ or" if camp == "haussier" else "▼ or"
            lignes_macro += f'<div class="macrol">{fleche} — {txt}</div>'
    else:
        lignes_macro = '<div class="macrol">macro FRED indisponible</div>'

    cot = n.get("cot") or {}
    if cot.get("disponible"):
        lignes_macro += (
            f'<div class="macrol">Fonds spéculatifs (COT {cot["date"]}) : '
            f'<b>{cot["net"]:+,}</b> contrats — {cot["percentile"]:.0f}e percentile, '
            f'{cot["variation_4s"]:+,} en 4 sem.</div>')

    mi = n.get("minieres") or {}
    if mi.get("disponible"):
        div = mi.get("divergence")
        etat_mi = (f'divergence {div} détectée' if div
                   else 'les minières confirment le mouvement')
        lignes_macro += (
            f'<div class="macrol">Minières (AEM, {mi["fenetre_jours"]} j) : '
            f'<b>{mi["aem"]["variation_pct"]:+.1f}%</b> vs or '
            f'<b>{mi["or"]["variation_pct"]:+.1f}%</b> — {etat_mi}</div>')

    bloc_news = f"""<div class="news">
<div><h3>Risque événementiel</h3>
<div class="risque {et}">{risque.get("detail", "?")}</div>
{lignes_agenda}</div>
<div><h3>Macro — moteurs de fond de l'or</h3>{lignes_macro}</div>
</div>"""

    boule = _boule(d.get("consensus"))
    widget = WIDGET_TV

    # Onglet analyse graphique : nos graphiques en grand, avec les zones de
    # la regle superposees — ce que le widget TradingView ne peut pas montrer.
    btns, charts = "", ""
    for i, r in enumerate(d["timeframes"]):
        actif = " actif" if i == 0 else ""
        btns += f'<button class="tf-btn{actif}" data-c="gc-{r["nom"]}">{r["nom"]}</button>'
        svg = _chandeliers(r.get("bougies", []), r.get("setup") or {}, largeur=920, hauteur=340)
        s_ = r.get("setup") or {}
        etat = (f'{s_["setup"].upper()} — entrée {s_["entree"]} · stop {s_["stop"]} · '
                f'TP {s_["objectif"]} · R:R {s_["rr"]}') if s_.get("setup")                else f'aucun signal — {s_.get("raison", "")}'
        charts += (f'<div id="gc-{r["nom"]}" class="grand-chart{actif}">'
                   f'<div style="font-size:13px;color:#c9d1d9;margin-bottom:8px">'
                   f'<b>{r["nom"]}</b> · {etat}</div>{svg}</div>')
    bloc_graph = f'<div class="tf-btns">{btns}</div>{charts}'

    # Onglet strategies : ce qui a ete mesure, y compris ce qui a ete rejete.
    bloc_strats = """<div class="strats"><table>
<tr><th>Couche</th><th>Effet mesuré (H4, ~3 ans, coût 0,3 pt)</th><th>Statut</th></tr>
<tr><td>Repli sur support en tendance (base)</td><td>70 trades · +0,656R · creux −4,11R</td><td class="ok">active</td></tr>
<tr><td>Filtre surachat/survente RSI 70/30</td><td>+0,762R · creux −3,10R (−25 %)</td><td class="ok">active</td></tr>
<tr><td>Contexte du timeframe supérieur</td><td>+16 % d'espérance (H4→Daily)</td><td class="ok">active</td></tr>
<tr><td>Veto d'extension gradué (score 0-100)</td><td>a évité l'achat au sommet du 24-25/08</td><td class="ok">active</td></tr>
<tr><td>Veto news à fort impact (calendrier éco)</td><td>non backtestable — protection de spread</td><td class="ok">active</td></tr>
<tr><td>Macro FRED (taux réels, dollar)</td><td>arguments de débat, poids ≤ 2,5</td><td class="ok">active</td></tr>
<tr><td>COT — positions des fonds spéculatifs</td><td>tendance + percentile 3 ans</td><td class="ok">active</td></tr>
<tr><td>Divergence minières (AEM)</td><td>corrélation +0,80 même jour, lead-lag nul</td><td class="ok">confirmation seule</td></tr>
<tr><td>Filtre Bollinger %B</td><td>+0,762R → +0,352R : dégrade</td><td class="ko">rejetée</td></tr>
<tr><td>AEM comme prédicteur</td><td>corrélations décalées &lt; 0,12</td><td class="ko">rejetée</td></tr>
<tr><td>Côté vendeur</td><td>5 trades, espérance négative</td><td class="ko">non validé</td></tr>
</table></div>"""

    hi = d.get("historique") or {}
    lignes_h = ""
    for x in hi.get("derniers", []):
        st = x["statut"]
        cls_h = {"gagnant": "ok", "perdant": "ko"}.get(st, "")
        r_txt = f'{x["r_obtenu"]:+.2f}R' if x.get("r_obtenu") is not None else "—"
        lignes_h += (f'<tr><td>{x["cree_le"][:16].replace("T"," ")}</td><td>{x["tf"]}</td>'
                     f'<td>{x["sens"]}</td><td>{x["entree"]}</td><td>{x["stop"]}</td>'
                     f'<td>{x["objectif"]}</td><td>{x["fiabilite"]}</td>'
                     f'<td class="{cls_h}">{st}</td><td>{r_txt}</td></tr>')
    if not lignes_h:
        lignes_h = '<tr><td colspan="9">aucun signal enregistré pour l&#39;instant — le journal se remplit à mesure que la règle émet</td></tr>'
    taux = hi.get("taux_reussite_pct")
    resume_h = (f'{hi.get("total_emis",0)} signaux émis · {hi.get("resolus",0)} résolus '
                f'({hi.get("gagnants",0)} gagnants / {hi.get("perdants",0)} perdants'
                + (f' · taux {taux}%' if taux is not None else "")
                + f') · cumul {hi.get("cumul_R",0):+.2f}R · '
                f'{hi.get("en_attente",0)} en attente · {hi.get("ouverts",0)} ouverts · '
                f'{hi.get("non_executes",0)} jamais exécutés')
    bloc_histo = f"""<div class="strats">
<div style="font-size:13.5px;color:#e6edf3;margin-bottom:10px"><b>Résultat global :</b> {resume_h}</div>
<table><tr><th>Émis le (UTC)</th><th>TF</th><th>Sens</th><th>Entrée</th><th>Stop</th><th>TP</th><th>Fiabilité</th><th>Statut</th><th>R</th></tr>
{lignes_h}</table>
<div style="font-size:11.5px;color:#6e7681;margin-top:8px">Résolution aux mêmes règles que le
backtest : bougie touchant stop ET objectif = perte. Une entrée limite jamais touchée sous 48 h
est classée « non exécuté » et ne compte pas dans le taux.</div></div>"""

    sa = d.get("sante") or {}
    ags = ""
    for a in sa.get("agents", []):
        pt = "ok" if a["ok"] else "ko"
        ags += (f'<div class="ag"><h4><span class="pt {pt}"></span>{a["nom"]}</h4>'
                f'<p>{a["role"]}</p><p>Source : {a["source"]}</p><p>{a["detail"]}</p></div>')
    probs = sa.get("problemes", [])
    diag = ("<b>Superviseur — problèmes détectés :</b><br>" + "<br>".join(f"• {x}" for x in probs))         if probs else "<b>Superviseur :</b> tous les agents répondent, aucun problème détecté."
    import json as _json
    donnees_cerveau = _json.dumps({"agents": [
        {"nom": a["nom"], "ok": a["ok"], "detail": a["detail"]}
        for a in sa.get("agents", [])]}, ensure_ascii=False)
    canvas = (f'<div style="background:#0d1117;border:1px solid #30363d;border-radius:10px;'
              f'margin-bottom:14px;overflow:hidden">'
              f'<canvas id="cerveau3d" style="width:100%;height:440px;display:block"></canvas></div>'
              f'<script id="donnees-cerveau" type="application/json">{donnees_cerveau}</script>'
              f'<script src="/cerveau.js" defer></script>')
    bloc_cerveau = (f'{canvas}<div class="cerveau">{ags}'
                    f'<div class="superviseur">{diag}<br><br>'
                    f'<span style="color:#8b949e;font-size:12px">{sa.get("note","")}</span></div></div>')

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
<div class="haut-page">{boule}{widget}</div>
<div class="onglets">
<button class="onglet actif" data-p="p-risque">Risque événementiel</button>
<button class="onglet" data-p="p-graph">Analyse graphique</button>
<button class="onglet" data-p="p-strats">Stratégies</button>
<button class="onglet" data-p="p-histo">Historique</button>
<button class="onglet" data-p="p-cerveau">Cerveau</button>
</div>
<div id="p-risque" class="panneau actif">{bloc_news}</div>
<div id="p-graph" class="panneau">{bloc_graph}</div>
<div id="p-strats" class="panneau">{bloc_strats}</div>
<div id="p-histo" class="panneau">{bloc_histo}</div>
<div id="p-cerveau" class="panneau">{bloc_cerveau}</div>
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
    if (d.boule) document.querySelector(".boule").outerHTML = d.boule;
    if (d.sante && window.majCerveau) window.majCerveau(d.sante);
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


# Reseau 3D du Cerveau — canvas autonome, aucune bibliotheque externe.
# Servi en fichier separe pour garder les accolades JS hors des f-strings.
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
  const noeuds = [{id:'sup', nom:'Superviseur', x:0, y:0, z:0, r:26, type:'centre', ok:true}];
  const sorties = [
    {id:'site', nom:'Site 8787', x:0, y:170, z:60, r:18, type:'sortie', ok:true},
    {id:'tel', nom:'Téléphone (ntfy)', x:150, y:150, z:-40, r:14, type:'sortie', ok:true},
    {id:'toi', nom:'TOI — décision', x:-150, y:150, z:-40, r:16, type:'humain', ok:true},
  ];
  const ags = donnees.agents || [];
  const n = ags.length;
  ags.forEach((a,i)=>{
    const ang = i/n*Math.PI*2, ray = 200;
    noeuds.push({id:'a'+i, nom:a.nom, ok:a.ok, detail:a.detail, type:'agent',
      x:Math.cos(ang)*ray, y:-40+Math.sin(ang*2)*38, z:Math.sin(ang)*ray, r:15});
  });
  noeuds.push(...sorties);

  const liens = [];
  ags.forEach((a,i)=>liens.push(['a'+i,'sup']));
  liens.push(['sup','site'],['site','tel'],['site','toi']);

  const parts = liens.map(()=>Math.random());   // particules de flux
  const idx = Object.fromEntries(noeuds.map((nd,i)=>[nd.id,i]));

  let ang = 0, survol = -1;
  cv.addEventListener('mousemove', e=>{
    const rc = cv.getBoundingClientRect();
    const mx = e.clientX-rc.left, my = e.clientY-rc.top;
    survol = -1;
    for (let i=0;i<noeuds.length;i++){
      const pn = noeuds[i]._p;
      if (pn && Math.hypot(mx-pn[0],my-pn[1]) < pn[2]+6) { survol=i; break; }
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
    ang += 0.0035;
    ctx.clearRect(0,0,W,H);
    noeuds.forEach(nd=>nd._p = proj(nd, nd.type==='sortie'||nd.type==='humain' ? 0 : ang));

    // Liens + particules de donnees
    liens.forEach((ln,i)=>{
      const A = noeuds[idx[ln[0]]]._p, B = noeuds[idx[ln[1]]]._p;
      const g = ctx.createLinearGradient(A[0],A[1],B[0],B[1]);
      g.addColorStop(0,'rgba(227,179,65,0.10)'); g.addColorStop(1,'rgba(227,179,65,0.32)');
      ctx.strokeStyle=g; ctx.lineWidth=1;
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
                 : (nd.ok ? '#3fb950' : '#f85149');
      const halo = ctx.createRadialGradient(x,y,0,x,y,r*2.4);
      halo.addColorStop(0, coul+'55'); halo.addColorStop(1,'transparent');
      ctx.fillStyle=halo; ctx.beginPath(); ctx.arc(x,y,r*2.4,0,7); ctx.fill();
      ctx.fillStyle=coul; ctx.beginPath(); ctx.arc(x,y,r*0.42,0,7); ctx.fill();
      ctx.strokeStyle=coul; ctx.lineWidth=1.2;
      ctx.beginPath(); ctx.arc(x,y,r*0.75,0,7); ctx.stroke();
      ctx.fillStyle='#c9d1d9'; ctx.font='11px -apple-system,sans-serif';
      ctx.textAlign='center';
      ctx.fillText(nd.nom, x, y + r*0.75 + 13);
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

        if self.path.startswith("/cerveau.js"):
            corps = CERVEAU_JS.encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/javascript; charset=utf-8")
            self.send_header("Content-Length", str(len(corps)))
            self.end_headers()
            self.wfile.write(corps)
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
                    "news": d.get("news"),
                    "boule": _boule(d.get("consensus")),
                    "sante": d.get("sante"),
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
