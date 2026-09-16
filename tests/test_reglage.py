"""CHANTIER #15 — les rejoueurs du Tuner re-simulent sur les bougies,
ils ne devinent jamais (sans réseau)."""
from gold_agent import reglage
from gold_agent.apprentissage import signaux


def _sig(entree=100.0, atr=2.0, stop=99.5, objectif=104.0, ts=1_750_000_000):
    return signaux([{
        "cle": f"BTC/USD|M15|achat|{entree}", "instrument": "BTC/USD",
        "tf": "M15", "sens": "achat", "entree": entree, "stop": stop,
        "objectif": objectif, "rr_prevu": 2.0, "statut": "perdant",
        "cree_ts": ts, "decision_chef": 50, "atr": atr, "avis": {},
        "r_realise": -1.0, "r_obtenu": -1.0, "extreme_favorable": None,
        "tp_atteint_apres_sl": False}])[0]


def _bars_creux_puis_hausse(ts=1_750_000_000):
    """Le prix trempe à 98,8 (touche un stop serré, pas un stop 1,5 ATR)
    puis monte au TP — le scénario « stop trop serré » type."""
    return [
        {"time": ts + 60, "open": 100, "high": 100.2, "low": 98.8, "close": 99},
        {"time": ts + 120, "open": 99, "high": 104.5, "low": 99, "close": 104},
    ]


def test_stop_large_change_le_verdict(monkeypatch):
    monkeypatch.setattr(reglage, "_bars_pour",
                        lambda inst, tf: _bars_creux_puis_hausse())
    s = _sig()
    serre = reglage.rejoueur_stop_atr([s], 0.5)    # stop 99,0 : touché
    large = reglage.rejoueur_stop_atr([s], 1.5)    # stop 97,0 : survit
    assert serre[0].statut == "SL" and serre[0].tp_atteint_apres_sl
    assert large[0].statut == "TP"
    assert large[0].rr > 0                          # rr recalculé du nouveau sl


def test_sans_bougies_ou_sans_atr_ecarte(monkeypatch):
    monkeypatch.setattr(reglage, "_bars_pour", lambda inst, tf: [])
    assert reglage.rejoueur_stop_atr([_sig()], 1.0) == []
    monkeypatch.setattr(reglage, "_bars_pour",
                        lambda inst, tf: _bars_creux_puis_hausse())
    s = _sig()
    object.__setattr__(s, "atr", None) if hasattr(s, "__dict__") else None
    s.atr = None
    assert reglage.rejoueur_stop_atr([s], 1.0) == []


def test_rr_minimum_est_un_filtre():
    s = _sig(stop=99.0, objectif=102.0)             # rr = 2
    assert reglage.rejoueur_rr_minimum([s], 1.5) == [s]
    assert reglage.rejoueur_rr_minimum([s], 2.5) == []
