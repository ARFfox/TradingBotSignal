"""Tests de l'analyse a la demande — invariants d'emission, sans reseau.

Ce qu'ils protegent :
- l'or ne passe PAS par l'analyse a la demande (il garde collecter)
- un setup detecte sur un instrument non valide est TOUJOURS suspendu
- aucun timeframe H4 pour un instrument Yahoo (pas de donnees mensongeres)
- analyser_tf produit tous les champs que la carte consomme
"""
import math
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from gold_agent import analyse


def _bars(n=600, graine=3, derive=0.4):
    rng = np.random.default_rng(graine)
    prix, out = 100.0, []
    for i in range(n):
        prix += derive + rng.normal(0, 1.0)
        c = prix + 6 * math.sin(i / 15)
        o = c + rng.normal(0, 0.5)
        h = max(o, c) + abs(rng.normal(0, 0.8)) + 0.3
        l = min(o, c) - abs(rng.normal(0, 0.8)) - 0.3
        out.append({"time": 1700000000 + i * 1800, "open": o, "high": h,
                    "low": l, "close": c})
    return out


TFS = ["H4", "H1", "M30", "M15", "M5"]


def test_l_or_ne_passe_pas_par_l_analyse_a_la_demande():
    with pytest.raises(ValueError):
        analyse.analyse_instrument("XAUUSD")


def test_instrument_inconnu_refuse():
    with pytest.raises(KeyError):
        analyse.analyse_instrument("NIMPORTEQUOI")


def test_tout_setup_detecte_est_suspendu():
    """Regles 2-3 : un instrument non valide par le walk-forward n'emet
    JAMAIS — s'il y a un setup, il est suspendu, et emission=False partout."""
    bars = {tf: _bars(graine=i) for i, tf in enumerate(TFS)}
    a = analyse.analyse_instrument("BTCUSD", bars_par_tf=bars)
    assert a["timeframes"], "aucun timeframe analyse"
    for r in a["timeframes"]:
        assert r.get("emission") is False
        st = r.get("setup") or {}
        if st.get("setup"):
            assert st.get("suspendu"), f"{r['nom']} : setup non suspendu !"


def test_pas_de_h4_pour_un_instrument_yahoo():
    bars = {tf: _bars(graine=i) for i, tf in enumerate(TFS)}
    a = analyse.analyse_instrument("SPY", bars_par_tf=bars)
    noms = [r["nom"] for r in a["timeframes"]]
    assert "H4" not in noms, "Yahoo n'a pas de 4 h natif"
    assert noms == ["H1", "M30", "M15", "M5"]


def test_analyser_tf_produit_les_champs_de_la_carte():
    spec = {"tf": "30", "nom": "M30", "role": "Timing", "mtf": 2,
            "params": dict(ema_fast=20, ema_slow=50, pivot_span=3, delai_max=40)}
    r = analyse.analyser_tf(_bars(), spec, {"niveau": "test"})
    for champ in ("setup", "prix", "rsi", "atr", "ema_fast", "ema_slow",
                  "extension", "volatilite", "ict", "abc", "pct_haussier",
                  "bougies", "fiabilite"):
        assert champ in r, f"champ manquant : {champ}"
    assert len(r["bougies"]) == 120
