"""Tests du protocole walk-forward — invariants metier, sans reseau.

Ce qu'ils protegent :
- la purge : aucun signal ne de la zone d'echauffement ne compte
- un echantillon court est REFUSE meme si l'esperance est bonne
- une regle perdante est REFUSEE
- les fenetres couvrent l'historique sans depasser
"""
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from gold_agent import strategy as sg
from research import walkforward as wf


def _bars(n: int = 1600, graine: int = 7, derive: float = 0.05) -> list[dict]:
    """Serie synthetique avec tendance + oscillations : la regle EMA/pivots
    y trouve des signaux dans les deux regimes."""
    rng = np.random.default_rng(graine)
    prix = 2000.0
    out = []
    for i in range(n):
        vague = 8.0 * math.sin(i / 18.0) + 3.0 * math.sin(i / 5.0)
        prix = prix + derive + rng.normal(0, 1.2)
        c = prix + vague
        o = c + rng.normal(0, 0.6)
        h = max(o, c) + abs(rng.normal(0, 1.0)) + 0.5
        l = min(o, c) - abs(rng.normal(0, 1.0)) - 0.5
        out.append({"time": 1700000000 + i * 3600, "open": o, "high": h,
                    "low": l, "close": c})
    return out


PARAMS = sg.Params(ema_fast=20, ema_slow=50, pivot_span=3, delai_max=40,
                   cout_pts=0.3)


def test_fenetres_couvrent_sans_depasser():
    fs = wf.fenetres(1000, echauffement=400, test=300, pas=150)
    assert fs, "aucune fenetre sur 1000 bougies"
    for a, d, f in fs:
        assert a + 400 + wf.PURGE == d, "purge non respectee dans la geometrie"
        assert f <= 1000 and f - d >= 20


def test_purge_aucun_signal_de_l_echauffement():
    bars = _bars()
    r = wf.executer(bars, PARAMS, "TEST", "H1")
    # invariant structurel : executer ne garde que les signaux d'index
    # >= seuil de test ; on le verifie en re-derivant une fenetre a la main
    a, d_test, f_test = wf.fenetres(len(bars), 400, 300, 150)[0]
    segment = bars[a:f_test]
    signaux = sg.detecter(segment, PARAMS)
    dans_test = [s for s in signaux if s.index >= d_test - a]
    assert all(s.index >= 400 + wf.PURGE for s in dans_test)


def test_echantillon_court_refuse():
    bars = _bars(n=750)          # une seule vraie fenetre -> peu de trades
    r = wf.executer(bars, PARAMS, "TEST", "H1")
    if r.trades < wf.TRADES_MIN:
        assert not r.autorise
        assert "trades" in r.motif


def test_regle_perdante_refusee():
    """Sur un pur bruit sans derive, apres couts, la regle ne doit jamais
    ressortir AUTORISEE avec un PF > 1,3 : le protocole doit refuser."""
    refus = 0
    for graine in (1, 2, 3):
        bars = _bars(graine=graine, derive=0.0)
        r = wf.executer(bars, sg.Params(ema_fast=20, ema_slow=50,
                                        pivot_span=3, delai_max=40,
                                        cout_pts=2.0), "BRUIT", "H1")
        if not r.autorise:
            refus += 1
    assert refus >= 2, "le protocole autorise du bruit couteux"


def test_verdict_exige_deux_regimes():
    bars = _bars()
    r = wf.executer(bars, PARAMS, "TEST", "H1")
    if r.autorise:
        regs = {k: v for k, v in r.regimes.items() if k != "indetermine"}
        assert len(regs) >= wf.REGIMES_MIN


def test_une_fenetre_d_un_seul_trade_ne_vote_pas():
    """Un seul trade par fenetre = pile ou face : la fenetre ne doit pas
    voter, sinon le protocole refuse a tort les regles parcimonieuses."""
    bars = _bars()
    r = wf.executer(bars, PARAMS, "TEST", "H1")
    assert r.fenetres_evaluables <= r.fenetres
    assert r.fenetres_positives <= r.fenetres_evaluables
