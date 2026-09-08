"""Tests de la grille de conviction — invariants des couleurs."""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from research import livetest as lt


def _sig(tf="H1", statut="gagnant", r=1.0, age_j=1.0):
    return {"tf": tf, "statut": statut, "r_obtenu": r,
            "cree_ts": time.time() - age_j * 86400}


def test_vert_exige_les_trois_criteres():
    # 30 gagnants a +1R -> R cumule 30, PF inf, n=30 : VERT
    sig = [_sig() for _ in range(30)]
    c = lt.carreau(sig, "H1")
    assert c["couleur"] == "vert" and c["emission_grille"]


def test_edge_positif_echantillon_court_est_bleu():
    sig = [_sig() for _ in range(5)]
    c = lt.carreau(sig, "H1")
    assert c["couleur"] == "bleu" and not c["emission_grille"], \
        "un edge non prouve ne donne PAS le droit d'emettre"


def test_perdant_est_rouge():
    sig = [_sig(statut="perdant", r=-1.0) for _ in range(4)]
    assert lt.carreau(sig, "H1")["couleur"] == "rouge"


def test_sans_trade_resolu_est_gris():
    assert lt.carreau([], "H1")["couleur"] == "gris"
    en_attente = [{"tf": "H1", "statut": "en_attente", "r_obtenu": None,
                   "cree_ts": time.time()}]
    assert lt.carreau(en_attente, "H1")["couleur"] == "gris"


def test_fenetre_glissante_oublie_le_passe():
    vieux = [_sig(r=-1.0, statut="perdant", age_j=120) for _ in range(10)]
    recents = [_sig(r=1.0, age_j=2) for _ in range(3)]
    c = lt.carreau(vieux + recents, "H1")
    assert c["trades"] == 3 and c["couleur"] == "bleu", \
        "les trades hors fenetre 90 j ne doivent pas compter"


def test_grille_un_carreau_par_tf():
    g = lt.grille([_sig()], ["H4", "H1", "M30"])
    assert [c["tf"] for c in g] == ["H4", "H1", "M30"]
