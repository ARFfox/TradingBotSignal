"""Collecte des données pour le tableau de bord.

Séparé du serveur : cette couche ne fait que produire un dictionnaire,
ce qui la rend testable sans lancer de serveur.
"""
from __future__ import annotations

import datetime as dt
import threading
import time

from . import datasource as ds, indicators as ind, regime as rg, strategy as sg

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
TTL_BASE_SURVEILLANCE = {"240": 3600, "60": 1800, "30": 1200, "15": 600}
# Plancher : en dessous, on rafraichit plus vite que la bougie ne se forme.
TTL_PLANCHER = {"240": 600, "60": 300, "30": 180, "15": 120}

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

    return {
        "genere_le": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "symbole": symbole,
        "prix": round(prix_actuel, 2) if prix_actuel else None,
        "quote": quote,
        "usage": usage,
        "news": {"risque": evenementiel, "agenda": agenda, "macro": macro,
                 "minieres": minieres, "cot": cot},
        "timeframes": resultats,
        "nb_setups": len(actifs),
    }
