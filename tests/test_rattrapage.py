"""Tests d'AG-17 Rattrapage — les garde-fous de la spec, sans reseau.

Invariants proteges :
- une divergence sur paire STABLE et correlee est detectee, avec le bon
  sens (achat du retardataire a la hausse)
- une paire INSTABLE ne propose JAMAIS rien, meme avec un z enorme
  (sur une correlation instable l'ecart s'elargit, il ne se referme pas)
- sans historique d'occurrences suffisant, pas d'avis (le taux est
  MESURE, jamais affirme)
- Vigie agitee -> l'opportunite nait marquee « a valider »
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from gold_agent import rattrapage as rp


def _paire_cointegree(n=800, graine=1, divergence_finale=0.06):
    """Deux series qui partagent le meme moteur (correlation stable), avec
    des episodes de divergence recurrents PUIS une divergence finale :
    le pivot monte, le satellite ne suit pas."""
    rng = np.random.default_rng(graine)
    idx = pd.date_range("2024-01-01", periods=n, freq="D")
    commun = rng.normal(0.0004, 0.01, n)
    a = 100 * np.exp(np.cumsum(commun + rng.normal(0, 0.002, n)))
    # le satellite suit, avec des retards periodiques qui se referment
    retard = 0.018 * np.sin(np.arange(n) / 9.0)
    b = 90 * np.exp(np.cumsum(commun + rng.normal(0, 0.002, n)) + retard)
    a, b = pd.Series(a, index=idx), pd.Series(b, index=idx)
    # divergence finale : +6 % sur le pivot en 5 jours, satellite immobile
    a.iloc[-5:] = a.iloc[-6] * np.exp(np.linspace(0.012, divergence_finale, 5))
    b.iloc[-5:] = b.iloc[-6]
    return pd.DataFrame({"PIVOT": a, "SAT": b})


MEMBRE_STABLE = {"ticker": "SAT", "corr": 0.85, "stabilite": 0.9}
MEMBRE_INSTABLE = {"ticker": "SAT", "corr": 0.85, "stabilite": 0.4}


def test_divergence_detectee_avec_le_bon_sens():
    px = _paire_cointegree()
    ops = rp.detecter(px, "PIVOT", [MEMBRE_STABLE])
    assert ops, "divergence de +6 % non detectee"
    o = ops[0]
    assert o["z"] >= rp.SEUIL_Z
    assert o["sens"] == "achat", "le satellite en retard a la hausse s'achete"
    assert o["historique"]["occurrences"] >= rp.OCCURRENCES_MIN
    assert "mesurées" in o["note"], "le taux doit dire qu'il est mesure"


def test_paire_instable_ne_propose_jamais_rien():
    px = _paire_cointegree()
    assert rp.detecter(px, "PIVOT", [MEMBRE_INSTABLE]) == [], \
        "stabilite 0,4 : l'ecart s'elargit, il ne se referme pas — refus"


def test_correlation_faible_refusee():
    px = _paire_cointegree()
    faible = {"ticker": "SAT", "corr": 0.45, "stabilite": 0.9}
    assert rp.detecter(px, "PIVOT", [faible]) == []


def test_sans_historique_pas_d_avis():
    # serie courte : impossible de mesurer un taux de fermeture
    px = _paire_cointegree(n=140)
    assert rp.detecter(px, "PIVOT", [MEMBRE_STABLE]) == []


def test_vigie_agitee_marque_a_valider():
    px = _paire_cointegree()
    ops = rp.detecter(px, "PIVOT", [MEMBRE_STABLE], vigie_calme=False)
    assert ops and ops[0]["a_valider"] is True, \
        "une news specifique n'est pas une divergence, c'est une information"


def test_statistique_fermeture_mesure_vraiment():
    px = _paire_cointegree()
    stats = rp.statistique_fermeture(px["PIVOT"], px["SAT"])
    assert stats and stats["occurrences"] >= rp.OCCURRENCES_MIN
    assert 0 <= stats["taux_fermeture_pct"] <= 100
    if stats["delai_median_j"] is not None:
        assert 1 <= stats["delai_median_j"] <= rp.HORIZON_J
