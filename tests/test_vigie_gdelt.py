"""Tests de la Vigie GDELT — interpretation PURE, reponses figees.

Invariants proteges :
- une tonalite nettement plus sombre que son fond est signalee
- un volume geopolitique x1,5+ est signale comme agitation
- des donnees insuffisantes donnent None (pas d'avis sur 3 points)
- une reponse malformee ne leve jamais
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from gold_agent import vigie_gdelt as vg


def _rep(valeurs):
    return {"timeline": [{"series": "x",
                          "data": [{"date": "d", "value": v} for v in valeurs]}]}


def test_tonalite_sombre_signalee():
    # fond a -2, dernier jour a -4 : ecart -2 -> nettement plus sombre
    ton = vg.interpreter_tonalite(_rep([-2.0] * 16 + [-4.0] * 8), points_jour=8)
    assert ton["ecart"] < -0.8
    lignes = vg.lecture(ton, None)
    assert any("NETTEMENT plus sombre" in x for x in lignes)


def test_tonalite_dans_la_norme():
    ton = vg.interpreter_tonalite(_rep([-2.0] * 24), points_jour=8)
    assert abs(ton["ecart"]) < 0.8
    assert any("dans sa norme" in x for x in vg.lecture(ton, None))


def test_volume_agite_signale():
    vol = vg.interpreter_volume(_rep([100.0] * 16 + [250.0] * 8), points_jour=8)
    assert vol["ratio"] >= 1.5
    assert any("s'agite" in x for x in vg.lecture(None, vol))


def test_donnees_insuffisantes_donnent_none():
    assert vg.interpreter_tonalite(_rep([-2.0] * 5)) is None
    assert vg.interpreter_volume(_rep([1.0] * 5)) is None
    assert vg.interpreter_volume(_rep([0.0] * 30)) is None, \
        "volume nul partout : ratio indefinissable"


def test_reponse_malformee_ne_leve_pas():
    for mauvaise in ({}, {"timeline": []}, {"timeline": [{"data": []}]},
                     {"autre": 1}):
        assert vg.interpreter_tonalite(mauvaise) is None
        assert vg.interpreter_volume(mauvaise) is None
