"""Tests d'AG-20 Chartiste.

Deux pièges, et ils sont symétriques : compter la même figure une fois par
timeframe (une confluence fabriquée), et confondre un niveau avec une
figure. Le premier gonfle la conviction, le second confond décrire et
prédire. La plupart de ces tests portent là-dessus.
"""
from __future__ import annotations

import importlib.util
import math
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


_charger("figures")
ac = _charger("agent_chartiste")


def serie(n, f, graine=3, bruit=0.0015):
    rng = random.Random(graine)
    out, px = [], 100.0
    for i in range(n):
        px = f(i, px)
        o = px * (1 + rng.uniform(-bruit, bruit))
        out.append({"open": o,
                    "high": max(o, px) * (1 + abs(rng.gauss(0, bruit))),
                    "low": min(o, px) * (1 - abs(rng.gauss(0, bruit))),
                    "close": px})
    return out


def monte(n=80, pas=0.15):
    return serie(n, lambda i, p: 100 + i * pas + math.sin(i / 4))


def descend(n=80, pas=0.15):
    return serie(n, lambda i, p: 120 - i * pas + math.sin(i / 4))


def plat(n=80):
    return serie(n, lambda i, p: 100 + math.sin(i / 3) * 2)


def cinq(h4=None, h1=None, m30=None, m15=None, m5=None):
    return {"H4": h4, "H1": h1, "M30": m30, "M15": m15, "M5": m5}


# =====================================================================
# Le piège n°1 : la même figure comptée une fois par timeframe
# =====================================================================
def test_une_figure_vue_sur_cinq_echelles_ne_compte_qu_une_fois():
    """H1 contient les mêmes bougies que H4, en plus fin. Compter la figure
    deux fois fabrique une confluence qui n'existe pas."""
    memes = monte()
    L = ac.lire("X", {tf: memes for tf in ac.TIMEFRAMES})
    assert L.n_figures >= L.n_uniques * 2, "les 5 TF doivent bien détecter"
    assert L.n_uniques < L.n_figures, "les doublons n'ont pas été retirés"


def test_l_attente_de_bruit_se_compare_aux_figures_DISTINCTES():
    """Afficher « 11 figures contre 0,8 attendues » compare des détections
    brutes à une attente dédoublonnée. Les deux ne comptent pas la même
    chose."""
    L = ac.lire("X", {tf: monte() for tf in ac.TIMEFRAMES})
    r = ac.rapport(L)
    assert f"{L.n_uniques} figure(s) distincte(s)" in r
    assert "distincte(s) — contre" in r


def test_la_conviction_vient_de_l_accord_pas_du_nombre_de_figures():
    """En voir beaucoup est la situation normale : 98 % du bruit en
    contient."""
    peu = ac.lire("X", cinq(monte(), monte(), monte(), monte(), monte()))
    assert ac.carte_agent(peu)["conviction"] == int(round(peu.accord * 100))


# --- le piège n°2 : décrire n'est pas prédire -------------------------
def test_les_arguments_donnes_aux_avocats_sont_des_NIVEAUX_pas_des_figures():
    """Un niveau se vérifie sur l'historique, une figure se croit."""
    L = ac.lire("X", cinq(plat(), plat(), plat(), plat(), plat()))
    prix = 100.0
    for a in ac.arguments_avocats(L, prix):
        assert "figure" not in a["code"], f"{a['code']} est une figure"


def test_la_source_direction_porte_la_tendance_pas_le_biais_des_figures():
    L = ac.lire("X", cinq(monte(), monte(), monte(), monte(), monte()))
    s = ac.source_direction(L)
    assert s["sens"] == L.sens_dominant and "timeframes" in s["mesure"]


# --- les niveaux -------------------------------------------------------
def test_un_niveau_exige_plusieurs_touches():
    """Un « niveau » à une seule touche est un point, pas un niveau."""
    h = [100 + i for i in range(40)]
    b = [99 + i for i in range(40)]
    assert ac.niveaux(h, b) == []


def test_un_prix_touche_plusieurs_fois_devient_un_niveau():
    v = [110.0 if i % 10 < 5 else 100.0 for i in range(70)]
    s = serie(70, lambda i, p: v[i], bruit=0.0002)
    n = ac.niveaux([x["high"] for x in s], [x["low"] for x in s])
    assert n and max(x.touches for x in n) >= 2


def test_la_force_d_un_niveau_monte_avec_les_touches_et_plafonne():
    assert ac.Niveau(100, "support", 2, 0, 0.4).force < \
           ac.Niveau(100, "support", 5, 0, 1.0).force
    v = [110.0 if i % 6 < 3 else 100.0 for i in range(120)]
    s = serie(120, lambda i, p: v[i], bruit=0.0002)
    for n in ac.niveaux([x["high"] for x in s], [x["low"] for x in s]):
        assert n.force <= 1.0


def test_les_points_pivots_sont_purement_arithmetiques():
    p = ac.points_pivots(110.0, 90.0, 100.0)
    assert p["P"] == pytest.approx(100.0)
    assert p["R1"] == pytest.approx(110.0) and p["S1"] == pytest.approx(90.0)
    assert p["S3"] < p["S2"] < p["S1"] < p["P"] < p["R1"] < p["R2"] < p["R3"]


