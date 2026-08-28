"""Analyse des news : calendrier économique + macro FRED.

Deux couches distinctes, aux rôles différents :

1. CALENDRIER (ForexFactory, JSON public, sans clé) — le risque événementiel.
   Avant un chiffre à fort impact (NFP, CPI, FOMC), le spread s'élargit et le
   prix peut sauter plusieurs ATR en quelques secondes : les stops calculés
   n'ont plus de sens. L'agent doit s'abstenir AVANT, pas expliquer après.

2. MACRO (FRED, clé gratuite) — la direction de fond. Sur longue période,
   l'or suit d'abord les taux réels US (inversement) et le dollar. Ce sont
   des arguments de débat, pas des signaux d'exécution.
"""
from __future__ import annotations

import datetime as dt
import json
import pathlib
import subprocess
import threading
import time

from . import datasource as ds

URL_CALENDRIER = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"

# L'or est cote en dollars : seuls les evenements USD le frappent directement.
# "All" couvre les evenements globaux (G20, guerres tarifaires...).
PAYS_SUIVIS = {"USD", "All"}

_CAL = {"valeur": None, "t": 0.0, "verrou": threading.Lock()}
_MACRO = {"valeur": None, "t": 0.0, "verrou": threading.Lock()}
TTL_CALENDRIER = 3600      # le calendrier de la semaine bouge peu
TTL_MACRO = 6 * 3600       # series quotidiennes


def _curl_json(url: str, timeout: int = 30):
    p = subprocess.run(["curl", "-s", "-m", str(timeout), url],
                       capture_output=True, text=True, timeout=timeout + 10)
    if not p.stdout.strip():
        raise RuntimeError("reponse vide")
    return json.loads(p.stdout)


# --------------------------------------------------------------------------
# Calendrier economique
# --------------------------------------------------------------------------

FICHIER_CAL = pathlib.Path.home() / ".gold_agent_calendrier.json"


def calendrier(ttl: int = TTL_CALENDRIER) -> list[dict]:
    """Événements USD de la semaine, horodatés en UTC.

    Cache sur DISQUE et pas seulement en mémoire : le feed ForexFactory
    limite les requêtes rapprochées, et chaque processus (analyse, tableau,
    surveillant) repartirait sinon de zéro. En cas de panne du feed, la
    dernière version connue est réutilisée — un calendrier d'hier vaut mieux
    que pas de calendrier : les événements de la semaine y figurent déjà.
    """
    with _CAL["verrou"]:
        if _CAL["valeur"] is not None and (time.time() - _CAL["t"]) < ttl:
            return _CAL["valeur"]

    if FICHIER_CAL.exists():
        age = time.time() - FICHIER_CAL.stat().st_mtime
        if age < ttl:
            try:
                evenements = json.loads(FICHIER_CAL.read_text())
                with _CAL["verrou"]:
                    _CAL["valeur"], _CAL["t"] = evenements, time.time()
                return evenements
            except Exception:
                pass

    try:
        brut = _curl_json(URL_CALENDRIER)
    except Exception:
        if FICHIER_CAL.exists():
            evenements = json.loads(FICHIER_CAL.read_text())
            with _CAL["verrou"]:
                _CAL["valeur"], _CAL["t"] = evenements, time.time()
            return evenements
        raise
    evenements = []
    for e in brut:
        if e.get("country") not in PAYS_SUIVIS:
            continue
        try:
            quand = dt.datetime.fromisoformat(e["date"]).astimezone(dt.timezone.utc)
        except (ValueError, KeyError):
            continue
        evenements.append({
            "quand_utc": quand.isoformat(timespec="minutes"),
            "timestamp": int(quand.timestamp()),
            "titre": e.get("title", "?"),
            "impact": e.get("impact", "?"),
            "prevu": e.get("forecast") or None,
            "precedent": e.get("previous") or None,
        })
    evenements.sort(key=lambda x: x["timestamp"])

    try:
        FICHIER_CAL.write_text(json.dumps(evenements, ensure_ascii=False))
    except Exception:
        pass
    with _CAL["verrou"]:
        _CAL["valeur"], _CAL["t"] = evenements, time.time()
    return evenements


def prochains(fenetre_heures: float = 24.0, impact_min: str = "High") -> list[dict]:
    """Événements à venir dans la fenêtre, du plus proche au plus lointain."""
    rangs = {"Low": 0, "Medium": 1, "High": 2}
    seuil = rangs.get(impact_min, 2)
    maintenant = time.time()
    horizon = maintenant + fenetre_heures * 3600
    out = []
    for e in calendrier():
        if e["timestamp"] < maintenant - 1800:      # passe depuis plus de 30 min
            continue
        if e["timestamp"] > horizon:
            break
        if rangs.get(e["impact"], 0) < seuil:
            continue
        d = dict(e)
        d["dans_minutes"] = round((e["timestamp"] - maintenant) / 60)
        out.append(d)
    return out


