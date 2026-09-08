"""Tests des agents de marche et de la matrice intermarches.

Aucun reseau. Le jeu synthetique INJECTE des proprietes connues (une avance
de 2 jours du crypto sur les actions, un forex disperse, un crypto en bloc)
et les tests verifient que le module les retrouve — et surtout qu'il
n'en invente pas d'autres.
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


am = _charger("agents_marches")

AVANCE_INJECTEE = 2      # jours d'avance du crypto sur les actions


def jeu(n: int = 600) -> pd.DataFrame:
    rng = np.random.default_rng(9)
    idx = pd.date_range("2024-01-01", periods=n, freq="D")
    dollar = rng.normal(0, .004, n)
    risque = rng.normal(.0005, .009, n)
    metal = rng.normal(.0006, .008, n)
    crypto_f = rng.normal(.001, .020, n)
    mk = lambda x: 100 * np.exp(np.cumsum(x))

    d = {}
    for t in am.MARCHES["forex"]["tickers"]:
        s = -1 if (t.startswith("USD") or t == "DX-Y.NYB") else 1
        d[t] = mk(-s * dollar * 1.2 + rng.normal(0, .004, n))
    for t in am.MARCHES["crypto"]["tickers"]:
        d[t] = mk(crypto_f * rng.uniform(.8, 1.3) + rng.normal(0, .012, n))
    for t in am.MARCHES["matieres"]["tickers"]:
        d[t] = mk(metal * rng.uniform(.6, 1.4) - dollar * .8 + rng.normal(0, .009, n))
    for t in am.MARCHES["actions"]["tickers"]:
        lag = np.roll(crypto_f, AVANCE_INJECTEE)
        lag[:AVANCE_INJECTEE] = 0
        d[t] = mk(risque * rng.uniform(.8, 1.2) + .35 * lag + rng.normal(0, .008, n))

    p = pd.DataFrame(d, index=idx)
    # tout sauf le crypto ferme le week-end
    p.loc[p.index.dayofweek >= 5,
          [c for c in p.columns if not c.endswith("-USD")]] = np.nan
    return p


@pytest.fixture
def m():
    return am.MatriceMarches(jeu())


# --- agents de marche -----------------------------------------------------
def test_les_quatre_marches_existent(m):
    assert set(m.agents) == {"forex", "crypto", "matieres", "actions"}


def test_chaque_marche_produit_un_etat_fiable(m):
    for cle, a in m.agents.items():
        assert a.etat().fiable, f"{cle} : {a.etat().note}"


def test_marche_inconnu_rejete():
    with pytest.raises(ValueError):
        am.AgentMarche("obligations", jeu())


def test_marche_sans_donnees_reste_non_fiable():
    vide = pd.DataFrame({"XXX": [1.0] * 300},
                        index=pd.date_range("2024-01-01", periods=300))
    e = am.AgentMarche("crypto", vide).etat()
    assert not e.fiable and e.regime == "indéterminé"


def test_largeur_et_cohesion_bornees(m):
    for a in m.agents.values():
        e = a.etat()
        assert 0.0 <= e.largeur <= 1.0
        assert -1.0 <= e.cohesion <= 1.0


def test_un_marche_a_un_facteur_est_detecte_en_bloc(m):
    """Le crypto synthetique partage un facteur commun fort : il doit
    ressortir cohesif, donc 'en bloc' ou 'groupe'."""
    e = m.agents["crypto"].etat()
    assert e.cohesion > 0.4, f"cohésion crypto trop faible : {e.cohesion}"
    assert "bloc" in e.regime or "groupé" in e.regime


def test_le_forex_synthetique_est_disperse(m):
    """Les paires sont construites en sens opposes autour du dollar :
    le marche ne bouge pas en bloc."""
    assert m.agents["forex"].etat().cohesion < 0.35


def test_leader_et_retardataire_sont_differents(m):
    for a in m.agents.values():
        e = a.etat()
        assert e.leader != e.retardataire


def test_les_carreaux_sont_tries_par_performance(m):
    for a in m.agents.values():
        v = [c.variation_pct for c in a.etat().carreaux]
        assert v == sorted(v, reverse=True)


def test_force_relative_centree_sur_la_mediane(m):
    """Par construction, autant de membres au-dessus qu'en dessous."""
    for a in m.agents.values():
        f = [c.force_relative for c in a.etat().carreaux]
        assert min(f) <= 0 <= max(f)


