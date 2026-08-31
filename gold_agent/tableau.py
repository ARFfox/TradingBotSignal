"""Collecte des données pour le tableau de bord.

Séparé du serveur : cette couche ne fait que produire un dictionnaire,
ce qui la rend testable sans lancer de serveur.
"""
from __future__ import annotations

import datetime as dt
import threading
import time

from . import datasource as ds, ict, indicators as ind, journal, patterns as pat, regime as rg, strategy as sg

# Twelve Data limite le plan gratuit a 8 requetes/minute et 800/jour. Sans
# cache, chaque rechargement en consomme 4 et le quota saute en quelques
# minutes. La duree de vie est calee sur la bougie : inutile de rafraichir
# du H4 toutes les 10 secondes, la bougie met 4 heures a se former.
_CACHE: dict = {}
_VERROU = threading.Lock()
# Deux profils. En consultation, on rafraichit vite parce que quelqu'un
# regarde. En surveillance continue, les memes TTL consommeraient 2928
# requetes/jour pour un quota de 800 — d'ou des durees de vie allongees.
# Durees de vie pour UNE cle, calibrees pour tenir sous 800 requetes/jour en
# surveillance continue. Avec plusieurs cles en rotation, le quota cumule
# permet de les raccourcir d'autant.
# Allonges depuis que le prix en direct vient d'un appel /quote separe :
# les bougies servent a l'analyse structurelle, qui bouge lentement.
TTL_BASE_SURVEILLANCE = {"240": 3600, "60": 1800, "30": 1200, "15": 600, "5": 300}
# Plancher : en dessous, on rafraichit plus vite que la bougie ne se forme.
TTL_PLANCHER = {"240": 600, "60": 300, "30": 180, "15": 120, "5": 60}

PROFILS = {"consultation": TTL_PLANCHER, "surveillance": None}
_PROFIL = {"actif": "consultation"}


def definir_profil(nom: str) -> None:
    if nom not in PROFILS:
        raise ValueError(f"profil inconnu : {nom}")
    _PROFIL["actif"] = nom


def _nb_cles() -> int:
    try:
        return max(1, len(ds.cles_twelvedata()))
    except Exception:
        return 1


def ttl_effectifs() -> dict:
    """TTL reellement appliques, adaptes au nombre de cles disponibles."""
    if _PROFIL["actif"] == "consultation":
        return dict(TTL_PLANCHER)
    n = _nb_cles()
    return {tf: max(TTL_PLANCHER[tf], round(base / n))
            for tf, base in TTL_BASE_SURVEILLANCE.items()}


def budget() -> dict:
    """Consommation prevue face au quota cumule des cles."""
    ttl = ttl_effectifs()
    par_jour = sum(86400 / t for t in ttl.values())
    n = _nb_cles()
    quota = n * 800
    return {"cles": n, "quota": quota, "prevu": round(par_jour),
            "part_pct": round(par_jour / quota * 100, 1), "ttl": ttl}


def _ttl(tf: str) -> int:
    return ttl_effectifs().get(tf, 120)


def _bars_caches(symbole: str, tf: str, bougies: int) -> tuple:
    """Renvoie (bougies, age_secondes, depuis_cache)."""
    cle = (symbole, tf, bougies)
    ttl = _ttl(tf)
    with _VERROU:
        entree = _CACHE.get(cle)
        if entree and (time.time() - entree["t"]) < ttl:
            return entree["bars"], int(time.time() - entree["t"]), True
    # Hors verrou : l'appel reseau ne doit pas bloquer les autres timeframes
    bars = ds.twelvedata_bars(symbole, tf, bougies)
    with _VERROU:
        _CACHE[cle] = {"bars": bars, "t": time.time()}
    return bars, 0, False

TIMEFRAMES = [
    {"tf": "240", "nom": "H4", "role": "Structure", "mtf": 6,
     "params": dict(ema_fast=50, ema_slow=200, pivot_span=3, delai_max=40)},
    {"tf": "60", "nom": "H1", "role": "Tendance", "mtf": 4,
     "params": dict(ema_fast=20, ema_slow=50, pivot_span=3, delai_max=40)},
    {"tf": "30", "nom": "M30", "role": "Timing", "mtf": 2,
     "params": dict(ema_fast=20, ema_slow=50, pivot_span=3, delai_max=40)},
    {"tf": "15", "nom": "M15", "role": "Exécution", "mtf": 4,
     "params": dict(ema_fast=20, ema_slow=50, pivot_span=3, delai_max=60)},
    {"tf": "5", "nom": "M5", "role": "Scalp", "mtf": 12,
     "params": dict(ema_fast=20, ema_slow=50, pivot_span=2, delai_max=60)},
]