def risque_evenementiel() -> dict:
    """Verdict pour le garde-fou : peut-on raisonnablement entrer maintenant ?

    Fenêtres asymétriques à dessein : le danger est maximal juste AVANT et
    pendant la publication (le chiffre est inconnu), moindre après (le marché
    digère, mais la volatilité reste élevée ~30 min).
    """
    try:
        imminents = prochains(fenetre_heures=2.0, impact_min="High")
    except Exception as e:
        return {"etat": "inconnu", "detail": f"calendrier indisponible ({str(e)[:60]})",
                "evenements": []}

    en_cours = [e for e in imminents if -30 <= e["dans_minutes"] <= 5]
    tres_proches = [e for e in imminents if 5 < e["dans_minutes"] <= 60]
    proches = [e for e in imminents if 60 < e["dans_minutes"] <= 120]

    if en_cours:
        return {"etat": "veto", "evenements": en_cours,
                "detail": f"publication en cours ou imminente : {en_cours[0]['titre']}"}
    if tres_proches:
        e = tres_proches[0]
        return {"etat": "veto", "evenements": tres_proches,
                "detail": f"{e['titre']} dans {e['dans_minutes']} min — spread élargi, "
                          f"stops sans valeur pendant la publication"}
    if proches:
        e = proches[0]
        return {"etat": "reserve", "evenements": proches,
                "detail": f"{e['titre']} dans {round(e['dans_minutes']/60,1)} h — "
                          f"éviter les positions qui ne seraient pas gérées d'ici là"}
    return {"etat": "ok", "evenements": [], "detail": "aucun événement USD à fort impact sous 2 h"}


# --------------------------------------------------------------------------
# Macro FRED : taux reels et dollar
# --------------------------------------------------------------------------

def _tendance(serie: list[dict], jours: int) -> dict | None:
    """Variation sur N observations ouvrées (approximation de N jours)."""
    if len(serie) < jours + 1:
        return None
    a, b = serie[-jours - 1]["valeur"], serie[-1]["valeur"]
    return {"de": a, "vers": b, "variation": round(b - a, 3)}


def macro(ttl: int = TTL_MACRO) -> dict:
    """Lecture macro : taux réels 10 ans et dollar pondéré, avec leur pente."""
    with _MACRO["verrou"]:
        if _MACRO["valeur"] is not None and (time.time() - _MACRO["t"]) < ttl:
            return _MACRO["valeur"]

    out = {"disponible": False, "arguments": []}
    try:
        debut = (dt.date.today() - dt.timedelta(days=120)).isoformat()
        reels = ds.fred_serie("taux_reel_10a", debut=debut)
        dollar = ds.fred_serie("dollar_index", debut=debut)

        t20 = _tendance(reels, 20)          # ~1 mois ouvre
        d20 = _tendance(dollar, 20)
        out = {
            "disponible": True,
            "taux_reel_10a": {"dernier": reels[-1]["valeur"], "date": reels[-1]["date"],
                              "tendance_1m": t20},
            "dollar_large": {"dernier": dollar[-1]["valeur"], "date": dollar[-1]["date"],
                             "tendance_1m": d20},
            "arguments": [],
        }

        # Traduction en arguments de debat. Seuils : un dixieme de point de
        # taux reel sur un mois est un mouvement notable ; en dessous, bruit.
        if t20:
            if t20["variation"] >= 0.10:
                out["arguments"].append(("baissier", 2.5,
                    f"taux réels 10 ans en hausse ({t20['de']:.2f}% → {t20['vers']:.2f}% sur 1 mois) — "
                    f"vent contraire structurel pour l'or"))
            elif t20["variation"] <= -0.10:
                out["arguments"].append(("haussier", 2.5,
                    f"taux réels 10 ans en baisse ({t20['de']:.2f}% → {t20['vers']:.2f}% sur 1 mois) — "
                    f"soutien structurel pour l'or"))
        if d20:
            pct = d20["variation"] / d20["de"] * 100 if d20["de"] else 0
            if pct >= 1.0:
                out["arguments"].append(("baissier", 1.5,
                    f"dollar pondéré en hausse de {pct:+.1f}% sur 1 mois"))
            elif pct <= -1.0:
                out["arguments"].append(("haussier", 1.5,
                    f"dollar pondéré en baisse de {pct:+.1f}% sur 1 mois"))
    except Exception as e:
        out["erreur"] = str(e)[:120]

    with _MACRO["verrou"]:
        _MACRO["valeur"], _MACRO["t"] = out, time.time()
    return out
