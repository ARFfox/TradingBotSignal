"""Tests de la couche feeds — reponses FIGEES, jamais d'appel reseau.

Invariants proteges :
- normalisation : bougies incoherentes jetees, ordre chronologique garanti
- seau a jetons : le rate limit tient par construction (horloge injectee)
- backoff : une erreur se retente, une panne totale finit par lever
- cache : deux appels rapproches ne coutent qu'une requete
- pagination Binance / ordre inverse Bybit respectes
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from feeds import base
from feeds.base import Feed, SeauJetons, valider_bars
from feeds.binance import Binance
from feeds.bybit import Bybit


# ---------------------------------------------------------------- validation
def test_validation_jette_les_bougies_incoherentes():
    bars = [
        {"time": 2, "open": 10, "high": 11, "low": 9, "close": 10.5},
        {"time": 1, "open": 10, "high": 9, "low": 11, "close": 10},   # h < l
        {"time": 3, "open": "x", "high": 11, "low": 9, "close": 10},  # non num
        {"time": 0, "open": 10, "high": 11, "low": 9, "close": 10.2},
    ]
    v = valider_bars(bars)
    assert [b["time"] for b in v] == [0, 2], "tri + rejet des incoherentes"
    assert all(isinstance(b["close"], float) for b in v)


def test_validation_dedoublonne_par_timestamp():
    b = {"open": 1, "high": 2, "low": 0.5, "close": 1.5}
    v = valider_bars([{"time": 5, **b}, {"time": 5, **b, "close": 1.7}])
    assert len(v) == 1 and v[0]["close"] == 1.7


# ---------------------------------------------------------------- seau
def test_seau_bloque_puis_recharge():
    t = {"v": 0.0}
    dormi = []
    seau = SeauJetons(2, 1.0, horloge=lambda: t["v"],
                      sommeil=lambda s: (dormi.append(s),
                                         t.__setitem__("v", t["v"] + s)))
    assert seau.prendre() == 0.0
    assert seau.prendre() == 0.0
    attendu = seau.prendre()          # seau vide -> doit attendre ~1 s
    assert attendu > 0 and dormi, "le rate limit doit bloquer, pas ignorer"


# ---------------------------------------------------------------- backoff
class _FeedTest(Feed):
    nom = "test"

    def __init__(self, reponses):
        super().__init__(seau=SeauJetons(100, 100.0), sommeil=lambda s: None)
        self.reponses = list(reponses)
        self.appels = 0

    def _transport(self, url, timeout=20):
        self.appels += 1
        r = self.reponses.pop(0)
        if isinstance(r, Exception):
            raise r
        return r

    def _fetch(self, symbole, tf, nombre):
        return self._requete("http://fige")


def test_backoff_retente_puis_reussit():
    f = _FeedTest([OSError("boom"), OSError("boom"),
                   [{"time": 1, "open": 1, "high": 2, "low": 0.5, "close": 1.5}]])
    bars = f.bars("X", "60", ttl=0)
    assert f.appels == 3 and len(bars) == 1


def test_panne_totale_finit_par_lever():
    f = _FeedTest([OSError("boom")] * 4)
    try:
        f.bars("X", "60", ttl=0)
        assert False, "aurait du lever"
    except RuntimeError:
        pass


# ---------------------------------------------------------------- cache
def test_cache_evite_la_seconde_requete(tmp_path, monkeypatch):
    monkeypatch.setattr(base, "DOSSIER_CACHE", tmp_path)
    rep = [{"time": 1, "open": 1, "high": 2, "low": 0.5, "close": 1.5}]
    f = _FeedTest([rep, rep])
    f.bars("X", "60", ttl=3600)
    f.bars("X", "60", ttl=3600)
    assert f.appels == 1, "le second appel doit venir du cache"


# ---------------------------------------------------------------- binance
def test_binance_normalise_et_pagine(monkeypatch):
    from feeds import binance as bn
    monkeypatch.setattr(bn, "MAX_PAR_APPEL", 2)
    pages = [
        # page 1 (la plus recente) : PLEINE (2 = max) -> pagination
        [[2000000, "10", "11", "9", "10.5", "7"],
         [2060000, "10.5", "12", "10", "11.5", "8"]],
        # page 2 : une seule ligne < max -> debut d'historique, stop
        [[1940000, "9", "10.2", "8.5", "10", "6"]],
    ]
    b = Binance(sommeil=lambda s: None, seau=SeauJetons(100, 100.0))
    b.reponses = list(pages)
    b._transport = lambda url, timeout=20: b.reponses.pop(0)
    bars = b._fetch("BTCUSDT", "60", 4)
    assert [x["time"] for x in bars] == [1940, 2000, 2060], "ordre chronologique"
    assert bars[0]["open"] == "9"      # la conversion float est le role de valider_bars


def test_bybit_inverse_l_ordre():
    rep = {"result": {"list": [
        [2060000, "11", "12", "10", "11.5", "8", "0"],
        [2000000, "10", "11", "9", "10.5", "7", "0"],
    ]}}
    b = Bybit(sommeil=lambda s: None, seau=SeauJetons(100, 100.0))
    b._transport = lambda url, timeout=20: rep
    bars = b._fetch("BTCUSDT", "60", 2)
    assert [x["time"] for x in bars] == [2000, 2060]


def test_un_petit_cache_ne_repond_pas_a_une_grosse_demande(tmp_path, monkeypatch):
    """Bug reel : un appel d'essai de 50 bougies avait fige le cache, et le
    walk-forward recevait 50 bougies au lieu des 5000 demandees."""
    monkeypatch.setattr(base, "DOSSIER_CACHE", tmp_path)
    rep_petit = [{"time": i, "open": 1, "high": 2, "low": 0.5, "close": 1.5}
                 for i in range(50)]
    rep_grand = [{"time": i, "open": 1, "high": 2, "low": 0.5, "close": 1.5}
                 for i in range(200)]
    f = _FeedTest([rep_petit, rep_grand])
    assert len(f.bars("X", "60", 50, ttl=3600)) == 50
    assert len(f.bars("X", "60", 200, ttl=3600)) == 200, \
        "le cache de 50 ne doit pas repondre a une demande de 200"
    assert f.appels == 2
