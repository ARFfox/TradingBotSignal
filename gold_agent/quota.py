"""Profils de rafraichissement et budget de requetes Twelve Data.

Separe de tableau.py (regle 17). Les TTL sont cales sur la bougie et
sur le nombre de cles en rotation pour tenir sous 800 requetes/jour.
"""
from __future__ import annotations

from . import datasource as ds


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




# Cache des bougies, protege par verrou : l'appel reseau se fait hors
# verrou pour ne pas bloquer les autres timeframes.
import threading as _th
import time as _time

_CACHE: dict = {}
_VERROU = _th.Lock()


def _bars_caches(symbole: str, tf: str, bougies: int) -> tuple:
    """Renvoie (bougies, age_secondes, depuis_cache)."""
    cle = (symbole, tf, bougies)
    ttl = _ttl(tf)
    with _VERROU:
        entree = _CACHE.get(cle)
        if entree and (_time.time() - entree["t"]) < ttl:
            return entree["bars"], int(_time.time() - entree["t"]), True
    # Hors verrou : l'appel reseau ne doit pas bloquer les autres timeframes
    bars = ds.twelvedata_bars(symbole, tf, bougies)
    with _VERROU:
        _CACHE[cle] = {"bars": bars, "t": _time.time()}
    return bars, 0, False



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


