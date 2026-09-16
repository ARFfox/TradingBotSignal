"""Tests des garde-fous. Cas réels tirés du journal du 16/09/2026."""
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


gf = _charger("garde_fous")


def bg(h, b, c=None):
    return {"high": h, "low": b, "close": c if c is not None else (h + b) / 2}


# --- stop minimum ---------------------------------------------------------
def test_le_cas_cuivre_reel_est_elargi():
    """Cuivre M5, entrée 6.50 / SL 6.49 : 0,29 ATR, dans le bruit."""
    s = gf.stop_minimum(6.50, 6.49, "achat", atr=0.035, spread=0.003)
    assert s.ajuste and s.distance_atr >= gf.SL_MIN_ATR


def test_un_stop_deja_large_n_est_jamais_resserre():
    """Un stop structurel plus large que le minimum a raison contre lui."""
    s = gf.stop_minimum(100.0, 90.0, "achat", atr=2.0)
    assert not s.ajuste and s.valeur == 90.0


def test_le_stop_reste_du_bon_cote_en_achat():
    s = gf.stop_minimum(100.0, 99.9, "achat", atr=5.0)
    assert s.valeur < 100.0


def test_le_stop_reste_du_bon_cote_en_vente():
    s = gf.stop_minimum(100.0, 100.1, "vente", atr=5.0)
    assert s.valeur > 100.0


def test_le_spread_peut_imposer_un_stop_plus_large_que_l_atr():
    s = gf.stop_minimum(100.0, 99.99, "achat", atr=0.01, spread=0.5)
    assert abs(100.0 - s.valeur) >= gf.MARGE_SPREAD * 0.5


def test_atr_inconnu_ne_touche_a_rien():
    s = gf.stop_minimum(100.0, 99.9, "achat", atr=0.0)
    assert not s.ajuste and s.valeur == 99.9


# --- validation -----------------------------------------------------------
def test_le_cuivre_reel_est_refuse_apres_elargissement():
    """LE cas qui compte : le setup ne tenait que par un stop irréaliste."""
    v = gf.valider_signal(6.50, 6.49, 6.53, "achat", atr=0.035, spread=0.003)
    assert not v["ok"] and v["rr"] < gf.RR_MIN


def test_un_bon_setup_passe():
    v = gf.valider_signal(100.0, 90.0, 130.0, "achat", atr=5.0)
    assert v["ok"] and v["rr"] == pytest.approx(3.0)


def test_risque_nul_refuse():
    assert not gf.valider_signal(100.0, 100.0, 110.0, "achat", atr=0.0)["ok"]


def test_l_elargissement_degrade_le_rr_et_c_est_voulu():
    serre = gf.valider_signal(100.0, 99.0, 104.0, "achat", atr=5.0)
    assert not serre["ok"], "un R:R qui ne survit pas à un stop réaliste est faux"


# --- anti-contradiction ---------------------------------------------------
def test_le_cas_gdx_reel_est_filtre():
    """12:17 — GDX en vente M15 ET en achat M5. L'un des deux perd."""
    lot = [{"instrument": "GDX", "tf": "M15", "sens": "vente", "note": 0.27,
            "cree_ts": 1000},
           {"instrument": "GDX", "tf": "M5", "sens": "achat", "note": 0.43,
            "cree_ts": 1000}]
    g, r = gf.filtrer_lot(lot)
    assert len(g) == 1 and g[0]["note"] == 0.43
    assert "contredit" in r[0]["motif"]


def test_le_meilleur_survit():
    lot = [{"instrument": "X", "tf": "A", "sens": "achat", "note": 0.9, "cree_ts": 0},
           {"instrument": "X", "tf": "B", "sens": "vente", "note": 0.2, "cree_ts": 0}]
    g, _ = gf.filtrer_lot(lot)
    assert g[0]["note"] == 0.9


