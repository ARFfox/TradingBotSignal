"""Tests du Directeur AG-19.

Un module de direction se casse d'une seule façon et elle est invisible :
il trouve toujours une direction. Sa sortie devient alors prévisible, donc
sans information — et elle a l'air parfaitement normale. La moitié de ces
tests vérifie qu'il sait dire « je ne sais pas ».
"""
from __future__ import annotations

import importlib.util
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


di = _charger("direction")


def S(code, famille, sens, force=1.0, predictive=False):
    return di.Source(code, famille, sens, force, f"{code} {sens}",
                     predictive=predictive)


def accord(n=4, sens="haussier", force=1.0):
    fams = ["tendance", "marche", "intermarche", "momentum", "memoire", "figure"]
    return [S(f"s{i}", fams[i], sens, force) for i in range(n)]


# =====================================================================
# LE test : savoir dire « je ne sais pas »
# =====================================================================
def test_des_sources_qui_se_contredisent_donnent_indetermine():
    """Deux camps qui tiennent chacun des faits réels : ce n'est pas un
    manque d'analyse, c'est un marché sans direction."""
    s = [S("a", "tendance", "haussier"), S("b", "marche", "baissier"),
         S("c", "intermarche", "haussier"), S("d", "momentum", "baissier")]
    assert di.decider(s).sens == "INDÉTERMINÉE"


def test_une_base_trop_mince_donne_indetermine():
    s = [S("a", "tendance", "haussier", force=0.2)]
    d = di.decider(s)
    assert d.sens == "INDÉTERMINÉE" and "mince" in d.motif


def test_aucune_source_donne_indetermine():
    d = di.decider([])
    assert d.sens == "INDÉTERMINÉE" and "aucun agent" in d.motif


def test_que_des_sources_neutres_donne_indetermine():
    s = [S(f"s{i}", f, "neutre") for i, f in enumerate(
        ("tendance", "marche", "intermarche"))]
    assert di.decider(s).sens == "INDÉTERMINÉE"


def test_un_accord_net_et_large_donne_une_direction():
    """L'inverse doit marcher aussi : un module qui ne conclut jamais est
    aussi cassé qu'un module qui conclut toujours."""
    d = di.decider(accord(4, "haussier"))
    assert d.sens == "haussier" and d.score > 0


def test_le_sens_baissier_marche_symetriquement():
    d = di.decider(accord(4, "baissier"))
    assert d.sens == "baissier" and d.score < 0


# --- décrire n'est pas prédire ---------------------------------------
def test_une_source_predictive_pese_zero_par_defaut():
    """figures.py affirme l'avenir ; la littérature dit « pas d'edge ».
    Elle doit gagner sa place avant de parler."""
    assert S("f", "figure", "haussier", predictive=True).poids_defaut == 0.0
    assert S("t", "tendance", "haussier", predictive=False).poids_defaut == 1.0


def test_des_figures_seules_ne_donnent_aucune_direction():
    s = [S("figures", "figure", "haussier", 1.0, predictive=True)]
    d = di.decider(s)
    assert d.sens == "INDÉTERMINÉE" and d.base == 0.0


def test_une_source_predictive_mesuree_compte():
    s = [S("figures", "figure", "haussier", 1.0, predictive=True)] \
        + accord(2, "haussier")
    sans = di.decider(s)
    avec = di.decider(s, {"figures": 1.5})
    assert avec.base > sans.base


# --- redondance -------------------------------------------------------
def test_trois_sources_de_la_meme_famille_ne_valent_qu_une_voix():
    """« le marché monte », « le régime est haussier », « l'instrument mène
    son marché haussier » sont UNE observation vue trois fois."""
    une = di.decider([S("a", "marche", "haussier"), S("x", "tendance", "haussier"),
                      S("y", "momentum", "haussier")])
    trois = di.decider([S("a", "marche", "haussier"), S("b", "marche", "haussier"),
                        S("c", "marche", "haussier"), S("x", "tendance", "haussier"),
                        S("y", "momentum", "haussier")])
    assert trois.score == pytest.approx(une.score), \
        "la même famille a compté plusieurs fois"


