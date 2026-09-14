"""Tests du rapport quotidien du Chef — sans reseau, disque isole.

Invariants proteges :
- generer() est pur et produit les sections attendues depuis le paquet
- quotidien() n'ecrit qu'UNE fois par jour (ni doublon, ni spam)
- un paquet minimal (systeme degrade) produit quand meme un rapport
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from gold_agent import rapport_chef as rc


PAQUET = {
    "prix": 4300.5,
    "consensus": {"pct_haussier": 42.0},
    "suspension": None,
    "grille": [{"tf": "H4", "couleur": "gris", "trades": 0, "r_cumule": 0.0,
                "walkforward": {"autorise": True}}],
    "constellation": {"sens_teste": "vente", "source_biais": "AG-02",
                      "score": {"score": -0.4, "base": 2.1, "fiable": True,
                                "bloque": False, "confirment": ["SI=F"],
                                "contredisent": []}},
    "calibration": {},
    "sante": {"problemes": []},
    "evenements": [{"t": "10:00", "agent": "Miroir", "texte": "blocage",
                    "niveau": "veto"}],
}


def test_generer_produit_les_sections():
    texte = rc.generer(PAQUET, signaux=[])
    for section in ("# Rapport du Chef", "## État", "## Signaux",
                    "## Grille de conviction", "## Miroir", "## Santé",
                    "## Événements marquants"):
        assert section in texte, f"section manquante : {section}"
    assert "ne passe aucun ordre" in texte


def test_paquet_minimal_ne_plante_pas():
    texte = rc.generer({}, signaux=[])
    assert "# Rapport du Chef" in texte and "## État" in texte


def test_quotidien_une_seule_fois_par_jour(tmp_path, monkeypatch):
    monkeypatch.setattr(rc, "DOSSIER", tmp_path)
    monkeypatch.setattr(rc, "_MEMO", {"jour": None})
    # pas de notification pendant les tests
    import gold_agent.notify as notify
    monkeypatch.setattr(notify, "pousser_telephone", lambda *a, **k: None)

    chemin = rc.quotidien(PAQUET)
    assert chemin and Path(chemin).exists(), "premier appel : rapport ecrit"
    assert rc.quotidien(PAQUET) is None, "second appel du jour : rien"
    # meme apres un redemarrage (memo vide), le fichier du jour suffit
    monkeypatch.setattr(rc, "_MEMO", {"jour": None})
    assert rc.quotidien(PAQUET) is None, "le fichier du jour existe deja"
    assert rc.dernier() and "# Rapport du Chef" in rc.dernier()
