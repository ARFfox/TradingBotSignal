"""Tests de la conversion en pips.

Un compteur de pips se casse silencieusement : il affiche un nombre
plausible qui ne correspond à rien. La moitié de ces tests vérifie que les
chiffres faux sont SIGNALÉS plutôt que fondus dans le total.
"""
from __future__ import annotations

import importlib.util
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent


def _charger(nom: str):
    spec = importlib.util.spec_from_file_location(nom, RACINE / f"{nom}.py")
    m = importlib.util.module_from_spec(spec)
    sys.modules[nom] = m
    spec.loader.exec_module(m)
    return m


pp = _charger("pips")


@dataclass
class S:
    instrument: str = "EURUSD"
    entree: float = 1.0850
    sl: float = 1.0830
    tp: float = 1.0890
    statut: str = "TP"

    @property
    def rr(self):
        r = abs(self.entree - self.sl)
        return abs(self.tp - self.entree) / r if r else 0.0

    @property
    def r_realise(self):
        return self.rr if self.statut == "TP" else -1.0 if self.statut == "SL" else None


# --- la conversion ---------------------------------------------------------
def test_les_tailles_de_pip_usuelles():
    assert pp.taille_pip("EUR/USD")[0] == pytest.approx(0.0001)
    assert pp.taille_pip("USD/JPY")[0] == pytest.approx(0.01)
    assert pp.taille_pip("XAUUSD")[0] == pytest.approx(0.01)


def test_une_paire_en_yen_inconnue_est_deduite():
    """Le yen a deux décimales de moins. Le deviner à 0,0001 multiplierait
    son total par 100."""
    assert pp.taille_pip("CADJPY")[0] == pytest.approx(0.01)


def test_le_format_du_nom_ne_change_rien():
    for n in ("EUR/USD", "eurusd", "EUR-USD", "eur/usd"):
        assert pp.normaliser(n) == "EURUSD"


def test_crypto_et_indices_disent_points_pas_pips():
    """Personne ne dit « pip » sur le Bitcoin. Inventer l'unité rendrait
    le chiffre incompréhensible."""
    assert pp.taille_pip("BTCUSD")[1] == "points"
    assert pp.taille_pip("NAS100")[1] == "points"
    assert pp.taille_pip("EURUSD")[1] == "pips"


# --- le calcul -------------------------------------------------------------
def test_un_tp_compte_positif():
    assert pp.pips_signal(S(statut="TP")) == pytest.approx(40.0)


def test_un_sl_compte_negatif():
    """« S'il y a plus de pertes, tu fais moins pips » : c'est ici."""
    assert pp.pips_signal(S(statut="SL")) == pytest.approx(-20.0)


def test_plus_de_pertes_donne_un_net_negatif():
    b = pp.bilan([S(statut="TP")] * 2 + [S(statut="SL")] * 10)
    assert b.net < 0 and b.net == pytest.approx(2 * 40 - 10 * 20)


def test_plus_de_gains_donne_un_net_positif():
    b = pp.bilan([S(statut="TP")] * 10 + [S(statut="SL")] * 2)
    assert b.net > 0


def test_l_or_se_compte_en_centimes():
    """1,00 $ de mouvement sur l'or = 100 pips."""
    s = S("XAUUSD", 2400.0, 2390.0, 2401.0, "TP")
    assert pp.pips_signal(s) == pytest.approx(100.0)


# --- ce qui ne doit PAS compter -------------------------------------------
def test_un_signal_non_resolu_ne_compte_pas():
    """Un trade jamais entré n'a fait gagner ni perdre un pip."""
    assert pp.pips_signal(S(statut="en_attente")) is None
    assert pp.pips_signal(S(statut="expire")) is None


def test_les_signaux_en_attente_ne_bougent_pas_le_total():
    reel = pp.bilan([S(statut="TP"), S(statut="SL")])
    avec = pp.bilan([S(statut="TP"), S(statut="SL")] + [S(statut="en_attente")] * 99)
    assert reel.net == avec.net and reel.n_resolus == avec.n_resolus


def test_un_signal_incomplet_ne_plante_pas():
    assert pp.pips_signal({"statut": "TP", "instrument": "EURUSD"}) is None


def test_un_dictionnaire_marche_aussi():
    """Le journal stocke des dicts, pas des dataclasses."""
    d = {"instrument": "EURUSD", "entree": 1.0850, "sl": 1.0830,
         "tp": 1.0890, "statut": "TP"}
    assert pp.pips_signal(d) == pytest.approx(40.0)


# --- l'honnêteté du total --------------------------------------------------
def test_un_instrument_inconnu_est_exclu_du_total():
    """4 signaux mal convertis produisaient 96 % du total. Les exclure est
    plus honnête que de laisser un chiffre faux écraser les autres."""
    propres = [S(statut="TP")] * 5
    b = pp.bilan(propres + [S("PLATINE", 980.0, 970.0, 1001.0, "SL")] * 4)
    assert b.net == pp.bilan(propres).net
    assert any(not l.converti for l in b.lignes), "il doit rester visible"


def test_un_instrument_inconnu_est_nomme_dans_le_rapport():
    b = pp.bilan([S("PLATINE", 980.0, 970.0, 1001.0, "SL")])
    r = pp.rapport(b)
    assert "PLATINE" in r and "exclu" in r


def test_le_melange_d_instruments_est_signale():
    """+500 pips d'or et −500 d'EUR/USD ne s'annulent pas."""
    b = pp.bilan([S("XAUUSD", 2400.0, 2390.0, 2420.0, "TP"),
                  S("EURUSD", 1.0850, 1.0830, 1.0890, "SL")])
    assert b.melange
    assert "≠" in pp.resume_court(b)
    assert "somme d'argent" in pp.rapport(b)


def test_un_seul_instrument_donne_un_chiffre_net():
    """Filtré sur un instrument, le total est exact : pas de marqueur."""
    b = pp.bilan([S(statut="TP"), S(statut="SL")])
    assert not b.melange and "≠" not in pp.resume_court(b)


def test_le_R_reste_affiche_a_cote_des_pips():
    """Le R est le seul agrégat comparable entre marchés : il ne doit
    jamais disparaître de l'en-tête."""
    b = pp.bilan([S(statut="TP"), S(statut="SL")] * 5)
    assert "R" in pp.resume_court(b)


# --- robustesse ------------------------------------------------------------
def test_aucun_signal_ne_plante_pas():
    b = pp.bilan([])
    assert b.n_resolus == 0 and b.net == 0
    assert "aucun" in pp.resume_court(b).lower()
    assert isinstance(pp.rapport(b), str)


def test_que_des_signaux_en_attente():
    b = pp.bilan([S(statut="en_attente")] * 20)
    assert b.n_resolus == 0 and isinstance(pp.rapport(b), str)


def test_le_taux_se_calcule_sur_les_resolus_seulement():
    b = pp.bilan([S(statut="TP")] * 3 + [S(statut="SL")] * 1
                 + [S(statut="expire")] * 96)
    assert b.taux == pytest.approx(0.75) and b.n_resolus == 4
