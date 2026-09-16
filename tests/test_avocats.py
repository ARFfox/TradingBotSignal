"""Tests du débat contradictoire AG-16 / AG-18.

Un module d'avocats se casse de deux façons opposées, et les deux sont
silencieuses : l'avocat qui plaide toujours, et l'avocat qui ne plaide
jamais. Les deux produisent une sortie d'apparence normale et une
information nulle. La moitié de ces tests ne teste que ça.
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


av = _charger("avocats")


@dataclass
class S:
    id: str = "s"
    instrument: str = "X"
    tf: str = "H1"
    sens: str = "achat"
    entree: float = 100.0
    sl: float = 90.0
    tp: float = 130.0
    note: float = 0.50
    statut: str = "en_attente"

    @property
    def rr(self):
        r = abs(self.entree - self.sl)
        return abs(self.tp - self.entree) / r if r else 0.0

    @property
    def resolu(self):
        return self.statut in ("TP", "SL")

    @property
    def r_realise(self):
        return self.rr if self.statut == "TP" else -1.0 if self.statut == "SL" else None


def ctx_propre(**kw):
    """Un contexte sans relief : rien à plaider dans un sens ni dans l'autre."""
    base = dict(atr=5.0, spread=0.0, score_intermarche=0.0,
                base_intermarche=1.0, base_fiable=True,
                regime_marche="neutre", n_combo=25, esperance_combo=0.0)
    base.update(kw)
    return av.Contexte(**base)


# --- le test qui compte le plus ------------------------------------------
def test_sur_un_signal_sans_relief_les_deux_se_taisent():
    """Un avocat qui trouve toujours quelque chose à dire n'apporte aucune
    information : sa conclusion est connue d'avance."""
    s = S(entree=100.0, sl=93.0, tp=114.0)     # 1,4 ATR, R:R 2,0
    v = av.debat(s, ctx_propre())
    assert v.muet, f"contre={[a.code for a in v.contre]} pour={[a.code for a in v.pour]}"
    assert v.verdict == "NEUTRE" and v.facteur == 1.0


def test_le_silence_est_une_position_affichable():
    v = av.debat(S(entree=100.0, sl=93.0, tp=114.0), ctx_propre())
    assert av.positions_graphe(v) == {"AG-16": "neutre", "AG-18": "neutre"}


# --- AG-16 sur des cas réels ---------------------------------------------
def test_le_cas_cuivre_est_bloque():
    """Cuivre M5, entrée 6.50 / SL 6.49 : 0,29 ATR."""
    s = S("c", "CUIVRE", "M5", "achat", 6.50, 6.49, 6.53, 0.31)
    v = av.debat(s, av.Contexte(atr=0.035, spread=0.003,
                                score_intermarche=-0.45, base_intermarche=2.28,
                                base_fiable=True, regime_marche="baissier",
                                n_combo=34, esperance_combo=-0.38))
    assert v.bloque
    assert "stop_dans_le_bruit" in [a.code for a in v.contre]


def test_la_defense_ne_plaide_pas_un_rr_obtenu_par_un_stop_irrealiste():
    """LE piège du module. Le cuivre affiche R:R 3,00 — mais seulement
    parce que le stop est à 0,29 ATR. La défense qui s'en sert s'appuie
    sur ce que l'accusation vient de démonter."""
    s = S("c", "CUIVRE", "M5", "achat", 6.50, 6.49, 6.53)
    v = av.debat(s, av.Contexte(atr=0.035, spread=0.003, base_fiable=True))
    assert s.rr > 2.5, "le R:R nominal est bien généreux"
    assert "rr_genereux" not in [a.code for a in v.pour], \
        "la défense s'appuie sur un stop irréaliste"


def test_le_rr_effectif_expose_l_illusion():
    s = S("c", "CUIVRE", "M5", "achat", 6.50, 6.49, 6.53)
    ctx = av.Contexte(atr=0.035, spread=0.003)
    assert s.rr == pytest.approx(3.0)
    assert av.rr_effectif(s, ctx) == pytest.approx(0.857, abs=1e-2)


def test_un_stop_deja_large_n_est_pas_penalise():
    s = S(entree=100.0, sl=90.0, tp=130.0)
    assert av.rr_effectif(s, av.Contexte(atr=5.0)) == pytest.approx(3.0)


