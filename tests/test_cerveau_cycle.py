"""Étape 10 — le cycle du cerveau : cinq calibrations fusionnées dans
cerveau.json, source unique des poids, réversible (sans réseau)."""
import json

from gold_agent import journal
from taches import cerveau_cycle


def _entree(i, statut="perdant", avec_traces=True):
    x = {"cle": f"BTC/USD|M15|achat|{70000 + i}", "instrument": "BTC/USD",
         "tf": "M15", "sens": "achat", "entree": 70000.0 + i,
         "stop": 69500.0 + i, "objectif": 71000.0 + i, "rr_prevu": 2.0,
         "statut": statut, "cree_ts": 1_750_000_000 + i * 900,
         "decision_chef": 40, "atr": 500.0,
         "avis": {"AG-02": "achat", "AG-10": "vente"},
         "r_realise": 2.0 if statut == "gagnant" else -1.0, "r_obtenu": None,
         "extreme_favorable": 70100.0, "tp_atteint_apres_sl": False}
    if avec_traces:
        x["figures"] = ["triangle_ascendant"]
        x["direction"] = {"sens": "haussier", "sources": [
            {"code": "structure_ema", "sens": "haussier"},
            {"code": "rsi", "sens": "haussier"}]}
        x["debat"] = {"verdict": "NEUTRE", "ctx": {"atr": 500.0, "spread": 5.0}}
    return x


def test_cycle_complet_fusionne_et_persiste(tmp_path, monkeypatch):
    monkeypatch.setattr(journal, "FICHIER", tmp_path / "j.json")
    monkeypatch.setattr(cerveau_cycle, "CERVEAU_JSON", tmp_path / "cerveau.json")
    monkeypatch.setattr(cerveau_cycle, "RAPPORT", tmp_path / "rapport.md")
    cerveau_cycle._CACHE_AUDITS.update({"t": 0.0, "audits": {}, "live": None})
    entrees = [_entree(i, "gagnant" if i % 4 == 0 else "perdant")
               for i in range(40)]
    (tmp_path / "j.json").write_text(json.dumps(entrees))

    motif = cerveau_cycle.cycle_complet()
    etat = json.loads((tmp_path / "cerveau.json").read_text())
    assert etat["version"] == 1
    assert "source" in etat["poids"] and "figure" in etat["poids"]
    # les sources tracées ont été calibrées (poids présents, même à zéro)
    assert "structure_ema" in etat["poids"]["source"]
    assert "triangle_ascendant" in etat["poids"]["figure"]
    assert (tmp_path / "rapport.md").exists()
    assert "poids" in motif or "résolus" in motif

    # second tour immédiat : rien de nouveau -> rien ne bouge (la règle)
    motif2 = cerveau_cycle.cycle_complet()
    etat2 = json.loads((tmp_path / "cerveau.json").read_text())
    assert etat2["version"] == etat["version"]
    assert "nouveau" in motif2


def test_etat_live_honnete(tmp_path, monkeypatch):
    monkeypatch.setattr(journal, "FICHIER", tmp_path / "j.json")
    monkeypatch.setattr(cerveau_cycle, "CERVEAU_JSON", tmp_path / "cerveau.json")
    monkeypatch.setattr(cerveau_cycle, "RAPPORT", tmp_path / "rapport.md")
    cerveau_cycle._CACHE_AUDITS.update({"t": 0.0, "audits": {}, "live": None,
                                        "t_live": 0.0})
    (tmp_path / "j.json").write_text(json.dumps(
        [_entree(i) for i in range(25)]))
    # avant tout cycle : jamais entraîné
    live = cerveau_cycle.etat_pour_le_site()
    assert live["statut"] in ("jamais entraîné", "bridé")
    cerveau_cycle.cycle_complet()
    cerveau_cycle._CACHE_AUDITS["live"] = None
    live2 = cerveau_cycle.etat_pour_le_site()
    assert live2["version"] == 1
    assert live2["statut"] in ("vient d'apprendre", "bridé", "en attente")