def test_la_famille_garde_son_membre_le_plus_fort():
    d = di.decider([S("faible", "marche", "haussier", 0.2),
                    S("fort", "marche", "haussier", 1.0)] + accord(2, "haussier"))
    assert any(s.code == "fort" for s in d.pour)


# --- la certitude -----------------------------------------------------
def test_la_certitude_monte_avec_le_nombre_de_sources_pas_leur_force():
    """Cinq sources faibles d'accord valent mieux qu'une source forte seule."""
    seule = di.decider([S("a", "tendance", "haussier", 1.0),
                        S("b", "marche", "haussier", 1.0)])
    beaucoup = di.decider(accord(5, "haussier", 0.8))
    assert beaucoup.certitude > seule.certitude


def test_sans_source_mesuree_la_certitude_est_plafonnee():
    d = di.decider(accord(5, "haussier"))
    assert d.n_mesurees == 0 and d.certitude <= 0.42


def test_des_sources_mesurees_augmentent_la_certitude():
    s = accord(5, "haussier")
    sans = di.decider(s)
    avec = di.decider(s, {f"s{i}": 1.0 for i in range(5)})
    assert avec.certitude > sans.certitude


def test_la_certitude_reste_entre_0_et_1():
    for n in range(1, 7):
        for f in (0.1, 0.5, 1.0):
            d = di.decider(accord(n, "haussier", f), {f"s{i}": 2.0 for i in range(6)})
            assert 0.0 <= d.certitude <= 1.0


# --- le point de bascule ----------------------------------------------
def test_le_point_de_bascule_nomme_UNE_source_pas_toutes():
    """« que la tendance ou le marché ou le momentum change » est vrai de
    toute conclusion et ne sert à rien. Il faut LE point faible."""
    d = di.decider([S("fort", "tendance", "haussier", 1.0),
                    S("moyen", "marche", "haussier", 0.9),
                    S("faible", "momentum", "haussier", 0.3)])
    assert d.bascule and " ou " not in d.bascule


def test_une_direction_tres_large_n_a_pas_de_point_faible_unique():
    d = di.decider(accord(6, "haussier"))
    assert "aucune source seule" in d.bascule


def test_le_point_de_bascule_designe_la_source_la_plus_legere():
    """Entre deux points faibles, on nomme le moins lourd : c'est celui qui
    a le plus de chances de basculer vraiment."""
    # `leger` ne casse rien s'il se retourne (l'accord reste à 85 %) : les
    # deux sources fragiles sont `lourd` et `moyen`, et c'est la plus légère
    # des deux qu'il faut nommer.
    d = di.decider([S("lourd", "tendance", "haussier", 1.00),
                    S("moyen", "intermarche", "haussier", 0.95),
                    S("leger", "marche", "haussier", 0.35)])
    assert d.sens == "haussier", d.motif
    assert "moyen" in d.bascule and "leger" not in d.bascule


# --- le texte ---------------------------------------------------------
def test_le_texte_nomme_les_chiffres():
    d = di.decider(di.sources_depuis_agents(
        structure={"ecart_ema": 0.031},
        marche={"regime": "haussier", "largeur": 0.78, "nom": "matières"},
        intermarche={"score": 0.52, "fiable": True}))
    t = di.expliquer(d)
    assert "EMA50" in t and "%" in t


def test_le_texte_dit_ce_qui_ferait_changer_d_avis():
    t = di.expliquer(di.decider(accord(3, "haussier")))
    assert "changer d'avis" in t


