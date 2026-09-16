"""Réglage automatique niveau 2 (CHANTIER #15) — le Tuner branché.

Le contrat de `parametres_agents.Tuner` exige un REJOUEUR par paramètre :
`rejouer(signaux, valeur)` rejoue l'historique comme si le paramètre avait
eu cette valeur, statuts recalculés. Un rejoueur qui devine est pire
qu'aucun rejoueur — ceux d'ici re-simulent sur les VRAIES bougies avec
`garde_fous.suivre` (mêmes conventions pessimistes que le journal).

Périmètre (règle 2 du CLAUDE.md) : le Tuner PROPOSE et JOURNALISE
(~/.gold_agent_reglages.json + rapport_reglages.md). Il n'applique RIEN :
changer un paramètre de stratégie reste un clic de Mushine.
"""
from __future__ import annotations

import dataclasses
import datetime as dt
import json
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
if str(RACINE) not in sys.path:
    sys.path.insert(0, str(RACINE))

RAPPORT = RACINE / "rapport_reglages.md"
JOURNAL_TUNER = Path.home() / ".gold_agent_reglages.json"
TF_CODES = {"H4": "240", "H1": "60", "M30": "30", "M15": "15", "M5": "5"}

_CACHE_BARS: dict[tuple, list] = {}


def _bars_pour(instrument: str, tf: str) -> list[dict]:
    """Bougies du couple, avec parcimonie : l'or ne lit QUE son cache
    (le quota Twelve Data ne se dépense pas en recherche), les autres
    passent par l'adapter normal (cache d'abord, réseau au besoin)."""
    cle = (instrument, tf)
    if cle in _CACHE_BARS:
        return _CACHE_BARS[cle]
    bars: list = []
    try:
        from . import instruments
        if instrument == instruments.par_defaut().symbole:
            from .quota import dernier_cache
            vieux = dernier_cache(instrument, TF_CODES.get(tf, tf), 600)
            bars = (vieux or {}).get("bars", [])
        else:
            inst = next((i for i in instruments.REGISTRE.values()
                         if i.symbole == instrument), None)
            if inst is not None:
                from .analyse import bars_instrument
                bars = bars_instrument(inst, TF_CODES.get(tf, tf), 600)
    except Exception:
        bars = []
    _CACHE_BARS[cle] = bars
    return bars


def rejoueur_stop_atr(signaux: list, valeur: float) -> list:
    """Rejoue chaque signal avec un stop à `valeur` ATR (TP inchangé).

    Un signal sans ATR ou sans bougies après son émission est ÉCARTÉ,
    jamais deviné : le Tuner juge sur ce qui est re-simulable."""
    from garde_fous import suivre
    out = []
    for s in signaux:
        if not s.atr:
            continue
        bars = [b for b in _bars_pour(s.instrument, s.tf)
                if b["time"] > s.cree_ts]
        if not bars:
            continue
        sl = (s.entree - valeur * s.atr if s.sens == "achat"
              else s.entree + valeur * s.atr)
        res = suivre({"entree": s.entree, "sl": sl, "tp": s.tp,
                      "sens": s.sens}, bars)
        if res.statut not in ("TP", "SL"):
            continue
        out.append(dataclasses.replace(
            s, sl=sl, statut=res.statut,
            extreme_favorable=res.extreme_favorable,
            tp_atteint_apres_sl=bool(res.tp_atteint_apres_sl)))
    return out


def rejoueur_rr_minimum(signaux: list, valeur: float) -> list:
    """Rejouer un R:R minimum = ne garder que les signaux qui l'avaient.
    Aucune re-simulation à inventer : le filtre est le paramètre."""
    return [s for s in signaux if s.resolu and s.rr >= valeur]


def passe(entrees: list[dict] | None = None) -> str:
    """Une passe complète du Tuner sur le journal réel. Écrit le rapport
    et le journal des propositions ; n'applique rien. Renvoie le chemin."""
    from parametres_agents import PARAMETRES_DEFAUT, Tuner, rapport
    from .apprentissage import signaux

    sig = [s for s in signaux(entrees) if s.resolu]
    rejoueurs = {"AG-03.stop_atr": rejoueur_stop_atr,
                 "AG-03.rr_minimum": rejoueur_rr_minimum}
    params = [p for p in PARAMETRES_DEFAUT
              if f"{p.agent}.{p.nom}" in rejoueurs]
    resultats = Tuner(journal=JOURNAL_TUNER).passe(sig, params, rejoueurs)

    horodatage = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    corps = rapport(resultats)
    RAPPORT.write_text(
        "# Réglage automatique — PROPOSITIONS (rien n'est appliqué)\n\n"
        f"généré le {horodatage} · {len(sig)} signaux résolus rejoués\n\n"
        "> Le Tuner propose, Mushine décide : appliquer un réglage reste\n"
        "> une action manuelle. Chaque proposition ci-dessous a survécu au\n"
        "> walk-forward corrigé du nombre de valeurs essayées — ou dit\n"
        "> pourquoi elle est refusée.\n\n"
        "```\n" + corps + "\n```\n")
    return str(RAPPORT)


if __name__ == "__main__":
    print(passe())