def test_le_signal_contre_son_marche_est_objecte():
    v = av.debat(S(), ctx_propre(regime_marche="baissier"))
    assert "contre_le_regime" in [a.code for a in v.contre]


def test_un_couple_historiquement_perdant_est_objecte():
    v = av.debat(S(), ctx_propre(n_combo=40, esperance_combo=-0.45))
    assert "combo_negatif" in [a.code for a in v.contre]


def test_un_couple_perdant_mais_peu_mesure_ne_l_est_pas():
    """12 trades ne condamnent pas un couple."""
    v = av.debat(S(), ctx_propre(n_combo=12, esperance_combo=-0.45))
    assert "combo_negatif" not in [a.code for a in v.contre]


# --- AG-18 -----------------------------------------------------------------
def test_un_setup_solide_est_renforce():
    s = S(entree=2400.0, sl=2380.0, tp=2455.0, note=0.62)
    v = av.debat(s, av.Contexte(atr=12.0, score_intermarche=0.52,
                                base_intermarche=4.1, base_fiable=True,
                                regime_marche="haussier",
                                instrument_leader=True, confluence_tf=3,
                                n_combo=41, esperance_combo=0.22))
    assert v.verdict == "RENFORCÉ" and v.facteur > 1.0


def test_la_conviction_ne_depasse_jamais_l_amplitude():
    """Aucun débat ne peut multiplier une conviction par 2."""
    s = S(entree=2400.0, sl=2340.0, tp=2700.0)
    v = av.debat(s, av.Contexte(atr=12.0, score_intermarche=1.0,
                                base_intermarche=9.0, base_fiable=True,
                                regime_marche="haussier", instrument_leader=True,
                                confluence_tf=6, n_combo=99, esperance_combo=1.5))
    assert v.facteur <= 1.0 + av.AMPLITUDE + 1e-9


# --- asymétrie -------------------------------------------------------------
def test_une_base_mince_peut_faire_douter():
    v = av.debat(S(), ctx_propre(base_fiable=False, base_intermarche=0.4,
                                 n_combo=0))
    assert "base_mince" in [a.code for a in v.contre]


def test_une_base_mince_ne_peut_jamais_rassurer():
    """L'asymétrie assumée : le doute passe, la confiance non."""
    s = S(entree=2400.0, sl=2380.0, tp=2455.0)
    v = av.debat(s, av.Contexte(atr=12.0, score_intermarche=0.9,
                                base_intermarche=0.3, base_fiable=False,
                                regime_marche="haussier", confluence_tf=4,
                                n_combo=3))
    assert v.facteur <= 1.0, "une information mince a rassuré — interdit"


# --- redondance ------------------------------------------------------------
def test_trois_arguments_de_la_meme_famille_ne_valent_pas_trois_voix():
    """« marché haussier » + « instrument leader » disent une seule chose.
    Sans ce regroupement, un avocat bavard gagne toujours."""
    s = S(entree=2400.0, sl=2380.0, tp=2455.0)
    une = av.debat(s, av.Contexte(atr=12.0, base_fiable=True,
                                  regime_marche="haussier", n_combo=25))
    deux = av.debat(s, av.Contexte(atr=12.0, base_fiable=True,
                                   regime_marche="haussier",
                                   instrument_leader=True, n_combo=25))
    assert len(deux.pour) > len(une.pour), "le 2e argument doit bien exister"
    assert deux.score == pytest.approx(une.score), \
        "deux arguments de la même famille ont compté deux fois"


def test_chaque_argument_appartient_a_une_famille_connue():
    s = S(entree=6.50, sl=6.49, tp=6.53)
    ctx = av.Contexte(atr=0.035, spread=0.003, score_intermarche=-0.5,
                      base_intermarche=2.0, regime_marche="baissier",
                      news_dans_h=1.0, n_combo=40, esperance_combo=-0.4,
                      seuil_note_mesure=0.7)
    for a in av.plaider_contre(s, ctx) + av.plaider_pour(s, ctx):
        assert a.famille in av.FAMILLES, f"{a.code} : famille « {a.famille} »"


# --- aucun argument ne lit le résultat ------------------------------------
def test_aucun_argument_ne_lit_le_statut():
    """Un argument qui lirait le résultat produirait un débat parfait et
    inutilisable en direct."""
    s = S(statut="TP")
    a = [x.code for x in av.plaider_contre(s, ctx_propre())
         + av.plaider_pour(s, ctx_propre())]
    s.statut = "SL"
    b = [x.code for x in av.plaider_contre(s, ctx_propre())
         + av.plaider_pour(s, ctx_propre())]
    assert a == b, "le débat change selon le résultat — fuite du futur"


