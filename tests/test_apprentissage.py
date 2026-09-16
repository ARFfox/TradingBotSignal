"""CHANTIER étapes 1, 4, 5 — le circuit d'apprentissage de bout en bout :
journal → adaptateur → Superviseur apprenant → rapports. Sans réseau."""
import datetime as dt
import json

import pytest

from gold_agent import apprentissage, journal


def _entree(statut="gagnant", instrument="XAU/USD", tf="H1", sens="achat",
            entree=100.0, stop=98.0, objectif=104.0, rr=2.0, note=60,
            atr=2.0, avis=None, **extra):
    x = {"cle": f"{instrument}|{tf}|{sens}|{entree}", "instrument": instrument,
         "tf": tf, "sens": sens, "entree": entree, "stop": stop,
         "objectif": objectif, "rr_prevu": rr, "fiabilite": "?",
         "prix_a_l_emission": entree, "cree_le": "2026-09-16T00:00:00",
         "cree_ts": 1_750_000_000, "statut": statut, "resolu_le": None,
         "r_obtenu": None, "intermarche": None, "avis": avis or {},
         "decision_chef": note, "atr": atr, "spread": 0.05,
         "extreme_favorable": None, "tp_atteint_apres_sl": False,
         "r_realise": None, "emis": True}
    x.update(extra)
    return x


# ------------------------------------------------------------------ étape 1
def test_resolution_porte_les_champs_d_apprentissage(tmp_path, monkeypatch):
    """Un SL suivi de TP doit laisser tp_atteint_apres_sl=True,
    extreme_favorable et r_realise — la matière d'auditer_sl."""
    monkeypatch.setattr(journal, "FICHIER", tmp_path / "j.json")
    s = _entree(statut="en_attente")
    (tmp_path / "j.json").write_text(json.dumps([s]))
    t0 = s["cree_ts"]
    bars = [
        {"time": t0 + 60, "open": 100, "high": 100.5, "low": 99.5, "close": 100},
        {"time": t0 + 120, "open": 100, "high": 100.2, "low": 97.9, "close": 98},
        {"time": t0 + 180, "open": 98, "high": 104.5, "low": 98, "close": 104},
    ]
    assert journal.resoudre({"H1": bars}, instrument="XAU/USD") >= 1
    x = json.loads((tmp_path / "j.json").read_text())[0]
    assert x["statut"] == "perdant"          # SL d'abord, convention prudente
    assert x["tp_atteint_apres_sl"] is True  # stop trop serré, pas direction
    assert x["r_realise"] == -1.0
    assert x["extreme_favorable"] is not None


def test_audit_sl_tranche_sur_signal_adapte():
    """Critère de fin CHANTIER : auditer_sl renvoie autre chose
    qu'indéterminé sur un signal du journal adapté."""
    from superviseur_apprenant import auditer_sl
    x = _entree(statut="perdant", stop=99.0, atr=4.0,
                tp_atteint_apres_sl=True)
    sig = apprentissage.signaux([x])[0]
    assert auditer_sl(sig).cause == "stop_trop_serre"


# ------------------------------------------------------------- adaptateur
def test_adaptateur_traduit_statuts_et_avis():
    entrees = [
        _entree(statut="gagnant", avis={"AG-02": "achat", "AG-10": "vente"}),
        _entree(statut="perdant", instrument="BTC/USD", tf="M15"),
        _entree(statut="non_execute"),
        _entree(statut="ouvert"),
    ]
    sig = apprentissage.signaux(entrees)
    assert [s.statut for s in sig] == ["TP", "SL", "expire", "en_attente"]
    assert sig[0].agents == {"AG-02": "haussier", "AG-10": "baissier"}
    assert sig[0].note == 0.60 and sig[0].sl == 98.0 and sig[0].tp == 104.0
    assert sig[1].marche == "crypto"


def test_adaptateur_ignore_entree_corrompue():
    sig = apprentissage.signaux([_entree(), {"cle": "cassée"}])
    assert len(sig) == 1


# ------------------------------------------------------------- équilibre
def test_equilibre_est_100_sur_1_plus_gain():
    entrees = [_entree(statut="gagnant", rr=2.0),
               _entree(statut="perdant", rr=2.0),
               _entree(statut="perdant", rr=2.0)]
    eq = apprentissage.equilibre(entrees)
    assert eq["gain_moyen"] == 2.0
    assert eq["equilibre_pct"] == 33.3      # 100/(1+2)
    assert eq["taux_pct"] == 33.3
    assert apprentissage.equilibre([]) is None


# ------------------------------------------------------------- rapports
def test_rapports_ecrits_puis_cadence_respectee(tmp_path, monkeypatch):
    monkeypatch.setattr(journal, "FICHIER", tmp_path / "j.json")
    monkeypatch.setattr(apprentissage, "RAPPORT_SUPERVISEUR",
                        tmp_path / "rapport_superviseur.md")
    monkeypatch.setattr(apprentissage, "RAPPORT_SOUS_ENSEMBLES",
                        tmp_path / "rapport_sous_ensembles.md")
    monkeypatch.setattr(apprentissage, "ETAT", tmp_path / "etat.json")
    entrees = [_entree(statut="gagnant" if i % 4 == 0 else "perdant",
                       tf=["H1", "M30", "M15"][i % 3],
                       entree=100.0 + i)
               for i in range(30)]
    (tmp_path / "j.json").write_text(json.dumps(entrees))

    ecrits = apprentissage.rapports_si_du()
    assert len(ecrits) == 2
    texte = (tmp_path / "rapport_superviseur.md").read_text()
    assert "30 résolus" in texte
    # le même jour, sans 20 nouveaux résolus : rien n'est dû
    assert apprentissage.rapports_si_du() == []
    # force=True passe outre la cadence
    assert len(apprentissage.rapports_si_du(force=True)) == 2
