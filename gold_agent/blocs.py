"""Les blocs HTML de la page : cartes de timeframe, boule de consensus,
panneau des agents, onglets Constellation et Marches, grille.
"""
from __future__ import annotations

from pathlib import Path

from .graphique import _chandeliers, _grand_graphique  # noqa: F401

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

    em = r.get("emission")
    tag_em = "" if em is None else (
        ' <span style="font-size:10px;color:#3fb950">émission ON</span>' if em
        else ' <span style="font-size:10px;color:#f85149">émission OFF</span>')
    h = [f'<div class="carte{actif}" data-tf="{r["nom"]}">',
         f'<div class="tete"><div style="display:flex;gap:10px;align-items:center">{jauge}'
         f'<div><div class="tf">{r["nom"]}</div>'
         f'<div class="role">{r["role"]}{tag_em}</div></div></div>'
         f'<span class="badge {cls}">{niveau} · {fi.get("note","")}</span></div>',
         '<div class="corps">']

    if s.get("setup") and s.get("suspendu"):
        h.append(f'<div class="al chaud" style="margin-bottom:8px">&#9940; SUSPENDU par le '
                 f'superviseur : {s["suspendu"]} — non journalisé, non notifié</div>')
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

    im = (r.get("setup") or {}).get("intermarche")
    if im:
        fiab_txt = "" if im.get("fiable") else " · base mince"
        h.append(f'<div class="ict-ligne">🪞 Miroir : confiance <b>×{im["facteur"]:.2f}</b> '
                 f'(score {im["score"]:+.2f}, base {im["base"]:.2f}{fiab_txt})</div>')
    av = (r.get("setup") or {}).get("avocat")
    if av and av.get("objections"):
        for o in av["objections"][:2]:
            etat = ("réfutée ✓" if o["refutee"]
                    else f'à réfuter : {o["refutation"]}')
            h.append(f'<div class="ict-ligne">😈 {o["quoi"]} — <i>{etat}</i></div>')

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


def _fragment_graphe() -> str:
    """graphe.html (INTEGRATION_GRAPHE.md) : rendu canvas autonome du reseau
    des agents. Lu tel quel — jamais interpole dans une f-string, le fichier
    est plein d'accolades JavaScript."""
    try:
        return (Path(__file__).resolve().parent.parent / "graphe.html").read_text(
            encoding="utf-8")
    except Exception:
        return ""


def _panneau_agents(d: dict) -> str:
    """Le système d'agents en direct — chaque champ vient de l'état réel."""
    ags = d.get("agents") or []
    if not ags:
        return ""
    EMOJIS = {"AG-01": "📡", "AG-02": "📈", "AG-03": "♟️", "AG-04": "✏️",
              "AG-05": "⛏️", "AG-06": "🎲", "AG-07": "💡", "AG-00": "🧠",
              "AG-09": "🌌", "AG-10": "🪞"}
    cartes = ""
    for a in ags:
        lignes = "".join(
            f'<div class="lg{" on" if i == 0 else ""}">&rsaquo; {l}</div>'
            for i, l in enumerate(a["activites"][:5]))
        cartes += f"""<div class="agc" style="color:{a['coul']}">
<span class="code">{a['code']}</span>
<h4><span class="ico">{EMOJIS.get(a['code'],'🤖')}</span>
<span style="color:#e6edf3">{a['nom']}</span>
<span class="chip">{a['statut']}</span></h4>
<div class="rl">{a['role']}</div>
<div class="barp"><i></i></div>
<div class="act">{lignes}</div>
<div class="pied"><span>{a['metriques'][:52]}</span>
<span class="mini-conv" title="charge cerveau mesurée (temps CPU réel)">🧠 {a['charge']}%</span></div>
</div>"""

    reps = (d.get("sante") or {}).get("reparations") or []
    if reps:
        boutons = "".join(
            f'<button class="tf-btn" style="margin:3px 6px 0 0;font-size:11px" '
            f'onclick="reparer(&#39;{r["action"]}&#39;, this)" title="{r["contexte"]}">'
            f'&#128295; {r["libelle"]}</button>' for r in reps)
        cartes += (f'<div class="agc" style="color:#1f6feb;grid-column:1/-1">'
                   f'<h4><span class="ico">🧠</span><span style="color:#e6edf3">Corrections '
                   f'proposées par le Superviseur</span>'
                   f'<span class="chip">EN ATTENTE DE TON CLIC</span></h4>'
                   f'<div class="rl">notification envoyée — rien ne s&#39;applique sans ta validation</div>'
                   f'{boutons}</div>')

    lignes_console = "".join(
        f'<div class="cl {e.get("niveau","")}">[{e["t"]}] <b>[{e["agent"]}]</b> {e["texte"]}</div>'
        for e in (d.get("evenements") or [])[-40:])

    convs = ""
    for a in ags:
        r, circ = 17, 2 * 3.14159 * 17
        convs += f"""<div class="cvx"><div style="position:relative;width:42px;height:42px">
<svg width="42" height="42" style="transform:rotate(-90deg)">
<circle cx="21" cy="21" r="{r}" fill="none" stroke="#1a2440" stroke-width="4"/>
<circle cx="21" cy="21" r="{r}" fill="none" stroke="{a['coul']}" stroke-width="4"
 stroke-dasharray="{circ*a['conviction']/100:.1f} {circ:.1f}" stroke-linecap="round"/></svg>
<span style="position:absolute;inset:0;display:flex;align-items:center;justify-content:center;
font-size:10px;font-weight:700;color:{a['coul']}">{a['conviction']}%</span></div>
{a['nom'][:11]}</div>"""

    return f"""<div id="sys-agents"><div class="convs">{convs}
<div style="margin-left:auto;font-size:11px;color:#6e7681;align-self:center">convictions
issues des métriques réelles · 🧠 = part du temps de calcul mesuré</div></div>
<div class="sys"><div class="ag-grille">{cartes}</div>
<div class="console"><h5>PROCESSUS — ÉVÉNEMENTS RÉELS</h5>{lignes_console}</div></div></div>"""


def _grille(d: dict) -> str:
    """Barre de boutons TF (avec pastilles de signal) + cartes cachées.

    Utilisée par la page ET par /json : le premier rafraîchissement
    remplaçait la grille par les cartes seules — la barre disparaissait
    et l'utilisateur restait bloqué sur H4.
    """
    nav_tf = ""
    for r in d["timeframes"]:
        st_ = r.get("setup") or {}
        bip = ""
        if st_.get("setup"):
            bip = ('<span class="bip">⛔</span>' if st_.get("suspendu")
                   else '<span class="bip ok">●</span>')
        nav_tf += f'<button class="tfb" data-tf="{r["nom"]}">{r["nom"]}{bip}</button>'
    return (f'<div class="tf-nav">{nav_tf}</div>'
            + "".join(_carte(r) for r in d["timeframes"]))


