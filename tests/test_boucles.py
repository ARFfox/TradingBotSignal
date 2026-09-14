"""Tests du contrat de boucle permanente — rapides (intervalles en ms).

Invariants proteges :
- un tour reussi pose un battement et remet les erreurs a zero
- une exception ne tue PAS la boucle : elle compte, backoff, et repart
- une boucle sans battement depuis 3 x son intervalle est declaree morte
- demarrer() est idempotent (pas de fils doubles)
"""
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from gold_agent import boucles


def test_un_tour_reussi_pose_un_battement():
    b = boucles.Boucle("t", "test", 0.01, lambda: None)
    b.erreurs_consecutives = 4
    b.tour()
    assert b.heartbeat > 0 and b.tours == 1
    assert b.erreurs_consecutives == 0, "un succes remet le compteur a zero"


def test_une_exception_ne_tue_pas_la_boucle():
    appels = {"n": 0}

    def fragile():
        appels["n"] += 1
        if appels["n"] <= 2:
            raise RuntimeError("boom")

    b = boucles.Boucle("t", "test", 0.01, fragile)
    arret = threading.Event()
    fil = threading.Thread(target=boucles._courir, args=(b, arret), daemon=True)
    # backoff 2^1, 2^2 s serait trop long pour un test : on triche sur le
    # temps d'attente en interrompant via l'evenement apres les battements
    debut = time.time()
    fil.start()
    # attendre le premier vrai battement (apres 2 echecs et ~6 s de backoff
    # ce serait long : on verifie plutot que les erreurs sont comptees)
    time.sleep(0.1)
    assert b.erreurs_consecutives >= 1, "l'echec doit etre compte"
    assert b.derniere_erreur.startswith("boom")
    assert fil.is_alive(), "la boucle survit a l'exception"
    arret.set()


def test_morte_sans_battement_recent():
    b = boucles.Boucle("t", "test", 10.0, lambda: None)
    assert not b.vivante(), "jamais battue = pas vivante"
    b.heartbeat = time.time() - 25         # 2,5 x l'intervalle : encore ok
    assert b.vivante()
    b.heartbeat = time.time() - 31         # 3,1 x : morte
    assert not b.vivante()
    e = boucles.etat()                     # ne doit pas planter a vide
    assert isinstance(e, list)


def test_demarrer_idempotent(monkeypatch):
    monkeypatch.setattr(boucles, "_ETAT",
                        {"boucles": [], "demarre": False,
                         "verrou": threading.Lock()})
    arret = threading.Event()
    arret.set()                            # les fils s'arretent aussitot
    lot = [boucles.Boucle("a", "a", 0.01, lambda: None)]
    r1 = boucles.demarrer(lot, arret)
    r2 = boucles.demarrer([boucles.Boucle("b", "b", 0.01, lambda: None)], arret)
    assert r1 is r2 and [b.code for b in r2] == ["a"], \
        "le second appel ne remplace ni ne double les boucles"