def test_le_texte_montre_les_deux_camps_quand_c_est_indetermine():
    s = [S("a", "tendance", "haussier"), S("b", "marche", "baissier"),
         S("c", "intermarche", "haussier"), S("d", "momentum", "baissier")]
    t = di.expliquer(di.decider(s))
    assert "pile ou face" in t and "hausse" in t and "baisse" in t


def test_le_texte_avertit_quand_rien_n_est_mesure():
    t = di.expliquer(di.decider(accord(4, "haussier")))
    assert "poids mesuré" in t


def test_le_texte_ne_plante_sur_aucun_cas():
    for s in ([], accord(1), accord(6), [S("n", "marche", "neutre")]):
        assert isinstance(di.expliquer(di.decider(s)), str)


# --- lecture des agents -----------------------------------------------
def test_un_agent_absent_ne_vote_pas_neutre():
    """Un agent muet doit réduire la base, pas diluer le score."""
    assert len(di.sources_depuis_agents()) == 0
    assert len(di.sources_depuis_agents(momentum={"rsi": 60})) == 1


def test_un_miroir_non_fiable_voit_sa_force_reduite():
    f = di.sources_depuis_agents(intermarche={"score": 0.8, "fiable": True})[0]
    nf = di.sources_depuis_agents(intermarche={"score": 0.8, "fiable": False})[0]
    assert nf.force < f.force and "base faible" in nf.mesure


def test_la_memoire_n_entre_qu_avec_assez_de_signaux():
    assert di.sources_depuis_agents(
        memoire={"esperance": 0.3, "n": 12, "sens_favorable": "haussier"}) == []
    assert len(di.sources_depuis_agents(
        memoire={"esperance": 0.3, "n": 40, "sens_favorable": "haussier"})) == 1


def test_les_figures_arrivent_marquees_predictives():
    s = di.sources_depuis_agents(figures_biais={
        "sens": "haussier", "score": 0.5, "n_figures": 2,
        "attendu_sur_bruit": 0.6})[0]
    assert s.predictive and "bruit" in s.mesure


# --- calibration ------------------------------------------------------
def _jeu(n=200, bon=True, graine=3):
    import random
    rng = random.Random(graine)
    out = []
    for i in range(n):
        daccord = i % 2 == 0
        p = (0.55 if daccord else 0.15) if bon else 0.35
        gagne = rng.random() < p
        src = S("structure_ema", "tendance",
                "haussier" if daccord else "baissier")
        out.append(({"statut": "TP" if gagne else "SL", "sens": "achat",
                     "r_realise": 2.1 if gagne else -1.0}, [src]))
    return out


def test_une_source_qui_discrimine_prend_du_poids():
    p = di.calibrer(_jeu())
    assert p["structure_ema"].verdict == "discriminante"
    assert p["structure_ema"].poids > 0.5


def test_une_source_qui_decrit_sans_predire_reste_a_zero():
    """Elle peut avoir parfaitement raison sur l'état du marché et n'apporter
    aucune information sur ce qui suit."""
    p = di.calibrer(_jeu(bon=False))
    assert p["structure_ema"].poids == 0.0
    assert p["structure_ema"].verdict in ("décrit sans prédire",
                                          "à retourner — elle prédit l'inverse")


def test_sous_30_observations_aucune_source_ne_vote():
    p = di.calibrer(_jeu(n=20))
    for s in p.values():
        assert s.poids == 0.0 and "non mesurée" in s.verdict


def test_calibrer_ignore_les_non_resolus():
    src = S("a", "tendance", "haussier")
    assert di.calibrer([({"statut": "en_attente", "sens": "achat",
                          "r_realise": None}, [src])] * 60) == {}


def test_calibrer_ne_plante_pas_sans_donnees():
    assert di.calibrer([]) == {}
    assert isinstance(di.rapport({}), str)


def test_le_rapport_le_dit_quand_aucune_source_ne_predit():
    assert "ne prétend pas le prévoir" in di.rapport(di.calibrer(_jeu(bon=False)))
