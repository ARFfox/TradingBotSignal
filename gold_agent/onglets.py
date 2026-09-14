"""Les onglets de la page : Risque evenementiel, Analyse graphique,
Strategies, Historique, Constellation, Marches. Separe de blocs.py
(regle 17).
"""
from __future__ import annotations

from .blocs import WIDGET_TV, _boule
from .graphique import _grand_graphique


def _bloc_marches(d: dict) -> str:
    """INTEGRATION_MARCHES.md §4 : tuiles, grilles, avances.

    variation_pct (perf 20 j du composite) et largeur (part de membres
    haussiers) mesurent deux choses differentes et s'affichent separement.
    Le degrade de la grille porte sur force_relative : dans un marche qui
    monte de 11 %, un actif a +8 % est un retardataire, pas un gagnant."""
    m = d.get("marches")
    if not m:
        return ('<div class="carte"><h3>🌍 Les 4 marchés</h3>'
                '<p style="color:#8b949e">cache de prix en cours de construction '
                '— revenir dans quelques minutes</p></div>')

    tuiles = ""
    for t in m["tuiles"]:
        if not t.get("fiable"):
            corps = '<div style="color:#8b949e;font-size:12px">données insuffisantes</div>'
        else:
            fl = "▲" if t["variation_pct"] >= 0 else "▼"
            cf = "#3fb950" if t["variation_pct"] >= 0 else "#f85149"
            corps = (f'<div style="font-size:18px;font-weight:700;color:{cf}">'
                     f'{fl} {abs(t["variation_pct"]):.1f}%<span style="font-size:10.5px;'
                     f'color:#6e7681;font-weight:400"> / 20 j</span></div>'
                     f'<div style="font-size:12px;color:#c9d1d9;margin:3px 0">{t["regime"]}</div>'
                     f'<div style="font-size:11px;color:#8b949e">largeur {t["largeur"]:.0%} haussiers '
                     f'· cohésion {t["cohesion"]:+.2f}</div>'
                     f'<div style="font-size:11px;color:#8b949e">{t["actifs"]} actifs · '
                     f'leader {t["leader"]}</div>')
        tuiles += (f'<div class="carte" style="cursor:pointer;border-color:{t["coul"]}44" '
                   f'onclick="marcheGrille(&#39;{t["cle"]}&#39;)">'
                   f'<h3 style="color:{t["coul"]}">{t["emoji"]} {t["nom"]}</h3>{corps}</div>')

    grilles = ""
    for cle, carreaux in m["grilles"].items():
        lignes = ""
        for c in carreaux:
            fr = c["force_relative"]
            # Degrade continu sur la force relative, borne a +/-3 points.
            x = max(-1.0, min(1.0, fr / 3.0))
            coul = f"rgba(63,185,80,{abs(x)*.85:.2f})" if x >= 0 else f"rgba(248,81,73,{abs(x)*.85:.2f})"
            role = {"leader": " 👑", "retardataire": " 🐌"}.get(c["role"], "")
            lignes += (f'<tr><td>{c["ticker"]}{role}</td>'
                       f'<td style="text-align:right">{c["variation_pct"]:+.2f}%</td>'
                       f'<td>{c["biais"]}</td>'
                       f'<td style="text-align:right;background:{coul}">{fr:+.2f}</td></tr>')
        grilles += (f'<div id="mg-{cle}" class="carte" hidden style="grid-column:1/-1">'
                    f'<h3>Grille — force relative (perf − médiane du marché)</h3>'
                    f'<table><tr><th>Actif</th><th>Perf 20 j</th><th>Biais</th>'
                    f'<th>Force rel.</th></tr>{lignes}</table></div>')

    fx = (d.get("news") or {}).get("flux_crypto") or {}
    if fx.get("disponible"):
        grilles += ('<div class="carte" style="grid-column:1/-1"><h3>₿ Positionnement '
                    'crypto (Binance Futures, quotidien)</h3>'
                    + "".join(f'<div style="font-size:12.5px;margin:3px 0">• {x}</div>'
                              for x in fx.get("lecture", []))
                    + '<div style="font-size:11px;color:#6e7681;margin-top:6px">'
                    'Lecture de positionnement, pas un vote — pertinente pour '
                    'l&#39;or depuis que la constellation mesure le recouplage '
                    'or/crypto.</div></div>')

    av = ""
    menes = [a for a in m.get("avances", []) if a.get("jours")]
    if menes:
        av = ("<div class='carte' style='grid-column:1/-1'><h3>🕸️ Avances mesurées</h3>" +
              "".join(f"<div style='font-size:12.5px;margin:3px 0'>→ {a['verdict']} "
                      f"(corr {a['corr']:+.2f}, gain {a['gain']:+.2f})</div>" for a in menes) +
              "<div style='font-size:11px;color:#6e7681;margin-top:6px'>Seuil corrigé du test "
              "multiple (z 2,8 sur 11 décalages) — « simultané » est la réponse la plus "
              "fréquente et c'est normal.</div></div>")

    return (f'<div class="cerveau" style="grid-template-columns:repeat(auto-fit,minmax(220px,1fr))">'
            f'{tuiles}{grilles}{av}</div>'
            '<script>function marcheGrille(k){document.querySelectorAll("[id^=mg-]")'
            '.forEach(e=>{e.hidden = (e.id !== "mg-"+k) || !e.hidden});}</script>')