# Fiabilité mesurée par backtest — affichée à côté de chaque signal pour que
# la confiance accordée soit proportionnée aux preuves.
FIABILITE = {
    "H4": {"trades": 64, "esperance": 0.762, "pf": 2.65, "creux": -3.10,
           "note": "3 ans de données", "niveau": "mesuré"},
    "H1": {"trades": 22, "esperance": 0.757, "pf": 2.60, "creux": -3.05,
           "note": "échantillon faible", "niveau": "indicatif"},
    "M30": {"trades": None, "esperance": None, "pf": None, "creux": None,
            "note": "jamais backtesté", "niveau": "non mesuré"},
    "M15": {"trades": None, "esperance": None, "pf": None, "creux": None,
            "note": "jamais backtesté", "niveau": "non mesuré"},
    "M5": {"trades": 32, "esperance": 0.194, "pf": 1.29, "creux": -6.03,
           "note": "17 j de données, spread sensible", "niveau": "indicatif"},
}


def _avec_prix_direct(bars: list[dict], prix: float) -> list[dict]:
    """Réplique les bougies en réalignant la dernière sur le prix en direct.

    La bougie en cours n'est pas close : sa clôture mise en cache est
    périmée. On la corrige pour que l'analyse porte sur le prix réel.
    On COPIE — muter la liste en cache la corromprait pour tous les appels
    suivants.
    """
    if not bars or prix is None:
        return bars
    copie = list(bars)
    d = dict(copie[-1])
    d["close"] = prix
    d["high"] = max(d["high"], prix)
    d["low"] = min(d["low"], prix)
    copie[-1] = d
    return copie


# Poids par timeframe pour le consensus : le H4 pese plus que le M15,
# comme dans le module de debat (un signal court ne renverse pas une
# structure longue).
POIDS_TF = {"H4": 3.0, "H1": 2.0, "M30": 1.0, "M15": 0.5, "M5": 0.25}


def _consensus(resultats: list, macro: dict, minieres: dict, cot: dict) -> dict:
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

    for src in (macro, minieres, cot):
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
    resolus = hist.get("resolus", 0)
    perdants = hist.get("perdants", 0)
    journal_ok = True
    detail_j = f"{resolus} resolu(s), cumul {hist.get('cumul_R', 0):+.1f}R"
    if resolus >= 5 and perdants / max(resolus, 1) >= 0.8:
        journal_ok = False
        detail_j = (f"{perdants}/{resolus} perdants (cumul {hist.get('cumul_R',0):+.1f}R) — "
                    f"les signaux recents ne fonctionnent pas dans ce regime de marche")
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

    return {"agents": agents, "problemes": problemes,
            "recommandations": recommandations,
            "note": ("Les prix affichés viennent de Twelve Data (agrégat institutionnel). "
                     "Ton courtier Pepperstone cote avec son propre spread : ajuste les "
                     "niveaux de quelques dixièmes de point. Le superviseur liste les "
                     "problèmes détectés ; les corrections sont appliquées sur demande, "
                     "jamais silencieusement.")}


