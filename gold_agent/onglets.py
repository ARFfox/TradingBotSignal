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
    btns, charts = "", ""
    for i, r in enumerate(d["timeframes"]):
        actif = " actif" if i == 0 else ""
        btns += f'<button class="tf-btn{actif}" data-c="gc-{r["nom"]}">{r["nom"]}</button>'
        svg = _grand_graphique(r)
        s_ = r.get("setup") or {}
        etat = (f'{s_["setup"].upper()} — entrée {s_["entree"]} · stop {s_["stop"]} · '
                f'TP {s_["objectif"]} · R:R {s_["rr"]}') if s_.get("setup")                else f'aucun signal — {s_.get("raison", "")}'
        abc_ = r.get("abc") or {}
        chips = ['<span style="color:#3fb950">📈 Structure : EMA + S/R + zigzag</span>',
                 '<span style="color:#a371f7">✏️ Traceur : Fibonacci 38/50/62</span>']
        if abc_.get("scenario"):
            chips.append(f'<span style="color:#a371f7">✏️ Traceur : ABC cible {abc_["cible_C"]}</span>')
        if s_.get("setup"):
            chips.append('<span style="color:#e3b341">♟️ Stratège : zones entrée/SL/TP</span>')
            chips.append(f'<span style="color:#1f6feb">🧠 Superviseur : '
                         f'{"SUSPENDU" if s_.get("suspendu") else "validé"}</span>')
        barre = ('<div style="font-size:11px;margin:2px 0 8px;display:flex;gap:14px;flex-wrap:wrap">'
                 + " ".join(chips) + '</div>')
        charts += (f'<div id="gc-{r["nom"]}" class="grand-chart{actif}">'
                   f'<div style="font-size:13px;color:#c9d1d9;margin-bottom:2px">'
                   f'<b>{r["nom"]}</b> · {etat}</div>{barre}{svg}</div>')
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
    # SPEC_SITE_V3 §7 — « Signaux validés » : seuls les signaux EMIS y
    # figurent (le journal n'enregistre que ceux-la : les suspendus et les
    # timeframes coupes n'y entrent jamais). C'est la seule definition qui
    # rend le taux honnete : il mesure ce qui t'a ete recommande.
    ICONES = {"gagnant": ("✅ TP", "ok"), "perdant": ("❌ SL", "ko"),
              "ouvert": ("⏳ en cours", ""), "en_attente": ("🕐 en attente", ""),
              "non_execute": ("⚪ expiré", "")}
    lignes_h = ""
    for x in hi.get("derniers", []):
        icone, cls_h = ICONES.get(x["statut"], (x["statut"], ""))
        r_txt = (f'{x["r_obtenu"]:+.2f}' if x.get("r_obtenu") is not None
                 and x["statut"] in ("gagnant", "perdant") else "—")
        estompe = ' style="opacity:.55"' if x["statut"] not in ("gagnant", "perdant") else ""
        lignes_h += (f'<tr{estompe}><td>{x["cree_le"][:16].replace("T", " ")}</td>'
                     f'<td>{x["tf"]}</td><td>{x["sens"]}</td><td>{x["entree"]}</td>'
                     f'<td>{x["stop"]}</td><td>{x["objectif"]}</td>'
                     f'<td class="{cls_h}">{icone}</td><td>{r_txt}</td></tr>')
    if not lignes_h:
        lignes_h = ('<tr><td colspan="8">aucun signal émis pour l&#39;instant — '
                    'le journal se remplit à mesure que la règle émet</td></tr>')

    resolus = hi.get("resolus", 0)
    # Regle 2 de la spec : sous 20 resolus, « echantillon insuffisant » A LA
    # PLACE du pourcentage — un taux sur 3 signaux est du bruit.
    if resolus >= 20 and hi.get("taux_reussite_pct") is not None:
        taux_txt = f'{hi["taux_reussite_pct"]}%'
        taux_sous = f'({resolus} résolus)'
    else:
        taux_txt = "échantillon<br>insuffisant"
        taux_sous = f'({resolus} résolus — il en faut 20)'
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
                + _stat(taux_txt, "taux de réussite", taux_sous)
                + _stat(f'{resolus} / {hi.get("total_emis", 0)}', "résolus / émis")
                + _stat(pf_txt, "profit factor") + '</div>')

    bloc_histo = f"""<div class="strats">
<div style="font-size:12px;color:#8b949e;margin-bottom:8px"><b style="color:#e6edf3">
SIGNAUX VALIDÉS</b> — uniquement ce qui t&#39;a été affiché ou notifié. Pas les setups
rejetés, pas les timeframes coupés : si tu ne l&#39;as pas vu à l&#39;écran, il n&#39;est pas ici.</div>
{entete_h}
<table><tr><th>Émis le (UTC)</th><th>TF</th><th>Sens</th><th>Entrée</th><th>SL</th><th>TP</th><th>Résultat</th><th>R</th></tr>
{lignes_h}</table>
<div style="font-size:11.5px;color:#6e7681;margin-top:8px">Les signaux expirés (entrée jamais
touchée) et en cours ne comptent ni dans le taux ni dans le R : il n&#39;y a rien à y gagner ni à
y perdre. Bougie touchant stop ET objectif = perte (convention prudente du backtest).</div></div>"""

    return {"news": bloc_news, "graph": bloc_graph,
            "strats": bloc_strats + _bloc_grille(d), "histo": bloc_histo,
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
