"""Tests du superviseur apprenant. Aucun réseau, données construites.

Chaque test verrouille un comportement qu'il serait tentant de « corriger »
en cassant l'honnêteté du module : ne pas inventer de seuil, ne pas
récompenser un agent sans pouvoir discriminant, ne pas confondre les deux
causes de stop touché.
"""
from __future__ import annotations

import importlib.util
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


def sig(i=0, note=0.5, statut="TP", rr=2.0, atr=10.0, risque=10.0,
        inst="XAUUSD", tf="H1", sens="achat", ts=1_750_000_000,
        agents=None, tp_apres_sl=False, extreme=None):
    e = 100.0
    s = sa.Signal(
        id=f"s{i}", instrument=inst, marche="matieres", tf=tf, sens=sens,
        entree=e,
        sl=e - risque if sens == "achat" else e + risque,
        tp=e + rr * risque if sens == "achat" else e - rr * risque,
        note=note, cree_ts=ts, statut=statut, atr=atr, agents=agents or {})
    s.tp_atteint_apres_sl = tp_apres_sl
    s.extreme_favorable = extreme
    return s


# --- signal ---------------------------------------------------------------
def test_r_realise():
    assert sig(statut="TP", rr=2.0).r_realise == pytest.approx(2.0)
    assert sig(statut="SL").r_realise == -1.0
    assert sig(statut="en_attente").r_realise is None


def test_un_signal_jamais_entre_n_est_pas_resolu():
    assert not sig(statut="en_attente").resolu
    assert not sig(statut="expire").resolu


def test_sl_en_atr():
    assert sig(risque=5.0, atr=10.0).sl_en_atr == pytest.approx(0.5)
    assert sig(atr=None).sl_en_atr is None


# --- audit des stops ------------------------------------------------------
def test_tp_atteint_apres_sl_signale_un_stop_trop_serre():
    """La panne la plus importante à distinguer : la direction était bonne."""
    d = sa.auditer_sl(sig(statut="SL", risque=5.0, tp_apres_sl=True))
    assert d.cause == "stop_trop_serre"


def test_stop_sous_un_atr_signale_un_stop_trop_serre():
    d = sa.auditer_sl(sig(statut="SL", risque=3.0, atr=10.0))
    assert d.cause == "stop_trop_serre"


def test_prix_jamais_parti_signale_une_direction_fausse():
    """Stop large ET aucune progression : l'analyse avait tort."""
    d = sa.auditer_sl(sig(statut="SL", risque=20.0, atr=10.0, extreme=101.0))
    assert d.cause == "direction_fausse"


def test_les_deux_causes_appellent_des_corrections_differentes():
    a = sa.auditer_sl(sig(statut="SL", risque=3.0, atr=10.0))
    b = sa.auditer_sl(sig(statut="SL", risque=20.0, atr=10.0, extreme=101.0))
    assert a.correction != b.correction, (
        "deux pannes opposées ne peuvent pas avoir la même correction")


def test_un_tp_n_est_pas_audite():
    assert sa.auditer_sl(sig(statut="TP")).cause == "sans_objet"


# --- calibration ----------------------------------------------------------
def test_courbe_de_calibration_detecte_une_note_mensongere():
    """50 signaux notés 80 % qui ne gagnent que 20 % : la note ment."""
    s = [sig(i, note=0.8, statut="TP" if i < 10 else "SL") for i in range(50)]
    c = sa.courbe_calibration(s)
    tr = next(t for t in c if t["n"] >= 20)
    assert tr["taux_reel"] == pytest.approx(0.20)
    assert sa.ecart_calibration(s) > 0.15, "un écart de 60 pts doit être signalé"


def test_une_note_honnete_donne_un_ecart_faible():
    s = [sig(i, note=0.5, statut="TP" if i % 2 == 0 else "SL") for i in range(60)]
    assert sa.ecart_calibration(s) < 0.10


# --- poids des agents -----------------------------------------------------
def test_un_agent_toujours_du_bon_cote_est_survalorise():
    s = [sig(i, statut="TP" if i % 2 == 0 else "SL",
             agents={"AG-X": "haussier" if i % 2 == 0 else "baissier"})
         for i in range(60)]
    p = sa.poids_agents(s)["AG-X"]
    assert p["poids"] > 1.0 and p["discrimination"] > 0


def test_un_agent_qui_vote_toujours_pareil_est_ecarte():
    """Même avec un bon taux apparent : sans variété, aucune information."""
    s = [sig(i, statut="TP" if i < 45 else "SL", agents={"AG-Y": "haussier"})
         for i in range(60)]
    p = sa.poids_agents(s)["AG-Y"]
    assert p["poids"] == sa.POIDS_MIN
    assert "pareil" in p["note"]


def test_un_contre_indicateur_est_nomme():
    s = [sig(i, statut="SL" if i % 2 == 0 else "TP",
             agents={"AG-Z": "haussier" if i % 2 == 0 else "baissier"})
         for i in range(60)]
    p = sa.poids_agents(s)["AG-Z"]
    assert p["discrimination"] < 0 and "inverser" in p["note"]


def test_echantillon_insuffisant_donne_un_poids_neutre():
    s = [sig(i, agents={"AG-W": "haussier"}) for i in range(5)]
    p = sa.poids_agents(s)["AG-W"]
    assert p["poids"] == 1.0 and not p["fiable"]