def _bloc_constellation(d: dict) -> str:
    """Onglet Constellation — INTEGRATION_AG09.md étape 5 (affichage).

    Les clusters sont encadrés avec la mention « une seule voix » : c'est ce
    qui rend le score compréhensible quand 13 lignes produisent une base de
    2,28. TRANSITION s'affiche avec sa flèche — changement de régime, pas
    du bruit.
    """
    c = d.get("constellation") or {}
    if not c:
        return ('<div class="strats">Constellation en cours d&#39;initialisation — '
                'le cache des 37 actifs se construit en tâche de fond.</div>')

    sc = c.get("score") or {}
    biais = c.get("biais") or {}

    h = ['<div class="strats">']
    for r_ in c.get("ruptures", []):
        h.append(f'<div class="risque veto" style="margin-bottom:8px">RUPTURE DE RÉGIME — '
                 f'{r_["actif"]} : corrélation {r_["avant"]:+.2f} → {r_["apres"]:+.2f}</div>')

    verd = ("BLOQUÉ" if sc.get("bloque") else
            ("fiable" if sc.get("fiable") else "base trop mince"))
    coul_v = "#f85149" if sc.get("bloque") else ("#3fb950" if sc.get("fiable") else "#d29922")
    h.append(f'<div style="font-size:14px;margin-bottom:12px">Verdict du Miroir — sens testé '
             f'<b>{c.get("sens_teste","?")}</b> : score <b style="color:{coul_v}">'
             f'{sc.get("score",0):+.2f}</b> sur base {sc.get("base",0):.2f} ({verd}) · '
             f'{len(sc.get("confirment",[]))} confirment · '
             f'{len(sc.get("contredisent",[]))} contredisent · '
             f'confiance ×{sc.get("facteur_confiance",1):.2f}'
             + (f'<br><span style="color:#8b949e;font-size:12px">{str(sc.get("motif",""))[:160]}'
                f'</span>' if sc.get("motif") else "") + '</div>')

    def table(membres, titre, coul):
        conf = set(sc.get("confirment", []))
        contre = set(sc.get("contredisent", []))
        lignes = ""
        for m in membres:
            fleche = {"TRANSITION ^": " ↑", "TRANSITION v": " ↓"}.get(m["tendance"], "")
            trans = (f'<span style="color:#d29922">TRANSITION{fleche}</span>'
                     if str(m["tendance"]).startswith("TRANSITION") else m["tendance"])
            etat = ("✅" if m["ticker"] in conf else
                    ("❌" if m["ticker"] in contre else "·"))
            lignes += (f'<tr><td>{etat}</td><td><b>{m["ticker"]}</b></td>'
                       f'<td>{m["corr"]:+.2f}</td><td>{m["poids"]:.2f}</td>'
                       f'<td>{biais.get(m["ticker"], "?")}</td><td>{trans}</td></tr>')
        return (f'<div style="margin-bottom:14px"><div style="color:{coul};font-weight:700;'
                f'margin-bottom:6px">{titre}</div><table>'
                f'<tr><th></th><th>actif</th><th>corr</th><th>poids</th>'
                f'<th>biais</th><th>régime</th></tr>{lignes}</table></div>')

    ops_r = d.get("rattrapage") or []
    if ops_r:
        lignes_r = ""
        for o in ops_r:
            val = ('<span style="color:#d29922"> · à valider (Vigie agitée : '
                   'une news spécifique n&#39;est pas une divergence)</span>'
                   if o.get("a_valider") else "")
            lignes_r += (f'<div style="margin:4px 0;font-size:12.5px">🎯 '
                         f'<b>{o["ticker"]}</b> en retard de <b>{o["z"]:+.1f} σ</b> '
                         f'sur l&#39;or (or {o.get("perf5j_pivot", "?"):+}% / '
                         f'{o["ticker"]} {o.get("perf5j_membre", "?"):+}% sur 5 j) '
                         f'→ piste <b>{o["sens"]}</b> {o["ticker"]} · {o["note"]}{val}</div>')
        h.append('<div style="border:1px solid #7ee787;border-radius:8px;'
                 'padding:10px 12px;margin-bottom:14px">'
                 '<div style="color:#7ee787;font-weight:700">🎯 Rattrapage (AG-17) '
                 '— paires à corrélation STABLE seulement</div>' + lignes_r +
                 '<div style="font-size:11px;color:#6e7681;margin-top:6px">'
                 'Piste d&#39;analyse, PAS un signal : cette famille n&#39;a pas '
                 'encore passé le walk-forward, et le taux affiché est mesuré '
                 'sur l&#39;historique de la paire.</div></div>')

    h.append(table(c.get("satellites", []), f'🟢 Satellites ({len(c.get("satellites",[]))}) '
             f'— bougent avec l&#39;or', "#3fb950"))
    h.append(table(c.get("miroirs", []), f'🔴 Miroirs ({len(c.get("miroirs",[]))}) '
             f'— bougent à l&#39;inverse', "#f85149"))

    cl = c.get("clusters") or []
    if cl:
        boites = "".join(
            f'<span style="border:1px solid #a371f7;border-radius:6px;padding:4px 10px;'
            f'margin:0 6px 6px 0;display:inline-block;font-size:12px">'
            f'{" + ".join(g)}</span>' for g in cl)
        h.append(f'<div style="margin-bottom:12px"><div style="color:#a371f7;font-weight:700">'
                 f'Clusters — chaque groupe encadré compte pour UNE seule voix</div>'
                 f'<div style="margin-top:6px">{boites}</div></div>')

    h.append(f'<details><summary style="cursor:pointer;color:#8b949e">'
             f'⚪ {c.get("n_decouples",0)} actifs découplés (aucune relation exploitable '
             f'avec l&#39;or en ce moment) — cliquer pour la liste</summary>'
             f'<div style="color:#6e7681;font-size:12px;margin-top:6px">'
             + ", ".join(sorted(set(biais.keys())
                 - {m["ticker"] for m in c.get("satellites",[]) + c.get("miroirs",[])}))
             + '</div></details>')
    h.append('<div style="color:#6e7681;font-size:11.5px;margin-top:10px">37 actifs · '
             'fenêtres 30/90/250 j · recalcul 6 h · source yfinance (cache disque) · '
             f'biais : {c.get("source_biais", "?")} · '
             'les relations viennent des DONNÉES, jamais d&#39;idées reçues</div>')
    h.append("</div>")
    return "".join(h)





