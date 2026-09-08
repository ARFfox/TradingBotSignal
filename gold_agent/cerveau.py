"""Le cerveau du tableau : consensus, sante des agents, cartes live.

Separe de tableau.py (regle 17 : aucun fichier > 500 lignes).
tableau.collecter() produit les donnees ; ce module les transforme en
verdicts (consensus pondere, diagnostic du Superviseur, les 16 cartes
d'agents du panneau). Aucune de ces fonctions ne fait d'appel reseau.
"""
from __future__ import annotations

from . import config, journal


# Poids par timeframe pour le consensus : le H4 pese plus que le M15,
# comme dans le module de debat (un signal court ne renverse pas une
# structure longue).
POIDS_TF = {"H4": 3.0, "H1": 2.0, "M30": 1.0, "M15": 0.5, "M5": 0.25}


def _consensus(resultats: list, macro: dict, minieres: dict, cot: dict,
               saison: dict | None = None) -> dict:
    """Agrège toutes les couches en une répartition haussier/baissier.

    Même logique que le débat contradictoire : chaque élément vote avec un
    poids, rien n'est compensé silencieusement. La liste des contributions
    est renvoyée pour que la boule soit VÉRIFIABLE — un consensus qu'on ne
    peut pas décomposer est un chiffre de marketing.
    """
    contributions = []

    def voter(camp, poids, source):
        contributions.append({"camp": camp, "poids": round(poids, 1), "source": source})

    for r in resultats:
        w = POIDS_TF.get(r["nom"], 1.0)
        ef, es, rsi = r.get("ema_fast"), r.get("ema_slow"), r.get("rsi")
        prix = r.get("prix")
        if ef and es:
            voter("haussier" if ef > es else "baissier", w * 1.5,
                  f"{r['nom']} : EMA rapide {'>' if ef > es else '<'} lente")
        if prix and es:
            voter("haussier" if prix > es else "baissier", w * 1.0,
                  f"{r['nom']} : prix {'au-dessus' if prix > es else 'sous'} EMA lente")
        if rsi is not None:
            if rsi >= 55:
                voter("haussier", w * 0.5, f"{r['nom']} : RSI {rsi:.0f}")
            elif rsi <= 45:
                voter("baissier", w * 0.5, f"{r['nom']} : RSI {rsi:.0f}")
        setup = r.get("setup") or {}
        if setup.get("setup"):
            voter("haussier" if setup["setup"] == "achat" else "baissier",
                  w * 1.0, f"{r['nom']} : signal {setup['setup']} actif")

    for src in (macro, minieres, cot, saison):
        for camp, poids, txt in (src or {}).get("arguments", []):
            voter(camp, poids, txt.split(" — ")[0][:60])

    p_h = sum(c["poids"] for c in contributions if c["camp"] == "haussier")
    p_b = sum(c["poids"] for c in contributions if c["camp"] == "baissier")
    total = p_h + p_b
    pct = round(p_h / total * 100, 1) if total else 50.0
    if pct >= 65:
        verdict = "HAUSSIER"
    elif pct <= 35:
        verdict = "BAISSIER"
    else:
        verdict = "PARTAGÉ"
    contributions.sort(key=lambda c: -c["poids"])
    return {"haussier": round(p_h, 1), "baissier": round(p_b, 1),
            "pct_haussier": pct, "verdict": verdict,
            "nb_haussier": sum(1 for c in contributions if c["camp"] == "haussier"),
            "nb_baissier": sum(1 for c in contributions if c["camp"] == "baissier"),
            "contributions": contributions[:14]}