def test_le_leader_a_la_meilleure_performance(m):
    for a in m.agents.values():
        e = a.etat()
        assert e.carreaux[0].ticker == e.leader
        assert e.carreaux[0].role == "leader"


# --- matrice intermarches -------------------------------------------------
def test_correlations_symetriques_et_diagonale_a_un(m):
    c = m.correlations()
    assert not c.empty
    assert np.allclose(np.diag(c.values), 1.0)
    assert np.allclose(c.values, c.values.T, equal_nan=True)


def test_avance_injectee_est_retrouvee(m):
    """Le crypto a 2 jours d'avance sur les actions par construction."""
    d = next(x for x in m.avance_retard()
             if {x["a"], x["b"]} == {"crypto", "actions"})
    assert d["meneur"] == "crypto", f"meneur trouve : {d['meneur']}"
    assert d["jours"] == AVANCE_INJECTEE, f"avance trouvee : {d['jours']} j"


def test_aucune_avance_inventee_ailleurs(m):
    """LE test qui compte. On teste 11 decalages par paire : sans
    correction du test multiple, un maximum apparait par hasard dans
    ~43 % des cas et le module annonce des avances inexistantes.
    Une seule avance est injectee — il ne doit en trouver qu'une."""
    menes = [d for d in m.avance_retard() if d["meneur"] != "—"]
    assert len(menes) == 1, f"avances annoncees : {[d['verdict'] for d in menes]}"


def test_toute_avance_annoncee_depasse_le_seuil(m):
    for d in m.avance_retard():
        if d["meneur"] != "—":
            assert abs(d["corr_max"]) >= d["seuil"]


def test_avance_bornee_par_les_lags_testes(m):
    for d in m.avance_retard():
        assert 0 <= d["jours"] <= max(am.LAGS)


# --- graphe ---------------------------------------------------------------
def test_graphe_a_quatre_noeuds(m):
    assert len(m.graphe()["noeuds"]) == 4


def test_le_graphe_ne_relie_pas_tout_a_tout(m):
    """Un graphe ou chaque noeud est relie a tous les autres ne montre
    rien. Le seuil doit filtrer."""
    g = m.graphe(seuil=0.20)
    assert len(g["liens"]) < 6, "aucun lien filtre : le seuil ne sert a rien"


def test_seuil_haut_donne_moins_de_liens(m):
    assert len(m.graphe(seuil=0.80)["liens"]) <= len(m.graphe(seuil=0.10)["liens"])


def test_liens_sans_boucle_ni_doublon(m):
    liens = m.graphe(seuil=0.0)["liens"]
    vus = set()
    for l in liens:
        assert l["de"] != l["vers"], "un marché relié à lui-même"
        cle = frozenset((l["de"], l["vers"]))
        assert cle not in vus, f"lien en double : {cle}"
        vus.add(cle)


# --- format des cartes ----------------------------------------------------
def test_cartes_au_format_du_panneau(m):
    champs = {"code", "nom", "role", "coul", "statut", "activites",
              "conviction", "metriques"}
    for cle, a in m.agents.items():
        c = a.carte_agent(am.CODES[cle])
        assert champs <= set(c), f"champs manquants : {champs - set(c)}"
        assert 0 <= c["conviction"] <= 100
        assert c["activites"]
    c = m.carte_agent()
    assert champs <= set(c) and 0 <= c["conviction"] <= 100


def test_tuiles_completes(m):
    t = m.tuiles()
    assert len(t) == 4
    for x in t:
        assert {"cle", "nom", "variation_pct", "largeur", "regime"} <= set(x)