def test_les_poids_restent_bornes():
    s = [sig(i, statut="TP", rr=50.0, agents={"AG-B": "haussier"}) for i in range(60)]
    assert sa.poids_agents(s)["AG-B"]["poids"] <= sa.POIDS_MAX


# --- seuil ----------------------------------------------------------------
def test_aucun_seuil_invente_quand_tout_perd():
    """LE test qui compte. Face à un système perdant, le module doit le
    dire, pas fabriquer un seuil rassurant."""
    s = [sig(i, note=0.1 + (i % 9) / 10, statut="SL") for i in range(120)]
    r = sa.seuil_optimal(s)
    assert r["assez_de_donnees"] and not r["rentable"]
    assert "AUCUN" in r["message"]


def test_le_seuil_maximise_le_R_total_pas_le_taux():
    """Deux régimes : beaucoup de petits gagnants sous 0,5, peu de gros
    au-dessus. Le seuil optimal doit suivre le R, pas le taux."""
    s = []
    for i in range(80):                        # note basse, R faible
        s.append(sig(i, note=0.3, statut="TP" if i % 3 else "SL", rr=0.4))
    for i in range(80, 160):                   # note haute, R fort
        s.append(sig(i, note=0.8, statut="TP" if i % 2 else "SL", rr=4.0))
    r = sa.seuil_optimal(s)
    # Le seuil doit exclure la tranche basse (note 0,3). Tout seuil entre
    # 0,35 et 0,80 donne le même R total ; le module retient le plus bas,
    # ce qui est le bon choix : à R égal, garder plus de signaux.
    assert r["rentable"] and r["seuil"] > 0.3


def test_donnees_insuffisantes_refuse_de_conclure():
    assert not sa.seuil_optimal([sig(i) for i in range(10)])["assez_de_donnees"]


# --- espérance par couple -------------------------------------------------
def test_un_couple_negatif_est_coupe():
    s = [sig(i, statut="SL", inst="CUIVRE", tf="M5") for i in range(25)]
    assert sa.esperance_par_combo(s)[("CUIVRE", "M5")]["verdict"] == "COUPE"


def test_un_couple_trop_jeune_reste_en_observation():
    s = [sig(i, statut="TP", inst="NEUF", tf="M5") for i in range(5)]
    assert sa.esperance_par_combo(s)[("NEUF", "M5")]["verdict"] == "OBSERVATION"


# --- garde-fous d'émission ------------------------------------------------
def test_contradiction_sur_le_meme_instrument_refusee():
    """Vu dans les données réelles : GDX en achat ET en vente à la même
    minute, sur deux timeframes."""
    c = [sig(1, note=0.9, inst="GDX", tf="M5", sens="achat"),
         sig(2, note=0.8, inst="GDX", tf="M15", sens="vente")]
    g, r = sa.filtrer_emission(c, 0.0, {})
    assert len(g) == 1 and "contredit" in r[0]["motif"]


def test_doublon_rapproche_refuse():
    c = [sig(1, note=0.9, inst="XAUUSD", tf="M5", ts=1000),
         sig(2, note=0.8, inst="XAUUSD", tf="M15", ts=1300)]
    g, r = sa.filtrer_emission(c, 0.0, {})
    assert len(g) == 1 and "doublon" in r[0]["motif"]


def test_deux_signaux_eloignes_passent():
    c = [sig(1, note=0.9, inst="XAUUSD", ts=1000),
         sig(2, note=0.8, inst="XAUUSD", ts=1000 + 3600 * 4)]
    g, _ = sa.filtrer_emission(c, 0.0, {})
    assert len(g) == 2


def test_stop_sous_un_atr_refuse_a_l_emission():
    c = [sig(1, note=0.9, risque=3.0, atr=10.0)]
    g, r = sa.filtrer_emission(c, 0.0, {})
    assert not g and "ATR" in r[0]["motif"]


def test_couple_coupe_refuse_meme_avec_une_note_parfaite():
    c = [sig(1, note=1.0, inst="CUIVRE", tf="M5", risque=15.0, atr=10.0)]
    g, r = sa.filtrer_emission(c, 0.0, {("CUIVRE", "M5"): {"verdict": "COUPE"}})
    assert not g and "négative" in r[0]["motif"]


def test_le_meilleur_est_garde_en_cas_de_contradiction():
    c = [sig(1, note=0.4, inst="GDX", sens="vente", risque=15.0, atr=10.0),
         sig(2, note=0.9, inst="GDX", sens="achat", risque=15.0, atr=10.0)]
    g, _ = sa.filtrer_emission(c, 0.0, {})
    assert len(g) == 1 and g[0].note == 0.9


# --- bilan ----------------------------------------------------------------
def test_les_signaux_jamais_entres_sortent_du_taux():
    s = ([sig(i, statut="TP") for i in range(2)]
         + [sig(i + 2, statut="SL") for i in range(2)]
         + [sig(i + 4, statut="en_attente") for i in range(96)])
    b = sa.bilan(s)
    assert b["resolus"] == 4 and b["taux"] == pytest.approx(0.5)
    assert b["jamais_entres"] == 96


def test_taux_d_equilibre_coherent():
    """À 2R de gain moyen, l'équilibre est à 1/3."""
    s = ([sig(i, statut="TP", rr=2.0) for i in range(10)]
         + [sig(i + 10, statut="SL") for i in range(10)])
    assert sa.bilan(s)["taux_equilibre"] == pytest.approx(1 / 3, abs=0.01)


def test_rapport_ne_plante_pas_sur_un_journal_vide():
    assert isinstance(sa.rapport([]), str)