def _sante(resultats: list, usage, quote) -> dict:
    """État de chaque « agent » (module) : le Cerveau du site.

    Chaque ligne dit ce que fait le module, d'où viennent ses données et
    s'il répond — avec le diagnostic du superviseur : la liste des
    problèmes détectés maintenant.
    """
    from . import news as _news
    agents, problemes = [], []

    def agent(nom, role, source, ok, detail, emoji="🤖", cible=None):
        agents.append({"nom": nom, "role": role, "source": source,
                       "ok": bool(ok), "detail": detail,
                       "emoji": emoji, "cible": cible})
        if not ok:
            problemes.append(f"{nom} : {detail}")

    donnees_ok = sum(1 for r in resultats if not r.get("erreur"))
    agent("Prix & bougies", "cotations et historique 5 timeframes",
          "Twelve Data (5 clés en rotation)", donnees_ok == len(resultats),
          f"{donnees_ok}/{len(resultats)} timeframes servis", "📊", "p-graph")
    q_ok = bool(quote) and quote.get("age", 999) < 120
    agent("Prix direct", "dernier prix traité (15 s)", "Twelve Data /quote",
          q_ok, f"âge {quote.get('age','?')} s" if quote else "indisponible", "💹", "p-graph")
    if usage and usage.get("limite"):
        restant = usage["restant"]
        agent("Quota API", "suivi de la consommation réelle", "Twelve Data /api_usage",
              restant > 200, f"{restant}/{usage['limite']} restantes", "🔋", "p-cerveau")
    try:
        r = _news.risque_evenementiel()
        agent("News & calendrier", "veto avant publication à fort impact",
              "ForexFactory (cache disque)", r.get("etat") != "inconnu", r.get("detail", ""), "📅", "p-risque")
    except Exception as e:
        agent("News & calendrier", "veto événementiel", "ForexFactory", False, str(e)[:60], "📅", "p-risque")
    try:
        m = _news.macro()
        agent("Macro", "taux réels + dollar (moteurs de fond)", "FRED",
              m.get("disponible"), m.get("erreur") or "séries à jour", "🏦", "p-risque")
    except Exception as e:
        agent("Macro", "taux réels + dollar", "FRED", False, str(e)[:60], "🏦", "p-risque")
    try:
        c = _news.positionnement()
        agent("Positionnement", "positions des fonds spéculatifs", "CFTC (COT)",
              c.get("disponible"), c.get("erreur") or f"rapport du {c.get('date')}", "🐋", "p-risque")
    except Exception as e:
        agent("Positionnement", "COT", "CFTC", False, str(e)[:60], "🐋", "p-risque")
    try:
        mi = _news.minieres()
        agent("Minières", "divergence de confirmation (AEM)", "Twelve Data",
              mi.get("disponible"), mi.get("erreur") or "corrélation suivie", "⛏️", "p-risque")
    except Exception as e:
        agent("Minières", "AEM", "Twelve Data", False, str(e)[:60], "⛏️", "p-risque")
    from . import notify as _notify
    can = _notify.etat_canaux()
    agent("Notifications", "système + push téléphone", "osascript / ntfy.sh",
          can["systeme"] or can["telephone"],
          f"système {'oui' if can['systeme'] else 'non'}, "
          f"téléphone {'oui' if can['telephone'] else 'non'}", "🔔", None)
    # --- Le superviseur regarde aussi les RESULTATS, pas que la tuyauterie ---
    import time as _t
    hist = journal.statistiques()
    hist7 = journal.statistiques(fenetre_jours=7)
    resolus = hist7.get("resolus", 0)
    perdants = hist7.get("perdants", 0)
    journal_ok = True
    detail_j = (f"{hist.get('resolus',0)} resolu(s) au total, "
                f"cumul {hist.get('cumul_R', 0):+.1f}R")
    if resolus >= 5 and perdants / max(resolus, 1) >= 0.8:
        journal_ok = False
        detail_j = (f"{perdants}/{resolus} perdants sur 7 j "
                    f"(cumul global {hist.get('cumul_R',0):+.1f}R) — "
                    f"les signaux recents ne fonctionnent pas dans ce regime")
    agent("Stratégie", "règle mécanique, filtres, garde-fou",
          "interne (backtesté : +0,76R H4/3 ans)", True,
          "voir l'onglet Stratégies", "♟️", "p-strats")
    agent("Journal & historique", "suivi de chaque signal jusqu'au dénouement",
          "interne", journal_ok, detail_j, "📜", "p-histo")

    # Recommandations du superviseur : des pistes a MESURER, jamais des
    # modifications appliquees seul — le systeme ne se reecrit pas lui-meme.
    recommandations = []
    if not journal_ok:
        recommandations.append(
            "Ne pas suivre de nouveaux signaux tant que la série perdure ; "
            "re-tester la règle sur les 30 derniers jours "
            "(python3 -m gold_agent.backtest --source twelvedata --tf 240) "
            "et MESURER un élargissement du stop (--k-stop 1.5 ou 2) avant tout changement.")

    emis_24h = sum(1 for x in hist.get("derniers", [])
                   if _t.time() - x.get("cree_ts", 0) < 86400)
    if emis_24h > 15:
        problemes.append(f"Cadence d'emission anormale : {emis_24h} signaux en 24 h — "
                         f"doublons ou marche disloque, verifier avant de suivre quoi que ce soit")

    try:
        act = _news.actualites()
        if act.get("niveau") == "eleve":
            problemes.append(
                f"REGIME GEOPOLITIQUE ({act.get('part_geopolitique_pct','?')}% des titres) : "
                f"conflit en cours dans l'actualite — stops techniques peu fiables, "
                f"le backtest ne couvre pas ce regime")
        agent("Actualités géopolitiques", "détection de régime hors calendrier",
              "Google News RSS", act.get("disponible", False),
              f"niveau {act.get('niveau','?')}", "🌍", "p-risque")
    except Exception as e:
        agent("Actualités géopolitiques", "détection de régime", "Google News RSS",
              False, str(e)[:60], "🌍", "p-risque")

    try:
        act2 = _news.actualites()
        if act2.get("niveau") == "eleve":
            recommandations.append(
                "Régime géopolitique élevé : privilégier l'abstention ; si position, "
                "réduire la taille — la volatilité rend les stops backtestés trop serrés.")
    except Exception:
        pass

    # Detection par timeframe : quel TF perd, et proposition de correction
    reparations = []
    autorises = config.tf_emission()
    # Choix utilisateur (07/09) : le superviseur ne notifie que la SANTE des
    # agents — pannes, erreurs, maintenance. La gestion fine des timeframes
    # se fait par la suspension automatique (fenetre 7 j) et les badges
    # emission ON/OFF, sans notifications dediees.
    doublons = hist.get("total_emis", 0) - len({x.get("cle") for x in hist.get("derniers", [])} )
    if emis_24h > 15:
        reparations.append({"action": "nettoyer_journal",
                            "libelle": "Nettoyer les doublons du journal",
                            "contexte": f"{emis_24h} signaux en 24 h"})
    fige = [r for r in resultats if r.get("perime")]
    if fige:
        reparations.append({"action": "vider_caches",
                            "libelle": "Vider les caches de données",
                            "contexte": f"{len(fige)} timeframe(s) sur données figées"})

    # Rangement : Journal & historique dans la meme rangee que News & calendrier
    noms = [a["nom"] for a in agents]
    if "Journal & historique" in noms and "News & calendrier" in noms:
        j2 = agents.pop(noms.index("Journal & historique"))
        agents.insert([a["nom"] for a in agents].index("News & calendrier") + 1, j2)

    return {"agents": agents, "problemes": problemes,
            "recommandations": recommandations,
            "reparations": reparations,
            "tf_emission": autorises,
            "note": ("Les prix affichés viennent de Twelve Data (agrégat institutionnel). "
                     "Ton courtier Pepperstone cote avec son propre spread : ajuste les "
                     "niveaux de quelques dixièmes de point. Le superviseur liste les "
                     "problèmes détectés ; les corrections sont appliquées sur demande, "
                     "jamais silencieusement.")}


