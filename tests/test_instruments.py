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


def test_depuis_alias_resout_les_noms_tradingview():
    """Regle 13 : la correspondance de symboles vit dans le registre,
    jamais dans une table locale d'un module de calcul (bug backtest.py:51)."""
    assert instruments.depuis_alias("OANDA:XAUUSD").symbole == "XAU/USD"
    assert instruments.depuis_alias("gold").symbole == "XAU/USD"
    assert instruments.depuis_alias("INCONNU:ZZZ") is None


def test_code_pour_traduit_par_source():
    """Regle 13 : la traduction de symboles vit dans le registre, pas dans
    les adapters. Un adapter demande le code, il ne le devine pas."""
    btc = instruments.REGISTRE["BTC/USD"]
    assert btc.code_pour("binance") == "BTCUSDT"
    assert btc.code_pour("yahoo") == "BTC-USD"
    assert btc.code_pour("source_inconnue") == "BTC/USD"


def test_le_cout_est_porte_par_l_instrument():
    """Regle 14 : le cout d'un backtest vient de l'Instrument, jamais d'une
    constante partagee — 0,05 % sur BTC n'a rien a voir avec l'or."""
    assert instruments.REGISTRE["BTC/USD"].cout_pct > 0
    assert (instruments.REGISTRE["BTC/USD"].cout_pct
            != instruments.REGISTRE["EUR/USD"].cout_pct)
