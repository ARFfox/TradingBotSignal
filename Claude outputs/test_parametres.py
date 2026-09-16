"""Tests du réglage automatique des paramètres.

Deux comportements comptent, et ils sont symétriques :
  · REJETER un gain qui n'est que du hasard (le cas fréquent)
  · ACCEPTER un gain réel et reproductible (sinon le module est inutile)

Un module qui refuse tout est aussi cassé qu'un module qui accepte tout.
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
pa = _charger("parametres_agents")


def base(n=400):
    out = []
    for i in range(n):
        out.append(sa.Signal(
            id=f"s{i}", instrument="XAUUSD", marche="matieres", tf="H1",
            sens="achat", entree=100.0, sl=90.0, tp=120.0, note=0.5,
            cree_ts=1_750_000_000 + i * 3600, statut="en_attente", atr=10.0))
    return out


def _copie(s, statut, rr=2.0):
    c = sa.Signal(id=s.id, instrument=s.instrument, marche=s.marche, tf=s.tf,
                  sens=s.sens, entree=100.0, sl=90.0, tp=100.0 + rr * 10.0,
                  note=s.note, cree_ts=s.cree_ts, statut=statut, atr=10.0)
    return c


def rejoueur_vrai_gain(signaux, valeur):
    """Un paramètre qui améliore VRAIMENT : la probabilité de TP monte
    franchement avec la valeur, de façon stable dans le temps."""
    out = []
    for s in signaux:
        p = min(0.75, 0.20 + 0.20 * valeur)
        r = random.Random(hash((s.id, round(valeur, 3))) & 0xFFFFFF).random()
        out.append(_copie(s, "TP" if r < p else "SL"))
    return out


def rejoueur_bruit(signaux, valeur):
    """Aucun lien entre le paramètre et le résultat — que du hasard.
    Une recherche naïve trouvera quand même un 'meilleur' réglage."""
    out = []
    for s in signaux:
        r = random.Random(hash((s.id, round(valeur, 3))) & 0xFFFFFF).random()
        out.append(_copie(s, "TP" if r < 0.33 else "SL"))
    return out


P = lambda: pa.Parametre("AG-03", "stop_atr", 1.0, 1.0, 3.0, 0.25, "ATR")


# --- le cœur du module ----------------------------------------------------
def test_un_vrai_gain_est_accepte():
    r = pa.evaluer_parametre(base(), P(), rejoueur_vrai_gain)
    assert r.accepte, f"un gain réel a été rejeté : {r.motif}"
    assert r.proposee > r.ancienne
    assert r.gain_hors_echantillon > pa.MARGE_BRUIT


def test_le_bruit_est_rejete():
    """LE test qui compte. Sur 400 signaux et 9 valeurs testées, une
    recherche naïve trouve toujours un gagnant. Le module ne doit pas."""
    r = pa.evaluer_parametre(base(), P(), rejoueur_bruit)
    assert not r.accepte, (
        f"du bruit pur a été accepté ({r.gain_hors_echantillon:+.3f}R) — "
        f"c'est exactement le sur-apprentissage qu'on veut éviter")


def test_historique_trop_court_refuse_de_conclure():
    r = pa.evaluer_parametre(base(30), P(), rejoueur_vrai_gain)
    assert not r.accepte and "honnête" in r.motif


# --- découpes -------------------------------------------------------------
def test_les_decoupes_sont_chronologiques():
    """Apprendre sur le futur pour juger le passé donne des résultats
    magnifiques et totalement faux."""
    for train, test in pa.decouper(base()):
        assert max(s.cree_ts for s in train) <= min(s.cree_ts for s in test)


def test_les_decoupes_ne_se_chevauchent_pas():
    for train, test in pa.decouper(base()):
        assert not ({s.id for s in train} & {s.id for s in test})


def test_chaque_decoupe_a_un_test_suffisant():
    for _, test in pa.decouper(base()):
        assert len(test) >= pa.N_MIN_TEST


# --- bornes ---------------------------------------------------------------
def test_les_bornes_ne_sont_jamais_franchies():
    p = P()
    assert p.borner(99.0) == p.maxi
    assert p.borner(-5.0) == p.mini


def test_la_valeur_proposee_reste_dans_les_bornes():
    p = P()
    r = pa.evaluer_parametre(base(), p, rejoueur_vrai_gain)
    assert p.mini <= r.proposee <= p.maxi


def test_les_candidats_couvrent_les_bornes():
    c = P().candidats()
    assert c[0] == 1.0 and c[-1] == 3.0


def test_appliquer_n_ecrit_que_les_acceptes():
    p = P()
    refuse = pa.Resultat("stop_atr", "AG-03", 1.0, 2.5, 0.01, 1, 4, 100,
                         False, "bruit")
    pa.Tuner(journal=None).appliquer([p], [refuse])
    assert p.valeur == 1.0, "un résultat refusé a modifié le paramètre"


def test_appliquer_reborne_meme_une_proposition_hors_bornes():
    p = P()
    tricheur = pa.Resultat("stop_atr", "AG-03", 1.0, 99.0, 1.0, 4, 4, 100,
                           True, "confirmé")
    pa.Tuner(journal=None).appliquer([p], [tricheur])
    assert p.valeur == p.maxi, "les bornes doivent tenir même sur un accepté"


# --- passe complète -------------------------------------------------------
def test_un_agent_sans_rejoueur_est_signale():
    r = pa.Tuner(journal=None).passe(base(), [P()], {})
    assert not r[0].accepte and "rejoueur" in r[0].motif


def test_un_parametre_a_la_fois():
    """Optimiser deux réglages ensemble multiplie les faux positifs et
    rend impossible de savoir lequel a apporté le gain."""
    params = [P(), pa.Parametre("AG-03", "rr_minimum", 1.5, 1.2, 3.0, 0.1)]
    r = pa.Tuner(journal=None).passe(base(), params,
                                     {"AG-03": rejoueur_vrai_gain})
    assert len(r) == 2
    assert {x.parametre for x in r} == {"stop_atr", "rr_minimum"}


def test_le_rapport_ne_plante_pas_sans_resultat():
    assert isinstance(pa.rapport([]), str)


# --- garde-fous déclarés --------------------------------------------------
def test_les_bornes_par_defaut_protegent_le_stop():
    """Le stop minimum reste à 1 ATR quoi que suggère l'historique."""
    p = next(x for x in pa.PARAMETRES_DEFAUT if x.nom == "stop_atr")
    assert p.mini >= 1.0 and p.raison_bornes


def test_chaque_parametre_par_defaut_est_coherent():
    for p in pa.PARAMETRES_DEFAUT:
        assert p.mini < p.maxi
        assert p.mini <= p.valeur <= p.maxi, f"{p.nom} hors de ses bornes"
        assert p.pas > 0 and len(p.candidats()) >= 3