def test_un_niveau_fusionne_garde_la_trace_de_ses_timeframes():
    L = ac.lire("X", cinq(plat(), plat(), plat(), plat(), plat()))
    if L.niveaux_fusionnes:
        n = L.niveaux_fusionnes[0]
        assert n["timeframes"] and n["poids"] > 0


def test_zone_trouve_le_niveau_au_dessus_et_au_dessous():
    niv = [ac.Niveau(90, "support", 3, 0, .6), ac.Niveau(110, "resistance", 3, 0, .6)]
    assert ac.zone(niv, 100, "haut").prix == 110
    assert ac.zone(niv, 100, "bas").prix == 90
    assert ac.zone(niv, 200, "haut") is None


# --- l'accord et les conflits -----------------------------------------
def test_cinq_echelles_haussieres_donnent_un_accord_total():
    L = ac.lire("X", cinq(monte(), monte(), monte(), monte(), monte()))
    assert L.sens_dominant == "haussier" and L.accord == 1.0 and not L.conflits


def test_un_desaccord_est_nomme_timeframe_par_timeframe():
    """C'est l'information la plus utile de la lecture : un accord parfait
    est rare, un désaccord dit où est le risque."""
    L = ac.lire("X", cinq(monte(), monte(), monte(), descend(), descend()))
    assert L.conflits and "M15" in " ".join(L.conflits)
    assert 0 < L.accord < 1


def test_les_grandes_echelles_pesent_plus_que_les_petites():
    """Une bougie H4 en vaut 48 en M5. Les traiter à égalité laisserait le
    bruit de court terme décider de la tendance."""
    assert ac.POIDS_TF["H4"] > ac.POIDS_TF["H1"] > ac.POIDS_TF["M5"]
    haut = ac.lire("X", cinq(monte(), descend(), descend(), descend(), descend()))
    bas = ac.lire("X", cinq(descend(), monte(), monte(), monte(), monte()))
    assert haut.sens_dominant == "baissier"     # 4 petits battent 1 grand
    assert bas.sens_dominant == "haussier"


def test_un_marche_plat_ne_donne_aucun_sens():
    L = ac.lire("X", cinq(plat(), plat(), plat(), plat(), plat()))
    assert L.sens_dominant == "neutre"
    assert ac.carte_agent(L)["position"] == "neutre"


def test_le_conflit_devient_un_argument_CONTRE():
    L = ac.lire("X", cinq(monte(), monte(), monte(), descend(), descend()))
    args = ac.arguments_avocats(L, 100.0)
    conflit = [a for a in args if a["code"] == "timeframes_en_conflit"]
    assert conflit and conflit[0]["camp"] == "contre"


# --- la carte d'agent --------------------------------------------------
def test_sans_bougies_l_agent_est_muet_pas_neutre():
    """Un agent qui n'a rien reçu doit se déclarer muet : sinon il baisse
    la moyenne en silence."""
    c = ac.carte_agent(ac.lire("X", {}))
    assert c["statut"] == "MUET" and c["conviction"] == 0


def test_la_carte_porte_une_position_lisible():
    for b, attendu in ((monte(), "pour"), (descend(), "contre")):
        L = ac.lire("X", {tf: b for tf in ac.TIMEFRAMES})
        assert ac.carte_agent(L)["position"] == attendu


def test_la_carte_nomme_le_conflit_quand_il_y_en_a_un():
    L = ac.lire("X", cinq(monte(), monte(), monte(), descend(), descend()))
    assert any("alors que" in a for a in ac.carte_agent(L)["activites"])


# --- robustesse --------------------------------------------------------
def test_un_timeframe_manquant_ne_plante_pas():
    L = ac.lire("X", {"H4": monte(), "M5": monte()})
    assert len(L.par_tf) == 2 and L.sens_dominant == "haussier"
    assert "pas de données" in ac.rapport(L)


def test_une_serie_trop_courte_est_ignoree():
    L = ac.lire("X", {"H4": monte(8)})
    assert L.par_tf["H4"].tendance == "neutre" and not L.par_tf["H4"].figures


def test_aucune_bougie_ne_plante_pas():
    L = ac.lire("X", {})
    assert L.accord == 0.0 and isinstance(ac.rapport(L), str)
    assert ac.arguments_avocats(L, 100.0) == []


def test_les_objets_marchent_comme_les_dicts():
    from dataclasses import dataclass

    @dataclass
    class B:
        open: float; high: float; low: float; close: float
    d = monte()
    o = [B(x["open"], x["high"], x["low"], x["close"]) for x in d]
    assert ac.lire("X", {"H4": o}).par_tf["H4"].tendance == \
           ac.lire("X", {"H4": d}).par_tf["H4"].tendance


def test_le_rapport_rappelle_la_difference_niveau_figure():
    L = ac.lire("X", cinq(plat(), plat(), plat(), plat(), plat()))
    r = ac.rapport(L, 100.0)
    if L.niveaux_fusionnes:
        assert "décrit" in r and "prédit" in r


def test_le_rapport_ne_plante_sur_aucun_cas():
    for b in ({}, {"H4": monte()}, cinq(monte(), descend(), plat(), monte(), plat())):
        assert isinstance(ac.rapport(ac.lire("X", b), 100.0), str)
