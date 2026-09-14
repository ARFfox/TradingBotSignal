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
<iframe id="tv-iframe" src="https://s.tradingview.com/widgetembed/?symbol=OANDA%3AXAUUSD&interval=30&theme=dark&style=1&locale=fr&hide_side_toolbar=0&allow_symbol_change=0&timezone=Etc%2FUTC"
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




# Couches de lecture du schema en cases — memes familles que graphe_agents.
COUCHES_CASES = [
    ("PERCEPTION", ["AG-01", "AG-02", "AG-04", "AG-05"]),
    ("MARCHÉS", ["AG-11", "AG-12", "AG-13", "AG-14"]),
    ("RELATIONS", ["AG-09", "AG-15", "AG-10"]),
    ("CRITIQUE", ["AG-16"]),
    ("DÉCISION", ["AG-03", "AG-06", "AG-07"]),
]


def _cases_agents(d: dict) -> str:
    """SPEC_SITE_V3 §6 : le panneau principal du Cerveau — un schema en
    CASES figees (CSS grid, traits SVG), lisible d'un coup d'oeil.

    - point de couleur = statut : vert actif · jaune veille · rouge blocage
      · gris muet ; un agent muet garde sa case, en pointilles — JAMAIS
      masque (une case absente ressemble a un agent qui n'existe pas)
    - pas d'icones, pas de moteur physique : les cases ne bougent pas
    - clic sur une case -> le panneau de l'agent
    """
    par_code = {a.get("code"): a for a in (d.get("agents") or [])}

    def _etat(a: dict | None) -> tuple[str, str, bool]:
        """(couleur du point, libelle, vivant)"""
        if not a:
            return "#484f58", "muet", False
        st = str(a.get("statut", "")).upper()
        if st in ("BLOCAGE",):
            return "#f85149", st, True
        if st in ("VEILLE", "OBSERVATION", "COMPUTING", "PERIME", "OBJECTION"):
            return "#d29922", st, True
        if st in ("MUET", "INITIALISATION", "PANNE"):
            return "#484f58", st, False
        return "#3fb950", st or "ACTIF", True

    n = len(COUCHES_CASES)
    colonnes = ""
    couleurs_traits = []
    for titre, codes in COUCHES_CASES:
        cases = ""
        pire = "#30363d"
        for code in codes:
            a = par_code.get(code)
            coul, st, vivant = _etat(a)
            if coul == "#f85149":
                pire = "#f85149"
            elif coul == "#d29922" and pire != "#f85149":
                pire = "#d29922"
            nom = a["nom"] if a else code
            conv = f'{a["conviction"]}%' if a else "—"
            bord = "1px dashed #484f58" if not vivant else "1px solid #30363d"
            detail = (a["activites"][0][:60] if a and a.get("activites") else "aucune donnée")
            cases += (
                f'<div onclick="allerOnglet(&#39;p-cerveau&#39;)" title="{detail}" '
                f'style="border:{bord};border-radius:8px;padding:7px 9px;margin:5px 0;'
                f'background:#0d1117;cursor:pointer;font-size:11.5px">'
                f'<span style="display:inline-block;width:8px;height:8px;border-radius:50%;'
                f'background:{coul};margin-right:6px"></span>'
                f'<b>{code}</b> {nom}'
                f'<span style="float:right;color:#8b949e">{conv}</span></div>')
        couleurs_traits.append(pire)
        colonnes += (f'<div><div style="font-size:10px;letter-spacing:.1em;'
                     f'color:#6e7681;margin-bottom:4px">{titre}</div>{cases}</div>')

    # Traits SVG : chaque couche converge vers le Superviseur. Rouge si la
    # couche porte un blocage, jaune si une contradiction, gris sinon.
    traits = "".join(
        f'<line x1="{(i + 0.5) * 1000 / n:.0f}" y1="0" x2="500" y2="54" '
        f'stroke="{c}" stroke-width="{3 if c != "#30363d" else 1.5}"/>'
        for i, c in enumerate(couleurs_traits))

    a00 = par_code.get("AG-00")
    c00, st00, _ = _etat(a00)
    setups = [x for x in (d.get("signaux_actifs") or [])]
    if not setups:
        for r in d.get("timeframes", []):
            st_ = r.get("setup") or {}
            if st_.get("setup") and not st_.get("suspendu"):
                setups.append({"tf": r["nom"], "sens": st_["setup"],
                               "entree": st_.get("entree")})
    if setups:
        s0 = setups[0]
        signal_txt = (f'{len(setups)} signal(aux) — {s0.get("tf")} '
                      f'{s0.get("sens")} @ {s0.get("entree")}')
        coul_sig = "#3fb950"
    else:
        signal_txt = "aucun signal émis en ce moment"
        coul_sig = "#8b949e"

    return (
        '<div style="background:#010409;border:1px solid #21262d;border-radius:10px;'
        'padding:14px;margin-bottom:14px">'
        f'<div style="display:grid;grid-template-columns:repeat({n},1fr);gap:12px">'
        f'{colonnes}</div>'
        f'<svg viewBox="0 0 1000 54" preserveAspectRatio="none" '
        f'style="display:block;width:100%;height:54px">{traits}</svg>'
        f'<div style="max-width:340px;margin:0 auto;text-align:center;'
        f'border:1.5px solid {c00};border-radius:10px;padding:10px;background:#0d1117">'
        f'<span style="display:inline-block;width:9px;height:9px;border-radius:50%;'
        f'background:{c00};margin-right:6px"></span>'
        f'<b>AG-00 SUPERVISEUR</b> — probabilité + opportunité'
        f'<div style="color:#8b949e;font-size:11.5px;margin-top:3px">{st00} · '
        f'conviction {a00["conviction"] if a00 else "—"}%</div></div>'
        f'<div style="text-align:center;color:#6e7681;font-size:16px">▼</div>'
        f'<div style="max-width:340px;margin:0 auto;text-align:center;'
        f'border:1px solid {coul_sig};border-radius:10px;padding:9px;'
        f'color:{coul_sig};font-size:12.5px;background:#0d1117">'
        f'<b>SIGNAL ÉMIS</b> — {signal_txt}</div></div>')


