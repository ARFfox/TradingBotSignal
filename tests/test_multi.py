"""Tests du multi-marches — invariants, journal isole, sans reseau.

Ce qu'ils protegent :
- deux instruments avec la MEME entree/tf ne se dedupliquent pas entre eux
  (la cle porte l'instrument)
- la resolution ne touche que l'instrument demande
- le plan de tour couvre toute la crypto et fait TOURNER la tranche Yahoo
- livetest.carreau ne melange pas les instruments
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from gold_agent import journal, multi
from research import livetest


def _setup(entree=100.0, sens="achat"):
    return {"setup": sens, "entree": entree, "stop": entree - 2,
            "objectif": entree + 4, "rr": 2.0}


def _journal_isole(tmp_path, monkeypatch):
    monkeypatch.setattr(journal, "FICHIER", tmp_path / "j.json")


def test_la_cle_porte_l_instrument(tmp_path, monkeypatch):
    _journal_isole(tmp_path, monkeypatch)
    assert journal.enregistrer("H1", _setup(), 100, "?", instrument="BTC/USD")
    assert journal.enregistrer("H1", _setup(), 100, "?", instrument="ETH/USD"), \
        "meme entree/tf sur un AUTRE instrument = un autre signal"
    assert not journal.enregistrer("H1", _setup(), 100, "?", instrument="BTC/USD"), \
        "le meme couple se deduplique toujours"
    sig = journal._charger()
    assert {s["instrument"] for s in sig} == {"BTC/USD", "ETH/USD"}


def test_la_resolution_ne_touche_que_son_instrument(tmp_path, monkeypatch):
    _journal_isole(tmp_path, monkeypatch)
    journal.enregistrer("H1", _setup(), 100, "?", instrument="BTC/USD")
    journal.enregistrer("H1", _setup(), 100, "?", instrument="ETH/USD")
    t = int(time.time()) + 60
    bars = [{"time": t, "high": 105.0, "low": 99.0, "close": 104.5}]
    journal.resoudre({"H1": bars}, instrument="BTC/USD")
    etats = {s["instrument"]: s["statut"] for s in journal._charger()}
    assert etats["BTC/USD"] in ("ouvert", "gagnant")
    assert etats["ETH/USD"] == "en_attente", \
        "ETH ne doit pas etre resolu avec les bougies de BTC"


def test_le_carreau_ne_melange_pas_les_instruments():
    t = time.time()
    sig = ([{"tf": "H1", "instrument": "BTC/USD", "statut": "perdant",
             "r_obtenu": -1.0, "cree_ts": t} for _ in range(6)]
           + [{"tf": "H1", "instrument": "ETH/USD", "statut": "gagnant",
               "r_obtenu": 2.0, "cree_ts": t} for _ in range(6)])
    btc = livetest.carreau(sig, "H1", instrument="BTC/USD")
    eth = livetest.carreau(sig, "H1", instrument="ETH/USD")
    assert btc["couleur"] == "rouge" and btc["trades"] == 6
    assert eth["r_cumule"] > 0 and eth["trades"] == 6


def test_le_plan_tourne_sur_yahoo(monkeypatch):
    monkeypatch.setattr(multi, "_ETAT",
                        {"index_yahoo": 0, "verrou": multi.threading.Lock(),
                         "signaux_actifs": [], "derniere_passe": {}})
    p1 = [i.symbole for i in multi._plan_tour()]
    p2 = [i.symbole for i in multi._plan_tour()]
    from gold_agent import instruments
    # MATIC est volontairement route par Yahoo (pas de code Binance fiable) :
    # il tourne avec la tranche, pas avec la crypto Binance.
    cryptos = {i.symbole for i in instruments.par_marche("crypto")
               if i.code_pour("binance") != i.symbole}
    assert cryptos <= set(p1) and cryptos <= set(p2), \
        "la crypto Binance entiere passe a chaque tour (l'API est genereuse)"
    assert set(p1) - cryptos != set(p2) - cryptos, \
        "la tranche Yahoo doit TOURNER d'un tour a l'autre"
    assert instruments.par_defaut().symbole not in p1, \
        "l'or garde son circuit temps reel"
