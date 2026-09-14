"""Tests de la calibration Brier — invariants metier, sans reseau.

Ce qu'ils protegent :
- un agent qui a toujours raison recoit le poids maximal
- une piece de monnaie (50 %) tombe au plancher, pas a un poids negatif
- sous AVIS_MIN, PAS de poids calcule (une base mince ne prouve rien)
- etre CONTRE un signal perdant compte comme un avis juste
- le neutre ne s'enregistre pas comme avis
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from gold_agent import avis


def _sig(direction, sens, statut, tf="H1"):
    return {"tf": tf, "sens": sens, "statut": statut,
            "avis": {"AG-X": direction}}


def test_toujours_juste_donne_le_poids_maximal():
    sig = [_sig("achat", "achat", "gagnant") for _ in range(12)]
    c = avis.evaluer(sig)["AG-X"]["global"]
    assert c["exactitude"] == 1.0 and c["poids"] == 1.0 and c["brier"] == 0.0


def test_une_piece_tombe_au_plancher():
    sig = ([_sig("achat", "achat", "gagnant") for _ in range(6)]
           + [_sig("achat", "achat", "perdant") for _ in range(6)])
    c = avis.evaluer(sig)["AG-X"]["global"]
    assert c["exactitude"] == 0.5 and c["poids"] == avis.POIDS_PLANCHER


def test_echantillon_court_reste_sans_poids():
    sig = [_sig("achat", "achat", "gagnant") for _ in range(avis.AVIS_MIN - 1)]
    c = avis.evaluer(sig)["AG-X"]["global"]
    assert c["poids"] is None, "9 avis parfaits ne prouvent pas encore"


def test_contre_un_perdant_est_juste():
    # l'agent disait VENTE, le signal etait ACHAT et a perdu -> l'agent
    # avait raison de s'y opposer
    sig = [_sig("vente", "achat", "perdant") for _ in range(12)]
    c = avis.evaluer(sig)["AG-X"]["global"]
    assert c["exactitude"] == 1.0


def test_les_avis_se_ventilent_par_timeframe():
    sig = ([_sig("achat", "achat", "gagnant", tf="H4") for _ in range(12)]
           + [_sig("achat", "achat", "perdant", tf="M30") for _ in range(12)])
    c = avis.evaluer(sig)["AG-X"]
    assert c["par_tf"]["H4"]["exactitude"] == 1.0
    assert c["par_tf"]["M30"]["exactitude"] == 0.0
    assert c["global"]["n"] == 24


def test_directions_ignore_le_neutre():
    paquet = {"news": {"macro": {"arguments": [("haussier", 2, "x"),
                                               ("baissier", 2, "y")]}},
              "constellation": {"score": {"fiable": False, "score": 0.9},
                                "sens_teste": "achat"}}
    r = {"tendance": "indeterminee"}
    d = avis.directions(paquet, r)
    assert "AG-01" not in d, "camps a egalite = pas d'avis"
    assert "AG-10" not in d, "base non fiable = pas d'avis"
    assert "AG-02" not in d


def test_directions_extrait_les_avis_fermes():
    paquet = {
        "news": {"macro": {"arguments": [("haussier", 2, "taux")]},
                 "minieres": {"aem": {"variation_pct": 3.2}}},
        "constellation": {"score": {"fiable": True, "score": 0.8},
                          "sens_teste": "achat"},
        "marches": {"tuiles": [{"cle": "matieres", "fiable": True,
                                "largeur": 0.75}]},
    }
    r = {"tendance": "haussiere"}
    d = avis.directions(paquet, r)
    assert d == {"AG-02": "achat", "AG-01": "achat", "AG-05": "achat",
                 "AG-10": "achat", "AG-13": "achat"}


def test_miroir_negatif_inverse_le_sens_teste():
    paquet = {"constellation": {"score": {"fiable": True, "score": -0.9},
                                "sens_teste": "vente"}}
    d = avis.directions(paquet, {})
    assert d.get("AG-10") == "achat", \
        "un score tres negatif sur 'vente' est un avis ACHAT"
