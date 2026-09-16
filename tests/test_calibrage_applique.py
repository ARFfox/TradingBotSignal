"""CHANTIER #7-9 — la calibration mesurée APPLIQUÉE : poids dans la note,
couples coupés et seuil mesuré à l'émission. Sans réseau."""
import json

from gold_agent import apprentissage
from gold_agent.decision import noter


def _st(sens="achat", avis=None):
    return {"setup": sens, "entree": 100.0, "stop": 98.0, "objectif": 104.0,
            "rr": 2.0, "avis": avis or {}}


# ------------------------------------------------------------- #7 poids
def test_poids_mesures_pesent_dans_la_note():
    poids = {"AG-02": {"poids": 2.0, "fiable": True, "note": "utile",
                       "discrimination": 0.4}}
    avec = noter(_st(avis={"AG-02": "achat"}), {}, None, False, None,
                 poids_mesures=poids)
    sans = noter(_st(avis={"AG-02": "achat"}), {}, None, False, None)
    assert avec["pct"] > sans["pct"]
    assert any("poids mesurés" in c for c in avec["composantes"])


def test_contre_indicateur_vote_a_l_envers():
    """AG-05 discr. −0,35 : son « achat » est un signal de VENTE."""
    poids = {"AG-05": {"poids": 0.1, "fiable": True,
                       "note": "contre-indicateur — inverser son vote",
                       "discrimination": -0.35}}
    n = noter(_st(sens="achat", avis={"AG-05": "achat"}), {}, None, False,
              None, poids_mesures=poids)
    base = noter(_st(sens="achat", avis={"AG-05": "achat"}), {}, None, False,
                 None)
    assert n["pct"] < base["pct"]          # l'avis inversé pèse CONTRE
    assert any("inversé" in c for c in n["composantes"])


def test_poids_non_fiable_reste_muet():
    poids = {"AG-02": {"poids": 3.0, "fiable": False, "note": "échantillon"}}
    n = noter(_st(avis={"AG-02": "achat"}), {}, None, False, None,
              poids_mesures=poids)
    assert not any("poids mesurés" in c for c in n["composantes"])


# ------------------------------------------------------- #8-9 émission
def test_couple_coupe_est_refuse(tmp_path, monkeypatch):
    monkeypatch.setattr(apprentissage, "CALIBRAGE", tmp_path / "c.json")
    (tmp_path / "c.json").write_text(json.dumps({
        "combos": {"XAU/USD|M5": {"verdict": "COUPE", "esperance": -0.56,
                                  "n": 20}},
        "seuil": {"assez_de_donnees": True, "rentable": False}}))
    motif = apprentissage.refus_calibrage("XAU/USD", "M5", 80)
    assert motif and "couple coupé" in motif
    assert apprentissage.refus_calibrage("XAU/USD", "H1", 80) is None


def test_aucun_seuil_rentable_ne_filtre_rien(tmp_path, monkeypatch):
    """APPLIQUER §2.2 : tant que la note est à reconstruire, « aucun
    seuil » signifie AUCUN filtrage sur la note."""
    monkeypatch.setattr(apprentissage, "CALIBRAGE", tmp_path / "c.json")
    (tmp_path / "c.json").write_text(json.dumps({
        "combos": {},
        "seuil": {"assez_de_donnees": True, "rentable": False,
                  "seuil": 0.45}}))
    assert apprentissage.refus_calibrage("XAU/USD", "M5", 5) is None


def test_seuil_rentable_filtre_en_dessous(tmp_path, monkeypatch):
    monkeypatch.setattr(apprentissage, "CALIBRAGE", tmp_path / "c.json")
    (tmp_path / "c.json").write_text(json.dumps({
        "combos": {},
        "seuil": {"assez_de_donnees": True, "rentable": True, "seuil": 0.40,
                  "message": "seuil 40% -> +12R"}}))
    assert apprentissage.refus_calibrage("XAU/USD", "M5", 35)
    assert apprentissage.refus_calibrage("XAU/USD", "M5", 55) is None


# ----------------------------------------------------- persistance
def test_persistance_et_historique(tmp_path, monkeypatch):
    monkeypatch.setattr(apprentissage, "CALIBRAGE", tmp_path / "c.json")
    monkeypatch.setattr(apprentissage, "HISTORIQUE_CALIBRATION",
                        tmp_path / "h.json")
    sig = apprentissage.signaux([{
        "cle": f"XAU/USD|M5|achat|{100 + i}", "instrument": "XAU/USD",
        "tf": "M5", "sens": "achat", "entree": 100.0 + i, "stop": 98.0 + i,
        "objectif": 104.0 + i, "rr_prevu": 2.0, "statut": "perdant",
        "cree_ts": 1_750_000_000 + i, "decision_chef": 40, "atr": 2.0,
        "avis": {}, "r_realise": -1.0, "r_obtenu": -1.0,
        "extreme_favorable": None, "tp_atteint_apres_sl": False}
        for i in range(25)])
    apprentissage._persister_calibrage(sig, 25)
    c = json.loads((tmp_path / "c.json").read_text())
    assert c["combos"]["XAU/USD|M5"]["verdict"] == "COUPE"   # 25 SL mesurés
    h = json.loads((tmp_path / "h.json").read_text())
    assert any(x["quoi"] == "couple XAU/USD|M5" and x["apres"] == "COUPE"
               and x["effectif"] == 25 for x in h)