def _blocs_onglets(d: dict) -> dict:
    """Construit les quatre onglets textuels de la page : Risque evenementiel,
    Analyse graphique, Strategies, Historique. Extrait de rendre() (regle 17).
    """
    q = d.get("quote") or {}
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

    sn = n.get("saison") or {}
    if sn.get("disponible"):
        lignes_macro += (
            f'<div class="macrol">Saisonnalité ({sn["annees"]} ans) : {sn["mois"]} '
            f'<b>{sn["moyen_pct"]:+.1f}%</b> en moyenne, {sn["taux_positif_pct"]}% de mois positifs</div>')

    mi = n.get("minieres") or {}
    if mi.get("disponible"):
        div = mi.get("divergence")
        etat_mi = (f'divergence {div} détectée' if div
                   else 'les minières confirment le mouvement')
        lignes_macro += (
            f'<div class="macrol">Minières (AEM, {mi["fenetre_jours"]} j) : '
            f'<b>{mi["aem"]["variation_pct"]:+.1f}%</b> vs or '
            f'<b>{mi["or"]["variation_pct"]:+.1f}%</b> — {etat_mi}</div>')

    gd = n.get("gdelt") or {}
    if gd.get("disponible"):
        lignes_macro += "".join(
            f'<div class="macrol">🌐 GDELT (presse mondiale, 15 min) : {x}</div>'
            for x in gd.get("lecture", []))

    act = n.get("actus") or {}
    bloc_geo = ""
    if act.get("niveau") == "eleve":
        bloc_geo = (f'<div class="risque veto" style="margin-bottom:10px">'
                    f'RÉGIME GÉOPOLITIQUE — {act.get("part_geopolitique_pct","?")}% des titres '
                    f'évoquent un conflit. Stops techniques peu fiables ; le backtest ne couvre '
                    f'pas ce régime.</div>')
    lignes_actus = ""
    for x in (act.get("titres") or [])[:8]:
        g = x.get("gravite") or ("rouge" if x.get("geopolitique") else "gris")
        coul = {"rouge": "#f85149", "jaune": "#d29922"}.get(g, "#6e7681")
        gras = ' style="color:#ffa198;font-weight:600"' if g == "rouge" else ""
        src = x.get("source", "")
        lignes_actus += (f'<div class="evt" style="border-left:3px solid {coul};padding-left:8px">'
                         f'<span class="t"{gras}>{x["titre"][:92]}</span>'
                         f'<span class="q">{src} · {x["date"]}</span></div>')
    if lignes_actus:
        lignes_actus = f'<h3 style="margin-top:14px">Actualités — 5 sources (Google, Yahoo, CNBC, MarketWatch, FXStreet)</h3>{lignes_actus}'

    bloc_news = f"""<div class="news">
<div><h3>Risque événementiel</h3>{bloc_geo}
<div class="risque {et}">{risque.get("detail", "?")}</div>
{lignes_agenda}{lignes_actus}</div>
<div><h3>Macro — moteurs de fond de l'or</h3>{lignes_macro}</div>
</div>"""

    boule = _boule(d.get("consensus"))
    widget = WIDGET_TV

    # Onglet analyse graphique : nos graphiques en grand, avec les zones de
    # la regle superposees — ce que le widget TradingView ne peut pas montrer.
    # Les onglets Analyse graphique / Strategies ont ete retires
    # (14/09) : le grand graphique vit dans les cartes, la grille de
    # conviction dans Signaux valides.
    hi = d.get("historique") or {}

    # SPEC_SITE_V3 §7 — « Signaux validés » : seuls les signaux EMIS y
    # figurent (le journal n'enregistre que ceux-la : les suspendus et les
    # timeframes coupes n'y entrent jamais). C'est la seule definition qui
    # rend le taux honnete : il mesure ce qui t'a ete recommande.
    from .instruments import par_defaut as _pd
    _defaut_inst = _pd().symbole
    ICONES = {"gagnant": ("✅ TP", "ok"), "perdant": ("❌ SL", "ko"),
              "ouvert": ("⏳ en cours", ""), "en_attente": ("🕐 en attente", ""),
              "non_execute": ("⚪ expiré", "")}
    lignes_h = ""
    for x in hi.get("derniers", []):
        icone, cls_h = ICONES.get(x["statut"], (x["statut"], ""))
        r_txt = (f'{x["r_obtenu"]:+.2f}' if x.get("r_obtenu") is not None
                 and x["statut"] in ("gagnant", "perdant") else "—")
        estompe = ' style="opacity:.55"' if x["statut"] not in ("gagnant", "perdant") else ""
        note_x = x.get("decision_chef")
        lignes_h += (f'<tr{estompe}><td>{x["cree_le"][:16].replace("T", " ")}</td>'
                     f'<td>{x.get("instrument", _defaut_inst)}</td>'
                     f'<td>{x["tf"]}</td><td>{x["sens"]}</td><td>{x["entree"]}</td>'
                     f'<td>{x["stop"]}</td><td>{x["objectif"]}</td>'
                     f'<td>{note_x if note_x is not None else "—"}%</td>'
                     f'<td class="{cls_h}">{icone}</td><td>{r_txt}</td></tr>')
    if not lignes_h:
        lignes_h = ('<tr><td colspan="10">aucun signal émis pour l&#39;instant — '
                    'le journal se remplit à mesure que la règle émet</td></tr>')

    resolus = hi.get("resolus", 0)
    # Definition de Mushine (14/09) : TP touche = positif, SL touche =
    # negatif, pourcentage du cumul des deux — toujours affiche, avec
    # l'effectif juste en dessous (un % sans effectif serait trompeur).
    if resolus and hi.get("taux_reussite_pct") is not None:
        taux_txt = f'{hi["taux_reussite_pct"]}%'
        taux_sous = (f'{hi.get("gagnants", 0)} TP ✅ / '
                     f'{hi.get("perdants", 0)} SL ❌ ({resolus} résolus)')
    else:
        taux_txt = "—"
        taux_sous = "aucun signal résolu encore"
    rs_ = [x.get("r_obtenu") or 0 for x in hi.get("derniers", [])
           if x.get("statut") in ("gagnant", "perdant")]
    gains_ = sum(r for r in rs_ if r > 0)
    pertes_ = abs(sum(r for r in rs_ if r < 0))
    pf_txt = (f'{gains_ / pertes_:.2f}' if pertes_ else ("∞" if gains_ else "—"))

    def _stat(valeur, libelle, sous=""):
        return (f'<div style="text-align:center;padding:4px 14px">'
                f'<div style="font-size:21px;font-weight:800">{valeur}</div>'
                f'<div style="font-size:10.5px;color:#8b949e">{libelle}'
                + (f'<br>{sous}' if sous else "") + '</div></div>')

    entete_h = ('<div style="display:flex;justify-content:space-around;flex-wrap:wrap;'
                'border:1px solid #21262d;border-radius:10px;background:#0d1117;'
                'padding:8px;margin-bottom:12px">'
                + _stat(f'{hi.get("cumul_R", 0):+.2f}R', "R cumulé",
                        "la mesure qui compte")
                + _stat(taux_txt, "signaux validés par les agents", taux_sous)
                + _stat(f'{resolus} / {hi.get("total_emis", 0)}', "résolus / émis")
                + _stat(pf_txt, "profit factor") + '</div>')

    bloc_histo = f"""<div class="strats">
<div style="font-size:12px;color:#8b949e;margin-bottom:8px"><b style="color:#e6edf3">
SIGNAUX VALIDÉS</b> — uniquement ce qui t&#39;a été affiché ou notifié. Pas les setups
rejetés, pas les timeframes coupés : si tu ne l&#39;as pas vu à l&#39;écran, il n&#39;est pas ici.</div>
{entete_h}
<table><tr><th>Émis le (UTC)</th><th>Instrument</th><th>TF</th><th>Sens</th><th>Entrée</th><th>SL</th><th>TP</th><th>Note</th><th>Résultat</th><th>R</th></tr>
{lignes_h}</table>
<div style="font-size:11.5px;color:#6e7681;margin-top:8px">Les signaux expirés (entrée jamais
touchée) et en cours ne comptent ni dans le taux ni dans le R : il n&#39;y a rien à y gagner ni à
y perdre. Bougie touchant stop ET objectif = perte (convention prudente du backtest).</div></div>"""

    return {"news": bloc_news,
            "histo": bloc_histo + _bloc_grille(d),
            "boule": boule, "widget": widget}