def test_chaque_argument_porte_un_chiffre():
    """« je le sens mal » n'est pas un argument."""
    s = S(entree=6.50, sl=6.49, tp=6.53)
    ctx = av.Contexte(atr=0.035, spread=0.003, score_intermarche=-0.5,
                      base_intermarche=2.0, n_combo=40, esperance_combo=-0.4)
    for a in av.plaider_contre(s, ctx):
        assert a.mesure.strip(), f"{a.code} plaide sans chiffre"


# --- calibration -----------------------------------------------------------
def _jeu_calibre(n=200):
    """`stop_dans_le_bruit` est vraiment mauvais ; `contre_le_regime` est
    posé à pile ou face et ne discrimine rien.

    Les deux groupes ont le MÊME R:R (2,0) : seule la fréquence de réussite
    diffère. Sinon on comparerait un +75R obtenu sur un stop minuscule à un
    +2R obtenu sur un stop honnête, et ce n'est pas la même monnaie.
    """
    import random
    rng = random.Random(7)
    out = []
    for i in range(n):
        serre = i % 2 == 0
        risque = 0.4 if serre else 10.0        # 0,08 ATR vs 2,0 ATR
        s = S(id=f"s{i}", entree=100.0, sl=100.0 - risque,
              tp=100.0 + 2 * risque)
        s.statut = "TP" if rng.random() < (0.05 if serre else 0.55) else "SL"
        ctx = av.Contexte(atr=5.0, base_fiable=True, n_combo=25,
                          regime_marche="baissier" if rng.random() < 0.5 else "neutre")
        out.append((s, ctx))
    return out


def test_un_argument_qui_discrimine_prend_du_poids():
    p = av.calibrer(_jeu_calibre())
    assert p["stop_dans_le_bruit"].verdict == "discriminant"
    assert p["stop_dans_le_bruit"].poids > 0.5


def test_un_argument_qui_ne_discrimine_rien_tombe_a_zero():
    """Il a l'air intelligent, il ne prédit rien : poids zéro."""
    p = av.calibrer(_jeu_calibre())
    assert p["contre_le_regime"].poids == av.POIDS_MIN
    assert p["contre_le_regime"].verdict in ("inutile", "à retourner")


def test_un_argument_peu_observe_garde_son_poids_par_defaut():
    """On ne recalibre pas un agent sur douze trades."""
    p = av.calibrer(_jeu_calibre(20))
    for x in p.values():
        assert x.verdict == "non mesuré" and x.poids == 1.0


def test_le_poids_mesure_change_le_debat():
    p = {k: v.poids for k, v in av.calibrer(_jeu_calibre()).items()}
    s = S(entree=100.0, sl=99.6, tp=130.0)
    ctx = av.Contexte(atr=5.0, base_fiable=True, n_combo=25)
    assert av.debat(s, ctx, p).score != av.debat(s, ctx).score


def test_un_gain_aberrant_ne_decide_pas_seul_du_poids():
    """Un signal au stop à 0,08 ATR affiche un R:R nominal de 75. S'il
    gagne une fois, sa moyenne écraserait 200 trades. On le borne."""
    paires = _jeu_calibre()
    monstre = S(id="monstre", entree=100.0, sl=99.6, tp=130.0, statut="TP")
    assert monstre.r_realise > 70
    p_avant = av.calibrer(paires)["stop_dans_le_bruit"].poids
    p_apres = av.calibrer(paires + [(monstre, av.Contexte(atr=5.0,
                                                          base_fiable=True,
                                                          n_combo=25))])
    assert abs(p_apres["stop_dans_le_bruit"].poids - p_avant) < 0.25


def test_calibrer_ignore_les_signaux_non_resolus():
    paires = [(S(id=f"s{i}", statut="en_attente"), ctx_propre()) for i in range(50)]
    assert av.calibrer(paires) == {}


def test_calibrer_ne_plante_pas_sans_donnees():
    assert av.calibrer([]) == {}
    assert isinstance(av.rapport_calibration({}), str)


def test_le_rapport_nomme_les_arguments_a_retourner():
    r = av.rapport_calibration(av.calibrer(_jeu_calibre()))
    assert "stop_dans_le_bruit" in r and "poids" in r
