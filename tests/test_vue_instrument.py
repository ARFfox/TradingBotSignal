"""Tests de la vue par instrument.

Le risque principal de ce module n'est pas de planter : c'est d'afficher un
« 67 % » calculé sur 3 trades. Un chiffre faux et lisible fait prendre des
décisions ; une erreur visible n'en fait prendre aucune. La moitié de ces
tests protège la première situation.
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


vi = _charger("vue_instrument")


def sig(instrument="XAU/USD", tf="H1", statut="SL", marche="matieres",
        i=0, px=4348.0, rr=2.0):
    risque = px * 0.004
    return {"id": f"s{i}", "instrument": instrument, "marche": marche,
            "tf": tf, "sens": "achat", "entree": px, "sl": px - risque,
            "tp": px + rr * risque, "cree_ts": 1_750_000_000 + i * 900,
            "statut": statut}


def jeu(instrument="XAU/USD", tf="H1", n_tp=10, n_sl=30, **kw):
    return ([sig(instrument, tf, "TP", i=i, **kw) for i in range(n_tp)]
            + [sig(instrument, tf, "SL", i=100 + i, **kw) for i in range(n_sl)])


# --- LE test : ne jamais afficher un taux sur trop peu de données ---------
def test_sous_20_resolus_aucun_taux_n_est_calcule():
    """« 67 % sur 3 trades » est un tirage à pile ou face affiché en gras."""
    f = vi.fiche(jeu(n_tp=2, n_sl=1), "XAU/USD")
    assert f.global_.taux is None
    assert f.global_.r_moyen is None and f.global_.ic is None


def test_le_texte_dit_insuffisant_avec_l_effectif():
    f = vi.fiche(jeu(n_tp=2, n_sl=1), "XAU/USD")
    t = f.global_.texte_taux
    assert "insuffisant" in t and "3/20" in t
    assert "%" not in t, "aucun pourcentage ne doit apparaître"


def test_a_partir_de_20_le_taux_apparait():
    f = vi.fiche(jeu(n_tp=5, n_sl=15), "XAU/USD")
    assert f.global_.n_resolus == 20 and f.global_.taux == pytest.approx(0.25)


def test_le_taux_sort_toujours_avec_son_intervalle():
    f = vi.fiche(jeu(n_tp=10, n_sl=30), "XAU/USD")
    t = f.global_.texte_taux
    assert "IC [" in t and "(10/40)" in t


def test_le_hasard_est_toujours_affiche_a_cote():
    """Comparer un taux à 50 % est l'erreur classique. À R:R 2, la
    référence est 33 %, pas 50 %."""
    f = vi.fiche(jeu(n_tp=10, n_sl=30, rr=2.0), "XAU/USD")
    assert f.global_.hasard == pytest.approx(1 / 3, abs=0.01)
    assert "hasard" in f.global_.texte_taux


def test_un_instrument_sous_le_hasard_est_signale():
    f = vi.fiche(jeu(n_tp=8, n_sl=42, rr=2.0), "XAU/USD")   # 16 % vs 33 %
    assert f.sous_le_hasard
    assert "pièce lancée" in vi.rapport(f)


def test_un_instrument_au_dessus_du_hasard_n_est_pas_signale():
    f = vi.fiche(jeu(n_tp=25, n_sl=25, rr=2.0), "XAU/USD")  # 50 % vs 33 %
    assert not f.sous_le_hasard


# --- le filtrage par instrument -------------------------------------------
def test_la_fiche_ne_contient_que_son_instrument():
    """C'est la demande : cliquer sur l'or montre l'or, rien d'autre."""
    j = jeu("XAU/USD", n_tp=10, n_sl=30) + jeu("EUR/USD", n_tp=9, n_sl=1, px=1.085)
    f = vi.fiche(j, "XAU/USD")
    assert f.global_.n_resolus == 40
    assert all(s["instrument"] == "XAU/USD" for s in f.signaux)


def test_deux_instruments_ont_des_taux_differents():
    j = jeu("XAU/USD", n_tp=8, n_sl=32) + jeu("EUR/USD", n_tp=30, n_sl=10, px=1.085)
    a = vi.fiche(j, "XAU/USD").global_.taux
    b = vi.fiche(j, "EUR/USD").global_.taux
    assert a == pytest.approx(0.20) and b == pytest.approx(0.75)


def test_l_historique_est_du_plus_recent_au_plus_ancien():
    f = vi.fiche(jeu(n_tp=10, n_sl=10), "XAU/USD")
    ts = [s["cree_ts"] for s in f.signaux]
    assert ts == sorted(ts, reverse=True)


def test_un_instrument_inconnu_ne_plante_pas():
    f = vi.fiche(jeu(), "N'EXISTE PAS")
    assert f.global_.n_resolus == 0 and f.badge == 0
    assert isinstance(vi.rapport(f), str)


# --- les 5 timeframes ------------------------------------------------------
def test_les_cinq_timeframes_sont_toujours_presents():
    """Même vides. Un timeframe absent du tableau se lit « pas de signal »,
    alors qu'il veut dire « pas de données » — ce n'est pas pareil."""
    f = vi.fiche(jeu(tf="H1"), "XAU/USD")
    assert list(f.timeframes) == list(vi.TIMEFRAMES)
    assert f.timeframes["M5"].n_resolus == 0


def test_chaque_timeframe_compte_ses_propres_signaux():
    j = jeu(tf="H4", n_tp=10, n_sl=30) + jeu(tf="M5", n_tp=2, n_sl=3)
    f = vi.fiche(j, "XAU/USD")
    assert f.timeframes["H4"].n_resolus == 40
    assert f.timeframes["M5"].n_resolus == 5
    assert f.timeframes["M5"].taux is None, "5 trades ne font pas un taux"


def test_un_timeframe_perdant_est_coupe():
    f = vi.fiche(jeu(tf="M5", n_tp=2, n_sl=38), "XAU/USD")
    assert f.timeframes["M5"].verdict == "COUPÉ"


def test_un_timeframe_gagnant_est_autorise():
    f = vi.fiche(jeu(tf="H4", n_tp=30, n_sl=10), "XAU/USD")
    assert f.timeframes["H4"].verdict == "AUTORISÉ"


def test_un_timeframe_peu_mesure_n_est_ni_coupe_ni_autorise():
    """On ne condamne pas un timeframe sur 5 trades, et on ne l'adoube
    pas non plus."""
    f = vi.fiche(jeu(tf="M15", n_tp=0, n_sl=5), "XAU/USD")
    assert f.timeframes["M15"].verdict == "INSUFFISANT"


# --- les badges ------------------------------------------------------------
def test_le_badge_compte_les_signaux_EN_COURS_pas_l_historique():
    """Un badge qui compte des trades finis ne se vide jamais, et on
    arrête de le regarder."""
    f = vi.fiche(jeu(n_tp=10, n_sl=30), "XAU/USD",
                 [{"instrument": "XAU/USD", "tf": "M5"}])
    assert f.badge == 1 and f.global_.n_resolus == 40


def test_le_badge_dit_QUELS_timeframes_portent_le_signal():
    """C'est la demande : voir sur quel timeframe est le signal."""
    f = vi.fiche(jeu(), "XAU/USD",
                 [{"instrument": "XAU/USD", "tf": "M15"},
                  {"instrument": "XAU/USD", "tf": "H4"}])
    assert f.tf_avec_signal == ["H4", "M15"], "et dans l'ordre des timeframes"


