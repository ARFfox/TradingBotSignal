"""APPLIQUER étape 6 — le pont setup → débat AG-16/AG-18 (sans réseau)."""
from gold_agent.debat import examiner_setup


def _setup(pct=60, stop=99.5, objectif=102.0):
    return {"setup": "achat", "entree": 100.0, "stop": stop,
            "objectif": objectif, "rr": 4.0,
            "decision_chef": {"pct": pct, "composantes": [],
                              "notifiable": pct >= 55}}


def test_stop_dans_le_bruit_est_bloque():
    """Le cas cuivre : stop 0,25 ATR, RR effectif qui s'écroule → BLOQUÉ,
    et la note n'est PAS touchée (le signal ne sort pas, point)."""
    st = _setup()
    v = examiner_setup(st, instrument="XAU/USD", tf="M5", atr=2.0, spread=0.5,
                       carreau={"trades": 30, "r_cumule": -15.0})
    assert v.bloque
    assert any(a.code == "stop_dans_le_bruit" for a in v.contre)
    assert st["decision_chef"]["pct"] == 60          # inchangée


def test_verdict_applique_le_facteur_a_la_note():
    st = _setup(pct=60, stop=97.0, objectif=106.0)   # stop 1,5 ATR, RR 2
    v = examiner_setup(st, instrument="XAU/USD", tf="H1", atr=2.0, spread=0.1,
                       intermarche={"score": 0.6, "base": 0.8, "fiable": True},
                       confluence=3,
                       carreau={"trades": 40, "r_cumule": 20.0})
    assert not v.bloque
    assert st["decision_chef"]["pct"] == max(5, min(95, round(60 * v.facteur)))
    assert any(c.startswith("débat") for c in st["decision_chef"]["composantes"])
    # notifiable recalculé sur la note ajustée
    assert st["decision_chef"]["notifiable"] == (st["decision_chef"]["pct"] >= 55)


def test_contexte_journalise_pour_la_calibration():
    st = _setup(stop=97.0, objectif=106.0)
    examiner_setup(st, instrument="BTC/USD", tf="M15", atr=2.0, spread=0.1,
                   news_dans_h=1.5, carreau={"trades": 5, "r_cumule": 1.0})
    d = st["debat"]
    assert d["ctx"]["news_dans_h"] == 1.5
    assert d["ctx"]["esperance_combo"] == 0.2
    assert d["ctx"]["n_combo"] == 5
    assert d["verdict"] in ("BLOQUÉ", "AFFAIBLI", "NEUTRE", "RENFORCÉ")


def test_base_mince_ne_rassure_jamais():
    """Défense favorable mais base non fiable : facteur plafonné à 1,0."""
    st = _setup(pct=60, stop=97.0, objectif=106.0)
    v = examiner_setup(st, instrument="XAU/USD", tf="H1", atr=2.0, spread=0.1,
                       intermarche={"score": 0.9, "base": 0.1, "fiable": False},
                       confluence=4)
    if not v.bloque:
        assert v.facteur <= 1.0
        assert st["decision_chef"]["pct"] <= 60