def _bloc_navigation(d: dict) -> str:
    """SPEC_SITE_V3 §2 : niveau 1 (barre de marches) + niveau 2 (grilles
    d'instruments, prix DIFFERES et annonces comme tels). Les pastilles ne
    sont PAS calculees ici : le JS les derive de la liste unique
    d.signaux_actifs — jamais deux compteurs separes."""
    import json as _json
    from . import instruments as _inst
    ms = d.get("marches_site") or {}
    age = ms.get("age_heures")

    barre, grilles, dico = "", "", {}
    for m in _inst.MARCHES_ORDRE:
        emoji, libelle = _inst.MARCHES_LIBELLES[m]
        barre += (f'<button class="m-btn" data-m="{m}">{emoji} {libelle} '
                  f'<span class="badge" hidden></span></button>')
        tuiles = ""
        for t in ms.get(m, []):
            dico[t["cle"]] = t
            if t["prix"] is not None:
                fmt = f'{{:.{t["decimales"]}f}}'
                prix_txt = fmt.format(t["prix"])
                v = t.get("variation_pct")
                var_txt = (f'<span style="color:{"#3fb950" if v >= 0 else "#f85149"}">'
                           f'{"▲" if v >= 0 else "▼"} {abs(v):.2f}%</span>'
                           if v is not None else "")
            else:
                prix_txt, var_txt = "—", ""
            tuiles += (f'<div class="tuile-inst" data-cle="{t["cle"]}" data-m="{m}">'
                       f'<b>{t["libelle"]}</b> <span class="badge" hidden></span>'
                       f'<div style="font-size:15px;font-weight:700">{prix_txt}</div>'
                       f'<div style="font-size:11px">{var_txt}</div>'
                       f'<div style="font-size:9.5px;color:#6e7681">{t["nom"]}</div></div>')
        note_age = f"prix différés · cache yfinance ({age} h)" if age is not None else "cache en construction"
        grilles += (f'<div id="mg2-{m}" class="m-grille" hidden>'
                    f'<div style="font-size:10.5px;color:#6e7681;margin:2px 0 6px">'
                    f'{note_age} — seul l&#39;instrument actif a un prix en direct</div>'
                    f'<div class="m-tuiles">{tuiles}</div></div>')

    donnees = _json.dumps({"instruments": dico,
                           "signaux": d.get("signaux_actifs") or []},
                          ensure_ascii=False)
    return (f'<div class="marches-nav">{barre}</div>{grilles}'
            f'<div id="note-instrument" class="bandeau" hidden '
            f'style="border-color:#d29922"></div>'
            f'<script type="application/json" id="donnees-instruments">'
            f'{donnees}</script>')


def _bloc_rapport() -> str:
    """Le dernier rapport quotidien du Chef, replie sous un <details>."""
    try:
        from . import rapport_chef
        texte = rapport_chef.dernier()
    except Exception:
        texte = None
    if not texte:
        return ('<div style="font-size:11px;color:#6e7681;margin:10px 0">'
                'Le premier rapport quotidien du Chef sera écrit à la '
                'prochaine collecte.</div>')
    import html as _html
    return ('<details style="margin:12px 0"><summary style="cursor:pointer;'
            'font-size:12.5px;color:#c9d1d9">📋 Rapport quotidien du Chef '
            '(dernier)</summary><pre style="white-space:pre-wrap;font-size:11.5px;'
            'color:#8b949e;background:#0d1117;border:1px solid #21262d;'
            'border-radius:8px;padding:12px;margin-top:8px">'
            + _html.escape(texte) + '</pre></details>')
