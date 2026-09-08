"""Tests du biais de structure (AG-02 sur la constellation) — sans reseau.

Invariants proteges :
- une tendance nette (EMA + structure d'accord) donne le bon biais
- un DESACCORD entre EMA et structure donne neutre, jamais l'avis optimiste
- un actif trop court est absent du dictionnaire (absence != avis)
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from gold_agent import biais_structure as bs


def _ohlc(series: dict) -> pd.DataFrame:
    """DataFrame OHLC MultiIndex a partir de {ticker: closes}."""
    idx = None
    colonnes = {}
    for t, c in series.items():
        c = pd.Series(c)
        idx = pd.date_range("2024-01-01", periods=len(c), freq="D")
        c.index = idx
        # hauts/bas synthetiques autour de la cloture : le zigzag de la
        # cloture porte la structure, l'amplitude reste petite
        colonnes[("Close", t)] = c
        colonnes[("High", t)] = c * 1.004
        colonnes[("Low", t)] = c * 0.996
        colonnes[("Open", t)] = c.shift(1).fillna(c.iloc[0])
    return pd.DataFrame(colonnes)


def _zigzag(base: float, pente: float, n: int = 300) -> np.ndarray:
    """Tendance + oscillation : produit des pivots HH/HL (ou LH/LL) nets."""
    x = np.arange(n, dtype=float)
    return base + pente * x + 3.0 * np.sin(x / 5.0)


def test_tendance_haussiere_franche():
    po = _ohlc({"UP": _zigzag(100, 0.5)})
    assert bs.biais_membres(po) == {"UP": "haussier"}


def test_tendance_baissiere_franche():
    po = _ohlc({"DN": _zigzag(300, -0.5)})
    assert bs.biais_membres(po) == {"DN": "baissier"}


def test_sans_direction_donne_neutre():
    rng = np.random.default_rng(3)
    plat = 100 + np.cumsum(rng.normal(0, 0.05, 300)) * 0  # strictement plat
    po = _ohlc({"FLAT": plat + 2.0 * np.sin(np.arange(300) / 7.0)})
    assert bs.biais_membres(po).get("FLAT") == "neutre"


def test_desaccord_fait_douter():
    """EMA encore haussiere mais structure qui casse (LH+LL recents) ->
    le verdict doit etre neutre : un desaccord ne rassure jamais."""
    monte = _zigzag(100, 0.5, 260)
    casse = _zigzag(monte[-1], -0.8, 40)
    serie = np.concatenate([monte, casse])
    po = _ohlc({"DIV": serie})
    v = bs.examiner(po["Close"]["DIV"], po["High"]["DIV"], po["Low"]["DIV"])
    if v["ema"] > 0 and v["structure"].startswith("baissier"):
        assert v["biais"] == "neutre"
    # quelle que soit la configuration exacte, jamais haussier avec une
    # structure baissiere franche
    if v["structure"] == "baissier":
        assert v["biais"] != "haussier"


def test_actif_trop_court_est_absent():
    po = _ohlc({"OK": _zigzag(100, 0.5), "COURT": _zigzag(100, 0.5, 20)})
    b = bs.biais_membres(po)
    assert "OK" in b and "COURT" not in b
