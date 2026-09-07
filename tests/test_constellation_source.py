"""Tests de la source de prix — AUCUN réseau : le téléchargeur est neutralisé.

Invariants du contrat :
- cache frais -> DataFrame, perime=False, pas de téléchargement lancé
- cache périmé -> le MEME DataFrame rendu tout de suite, perime=True,
  téléchargement déclenché une seule fois
- aucun cache -> None + téléchargement déclenché
"""
import sys
import time
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from gold_agent import constellation_source as cs


def _neutraliser(monkeypatch, compteur):
    monkeypatch.setattr(cs, "_telecharger", lambda: compteur.append(1))
    # _lancer_telechargement utilise un thread : on garde le mecanisme mais
    # le corps est inoffensif et synchrone une fois le thread joint
    with cs._TELECHARGEMENT["verrou"]:
        cs._TELECHARGEMENT["en_cours"] = False


def _ecrire_cache(tmp_path, monkeypatch, age_s):
    cache = tmp_path / "prix.parquet"
    df = pd.DataFrame({"GC=F": [1.0, 2.0, 3.0], "BTC-USD": [4.0, 5.0, 6.0]})
    df.to_parquet(cache)
    vieux = time.time() - age_s
    import os
    os.utime(cache, (vieux, vieux))
    monkeypatch.setattr(cs, "CACHE", cache)
    return df


def test_cache_frais(tmp_path, monkeypatch):
    compteur = []
    _neutraliser(monkeypatch, compteur)
    _ecrire_cache(tmp_path, monkeypatch, age_s=60)
    df = cs.prix()
    assert df is not None and df.attrs["perime"] is False
    time.sleep(0.05)
    assert not compteur, "cache frais : aucun telechargement"


def test_cache_perime_rendu_immediatement(tmp_path, monkeypatch):
    compteur = []
    _neutraliser(monkeypatch, compteur)
    _ecrire_cache(tmp_path, monkeypatch, age_s=7 * 3600)
    df = cs.prix()
    assert df is not None, "le vieux cache doit etre rendu tout de suite"
    assert df.attrs["perime"] is True
    time.sleep(0.1)
    assert len(compteur) == 1, "telechargement lance exactement une fois"


def test_aucun_cache(tmp_path, monkeypatch):
    compteur = []
    _neutraliser(monkeypatch, compteur)
    monkeypatch.setattr(cs, "CACHE", tmp_path / "absent.parquet")
    assert cs.prix() is None
    time.sleep(0.1)
    assert len(compteur) == 1