def test_aucun_signal_en_cours_donne_un_badge_vide():
    assert vi.fiche(jeu(), "XAU/USD", []).badge == 0


def test_le_badge_du_marche_somme_ses_instruments():
    j = jeu("BTC/USD", marche="crypto", px=75713.0) + \
        jeu("ETH/USD", marche="crypto", px=2396.0)
    actifs = [{"instrument": "BTC/USD", "tf": "H4"},
              {"instrument": "ETH/USD", "tf": "M5"},
              {"instrument": "ETH/USD", "tf": "H1"}]
    b = vi.badges_par_marche(vi.toutes_les_fiches(j, actifs))
    assert b["crypto"] == 3


def test_un_instrument_sans_historique_mais_avec_signal_apparait():
    """Sinon un nouvel instrument qui émet son premier signal est invisible."""
    fs = vi.toutes_les_fiches([], [{"instrument": "SOL/USD", "tf": "M30"}])
    assert [f.instrument for f in fs] == ["SOL/USD"] and fs[0].badge == 1


def test_les_instruments_avec_signal_passent_en_premier():
    j = jeu("XAU/USD", n_tp=10, n_sl=30) + jeu("BTC/USD", marche="crypto",
                                               n_tp=1, n_sl=1, px=75713.0)
    fs = vi.toutes_les_fiches(j, [{"instrument": "BTC/USD", "tf": "H4"}])
    assert fs[0].instrument == "BTC/USD"


# --- ce qui ne doit pas compter -------------------------------------------
def test_les_signaux_en_attente_ne_comptent_dans_aucun_taux():
    j = jeu(n_tp=10, n_sl=30) + [sig(statut="en_attente", i=900 + k)
                                 for k in range(50)]
    f = vi.fiche(j, "XAU/USD")
    assert f.global_.n_resolus == 40 and f.global_.n_attente == 50


def test_les_expires_sont_exclus_du_taux_mais_restent_visibles():
    """Entrée jamais touchée : rien à gagner ni à perdre. Mais les cacher
    empêcherait de voir qu'on annonce des entrées jamais atteintes."""
    j = jeu(n_tp=10, n_sl=30) + [sig(statut="expire", i=800 + k)
                                 for k in range(25)]
    f = vi.fiche(j, "XAU/USD")
    assert f.global_.n_resolus == 40 and f.global_.n_expire == 25


# --- robustesse ------------------------------------------------------------
def test_le_R_est_lu_du_journal_quand_il_existe():
    s = sig(statut="TP", i=1)
    s["r_realise"] = 7.0
    assert vi._r(s) == 7.0


def test_le_R_est_recalcule_quand_le_journal_ne_le_porte_pas():
    """Repli tant que l'étape 1 n'est pas faite. C'est la cause du
    « profit factor 0.00 » affiché sur le site."""
    assert vi._r(sig(statut="TP", rr=2.0)) == pytest.approx(2.0)
    assert vi._r(sig(statut="SL")) == -1.0


def test_un_signal_non_resolu_n_a_pas_de_R():
    assert vi._r(sig(statut="en_attente")) is None


def test_un_journal_vide_ne_plante_pas():
    assert vi.toutes_les_fiches([]) == []
    assert isinstance(vi.rapport(vi.fiche([], "XAU/USD")), str)


def test_le_rapport_nomme_les_timeframes_insuffisants():
    r = vi.rapport(vi.fiche(jeu(tf="H4", n_tp=1, n_sl=2), "XAU/USD"))
    assert "insuffisant" in r.lower() and "M5" in r
