"""Sessions de cotation — Asie, Londres, New York (skill §6).

Les horaires (UTC) valent pour le FOREX et les METAUX. Le crypto cote en
continu : AUCUNE session n'y a de sens, et appliquer ces filtres a BTC
produirait des regles arbitraires — les fonctions REFUSENT de repondre
pour un marche crypto plutot que d'inventer une session.

VWAP vit ici aussi : il se remet a zero a l'ouverture de session, et sans
volume (l'or spot n'en a pas) il degenere en prix typique moyen — la
sortie l'annonce (`source_poids`).
"""
from __future__ import annotations

import datetime as dt

HEURES = {"asie": (0, 8), "londres": (8, 16), "ny": (13, 21)}
MARCHES_AVEC_SESSIONS = ("matieres", "forex")


def _refuser_crypto(marche: str) -> None:
    if marche not in MARCHES_AVEC_SESSIONS:
        raise ValueError(f"pas de session pour le marché « {marche} » : "
                         "le crypto cote 24/7, une session y serait arbitraire")


def session_active(ts: int, marche: str = "matieres") -> str:
    """"asie" | "londres" | "ny" | "chevauchement" | "creux"."""
    _refuser_crypto(marche)
    h = dt.datetime.fromtimestamp(ts, dt.timezone.utc).hour
    if 13 <= h < 16:
        return "chevauchement"      # Londres + New York : le plus volatil
    for nom, (a, b) in HEURES.items():
        if a <= h < b:
            return nom
    return "creux"


def _jour_utc(ts: int) -> dt.date:
    return dt.datetime.fromtimestamp(ts, dt.timezone.utc).date()


def range_asiatique(bars: list[dict], marche: str = "matieres") -> dict | None:
    """Le range 00:00-08:00 UTC du DERNIER jour present dans les bougies.

    Ses bornes sont les premieres cibles de liquidite de Londres.
    """
    _refuser_crypto(marche)
    if not bars:
        return None
    jour = _jour_utc(bars[-1]["time"])
    asie = [b for b in bars
            if _jour_utc(b["time"]) == jour
            and HEURES["asie"][0] <= dt.datetime.fromtimestamp(
                b["time"], dt.timezone.utc).hour < HEURES["asie"][1]]
    if len(asie) < 2:
        return None
    haut = max(b["high"] for b in asie)
    bas = min(b["low"] for b in asie)
    return {"jour": jour.isoformat(), "haut": haut, "bas": bas,
            "largeur": round(haut - bas, 6), "bougies": len(asie)}


def balayage_asiatique(bars: list[dict], marche: str = "matieres") -> dict | None:
    """Le range asiatique du jour a-t-il ete balaye, et de quel cote ?"""
    ra = range_asiatique(bars, marche)
    if ra is None:
        return None
    jour = ra["jour"]
    apres = [b for b in bars
             if _jour_utc(b["time"]).isoformat() == jour
             and dt.datetime.fromtimestamp(b["time"], dt.timezone.utc).hour
             >= HEURES["asie"][1]]
    haut_pris = any(b["high"] > ra["haut"] for b in apres)
    bas_pris = any(b["low"] < ra["bas"] for b in apres)
    cote = ("les_deux" if haut_pris and bas_pris else
            "haut" if haut_pris else "bas" if bas_pris else None)
    return {**ra, "balaye": cote is not None, "cote": cote}


def vwap(bars: list[dict], depuis_index: int = 0) -> tuple[float | None, str]:
    """(vwap, source_poids) depuis l'index d'ancrage (ouverture de session).

    Sans volume, poids = 1 : c'est un prix typique moyen, pas un VWAP —
    et la sortie le dit plutot que de le cacher.
    """
    seg = bars[depuis_index:]
    if not seg:
        return None, "aucune"
    a_du_volume = any((b.get("volume") or 0) > 0 for b in seg)
    num = den = 0.0
    for b in seg:
        typique = (b["high"] + b["low"] + b["close"]) / 3
        poids = (b.get("volume") or 0.0) if a_du_volume else 1.0
        num += typique * poids
        den += poids
    if den <= 0:
        return None, "aucune"
    return num / den, ("volume" if a_du_volume else "temps")


def index_ouverture(bars: list[dict], heure_utc: int = 13) -> int | None:
    """Index de la premiere bougie >= heure_utc du dernier jour des bougies
    (l'ancrage du VWAP et du range d'ouverture de New York)."""
    if not bars:
        return None
    jour = _jour_utc(bars[-1]["time"])
    for i, b in enumerate(bars):
        d = dt.datetime.fromtimestamp(b["time"], dt.timezone.utc)
        if d.date() == jour and d.hour >= heure_utc:
            return i
    return None