def collecter(symbole: str = "XAU/USD", bougies: int = 600) -> dict:
    resultats = []
    prix_actuel = None

    # Prix en direct : une seule requete, independante du cache des bougies.
    quote = None
    try:
        quote = ds.quote_direct(symbole)
        prix_actuel = quote["prix"]
    except Exception:
        pass

    for spec in TIMEFRAMES:
        entree = {"nom": spec["nom"], "role": spec["role"], "tf": spec["tf"],
                  "fiabilite": FIABILITE.get(spec["nom"], {})}
        try:
            bars_cache, age, du_cache = _bars_caches(symbole, spec["tf"], bougies)
            entree["age_secondes"] = age
            entree["du_cache"] = du_cache
            bars = _avec_prix_direct(bars_cache, prix_actuel)
            h = [b["high"] for b in bars]
            l = [b["low"] for b in bars]
            c = [b["close"] for b in bars]
            o = [b["open"] for b in bars]
            p = sg.Params(k_stop=1.0, rr_min=1.5, cout_pts=0.3,
                          facteur_superieur=spec["mtf"], **spec["params"])
            entree["setup"] = sg.setup_actuel(bars, p)
            entree["prix"] = round(c[-1], 2)
            entree["prix_direct"] = prix_actuel
            entree["rsi"] = ind.last_valid(ind.rsi(c, 14))
            entree["atr"] = ind.last_valid(ind.atr(h, l, c, 14))
            entree["ema_fast"] = ind.last_valid(ind.ema(c, p.ema_fast))
            entree["ema_slow"] = ind.last_valid(ind.ema(c, p.ema_slow))
            entree["periodes"] = [p.ema_fast, p.ema_slow]
            entree["extension"] = rg.score_extension(c[-1], entree["ema_fast"], entree["rsi"])
            entree["volatilite"] = rg.regime_volatilite(h, l, c)
            entree["renversement"] = rg.renversement(o, h, l, c)
            try:
                entree["ict"] = ict.analyse_ict(bars, entree["atr"])
            except Exception:
                entree["ict"] = None
            try:
                zz = pat.zigzag(h, l, seuil=(entree["atr"] or 1) * 2)
                entree["abc"] = pat.correction_abc(zz, entree["atr"])
            except Exception:
                entree["abc"] = {"scenario": None}

            # Pourcentage haussier de CE timeframe (jauge de la carte)
            b_pts = s_pts = 0.0
            if entree["ema_fast"] and entree["ema_slow"]:
                (b_pts, s_pts) = (b_pts + 1.5, s_pts) if entree["ema_fast"] > entree["ema_slow"]                     else (b_pts, s_pts + 1.5)
                if c[-1] > entree["ema_slow"]:
                    b_pts += 1.0
                else:
                    s_pts += 1.0
            if entree["rsi"] is not None:
                if entree["rsi"] >= 55: b_pts += 0.5
                elif entree["rsi"] <= 45: s_pts += 0.5
            tot = b_pts + s_pts
            entree["pct_haussier"] = round(b_pts / tot * 100) if tot else 50

            entree["bougies"] = [
                {"t": b["time"], "o": b["open"], "h": b["high"],
                 "l": b["low"], "c": b["close"]} for b in bars[-120:]
            ]
            entree["erreur"] = None
        except Exception as e:
            # Repli sur la derniere donnee connue, en le signalant clairement :
            # une carte vide est moins utile qu'une carte datee et annoncee.
            with _VERROU:
                vieux = _CACHE.get((symbole, spec["tf"], bougies))
            msg = str(e)[:160]
            if vieux:
                entree["erreur"] = f"rafraichissement impossible ({msg})"
                entree["age_secondes"] = int(time.time() - vieux["t"])
                entree["du_cache"] = True
                entree["perime"] = True
                entree["setup"] = {"setup": None,
                                   "raison": f"donnees figees depuis {entree['age_secondes']}s"}
            else:
                entree["erreur"] = msg
                entree["setup"] = {"setup": None, "raison": "donnees indisponibles"}
        resultats.append(entree)

    actifs = [r for r in resultats if (r.get("setup") or {}).get("setup")]
    if prix_actuel is None:
        # Repli : derniere cloture connue, faute de quote
        for r in resultats:
            if r.get("prix"):
                prix_actuel = r["prix"]
                break

    try:
        usage = ds.usage_api()
    except Exception:
        usage = None

    from . import news as _news
    try:
        evenementiel = _news.risque_evenementiel()
        agenda = _news.prochains(fenetre_heures=48)
    except Exception as e:
        evenementiel = {"etat": "inconnu", "detail": str(e)[:80]}
        agenda = []
    try:
        macro = _news.macro()
    except Exception:
        macro = {"disponible": False}
    try:
        minieres = _news.minieres()
    except Exception:
        minieres = {"disponible": False}
    try:
        cot = _news.positionnement()
    except Exception:
        cot = {"disponible": False}
    try:
        actus = _news.actualites()
    except Exception:
        actus = {"disponible": False, "niveau": "inconnu", "titres": []}

    # Journal : chaque signal emis est memorise puis suivi jusqu'a son
    # denouement, avec les bougies deja en cache (zero requete en plus).
    bars_par_tf = {}
    for r in resultats:
        if r.get("bougies"):
            bars_par_tf[r["nom"]] = [
                {"time": b["t"], "high": b["h"], "low": b["l"], "close": b["c"]}
                for b in r["bougies"]]
        st = r.get("setup") or {}
        if st.get("setup"):
            journal.enregistrer(r["nom"], st, prix_actuel or 0,
                                (r.get("fiabilite") or {}).get("niveau", "?"))
    try:
        journal.resoudre(bars_par_tf)
    except Exception:
        pass
    historique = journal.statistiques()

    consensus = _consensus(resultats, macro, minieres, cot)

    return {
        "consensus": consensus,
        "genere_le": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "symbole": symbole,
        "prix": round(prix_actuel, 2) if prix_actuel else None,
        "quote": quote,
        "usage": usage,
        "news": {"risque": evenementiel, "agenda": agenda, "macro": macro,
                 "minieres": minieres, "cot": cot, "actus": actus},
        "historique": historique,
        "sante": _sante(resultats, usage, quote),
        "timeframes": resultats,
        "nb_setups": len(actifs),
    }
