"""Collecte des données pour le tableau de bord.

Séparé du serveur : cette couche ne fait que produire un dictionnaire,
ce qui la rend testable sans lancer de serveur.
"""
from __future__ import annotations

import datetime as dt
import threading
import time

from . import avocat, config, datasource as ds, ict, indicators as ind, instruments, journal, patterns as pat, regime as rg, strategy as sg
from .cerveau import _consensus, _notifier_reparations, _sante, agents_live  # noqa: F401

# Twelve Data limite le plan gratuit a 8 requetes/minute et 800/jour. Sans
# cache, chaque rechargement en consomme 4 et le quota saute en quelques
# minutes. La duree de vie est calee sur la bougie : inutile de rafraichir
# du H4 toutes les 10 secondes, la bougie met 4 heures a se former.

# Console d'evenements : chaque collecte y consigne ce qui s'est reellement
# passe (donnees, signaux, vetos). C'est la matiere de la console du
# panneau Agents — du vrai vecu, pas un decor.
from collections import deque
_EVENEMENTS: deque = deque(maxlen=80)
_EV_VERROU = threading.Lock()


def _evt(agent: str, texte: str, niveau: str = "info") -> None:
    with _EV_VERROU:
        _EVENEMENTS.append({
            "t": dt.datetime.now(dt.timezone.utc).strftime("%H:%M:%S"),
            "agent": agent, "texte": texte[:130], "niveau": niveau})


def evenements() -> list:
    with _EV_VERROU:
        return list(_EVENEMENTS)
from .quota import (PROFILS, TTL_PLANCHER, _bars_caches, _ttl,  # noqa: F401
                    budget, definir_profil, ttl_effectifs)