def test_doublon_rapproche_refuse():
    lot = [{"instrument": "X", "tf": "M5", "sens": "achat", "note": 0.9, "cree_ts": 0},
           {"instrument": "X", "tf": "M15", "sens": "achat", "note": 0.8, "cree_ts": 300}]
    g, r = gf.filtrer_lot(lot)
    assert len(g) == 1 and "doublon" in r[0]["motif"]


def test_deux_instruments_differents_passent():
    lot = [{"instrument": "A", "tf": "M5", "sens": "achat", "note": 0.9, "cree_ts": 0},
           {"instrument": "B", "tf": "M5", "sens": "vente", "note": 0.8, "cree_ts": 0}]
    g, _ = gf.filtrer_lot(lot)
    assert len(g) == 2


# --- suivi ----------------------------------------------------------------
SIG = {"entree": 100.0, "sl": 98.0, "tp": 106.0, "sens": "achat"}


def test_tp_atteint_apres_sl_est_detecte():
    """Sans ça, impossible de distinguer un stop trop serré d'une erreur
    de direction — donc impossible de corriger la bonne chose."""
    r = gf.suivre(SIG, [bg(100.5, 99.0), bg(101.0, 97.5), bg(107.0, 99.0)])
    assert r.statut == "SL" and r.tp_atteint_apres_sl


def test_direction_fausse_ne_leve_pas_le_drapeau():
    r = gf.suivre(SIG, [bg(100.2, 99.5), bg(100.1, 97.0), bg(97.8, 95.0)])
    assert r.statut == "SL" and not r.tp_atteint_apres_sl


def test_objectif_atteint():
    r = gf.suivre(SIG, [bg(100.5, 99.2), bg(106.5, 100.0)])
    assert r.statut == "TP" and r.r_realise == pytest.approx(3.0)


def test_entree_jamais_touchee_donne_expire():
    """Un signal jamais entré ne compte dans aucun taux : il n'y avait
    rien à gagner ni à perdre."""
    r = gf.suivre(SIG, [bg(105.0, 101.0)])
    assert r.statut == "expire" and not r.entree_touchee and r.r_realise is None


def test_une_bougie_touchant_sl_et_tp_compte_comme_sl():
    """Choix pessimiste assumé : en OHLC on ignore l'ordre des extrêmes.
    Supposer le TP gonflerait les résultats, et un backtest optimiste est
    pire qu'un backtest absent."""
    r = gf.suivre(SIG, [bg(100.1, 99.5), bg(107.0, 97.0)])
    assert r.statut == "SL"


def test_extreme_favorable_suit_le_meilleur_prix():
    r = gf.suivre(SIG, [bg(100.5, 99.0), bg(104.0, 100.0), bg(103.0, 97.5)])
    assert r.extreme_favorable == pytest.approx(104.0)


def test_horizon_respecte():
    bougies = [bg(100.5, 99.5)] * 5 + [bg(107.0, 99.0)]
    assert gf.suivre(SIG, bougies, horizon=3).statut == "en_attente"


def test_vente_symetrique():
    s = {"entree": 100.0, "sl": 102.0, "tp": 94.0, "sens": "vente"}
    r = gf.suivre(s, [bg(101.0, 99.5), bg(100.0, 93.5)])
    assert r.statut == "TP" and r.r_realise == pytest.approx(3.0)


def test_aucune_bougie_ne_plante_pas():
    assert gf.suivre(SIG, []).statut == "en_attente"


def test_bougies_jusqu_a_entree_enregistre():
    r = gf.suivre(SIG, [bg(105.0, 101.0), bg(102.0, 99.0), bg(106.5, 100.0)])
    assert r.bougies_jusqu_a_entree == 1


# --- schéma ---------------------------------------------------------------
def test_les_champs_critiques_sont_declares():
    c = gf.champs_journal()
    for champ in ("emis", "atr", "tp_atteint_apres_sl", "extreme_favorable"):
        assert champ in c, f"{champ} manquant — le superviseur ne peut pas apprendre"
