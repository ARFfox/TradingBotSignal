"""AG-20 Chartiste — l'agent qui lit les graphiques (étape 6ter).

Pont vers `agent_chartiste.py` (module livré) : lecture des 5 timeframes
ensemble (niveaux, tendances, CONFLITS entre échelles), carte pour le
graphe et le panneau, source descriptive pour AG-19, faits de niveau pour
le débat. La dernière lecture de chaque instrument est mémorisée : la
fiche l'affiche sans refaire le travail.

Un NIVEAU décrit (poids 1,0), une FIGURE prédit (poids 0,0) : les figures
partent déjà par leur propre canal (analyse → figures_biais), AG-20 ne
transmet QUE la partie vérifiable.

⚠️ Limite assumée, à signaler : `arguments_avocats()` produit des faits de
niveau pour AG-16/18, mais `avocats.py` (livré, non réécrit) n'expose pas
d'entrée pour des arguments externes — ils sont donc versés à la TRACE du
débat (visibles, journalisés, calibrables plus tard), sans toucher au
score du verdict tant que le module ne les accepte pas nativement.
"""
from __future__ import annotations

import sys
import threading
import time
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
if str(RACINE) not in sys.path:
    sys.path.insert(0, str(RACINE))

_MEM: dict = {}
_VERROU = threading.Lock()


def lire_instrument(instrument: str, bars_par_tf: dict):
    """Lecture complète + mémorisation. Renvoie la Lecture (ou None)."""
    try:
        from agent_chartiste import lire
        L = lire(instrument, {tf: b for tf, b in bars_par_tf.items() if b})
    except Exception:
        return None
    with _VERROU:
        _MEM[instrument] = {"L": L, "t": time.time()}
    return L


def derniere(instrument: str):
    """La dernière lecture mémorisée (2 h max) — pour la fiche."""
    with _VERROU:
        d = _MEM.get(instrument)
    if d and time.time() - d["t"] < 7200:
        return d["L"]
    return None


def integrer(paquet: dict, bars_par_tf: dict, symbole: str) -> None:
    """Côté or : lecture AVANT l'étape d'émission (AG-19 et le débat la
    consomment) + résumé dans le paquet pour la fiche et le rapport."""
    from agent_chartiste import source_direction
    L = lire_instrument(symbole, bars_par_tf)
    if L is None:
        return
    paquet["chartiste"] = {
        "source": source_direction(L),
        "niveaux": L.niveaux_fusionnes[:5],
        "conflits": L.conflits,
        "n_uniques": L.n_uniques,
        "n_brutes": L.n_figures,
        "attendu_sur_bruit": L.attendu_sur_bruit,
    }


def carte_dans_agents(paquet: dict, symbole: str) -> None:
    """La carte AG-20 rejoint le panneau (après agents_live)."""
    L = derniere(symbole)
    if L is None or not isinstance(paquet.get("agents"), list):
        return
    from agent_chartiste import carte_agent
    paquet["agents"] = [c for c in paquet["agents"]
                        if c.get("code") != "AG-20"] + [carte_agent(L)]


def enrichir_debat(st: dict, instrument: str, prix: float | None) -> None:
    """Verse les faits de NIVEAU d'AG-20 à la trace du débat — jamais de
    figure (une figure se croit, un niveau se vérifie)."""
    L = derniere(instrument)
    d = st.get("debat")
    if L is None or not d or not prix:
        return
    try:
        from agent_chartiste import arguments_avocats
        for a in arguments_avocats(L, prix):
            cible = d.setdefault("contre" if a["camp"] == "contre"
                                 else "pour", [])
            cible.append({"code": a["code"], "texte": f"[AG-20] {a['texte']}",
                          "mesure": a["mesure"]})
    except Exception:
        pass


def source_pour_directeur(instrument: str):
    """La tendance multi-timeframe (DESCRIPTIVE) pour AG-19 — None si
    aucune lecture mémorisée ou sens neutre : absent ne vote pas."""
    L = derniere(instrument)
    if L is None or L.sens_dominant == "neutre" or not L.par_tf:
        return None
    try:
        from agent_chartiste import source_direction
        from direction import Source
        s = source_direction(L)
        return Source("chartiste", "tendance", L.sens_dominant,
                      min(1.0, L.accord), s["mesure"],
                      predictive=False, agent="AG-20")
    except Exception:
        return None