TIMEFRAMES = [
    # k_stop par timeframe — mesure du 01/09/2026 sur deux fenetres
    # (historique complet ET 60 derniers jours, guerre comprise) :
    # H4 k1,5 : +0,76R -> +1,12R · H1 k1,5 : +0,09R -> +0,58R (et la fenetre
    # recente repasse positive) · M30 : k1,0 reste meilleur (+0,74R).
    {"tf": "240", "nom": "H4", "role": "Structure", "mtf": 6, "k_stop": 1.5,
     "params": dict(ema_fast=50, ema_slow=200, pivot_span=3, delai_max=40)},
    {"tf": "60", "nom": "H1", "role": "Tendance", "mtf": 4, "k_stop": 1.5,
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
    "H4": {"trades": 19, "esperance": 1.117, "pf": None, "creux": None,
           "note": "3 ans, stop 1,5 ATR : +1,12R", "niveau": "mesuré"},
    "H1": {"trades": 10, "esperance": 0.583, "pf": None, "creux": None,
           "note": "stop 1,5 ATR : +0,58R, échantillon faible", "niveau": "indicatif"},
    "M30": {"trades": 25, "esperance": 0.626, "pf": 2.38, "creux": -3.13,
            "note": "104 j, +0,63R", "niveau": "indicatif"},
    "M15": {"trades": 28, "esperance": 0.058, "pf": 1.09, "creux": -11.37,
            "note": "espérance ~0, creux −11R", "niveau": "déconseillé"},
    "M5": {"trades": 21, "esperance": 0.340, "pf": 1.60, "creux": -4.33,
           "note": "17 j seulement", "niveau": "non mesuré"},
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


def collecter(symbole: str | None = None, bougies: int = 600) -> dict:
    if symbole is None:
        symbole = instruments.par_defaut().symbole
    resultats = []
    prix_actuel = None

    import time as _tps
    chrono = {}

    def _mesure(nom, fn):
        d0 = _tps.perf_counter()
        try:
            return fn()
        finally:
            chrono[nom] = chrono.get(nom, 0.0) + (_tps.perf_counter() - d0)

    # Prix en direct : une seule requete, independante du cache des bougies.
    quote = None
    try:
        quote = _mesure("donnees", lambda: ds.quote_direct(symbole))
        prix_actuel = quote["prix"]
        if quote.get("age", 99) == 0:
            _evt("Vigie", f"cotation fraiche {prix_actuel} ({quote.get('variation_pct',0):+.2f}%)")
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
            d_struct = __import__("time").perf_counter()
            h = [b["high"] for b in bars]
            l = [b["low"] for b in bars]
            c = [b["close"] for b in bars]
            o = [b["open"] for b in bars]
            p = sg.Params(k_stop=spec.get("k_stop", 1.0), rr_min=1.5, cout_pts=0.3,
                          facteur_superieur=spec["mtf"], **spec["params"])
            d0 = __import__("time").perf_counter()
            entree["setup"] = sg.setup_actuel(bars, p)
            chrono["stratege"] = chrono.get("stratege", 0.0) + (__import__("time").perf_counter() - d0)
            entree["prix"] = round(c[-1], 2)
            entree["prix_direct"] = prix_actuel
            entree["rsi"] = ind.last_valid(ind.rsi(c, 14))
            entree["atr"] = ind.last_valid(ind.atr(h, l, c, 14))
            entree["ema_fast"] = ind.last_valid(ind.ema(c, p.ema_fast))
            entree["ema_slow"] = ind.last_valid(ind.ema(c, p.ema_slow))
            entree["periodes"] = [p.ema_fast, p.ema_slow]
            entree["extension"] = rg.score_extension(c[-1], entree["ema_fast"], entree["rsi"])
            chrono["structure"] = chrono.get("structure", 0.0) + (__import__("time").perf_counter() - d_struct)
            entree["volatilite"] = rg.regime_volatilite(h, l, c)
            entree["renversement"] = rg.renversement(o, h, l, c)
            d0 = __import__("time").perf_counter()
            try:
                entree["ict"] = ict.analyse_ict(bars, entree["atr"])
            except Exception:
                entree["ict"] = None
            chrono["traceur"] = chrono.get("traceur", 0.0) + (__import__("time").perf_counter() - d0)
            d0 = __import__("time").perf_counter()
            try:
                zz = pat.zigzag(h, l, seuil=(entree["atr"] or 1) * 2)
                entree["abc"] = pat.correction_abc(zz, entree["atr"])
            except Exception:
                entree["abc"] = {"scenario": None}
            chrono["traceur"] = chrono.get("traceur", 0.0) + (__import__("time").perf_counter() - d0)
            chrono["structure"] = chrono.get("structure", 0.0)

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
    d0 = _tps.perf_counter()
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
    d0 = _tps.perf_counter()
    try:
        minieres = _news.minieres()
    except Exception:
        minieres = {"disponible": False}
    try:
        cot = _news.positionnement()
    except Exception:
        cot = {"disponible": False}
    chrono["minieres"] = chrono.get("minieres", 0.0) + (_tps.perf_counter() - d0)
    try:
        actus = _news.actualites()
    except Exception:
        actus = {"disponible": False, "niveau": "inconnu", "titres": []}
    try:
        saison = _news.saisonnalite()
    except Exception:
        saison = {"disponible": False, "arguments": []}
    chrono["vigie"] = chrono.get("vigie", 0.0) + (_tps.perf_counter() - d0)

    # Journal : chaque signal emis est memorise puis suivi jusqu'a son
    # denouement, avec les bougies deja en cache (zero requete en plus).
    # SUSPENSION D'EMISSION — le superviseur applique sa propre discipline :
    # en regime geopolitique eleve ou en serie perdante averee, les setups
    # restent AFFICHES (marques) mais ne sont ni journalises ni notifies.
    # Mesure du 01/09 : la regle H4 tient sur 60 jours (+0,7R) mais les
    # timeframes non backtestes ont produit 14 pertes pendant le choc.
    tf_autorises = config.tf_emission()
    suspension = None
    if actus.get("niveau") == "eleve":
        suspension = ("régime géopolitique élevé — non couvert par le backtest")
    # Fenetre 7 jours : les vieilles pertes expirent, sinon la suspension
    # serait un verrou definitif (les nouveaux trades etant bloques, le
    # ratio ne pourrait jamais s'ameliorer).
    _h = journal.statistiques(fenetre_jours=7)
    if _h.get("resolus", 0) >= 5 and _h.get("perdants", 0) / max(_h.get("resolus", 1), 1) >= 0.8:
        suspension = (suspension + " · " if suspension else "") + f"série perdante récente ({_h['perdants']}/{_h['resolus']} sur 7 j)"

    bars_par_tf = {}
    for r in resultats:
        if r.get("bougies"):
            bars_par_tf[r["nom"]] = [
                {"time": b["t"], "high": b["h"], "low": b["l"], "close": b["c"]}
                for b in r["bougies"]]
        r["emission"] = r["nom"] in tf_autorises
        st = r.get("setup") or {}
        if st.get("setup"):
            if r["nom"] not in tf_autorises:
                st["suspendu"] = (f"émission désactivée pour {r['nom']} "
                                  f"(backtest insuffisant ou négatif)")
            elif suspension:
                st["suspendu"] = suspension
            # L'enregistrement au journal est DIFFERE apres le verdict du
            # Miroir (etape 5) : un signal bloque par l'intermarche ne doit
            # jamais y entrer, et un signal valide doit y entrer AVEC son
            # champ intermarche pour qu'on puisse mesurer l'apport du Miroir.
    d0 = _tps.perf_counter()
    try:
        n_res = journal.resoudre(bars_par_tf)
        if n_res:
            _evt("Superviseur", f"{n_res} signal(aux) du journal resolus", "alerte")
    except Exception:
        pass
    historique = journal.statistiques()
    chrono["journal"] = chrono.get("journal", 0.0) + (_tps.perf_counter() - d0)

    d0 = _tps.perf_counter()
    consensus = _consensus(resultats, macro, minieres, cot, saison)
    chrono["probabilite"] = chrono.get("probabilite", 0.0) + (_tps.perf_counter() - d0)

    # Evenements reels de cette passe
    for r in resultats:
        st_ = r.get("setup") or {}
        if st_.get("setup"):
            if st_.get("suspendu"):
                _evt("Superviseur", f"{r['nom']} {st_['setup']} SUSPENDU — {st_['suspendu'][:60]}", "veto")
            else:
                _evt("Stratège", f"{r['nom']} {st_['setup']} entrée {st_['entree']} RR {st_['rr']}", "signal")
    if suspension:
        _evt("Superviseur", f"suspension active : {suspension[:80]}", "veto")
    if (evenementiel or {}).get("etat") in ("veto", "reserve"):
        _evt("Vigie", evenementiel.get("detail", "")[:100], "alerte")
    if (actus or {}).get("niveau") == "eleve":
        _evt("Vigie", f"régime géopolitique élevé ({actus.get('part_geopolitique_pct')}% des titres)", "veto")

    paquet = {
        "consensus": consensus,
        "genere_le": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "symbole": symbole,
        "prix": round(prix_actuel, 2) if prix_actuel else None,
        "quote": quote,
        "usage": usage,
        "news": {"risque": evenementiel, "agenda": agenda, "macro": macro,
                 "minieres": minieres, "cot": cot, "actus": actus, "saison": saison},
        "historique": historique,
        "suspension": suspension,
        "tf_emission": tf_autorises,
        "chrono": {k: round(v * 1000, 1) for k, v in chrono.items()},
        "evenements": evenements(),
        "sante": (lambda sa: (_notifier_reparations(sa), sa)[1])(_sante(resultats, usage, quote)),
        "timeframes": resultats,
        "nb_setups": len(actifs),
    }
    # --- constellation (AG-09/AG-10) — INTEGRATION_AG09.md etape 2 --------
    # try/except large EXPRES : une constellation indisponible ne doit
    # jamais empecher le reste du tableau de s'afficher.
    d0 = _tps.perf_counter()
    paquet["constellation"] = None
    sens_courant = "achat" if paquet["consensus"]["pct_haussier"] >= 50 else "vente"
    memo = globals().setdefault("_MEMO_CONSTELLATION", {})
    if memo.get("paquet") is not None and             _tps.time() - memo.get("t", 0) < 600 and memo.get("sens") == sens_courant:
        paquet["constellation"] = memo["paquet"]
        chrono["constellation"] = chrono.get("constellation", 0.0)
        paquet["chrono"]["constellation"] = 0.0
        paquet["agents"] = agents_live(paquet)
        return paquet
    try:
        from . import constellation_source
        import sys as _sys
        _racine = str(__import__("pathlib").Path(__file__).resolve().parent.parent)
        if _racine not in _sys.path:
            _sys.path.insert(0, _racine)
        from constellation_agent import Constellation, Miroir, biais_provisoire

        px = constellation_source.prix()
        if px is not None and "GC=F" in px.columns:
            ag = Constellation(px)
            biais = biais_provisoire(px)
            mi = Miroir(ag)
            g = ag.groupes("GC=F")

            # Le sens teste est celui du consensus courant, pas une hypothese.
            sens = "achat" if paquet["consensus"]["pct_haussier"] >= 50 else "vente"
            score = mi.evaluer("GC=F", sens, biais)

            paquet["constellation"] = {
                "sens_teste": sens,
                "satellites": [vars(m) for m in g["satellites"]],
                "miroirs": [vars(m) for m in g["miroirs"]],
                "n_decouples": len(g["decouples"]),
                "clusters": ag.clusters("GC=F"),
                "score": vars(score),
                "biais": biais,
                "ruptures": ag.ruptures(),
                "perime": getattr(px, "attrs", {}).get("perime", False),
            }
            ag.sauver()
        memo["paquet"] = paquet["constellation"]
        memo["t"] = _tps.time()
        memo["sens"] = sens_courant
    except Exception as e:
        _evt("Constellation", f"indisponible : {str(e)[:90]}", "alerte")
    chrono["constellation"] = chrono.get("constellation", 0.0) + (_tps.perf_counter() - d0)
    paquet["chrono"]["constellation"] = round(chrono["constellation"] * 1000, 1)

    # --- Etape 5 (validee par l'utilisateur) : le Miroir agit sur les
    #     signaux. Sens conteste + score bloque -> suspension ; sinon le
    #     facteur et le score sont attaches au setup et au journal.
    cst = paquet.get("constellation") or {}
    sc_ = cst.get("score") or {}

    # AG-16 Avocat du diable : ses donnees (journal + agenda), une seule fois.
    d0 = _tps.perf_counter()
    try:
        _sig_journal = journal._charger()
    except Exception:
        _sig_journal = []
    try:
        from . import news as _news_av
        _evts_agenda = _news_av.prochains(fenetre_heures=8.0, impact_min="High")
    except Exception:
        _evts_agenda = []

    for r in resultats:
        st = r.get("setup") or {}
        if not st.get("setup"):
            continue
        if sc_ and cst.get("sens_teste") == st["setup"] and not st.get("suspendu"):
            if sc_.get("bloque"):
                st["suspendu"] = ("contradiction intermarché : "
                                  + str(sc_.get("motif", ""))[:110])
                _evt("Miroir", f"{r['nom']} {st['setup']} BLOQUÉ — "
                     f"{len(sc_.get('contredisent', []))} actifs contredisent", "veto")
            else:
                st["intermarche"] = {
                    "score": sc_.get("score"), "base": sc_.get("base"),
                    "fiable": sc_.get("fiable"),
                    "facteur": sc_.get("facteur_confiance", 1.0)}
        # L'Avocat du diable examine tout setup encore vivant : une objection
        # majeure non refutee bloque, les autres sont montrees sur la carte.
        if not st.get("suspendu"):
            try:
                verdict = avocat.examiner(r, _sig_journal, _evts_agenda)
            except Exception as e:
                verdict = None
                _evt("Avocat", f"examen impossible : {str(e)[:60]}", "warn")
            if verdict:
                st["avocat"] = verdict
                if verdict["verdict"] == "non_refute":
                    st["suspendu"] = ("avocat du diable : "
                                      + str(verdict["motif_blocage"])[:110])
                    _evt("Avocat", f"{r['nom']} {st['setup']} BLOQUÉ — "
                         f"{verdict['motif_blocage'][:70]}", "veto")
        if not st.get("suspendu"):
            journal.enregistrer(r["nom"], st, prix_actuel or 0,
                                (r.get("fiabilite") or {}).get("niveau", "?"))
    paquet["chrono"]["avocat"] = round((_tps.perf_counter() - d0) * 1000, 1)

    # --- les 4 marches + matrice intermarches (AG-11..15) -----------------
    # INTEGRATION_MARCHES.md : meme cache disque que la constellation,
    # jamais de telechargement au rendu, jamais Twelve Data.
    d0 = _tps.perf_counter()
    paquet["marches"] = None
    try:
        from . import constellation_source
        from agents_marches import MatriceMarches, CODES
        px = constellation_source.prix()
        if px is not None:
            mm = MatriceMarches(px)
            paquet["marches"] = {
                "tuiles": mm.tuiles(),
                "grilles": {k: [vars(c) for c in a.etat().carreaux]
                            for k, a in mm.agents.items()},
                "etats": {k: {x: v for x, v in vars(a.etat()).items()
                              if x != "carreaux"}
                          for k, a in mm.agents.items()},
                "correlations": mm.correlations().round(3).to_dict(),
                "avances": mm.avance_retard(),
                "graphe": mm.graphe(),
                "cartes": [mm.agents[k].carte_agent(CODES[k]) for k in mm.agents]
                          + [mm.carte_agent("AG-15")],
            }
    except Exception as e:
        _evt("marches", f"indisponible : {str(e)[:80]}", "warn")
    paquet["chrono"]["marches"] = round((_tps.perf_counter() - d0) * 1000, 1)

    paquet["agents"] = agents_live(paquet)

    # --- le reseau des agents (INTEGRATION_GRAPHE.md) ---------------------
    # Tout ce que le graphe montre est mesure a l'instant du rendu : un
    # agent sans carte s'affiche MUET, un blocage s'anime en rouge.
    try:
        from graphe_agents import construire
        avocat_resume = None
        for r in resultats:
            v = (r.get("setup") or {}).get("avocat")
            if v and v.get("objections"):
                avocat_resume = {"cible": "AG-03",
                                 "objections": v["objections"],
                                 "bloque": v["verdict"] == "non_refute"}
                if avocat_resume["bloque"]:
                    break
        paquet["graphe"] = construire(
            cartes=paquet["agents"],
            intermarches=(paquet.get("marches") or {}).get("graphe"),
            miroir=(paquet.get("constellation") or {}).get("score"),
            avocat=avocat_resume,
        ).json()
    except Exception as e:
        paquet["graphe"] = {"noeuds": [], "liens": []}
        _evt("graphe", f"indisponible : {str(e)[:80]}", "warn")

    globals()["DERNIER_PAQUET"] = paquet
    return paquet


