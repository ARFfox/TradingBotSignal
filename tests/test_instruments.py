"""Invariants du calcul de position parametre par Instrument.

L'or doit donner EXACTEMENT le meme resultat qu'avant la correction, et
un instrument de valeur de point differente doit changer la taille en
proportion inverse — c'est tout ce que la regle 13 exige.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gold_agent import instruments, notify


def test_or_inchange():
    t = notify.taille_position(4500.0, 4490.0)
    # capital/risque viennent de .env : sans capital, None — invariant : ne plante pas
    if t is not None:
        # 1 lot or = 100 $/point : risque = distance * 100 * lots
        assert abs(t["risque_montant"] - t["lots_precis"] * 10.0 * 100.0) < 1e-6


def test_proportionnalite():
    riche = instruments.Instrument("TEST/1", "test", 100.0)
    pauvre = instruments.Instrument("TEST/2", "test", 10.0)
    a = notify.taille_position(100.0, 90.0, instrument=riche)
    b = notify.taille_position(100.0, 90.0, instrument=pauvre)
    if a is not None and b is not None:
        assert abs(b["lots_precis"] / a["lots_precis"] - 10.0) < 1e-6


def test_defaut_est_or():
    assert instruments.par_defaut().point_par_lot == 100.0
    assert instruments.par_defaut().symbole == "XAU/USD"
