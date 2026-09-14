"""Tests de la decision auto-calibree du Superviseur — sans reseau.

Invariants proteges :
- un timeframe qui PERD en live voit ses notes descendre, un qui gagne
  les voit monter — automatiquement, des 5 trades resolus
- sous 5 resolus, le vecu ne pese pas (une stat sur 3 trades est du bruit)
- un agent calibre (>= 10 avis) qui est CONTRE fait baisser la note ;
  sans poids calcule, la calibration se tait
- la note reste bornee 5-95 et chaque composante est nommee
- notifiable = note >= SEUIL_NOTIFICATION (le telephone ne recoit que le
  propre, tout reste visible)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from gold_agent import decision

FIAB = {"niveau": "indicatif"}


def _st(sens="achat", avis=None):
    return {"setup": sens, "avis": avis or {}}


def test_le_vecu_du_tf_pese_dans_les_deux_sens():
    perdant = {"tf": "M5", "trades": 9, "taux_reussite": 22.0, "r_cumule": -5.0}
    gagnant = {"tf": "H1", "trades": 8, "taux_reussite": 75.0, "r_cumule": 9.0}
    n_perd = decision.noter(_st(), FIAB, None, False, None, carreau=perdant)
    n_gagn = decision.noter(_st(), FIAB, None, False, None, carreau=gagnant)
    assert n_perd["pct"] < 60 < n_gagn["pct"]
    assert any(c.startswith("journal") for c in n_perd["composantes"])


def test_sous_cinq_resolus_le_vecu_se_tait():
    court = {"tf": "M15", "trades": 3, "taux_reussite": 0.0, "r_cumule": -3.0}
    n = decision.noter(_st(), FIAB, None, False, None, carreau=court)
    assert not any(c.startswith("journal") for c in n["composantes"])


def test_un_agent_calibre_contre_fait_baisser():
    cal = {"AG-02": {"global": {"n": 20, "exactitude": 0.8, "poids": 0.6},
                     "par_tf": {}}}
    pour = decision.noter(_st("achat", {"AG-02": "achat"}), FIAB, None,
                          False, None, calibration=cal, carreau={"tf": "H1"})
    contre = decision.noter(_st("achat", {"AG-02": "vente"}), FIAB, None,
                            False, None, calibration=cal, carreau={"tf": "H1"})
    assert pour["pct"] > contre["pct"]
    assert any("Brier" in c for c in pour["composantes"])


def test_sans_poids_calcule_la_calibration_se_tait():
    cal = {"AG-02": {"global": {"n": 4, "exactitude": 1.0, "poids": None},
                     "par_tf": {}}}
    n = decision.noter(_st("achat", {"AG-02": "achat"}), FIAB, None,
                       False, None, calibration=cal, carreau={"tf": "H1"})
    assert not any("Brier" in c for c in n["composantes"]), \
        "4 avis parfaits ne prouvent rien encore"


def test_bornes_et_notifiable():
    tres_mauvais = {"tf": "M5", "trades": 20, "taux_reussite": 0.0,
                    "r_cumule": -20.0}
    n = decision.noter(_st(), {"niveau": "déconseillé"},
                       "vigilance", True, None, carreau=tres_mauvais)
    assert 5 <= n["pct"] <= 95
    assert n["notifiable"] is False
    bon = decision.noter(_st(), {"niveau": "mesuré"}, None, False, None,
                         carreau={"tf": "H4", "trades": 10,
                                  "taux_reussite": 70.0, "r_cumule": 8.0})
    assert bon["notifiable"] is True and bon["pct"] >= decision.SEUIL_NOTIFICATION
