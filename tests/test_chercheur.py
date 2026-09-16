"""Tests du chercheur de sous-ensembles.

Le module doit répondre honnêtement dans les deux sens : trouver un edge
réel, et refuser d'en inventer un. Les deux échecs coûtent cher.
"""
from __future__ import annotations

import importlib.util
import random
import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent


def _charger(nom: str):
    spec = importlib.util.spec_from_file_location(nom, RACINE / f"{nom}.py")
    m = importlib.util.module_from_spec(spec)
    sys.modules[nom] = m
    spec.loader.exec_module(m)
    return m


sa = _charger("superviseur_apprenant")
ce = _charger("chercheur_sous_ensembles")


def jeu(n=400, p_marque=0.20, p_autre=0.20, graine=1):
    """`p_marque` = taux de réussite des signaux notés >= 0,60."""
    rng = random.Random(graine)
    out = []
    for i in range(n):
        note = rng.uniform(0.2, 0.9)
        e, risque = 100.0, 10.0
        s = sa.Signal(
            id=f"s{i}", instrument="X", marche="matieres", tf="H1",
            sens="achat", entree=e, sl=e - risque, tp=e + 2.0 * risque,
            note=note, cree_ts=1_750_000_000 + i * 3600,
            statut="en_attente", atr=10.0)
        p = p_marque if note >= 0.60 else p_autre
        s.statut = "TP" if rng.random() < p else "SL"
        out.append(s)
    return out


# --- la référence ---------------------------------------------------------
def test_taux_hasard_est_bien_l_inverse_du_rr():
    """P(toucher +rr avant -1) = 1/(1+rr). C'est la seule référence
    honnête : à 2R, une pièce donne 33 %, pas 50 %."""
    assert ce.taux_hasard(1.0) == pytest.approx(0.5)
    assert ce.taux_hasard(2.0) == pytest.approx(1 / 3)
    assert ce.taux_hasard(2.09) == pytest.approx(0.3236, abs=1e-3)
    assert ce.taux_hasard(4.0) == pytest.approx(0.2)


def test_taux_hasard_robuste():
    assert ce.taux_hasard(0.0) == 0.0


# --- intervalle de confiance ---------------------------------------------
def test_wilson_reste_dans_les_bornes():
    for k, n in [(0, 10), (10, 10), (8, 20), (160, 200)]:
        b, h = ce.wilson(k, n)
        assert 0.0 <= b <= h <= 1.0


def test_l_intervalle_retrecit_avec_l_effectif():
    """« 80 % sur 20 trades » et « 80 % sur 200 » ne sont pas la même
    affirmation. Le module doit le refléter."""
    b1, h1 = ce.wilson(16, 20)
    b2, h2 = ce.wilson(160, 200)
    assert (h1 - b1) > (h2 - b2) * 2


def test_80_pourcent_sur_20_trades_reste_tres_incertain():
    b, h = ce.wilson(16, 20)
    assert b < 0.65, "un taux de 80 % sur 20 trades ne prouve pas 80 %"


def test_la_correction_elargit_l_intervalle():
    assert ce.z_corrige(43) > ce.z_corrige(1)
    assert ce.z_corrige(1) == ce.Z_BASE


# --- détection d'un edge réel --------------------------------------------
def test_un_edge_reel_est_trouve():
    """Note >= 0,60 gagne 65 % contre 15 % ailleurs. Ça doit ressortir."""
    s = jeu(500, p_marque=0.65, p_autre=0.15)
    r = ce.chercher(s, [ce.Condition("note >= 60 %", lambda x: x.note >= 0.60)])
    assert r, "aucun sous-ensemble retenu alors qu'un edge net existe"
    assert r[0].verdict in ("EDGE SOLIDE", "PROMETTEUR") or \
        r[0].verdict.startswith("ATTEINT"), f"verdict inattendu : {r[0].verdict}"


def test_un_edge_tres_fort_atteint_la_cible():
    s = jeu(600, p_marque=0.88, p_autre=0.15)
    r = ce.chercher(s, [ce.Condition("note >= 60 %", lambda x: x.note >= 0.60)],
                    cible=0.80)
    assert r[0].verdict.startswith("ATTEINT"), \
        f"un taux de 88 % confirmé devrait atteindre la cible : {r[0].verdict}"


# --- refus d'inventer -----------------------------------------------------
def test_le_bruit_pur_ne_produit_aucun_edge():
    """LE test qui compte. Sans edge, aucun sous-ensemble ne doit être
    déclaré solide — quel que soit le nombre de conditions testées."""
    s = jeu(500, p_marque=0.20, p_autre=0.20)
    r = ce.chercher(s, ce.conditions_standard())
    solides = [x for x in r if x.verdict.startswith("ATTEINT")
               or x.verdict == "EDGE SOLIDE"]
    assert not solides, f"edge inventé dans du bruit : {[x.conditions for x in solides]}"


def test_un_motif_qui_s_effondre_hors_echantillon_est_signale():
    """Beau sur le passé, nul sur la suite : le cas classique du
    sur-apprentissage. Il doit être nommé, pas retenu."""
    rng = random.Random(3)
    s = []
    for i in range(400):
        note = rng.uniform(0.2, 0.9)
        e, risque = 100.0, 10.0
        x = sa.Signal(id=f"s{i}", instrument="X", marche="m", tf="H1",
                      sens="achat", entree=e, sl=e - risque, tp=e + 2 * risque,
                      note=note, cree_ts=1_750_000_000 + i * 3600,
                      statut="en_attente", atr=10.0)
        # l'edge n'existe QUE dans la première moitié
        p = 0.75 if (note >= 0.60 and i < 280) else 0.15
        x.statut = "TP" if rng.random() < p else "SL"
        s.append(x)
    r = ce.chercher(s, [ce.Condition("note >= 60 %", lambda y: y.note >= 0.60)])
    assert r and r[0].verdict == "NON CONFIRMÉ", \
        f"un effondrement hors échantillon doit être signalé : {r[0].verdict}"


# --- garde-fous structurels ----------------------------------------------
def test_pas_plus_de_deux_conditions_combinees():
    """Au-delà de 2, on ne sélectionne plus, on mémorise."""
    assert ce.MAX_CONDITIONS == 2
    r = ce.chercher(jeu(500), ce.conditions_standard())
    for x in r:
        assert len(x.conditions) <= 2


def test_les_sous_ensembles_trop_petits_sont_ignores():
    r = ce.chercher(jeu(500), [ce.Condition("rare", lambda s: s.note > 0.895)])
    assert not r


def test_donnees_insuffisantes_ne_conclut_pas():
    assert ce.chercher(jeu(20), ce.conditions_standard()) == []


def test_les_conditions_standard_ne_lisent_que_le_present():
    """Une condition qui utiliserait le résultat produirait un edge
    magnifique et inutilisable. Aucune ne doit toucher au statut."""
    s = jeu(100)[0]
    for c in ce.conditions_standard():
        avant = s.statut
        c.test(s)
        assert s.statut == avant


def test_toutes_les_conditions_standard_s_executent():
    s = jeu(50)
    for c in ce.conditions_standard():
        for x in s[:5]:
            assert isinstance(c.test(x), bool)


# --- rapport --------------------------------------------------------------
def test_le_rapport_signale_un_systeme_sous_le_hasard():
    s = jeu(400, p_marque=0.10, p_autre=0.10)
    assert "SOUS le hasard" in ce.rapport(s)


def test_le_rapport_ne_plante_pas_sans_donnees():
    assert isinstance(ce.rapport([]), str)
