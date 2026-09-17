"""Étape 6bis — le pont AG-19 : la direction s'attache au setup, avec
« INDÉTERMINÉE » comme vraie réponse (sans réseau)."""
from gold_agent import directeur


def _r(**extra):
    r = {"prix": 100.0, "ema_slow": 97.0, "rsi": 62.0,
         "figures_biais": {"sens": "haussier", "score": 0.4, "n_figures": 2,
                           "attendu_sur_bruit": 0.5}}
    r.update(extra)
    return r


def _st():
    return {"setup": "achat", "entree": 100.0, "stop": 98.0,
            "objectif": 104.0, "intermarche": {"score": 0.5, "fiable": True}}


def test_direction_attachee_avec_sources(monkeypatch):
    monkeypatch.setattr(directeur, "_memoire_couple",
                        lambda i, t: ("haussier", 0.3, 25))
    monkeypatch.setattr(directeur, "_regime_marche",
                        lambda m: {"regime": "haussier", "largeur": 0.7,
                                   "nom": m})
    st = _st()
    directeur.analyser(st, _r(), instrument="XAU/USD", tf="H1")
    d = st["direction"]
    assert d["sens"] == "haussier" and d["certitude"] > 0
    assert d["bascule"]                      # le point de bascule est nommé
    assert any(c in d["texte"] for c in ("EMA", "%"))   # des chiffres, pas du vent
    codes = [s["code"] for s in d["sources"]]
    assert "structure_ema" in codes and "figures" in codes


def test_indeterminee_est_une_reponse(monkeypatch):
    """Base mince : le module refuse de se prononcer — aucun repli
    « sens majoritaire » n'est ajouté par le pont."""
    monkeypatch.setattr(directeur, "_memoire_couple", lambda i, t: (None, None, 0))
    monkeypatch.setattr(directeur, "_regime_marche", lambda m: None)
    st = {"setup": "achat", "entree": 100.0, "stop": 98.0, "objectif": 104.0}
    directeur.analyser(st, {"prix": 100.0, "ema_slow": 99.95, "rsi": 51.0},
                       instrument="XAU/USD", tf="M5")
    assert st["direction"]["sens"] == "INDÉTERMINÉE"
    assert st["direction"]["texte"]


def test_panne_annoncee_jamais_levee(monkeypatch):
    monkeypatch.setattr(directeur, "_memoire_couple",
                        lambda i, t: 1 / 0)     # panne simulée
    st = _st()
    directeur.analyser(st, _r(), instrument="XAU/USD", tf="H1")
    assert st["direction"]["sens"] == "INDÉTERMINÉE"
    assert "indisponible" in st["direction"]["texte"]


def test_poids_cerveau_vide_sans_fichier(tmp_path, monkeypatch):
    monkeypatch.setattr(directeur, "CERVEAU_JSON", tmp_path / "c.json")
    directeur._CACHE["t"] = 0.0
    assert directeur.poids_cerveau("source") == {}