COULEUR_CARREAU = {"vert": "#3fb950", "bleu": "#58a6ff",
                   "gris": "#8b949e", "rouge": "#f85149"}


def _bloc_grille(d: dict) -> str:
    """La grille de conviction : etat live 90 j + verdict walk-forward.

    Affichage seulement : l'emission reste gouvernee par config.tf_emission
    tant que Mushine n'a pas valide le cablage de la regle 3.
    """
    g = d.get("grille") or []
    if not g:
        return ""
    lignes = ""
    for x in g:
        cl = COULEUR_CARREAU.get(x["couleur"], "#8b949e")
        wf = x.get("walkforward")
        if wf:
            v = "✅ autorisé" if wf["autorise"] else "❌ refusé"
            wf_txt = (f'{v} · {wf["trades"]} trades · R moyen '
                      f'{wf["r_moyen"]:+.3f} · PF {wf["profit_factor"]}')
            if wf.get("note"):
                wf_txt += f'<br><span style="color:#d29922">{wf["note"]}</span>'
        else:
            wf_txt = "pas encore mesuré — lancer python3 -m research.rapport_edge"
        pf = x["profit_factor"]
        pf_txt = "∞" if pf == float("inf") else f"{pf}"
        lignes += (
            f'<tr><td><span style="display:inline-block;width:10px;height:10px;'
            f'border-radius:50%;background:{cl};margin-right:7px"></span>'
            f'<b>{x["tf"]}</b></td>'
            f'<td style="color:{cl};font-weight:700">{x["couleur"].upper()}</td>'
            f'<td>{x["trades"]} résolu(s) · {x["r_cumule"]:+.2f}R · PF {pf_txt} · '
            f'{x["taux_reussite"]}%</td>'
            f'<td style="font-size:11.5px">{wf_txt}</td></tr>')
    return (
        '<div class="strats" style="margin-top:14px"><h3 style="margin:0 0 8px">'
        '🟩 Grille de conviction — XAU/USD</h3><table>'
        '<tr><th>TF</th><th>Carreau (90 j live)</th><th>Journal réel</th>'
        '<th>Walk-forward (protocole)</th></tr>' + lignes + '</table>'
        '<div style="font-size:11.5px;color:#6e7681;margin-top:8px">'
        'VERT = R &gt; +0,3 ET PF &gt; 1,3 ET ≥ 30 trades résolus sur 90 jours '
        'glissants — le seul état qui donnera le droit d&#39;émettre quand la '
        'règle 3 sera câblée (pour l&#39;instant la grille OBSERVE, l&#39;émission '
        'reste fondée sur les backtests H4/H1/M30).</div></div>')
