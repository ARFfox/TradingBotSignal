"""APPLIQUER 8.2-8.4 (revue du 16/09 soir) — la fiche instrument : contrat
JSON à la lettre, texte du taux jamais réinventé, HTML honnête. Sans réseau."""
import json

import pytest

from gold_agent import fiche_instrument, journal


def _journal(tmp_path, monkeypatch, n_btc=25, n_or=3):
    entrees = []
    for i in range(n_btc):
        entrees.append({
            "cle": f"BTC/USD|M15|achat|{70000 + i}", "instrument": "BTC/USD",
            "tf": "M15", "sens": "achat", "entree": 70000.0 + i,
            "stop": 69500.0 + i, "objectif": 71000.0 + i, "rr_prevu": 2.0,
            "statut": "gagnant" if i % 5 == 0 else "perdant",
            "cree_ts": 1_750_000_000 + i * 900, "decision_chef": 40,
            "atr": 500.0, "avis": {}, "r_realise": 2.0 if i % 5 == 0 else -1.0,
            "r_obtenu": None, "extreme_favorable": None,
            "tp_atteint_apres_sl": False})
    for i in range(n_or):
        entrees.append({
            "cle": f"XAU/USD|H1|vente|{4300 + i}", "instrument": "XAU/USD",
            "tf": "H1", "sens": "vente", "entree": 4300.0 + i,
            "stop": 4310.0 + i, "objectif": 4280.0 + i, "rr_prevu": 2.0,
            "statut": "perdant", "cree_ts": 1_750_100_000 + i * 900,
            "decision_chef": 60, "atr": 10.0, "avis": {}, "r_realise": -1.0,
            "r_obtenu": None, "extreme_favorable": None,
            "tp_atteint_apres_sl": False})
    monkeypatch.setattr(journal, "FICHIER", tmp_path / "j.json")
    (tmp_path / "j.json").write_text(json.dumps(entrees))
    monkeypatch.setattr(fiche_instrument, "_actifs",
                        lambda: [{"instrument": "BTC/USD", "tf": "H4",
                                  "marche": "crypto"}])


def test_json_respecte_le_contrat(tmp_path, monkeypatch):
    _journal(tmp_path, monkeypatch)
    d = fiche_instrument.json_fiche("BTCUSD")
    assert d["instrument"] == "BTC/USD" and d["marche"] == "crypto"
    assert d["badge"] == 1 and d["tf_signal"] == ["H4"]
    assert d["global"]["n"] == 25 and d["global"]["taux"] is not None
    tf = {t["tf"]: t for t in d["timeframes"]}
    assert set(tf) == {"H4", "H1", "M30", "M15", "M5"}   # les 5, toujours
    assert tf["H4"]["signal"] is True
    assert tf["M15"]["n"] == 25
    # l'historique est DEJA filtre : aucun signal or dedans
    assert all("XAU" not in str(h) for h in d["historique"])


def test_sous_20_resolus_texte_insuffisant(tmp_path, monkeypatch):
    """Règle 3 : « échantillon insuffisant (3/20) » A LA PLACE du taux."""
    _journal(tmp_path, monkeypatch)
    d = fiche_instrument.json_fiche("XAUUSD")
    assert d["global"]["taux"] is None
    assert "insuffisant (3/20)" in d["global"]["texte"]
    assert "insuffisant (3/20)" in d["html_haut"]
    # le texte REMPLACE le pourcentage : aucune jauge, aucun % avant lui
    assert "dansbarre" not in d["html_haut"]
    assert "%" not in d["global"]["texte"].split("insuffisant")[0]


def test_html_montre_verdicts_et_filtre(tmp_path, monkeypatch):
    _journal(tmp_path, monkeypatch)
    d = fiche_instrument.json_fiche("BTCUSD")
    haut, bas = d["html_haut"], d["html_bas"]
    # 8.3 : les 6 boutons pleine largeur, verdict + effectif dessus
    for tf in ("TOUS", "H4", "H1", "M30", "M15", "M5"):
        assert f'data-tf="{tf}"' in haut
    assert "n=25" in haut and 'class="pastille"' in haut     # signal H4 visible
    # M15 : 5 TP / 25 a RR 2 -> R moyen -0.4 : coupé, atténué mais cliquable
    assert "coupé" in haut and 'class="tfx coupe"' in haut
    # la jauge oppose taux et équilibre, l'écart est écrit
    assert "équilibre" in haut and "dansbarre" in haut
    # 8.4 : tables avec signes, icône+mot, cause du SL, data-tf/data-etat
    assert "✗ non validé (SL)" in bas and "✓ validé (TP)" in bas
    assert 'data-tf="M15" data-etat="SL"' in bas
    assert "−1.00" in bas and "+2.00" in bas                 # le signe, toujours
    assert "Historique complet" in bas and "Risque événementiel" in bas


def test_sous_le_hasard_annonce(tmp_path, monkeypatch):
    """20 % de réussite à RR 2 (hasard 33 %) : la fiche le dit en face."""
    _journal(tmp_path, monkeypatch)
    d = fiche_instrument.json_fiche("BTCUSD")
    assert d["sous_hasard"] is True
    assert "pièce lancée" in d["html_haut"]
