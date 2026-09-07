"""Tests du moteur de constellations. Aucun reseau : donnees synthetiques.

    pip3 install pytest && python3 -m pytest tests/ -q

Chaque test verifie un INVARIANT METIER, pas une valeur numerique precise :
un test qui verrouille "corr == 0.82" casse au premier changement de donnees
et ne prouve rien. Un test qui verrouille "un satellite construit comme tel
est classe satellite" attrape les vraies regressions.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

RACINE = Path(__file__).resolve().parent.parent


def _charger(nom: str):
    spec = importlib.util.spec_from_file_location(nom, RACINE / f"{nom}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[nom] = mod
    spec.loader.exec_module(mod)
    return mod


ca = _charger("constellation_agent")


# --------------------------------------------------------------------------
def jeu(n: int = 800, avec_weekend: bool = True) -> pd.DataFrame:
    """Univers synthetique : 1 pivot, 2 satellites correles ENTRE EUX,
    1 miroir PARTIEL, 1 actif independant. Le pivot ne cote pas le week-end.

    Le miroir porte volontairement une grosse composante propre (corr ~ -0,60
    avec le pivot). Un miroir PARFAIT (-1,0 x pivot, sans bruit) serait, du
    point de vue de l'information, le meme actif que les satellites au signe
    pres : le clustering le fusionnerait avec eux — et il aurait raison. Un
    univers a un seul facteur ne permet donc pas de tester le vote a
    plusieurs voix. C'est ce qu'ont revele les deux tests en echec.
    """
    rng = np.random.default_rng(42)
    idx = pd.date_range("2023-01-01", periods=n, freq="D")
    g = rng.normal(0, .010, n)          # facteur pivot
    m = rng.normal(0, .005, n)          # facteur commun aux 2 satellites
    mk = lambda x: 100 * np.exp(np.cumsum(x))
    d = pd.DataFrame({
        "PIVOT": mk(g),
        "SAT_A": mk(1.6 * g + 1.2 * m + rng.normal(0, .004, n)),
        "SAT_B": mk(1.4 * g + 1.1 * m + rng.normal(0, .004, n)),
        "MIROIR": mk(-0.9 * g + rng.normal(0, .012, n)),
        "INDEP": mk(rng.normal(0, .012, n)),
    }, index=idx)
    if avec_weekend:
        # tout sauf INDEP ferme le week-end : reproduit le piege du calendrier
        d.loc[d.index.dayofweek >= 5, ["PIVOT", "SAT_A", "SAT_B", "MIROIR"]] = np.nan
    return d


@pytest.fixture
def ag():
    return ca.Constellation(jeu(), cache=None)


# --- calendrier -----------------------------------------------------------
def test_le_pivot_survit_au_calendrier_mixte():
    """Regression : avec des actifs 7j/7 et 5j/7 melanges, le pivot se
    faisait eliminer de son propre calcul (57 % de rendements valides)."""
    a = ca.Constellation(jeu(avec_weekend=True), cache=None)
    assert a.membres("PIVOT"), "le pivot a ete elimine par le filtre de couverture"


def test_calendrier_aligne_sur_les_jours_du_pivot():
    a = ca.Constellation(jeu(), cache=None)
    r = a._rendements("PIVOT")
    assert (r.index.dayofweek < 5).all(), "des jours de week-end subsistent"


# --- classification -------------------------------------------------------
def test_satellite_et_miroir_sont_bien_classes(ag):
    g = {m.ticker: m.groupe for m in ag.membres("PIVOT")}
    assert g["SAT_A"] == "satellite"
    assert g["SAT_B"] == "satellite"
    assert g["MIROIR"] == "miroir"
    assert g["INDEP"] == "decouple"


def test_poids_est_continu_et_borne(ag):
    for m in ag.membres("PIVOT"):
        assert 0.0 <= m.poids <= 1.0, f"{m.ticker} poids hors bornes : {m.poids}"


def test_membres_tries_par_poids_decroissant(ag):
    p = [m.poids for m in ag.membres("PIVOT")]
    assert p == sorted(p, reverse=True)


# --- redondance -----------------------------------------------------------
def test_les_satellites_correles_forment_un_seul_cluster(ag):
    """SAT_A et SAT_B partagent un facteur commun : ils portent la MEME
    information et ne doivent pas voter deux fois."""
    cl = ag.clusters("PIVOT")
    ensemble = next((c for c in cl if "SAT_A" in c), [])
    assert "SAT_B" in ensemble, f"SAT_A et SAT_B separes : {cl}"


def test_la_base_ne_double_pas_avec_des_membres_redondants(ag):
    mi = ca.Miroir(ag)
    s_un = mi.evaluer("PIVOT", "achat", {"SAT_A": "haussier"})
    s_deux = mi.evaluer("PIVOT", "achat", {"SAT_A": "haussier", "SAT_B": "haussier"})
    assert s_deux.base <= s_un.base * 1.10, (
        f"la base a gonfle ({s_un.base} -> {s_deux.base}) alors que le second "
        f"membre porte la meme information")


# --- decision -------------------------------------------------------------
def test_confirmation_totale_augmente_la_confiance(ag):
    mi = ca.Miroir(ag)
    c, s = mi.appliquer("PIVOT", "achat", 0.60,
                        {"SAT_A": "haussier", "SAT_B": "haussier", "MIROIR": "baissier"})
    assert c > 0.60 and s.score > 0


def test_contradiction_totale_bloque(ag):
    mi = ca.Miroir(ag)
    c, s = mi.appliquer("PIVOT", "achat", 0.70,
                        {"SAT_A": "baissier", "SAT_B": "baissier", "MIROIR": "haussier"})
    assert s.bloque and c == 0.0


def test_une_base_mince_ne_peut_pas_rassurer(ag):
    """Asymetrie voulue : peu d'information peut faire douter, jamais
    augmenter la confiance."""
    mi = ca.Miroir(ag)
    c, s = mi.appliquer("PIVOT", "achat", 0.60, {"SAT_A": "haussier"})
    assert not s.fiable
    assert c <= 0.60, f"une base de {s.base} a fait monter la confiance a {c}"


def test_une_base_mince_peut_faire_douter(ag):
    mi = ca.Miroir(ag)
    c, _ = mi.appliquer("PIVOT", "achat", 0.60, {"SAT_A": "baissier"})
    assert c < 0.60


def test_aucun_biais_laisse_la_confiance_intacte(ag):
    mi = ca.Miroir(ag)
    c, s = mi.appliquer("PIVOT", "achat", 0.66, {})
    assert c == 0.66 and s.base == 0.0


def test_un_miroir_parfait_fusionne_avec_les_satellites():
    """Propriete voulue, pas un bug : deux series parfaitement
    anti-correlees portent EXACTEMENT la meme information. Les fusionner
    en un cluster est correct — le sens attendu de chacun est gere par
    sens_attendu, pas par le clustering."""
    rng = np.random.default_rng(3)
    n = 700
    idx = pd.date_range("2023-01-01", periods=n, freq="D")
    g = rng.normal(0, .010, n)
    mk = lambda x: 100 * np.exp(np.cumsum(x))
    d = pd.DataFrame({
        "PIVOT": mk(g),
        "SAT": mk(1.5 * g + rng.normal(0, .002, n)),
        "MIR": mk(-1.5 * g + rng.normal(0, .002, n)),
    }, index=idx)
    a = ca.Constellation(d, cache=None)
    cl = a.clusters("PIVOT")
    assert len(cl) == 1, f"un facteur unique devrait donner un seul cluster : {cl}"


def test_les_decouples_ne_votent_jamais(ag):
    mi = ca.Miroir(ag)
    s = mi.evaluer("PIVOT", "achat", {"INDEP": "baissier"})
    assert s.base == 0.0, "un actif decouple a vote"


def test_vente_est_le_miroir_de_achat(ag):
    mi = ca.Miroir(ag)
    b = {"SAT_A": "haussier", "SAT_B": "haussier", "MIROIR": "baissier"}
    a = mi.evaluer("PIVOT", "achat", b)
    v = mi.evaluer("PIVOT", "vente", b)
    assert a.score == pytest.approx(-v.score, abs=1e-9)


def test_score_toujours_borne(ag):
    mi = ca.Miroir(ag)
    for b in ({"SAT_A": "haussier", "MIROIR": "haussier"},
              {"SAT_A": "baissier", "SAT_B": "haussier", "MIROIR": "baissier"},
              {}):
        s = mi.evaluer("PIVOT", "achat", b)
        assert -1.0 <= s.score <= 1.0


def test_sens_invalide_rejete(ag):
    with pytest.raises(ValueError):
        ca.Miroir(ag).evaluer("PIVOT", "acheter", {})


# --- robustesse -----------------------------------------------------------
def test_pivot_absent_leve_une_erreur_claire(ag):
    with pytest.raises(KeyError):
        ag.membres("INEXISTANT")


def test_historique_trop_court_est_refuse():
    a = ca.Constellation(jeu(n=40), cache=None)
    with pytest.raises(ValueError):
        a.membres("PIVOT")


def test_biais_provisoire_produit_des_neutres():
    """Un biais qui ne renvoie jamais 'neutre' n'a aucun pouvoir
    discriminant — c'est le bug qui donnait 16 confirmations sur 16."""
    rng = np.random.default_rng(1)
    idx = pd.date_range("2024-01-01", periods=400, freq="D")
    d = pd.DataFrame({f"A{i}": 100 * np.exp(np.cumsum(rng.normal(0, .01, 400)))
                      for i in range(12)}, index=idx)
    b = ca.biais_provisoire(d)
    assert set(b.values()) <= {"haussier", "baissier", "neutre"}
    assert len(set(b.values())) > 1, "le biais classe tout pareil"