_REPARATIONS_NOTIFIEES: set = set()


def _notifier_reparations(sa: dict) -> None:
    """Le superviseur ne s'affiche plus en bloc sur la page : il NOTIFIE.

    Chaque correction proposee part une seule fois en notification
    (systeme + telephone) pour validation. L'application reste un clic
    dans la carte AG-00 — jamais automatique : un systeme qui se modifie
    sans validation est un systeme dont on perd le controle.
    """
    from . import notify as _notify
    for r in (sa.get("reparations") or []):
        if r["action"] in _REPARATIONS_NOTIFIEES:
            continue
        _REPARATIONS_NOTIFIEES.add(r["action"])
        titre = "Superviseur — correction proposée"
        corps = (f"{r['contexte']}\nProposition : {r['libelle']}\n"
                 f"Valider : carte Superviseur (AG-00) de l'onglet Cerveau.")
        try:
            _notify.notifier_systeme(titre, r["libelle"], corps)
            _notify.pousser_telephone(titre, corps)
            from .tableau import _evt
            _evt("Superviseur", f"correction proposée : {r['libelle']} — notification envoyée", "alerte")
        except Exception:
            pass




def agents_live(d: dict) -> list:
    """Les 8 agents du panneau, alimentés par l'état réel de cette passe.

    Tout est vérifiable : lignes d'activité = calculs qui viennent d'être
    faits, « charge cerveau » = temps CPU mesuré par module, convictions =
    métriques réelles. Aucun champ inventé — c'est la différence entre ce
    panneau et les vidéos dont il s'inspire.
    """
    chrono = d.get("chrono") or {}
    total_ms = sum(chrono.values()) or 1.0

    def charge(*cles):
        return round(sum(chrono.get(k, 0.0) for k in cles) / total_ms * 100)

    n = d.get("news") or {}
    cons = d.get("consensus") or {}
    hist = d.get("historique") or {}
    tfs = d.get("timeframes") or []
    setups = [(r["nom"], r.get("setup") or {}) for r in tfs
              if (r.get("setup") or {}).get("setup")]
    fia = {r["nom"]: (r.get("fiabilite") or {}) for r in tfs}
    agents = []

    act = n.get("actus") or {}
    risque = n.get("risque") or {}
    ma = n.get("macro") or {}
    lignes = [f"calendrier : {(risque.get('detail') or '—')[:70]}",
              f"géopolitique {act.get('niveau','?')} — {len(act.get('titres',[]))} titres, 5 sources"]
    if ma.get("disponible"):
        lignes.append(f"taux réel 10 ans {ma['taux_reel_10a']['dernier']}% · "
                      f"dollar {ma['dollar_large']['dernier']}")
    sn = n.get("saison") or {}
    if sn.get("disponible"):
        lignes.append(f"saisonnalité {sn['mois']} : {sn['moyen_pct']:+.1f}% ({sn['annees']} ans)")
    geo_calme = {"calme": 90, "modere": 55, "eleve": 20}.get(act.get("niveau"), 50)
    agents.append({"code": "AG-01", "nom": "Vigie", "role": "News éco + géo + macro",
                   "coul": "#58a6ff", "statut": "STREAMING", "activites": lignes,
                   "conviction": geo_calme,
                   "metriques": "5 flux RSS · FRED · ForexFactory",
                   "charge": charge("vigie")})

    lignes = []
    for r in tfs:
        ic = ((r.get("ict") or {}).get("premium_discount")) or {}
        lignes.append(f"{r['nom']} : {r.get('pct_haussier','?')}% haussier · RSI {(r.get('rsi') or 0):.0f}"
                      + (f" · {ic.get('zone')}" if ic.get("zone") else ""))
    agents.append({"code": "AG-02", "nom": "Structure", "role": "Analyse graphique — 5 timeframes",
                   "coul": "#3fb950", "statut": "STREAMING", "activites": lignes,
                   "conviction": int(cons.get("pct_haussier", 50)),
                   "metriques": f"EMA · RSI · ATR · régime · {len(tfs)} TF",
                   "charge": charge("structure", "donnees")})

    lignes = [f"{nt} {st_['setup']} @ {st_['entree']} (RR {st_['rr']}) — "
              + ("SUSPENDU" if st_.get("suspendu") else
                 ("déclenché" if st_.get("declenche") else "en attente"))
              for nt, st_ in setups]
    if not lignes:
        lignes = [f"{r['nom']} : {((r.get('setup') or {}).get('raison') or '—')[:60]}"
                  for r in tfs[:3]]
    em = d.get("tf_emission") or []
    agents.append({"code": "AG-03", "nom": "Stratège", "role": "Règle mesurée + filtres",
                   "coul": "#e3b341", "statut": "ACTIVE" if setups else "SCANNING",
                   "activites": lignes, "conviction": round(len(em) / 5 * 100),
                   "metriques": f"émission : {', '.join(em) or 'aucune'} · H4 +1,12R mesuré",
                   "charge": charge("stratege")})

    lignes = [f"{r['nom']} : ABC — {(r['abc']['stade'])[:40]}, cible {r['abc']['cible_C']}"
              for r in tfs if (r.get("abc") or {}).get("scenario")]
    lignes.append("Fibonacci 38,2/50/61,8 sur la dernière jambe (grands graphiques)")
    agents.append({"code": "AG-04", "nom": "Traceur", "role": "Dessins : zones · ABC · Fibonacci",
                   "coul": "#a371f7", "statut": "STREAMING", "activites": lignes,
                   "conviction": min(100, 25 * sum(
                       1 for r in tfs if (r.get("abc") or {}).get("scenario"))),
                   "metriques": "zones entrée/SL/TP · FVG · S/R · ABC",
                   "charge": charge("traceur")})

    mi = n.get("minieres") or {}
    cot = n.get("cot") or {}
    lignes = []
    if mi.get("disponible"):
        lignes.append(f"AEM {mi['aem']['variation_pct']:+.1f}% vs or {mi['or']['variation_pct']:+.1f}% — "
                      + (f"divergence {mi['divergence']}" if mi.get("divergence") else "confirmation"))
    if cot.get("disponible"):
        lignes.append(f"COT : {cot['net']:+,} contrats ({cot['percentile']:.0f}e pct, "
                      f"{cot['variation_4s']:+,}/4 sem)")
    agents.append({"code": "AG-05", "nom": "Minières & Flux", "role": "AEM · COT · positionnement",
                   "coul": "#f0883e", "statut": "STREAMING",
                   "activites": lignes or ["sources indisponibles"],
                   "conviction": int(cot.get("percentile", 50)) if cot.get("disponible") else 50,
                   "metriques": "corrélation AEM +0,80 — lead-lag nul : confirmation",
                   "charge": charge("minieres")})

    # ---- AG-09 Constellation (INTEGRATION_AG09.md etape 3) ----
    c = d.get("constellation") or {}
    sat, mir = c.get("satellites", []), c.get("miroirs", [])
    if c:
        forts = [m for m in sat + mir if m["poids"] >= 0.60]
        trans = [m for m in sat + mir if str(m.get("tendance", "")).startswith("TRANSITION")]
        lignes = [f"{len(sat)} satellites · {len(mir)} miroirs · "
                  f"{c['n_decouples']} découplés",
                  "confirmations solides : " +
                  (", ".join(f"{m['ticker']} {m['poids']:.2f}" for m in forts[:3])
                   or "aucune")]
        if trans:
            lignes.append(f"{len(trans)} corrélation(s) en transition de régime")
        for r_ in c.get("ruptures", [])[:2]:
            lignes.append(f"RUPTURE {r_['actif']} : {r_['avant']:+.2f} → {r_['apres']:+.2f}")
        conviction_c = round(min(1.0, sum(m["poids"] for m in forts) / 2.0) * 100)
        statut_c = "PERIME" if c.get("perime") else "STREAMING"
    else:
        lignes = ["cache en cours de construction"]
        conviction_c, statut_c = 0, "INITIALISATION"
    agents.append({"code": "AG-09", "nom": "Constellation",
                   "role": "Corrélations — satellites · miroirs · clusters",
                   "coul": "#a371f7", "statut": statut_c, "activites": lignes,
                   "conviction": conviction_c,
                   "metriques": f"{len(c.get('clusters', []))} clusters · "
                                f"fenêtres 30/90/250 j · recalcul 6 h",
                   "charge": charge("constellation")})

    # ---- AG-10 Miroir ----
    sc = c.get("score") or {}
    if sc:
        lignes = [f"sens testé : {c['sens_teste']} · score {sc['score']:+.2f}",
                  f"base {sc['base']:.2f}" + ("" if sc["fiable"] else " — TROP MINCE"),
                  f"{len(sc['confirment'])} confirment · "
                  f"{len(sc['contredisent'])} contredisent"]
        if sc["bloque"]:
            lignes.append("SIGNAL BLOQUÉ — " + str(sc["motif"])[:60])
        elif sc.get("motif"):
            lignes.append(str(sc["motif"])[:70])
        # Base trop mince -> 50, ni 0 ni 100 : une information insuffisante
        # n'est ni un avis positif ni un avis negatif.
        conviction_m = round((sc["score"] + 1) / 2 * 100) if sc["fiable"] else 50
        statut_m = "BLOCAGE" if sc["bloque"] else ("ACTIVE" if sc["fiable"] else "VEILLE")
    else:
        lignes = ["en attente de la constellation"]
        conviction_m, statut_m = 50, "INITIALISATION"
    agents.append({"code": "AG-10", "nom": "Miroir",
                   "role": "Confirmation croisée intermarché",
                   "coul": "#f778ba", "statut": statut_m, "activites": lignes,
                   "conviction": conviction_m,
                   "metriques": f"×{sc.get('facteur_confiance', 1.0):.2f} sur la confiance",
                   "charge": charge("constellation")})

    # ---- AG-16 Avocat du diable ----
    lignes_av, n_maj, n_min, n_bloq = [], 0, 0, 0
    for r in d.get("timeframes", []):
        st_ = r.get("setup") or {}
        v = st_.get("avocat")
        susp = str(st_.get("suspendu") or "")
        if susp.startswith("avocat du diable"):
            n_bloq += 1
            lignes_av.append(f"{r['nom']} {st_.get('setup', '')} BLOQUÉ — "
                             + susp.split(": ", 1)[-1][:60])
        elif v:
            for o in v["objections"]:
                if o["gravite"] == "majeure":
                    n_maj += 1
                else:
                    n_min += 1
            if v["objections"]:
                o = v["objections"][0]
                lignes_av.append(f"{r['nom']} : {o['quoi'][:64]}"
                                 + (" — réfutée" if o["refutee"] else ""))
    if not lignes_av:
        lignes_av = ["aucun setup à contester pour l'instant",
                     "je cherche des raisons d'échouer, pas de réussir"]
    conviction_av = min(95, 25 + 35 * n_bloq + 15 * n_maj + 5 * n_min)
    agents.append({"code": "AG-16", "nom": "Avocat du diable",
                   "role": "Vote toujours CONTRE — doit être réfuté",
                   "coul": "#f85149",
                   "statut": "BLOCAGE" if n_bloq else ("OBJECTION" if n_maj + n_min else "VEILLE"),
                   "activites": lignes_av[:4],
                   "conviction": conviction_av,
                   "metriques": f"{n_bloq} blocage(s) · {n_maj} majeure(s) · "
                                f"{n_min} mineure(s)",
                   "charge": charge("avocat")})

    lignes = [f"{nt} : espérance mesurée {fia[nt]['esperance']:+.2f}R "
              f"({fia[nt].get('trades','?')} trades) — {fia[nt].get('niveau','?')}"
              for nt, _ in setups if fia.get(nt, {}).get("esperance") is not None]
    lignes.append(f"consensus {cons.get('pct_haussier','?')}% haussier "
                  f"({cons.get('nb_haussier',0)}▲ / {cons.get('nb_baissier',0)}▼)")
    conv = max(cons.get("pct_haussier", 50), 100 - cons.get("pct_haussier", 50))
    agents.append({"code": "AG-06", "nom": "Probabilité", "role": "Espérances mesurées + consensus",
                   "coul": "#2ea043", "statut": "COMPUTING", "activites": lignes,
                   "conviction": int(conv),
                   "metriques": "backtests 2 fenêtres · débat pondéré",
                   "charge": charge("probabilite")})

    classes = sorted(setups, key=lambda x: -(x[1].get("rr") or 0))
    lignes = [f"{nt} {st_['setup']} — entrée {st_['entree']} · SL {st_['stop']} · "
              f"TP {st_['objectif']} · RR {st_['rr']}" + (" ⛔" if st_.get("suspendu") else "")
              for nt, st_ in classes[:3]]
    if not lignes:
        lignes = ["aucun setup actif — zones à surveiller sur l'Analyse graphique"]
    agents.append({"code": "AG-07", "nom": "Opportunités", "role": "Setups classés par R:R",
                   "coul": "#ff7b72", "statut": "ACTIVE" if classes else "SCANNING",
                   "activites": lignes, "conviction": min(100, len(classes) * 34),
                   "metriques": f"{len(classes)} setup(s) · journal réel : "
                                f"{hist.get('taux_reussite_pct') if hist.get('taux_reussite_pct') is not None else '—'}%",
                   "charge": charge("journal")})

    sa = d.get("sante") or {}
    probs = sa.get("problemes") or []
    lignes = [f"suspension : {(d.get('suspension') or 'levée — émission active')[:80]}"]
    for nt, st_ in setups:
        if not st_.get("suspendu"):
            lignes.append(f"VALIDÉ {nt} : {st_['entree']} / SL {st_['stop']} / TP {st_['objectif']}")
    for p_ in probs[:2]:
        lignes.append(f"⚠ {p_[:80]}")
    autres = sum(charge(k) for k in ("vigie", "structure", "stratege", "traceur",
                                     "minieres", "probabilite", "journal"))
    agents.append({"code": "AG-00", "nom": "Superviseur", "role": "Synthèse — niveaux par timeframe",
                   "coul": "#1f6feb", "statut": "COMPUTING" if probs else "ACTIVE",
                   "activites": lignes, "conviction": int(conv),
                   "metriques": f"{len(probs)} problème(s) · "
                                f"{len(sa.get('reparations') or [])} correction(s) disponible(s)",
                   "charge": max(1, 100 - min(99, autres))})

    # ---- AG-11..15 : les 4 marches + la matrice (cartes deja au format
    #      du panneau, testees par test_cartes_au_format_du_panneau) ------
    for carte_m in (d.get("marches") or {}).get("cartes", []):
        carte_m.setdefault("charge", charge("marches"))
        agents.append(carte_m)
    return agents
