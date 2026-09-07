"""Tests de l'AG-16 Avocat du diable — module pur, sans reseau."""
import time

from gold_agent import avocat


def _tf(sens="achat", entree=4400.0, stop=4394.0, objectif=4412.0,
        atr=5.0, haut=4450.0, bas=4350.0, nom="M30", ext=None):
    return {
        "nom": nom, "atr": atr,
        "setup": {"setup": sens, "entree": entree, "stop": stop,
                  "objectif": objectif},
        "ict": {"premium_discount": {"haut_range": haut, "bas_range": bas}},
        "extension": ext or {"niveau": "faible", "sens": "neutre"},
    }


def test_sans_setup():
    assert avocat.examiner({"nom": "M30", "setup": {}}) is None


def test_rien_a_redire():
    v = avocat.examiner(_tf())
    assert v["verdict"] == "refute" and v["objections"] == []


def test_resistance_proche_bloque():
    # resistance a 0.6 ATR au-dessus, TP au-dela : le trade doit la traverser
    v = avocat.examiner(_tf(haut=4403.0, objectif=4412.0))
    assert v["verdict"] == "non_refute"
    assert "résistance" in v["motif_blocage"]


def test_resistance_proche_refutee_si_tp_avant():
    v = avocat.examiner(_tf(haut=4403.0, objectif=4402.5))
    assert v["verdict"] == "refute"
    assert v["objections"][0]["refutee"] is True


def test_support_proche_bloque_une_vente():
    v = avocat.examiner(_tf(sens="vente", stop=4406.0, objectif=4388.0,
                            bas=4397.0))
    assert v["verdict"] == "non_refute" and "support" in v["motif_blocage"]


def test_news_dans_la_fenetre_bloque():
    evts = [{"titre": "CPI m/m", "dans_minutes": 45}]
    v = avocat.examiner(_tf(), evenements=evts)
    assert v["verdict"] == "non_refute" and "CPI" in v["motif_blocage"]


def test_news_hors_fenetre_ignoree():
    # M30 -> fenetre 2 h ; un evenement a 5 h ne compte pas
    evts = [{"titre": "NFP", "dans_minutes": 300}]
    v = avocat.examiner(_tf(), evenements=evts)
    assert v["verdict"] == "refute"


def test_serie_echecs_bloque():
    t = time.time()
    sig = [{"tf": "M30", "sens": "achat", "statut": "perdant", "cree_ts": t}
           for _ in range(3)]
    v = avocat.examiner(_tf(), signaux=sig, maintenant=t)
    assert v["verdict"] == "non_refute" and "échoué 3 fois" in v["motif_blocage"]


def test_serie_echecs_refutee_par_une_reussite():
    t = time.time()
    sig = [{"tf": "M30", "sens": "achat", "statut": "perdant", "cree_ts": t}
           for _ in range(3)]
    sig.append({"tf": "M30", "sens": "achat", "statut": "gagnant", "cree_ts": t})
    v = avocat.examiner(_tf(), signaux=sig, maintenant=t)
    assert v["verdict"] == "refute"


def test_stop_dans_le_bruit_mineure():
    v = avocat.examiner(_tf(stop=4397.5))          # 2.5 pt = 0.5 ATR
    assert v["verdict"] == "refute"                # mineure ne bloque pas
    assert any("bruit" in o["quoi"] for o in v["objections"])


def test_poursuite_extension_mineure():
    v = avocat.examiner(_tf(ext={"niveau": "forte", "sens": "haussiere",
                                 "score": 0.8}))
    assert v["verdict"] == "refute"
    assert any("poursuite" in o["quoi"] for o in v["objections"])
