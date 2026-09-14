"""GDELT pour la Vigie (AG-01) — la presse MONDIALE, pas 5 flux RSS.

GDELT 2.0 indexe la presse mondiale toutes les 15 minutes avec un score de
tonalite, gratuitement et sans cle. Deux lectures :

1. TONALITE de la presse sur l'or : la moyenne du jour comparee a celle
   des 3 derniers jours — la presse devient-elle plus negative ?
2. VOLUME geopolitique mondial : le nombre d'articles (guerre, missile,
   escalade) du jour compare a la moyenne 7 jours — le monde s'agite-t-il ?
   C'est le complement du thermometre RSS : lui compte des MOTS dans 5
   flux, GDELT compte des ARTICLES dans la presse mondiale.

Contrainte dure de l'API : UNE requete toutes les 5 secondes (le 429 est
poli mais ferme). D'ou : seau a jetons 1 req/6 s, cache disque 15 min, et
JAMAIS d'exception qui remonte — indisponible est un etat normal.

Lecture de contexte : rien ici ne vote au consensus ni ne suspend quoi
que ce soit (toute regle de decision = demander avant).
"""
from __future__ import annotations

import json
import pathlib
import threading
import time

URL = ("https://api.gdeltproject.org/api/v2/doc/doc"
       "?query={requete}&mode={mode}&timespan={duree}&format=json")
REQ_TON = "%22gold%20price%22%20sourcelang:eng"
REQ_GEO = "(war%20OR%20missile%20OR%20escalation)%20sourcelang:eng"

FICHIER = pathlib.Path.home() / ".gold_agent_gdelt.json"
TTL = 900                     # les donnees GDELT bougent au quart d'heure
_MEMO = {"valeur": None, "t": 0.0, "verrou": threading.Lock()}
_SEAU = None                  # 1 requete / 6 s — la limite de l'API est 5 s


# --------------------------------------------------------------------------
# Interpretation — PURE, testable sans reseau
# --------------------------------------------------------------------------
def _points(reponse: dict) -> list[float]:
    tl = (reponse or {}).get("timeline") or []
    if not tl:
        return []
    return [float(x.get("value", 0)) for x in tl[0].get("data", [])
            if x.get("value") is not None]


def interpreter_tonalite(reponse: dict, points_jour: int = 8) -> dict | None:
    """Tonalite recente vs moyenne de la fenetre. Negatif = presse sombre."""
    v = _points(reponse)
    if len(v) < points_jour * 2:
        return None
    recent = sum(v[-points_jour:]) / points_jour
    fond = sum(v) / len(v)
    return {"recente": round(recent, 2), "fond": round(fond, 2),
            "ecart": round(recent - fond, 2)}


def interpreter_volume(reponse: dict, points_jour: int = 8) -> dict | None:
    """Volume d'articles geopolitiques du jour vs moyenne de la fenetre."""
    v = _points(reponse)
    if len(v) < points_jour * 2 or sum(v) <= 0:
        return None
    recent = sum(v[-points_jour:]) / points_jour
    fond = sum(v) / len(v)
    if fond <= 0:
        return None
    return {"ratio": round(recent / fond, 2),
            "articles_recents": round(recent)}


def lecture(ton: dict | None, vol: dict | None) -> list[str]:
    """Les lignes lisibles de la Vigie."""
    out = []
    if ton:
        if ton["ecart"] <= -0.8:
            out.append(f"presse mondiale sur l'or : tonalité {ton['recente']:+.1f}, "
                       f"NETTEMENT plus sombre que son fond ({ton['fond']:+.1f})")
        elif ton["ecart"] >= 0.8:
            out.append(f"presse mondiale sur l'or : tonalité {ton['recente']:+.1f}, "
                       f"plus positive que son fond ({ton['fond']:+.1f})")
        else:
            out.append(f"presse mondiale sur l'or : tonalité {ton['recente']:+.1f} "
                       f"(dans sa norme)")
    if vol:
        if vol["ratio"] >= 1.5:
            out.append(f"volume géopolitique mondial × {vol['ratio']} vs 7 j — "
                       f"le monde s'agite ({vol['articles_recents']} art./15 min)")
        elif vol["ratio"] <= 0.7:
            out.append(f"volume géopolitique mondial × {vol['ratio']} vs 7 j — calme")
        else:
            out.append(f"volume géopolitique mondial × {vol['ratio']} vs 7 j — normal")
    return out


# --------------------------------------------------------------------------
# Recuperation — seau 1/6 s, cache disque, jamais d'exception
# --------------------------------------------------------------------------
def _requete(url: str):
    global _SEAU
    from feeds.base import Feed, SeauJetons
    if _SEAU is None:
        _SEAU = SeauJetons(1, 1 / 6.0)
    f = Feed(seau=_SEAU)
    f.nom = "gdelt"
    return f._requete(url, essais=2)


def presse(ttl: int = TTL) -> dict:
    """{disponible, tonalite, volume, lecture:[...]} — cache 15 min."""
    with _MEMO["verrou"]:
        if _MEMO["valeur"] is not None and time.time() - _MEMO["t"] < ttl:
            return _MEMO["valeur"]
    # cache disque (survit au redemarrage, evite le 429 au boot)
    try:
        if FICHIER.exists() and time.time() - FICHIER.stat().st_mtime < ttl:
            out = json.loads(FICHIER.read_text())
            with _MEMO["verrou"]:
                _MEMO["valeur"], _MEMO["t"] = out, time.time()
            return out
    except Exception:
        pass

    out = {"disponible": False, "lecture": []}
    try:
        ton = interpreter_tonalite(_requete(
            URL.format(requete=REQ_TON, mode="timelinetone", duree="3d")))
        vol = interpreter_volume(_requete(
            URL.format(requete=REQ_GEO, mode="timelinevolraw", duree="7d")))
        lignes = lecture(ton, vol)
        out = {"disponible": bool(lignes), "tonalite": ton, "volume": vol,
               "lecture": lignes}
    except Exception as e:
        out["erreur"] = str(e)[:80]
    if out.get("disponible"):
        try:
            FICHIER.write_text(json.dumps(out, ensure_ascii=False))
        except Exception:
            pass
        with _MEMO["verrou"]:
            _MEMO["valeur"], _MEMO["t"] = out, time.time()
    return out
