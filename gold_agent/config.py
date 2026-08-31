"""Configuration persistante et corrections du superviseur.

Le superviseur ne modifie jamais la stratégie ; il applique des corrections
MECANIQUES d'une liste blanche : activer/désactiver l'émission d'un
timeframe, nettoyer le journal, vider les caches. Chaque action est
journalisée dans le fichier de config pour rester traçable.
"""
from __future__ import annotations

import datetime as dt
import json
import threading
from pathlib import Path

FICHIER = Path.home() / ".gold_agent_config.json"
_VERROU = threading.Lock()

# Emission par defaut : uniquement les timeframes dont le backtest est
# positif avec un echantillon defendable (01/09/2026) :
#   H4 +0,76R/64t/3ans · H1 +0,52R/25t · M30 +0,63R/25t/104j
#   M15 +0,06R et pire creux -11R -> OFF · M5 17 jours de donnees -> OFF
TF_EMISSION_DEFAUT = ["H4", "H1", "M30"]


def _charger() -> dict:
    if FICHIER.exists():
        try:
            return json.loads(FICHIER.read_text())
        except Exception:
            pass
    return {}


def _ecrire(d: dict) -> None:
    FICHIER.write_text(json.dumps(d, ensure_ascii=False, indent=1))


def tf_emission() -> list[str]:
    with _VERROU:
        return _charger().get("tf_emission", list(TF_EMISSION_DEFAUT))


def _journaliser(d: dict, action: str) -> None:
    d.setdefault("historique_actions", []).append(
        {"quand": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
         "action": action})
    d["historique_actions"] = d["historique_actions"][-50:]


def basculer_tf(tf: str, actif: bool) -> str:
    with _VERROU:
        d = _charger()
        lst = d.get("tf_emission", list(TF_EMISSION_DEFAUT))
        if actif and tf not in lst:
            lst.append(tf)
        if not actif and tf in lst:
            lst.remove(tf)
        d["tf_emission"] = lst
        _journaliser(d, f"emission {tf} -> {'ON' if actif else 'OFF'}")
        _ecrire(d)
    return f"émission {tf} {'activée' if actif else 'désactivée'} — timeframes émetteurs : {', '.join(lst) or 'aucun'}"


def appliquer(action: str) -> str:
    """Point d'entrée unique des corrections. Liste blanche stricte."""
    if action.startswith("tf_on:"):
        return basculer_tf(action.split(":", 1)[1], True)
    if action.startswith("tf_off:"):
        return basculer_tf(action.split(":", 1)[1], False)
    if action == "nettoyer_journal":
        from . import journal
        import json as _j
        f = journal.FICHIER
        sig = _j.loads(f.read_text()) if f.exists() else []
        vus, propres = set(), []
        for x in sorted(sig, key=lambda y: y["cree_ts"]):
            k = f"{x['tf']}|{x['sens']}|{round(x['entree'])}"
            if k in vus:
                continue
            vus.add(k)
            propres.append(x)
        f.write_text(_j.dumps(propres, ensure_ascii=False, indent=1))
        with _VERROU:
            d = _charger(); _journaliser(d, "nettoyage journal"); _ecrire(d)
        return f"journal nettoyé : {len(sig)} → {len(propres)} entrées"
    if action == "vider_caches":
        from . import tableau, datasource as ds
        with tableau._VERROU:
            tableau._CACHE.clear()
        for c in (ds._QUOTE, ds._USAGE):
            with c["verrou"]:
                c["valeur"], c["t"] = None, 0.0
        with _VERROU:
            d = _charger(); _journaliser(d, "caches vides"); _ecrire(d)
        return "caches vidés — prochaines données entièrement fraîches"
    raise ValueError(f"action inconnue : {action}")
