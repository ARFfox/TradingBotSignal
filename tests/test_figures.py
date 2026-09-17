"""Tests du détecteur de figures.

Un détecteur de figures se casse d'une seule façon, et elle est silencieuse :
il trouve des figures partout. Du bruit pur en contient déjà 1,5 par
graphique. La moitié de ces tests vérifie que le module le SAIT et refuse
d'en tirer une direction.
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


fg = _charger("figures")


def bougie(px, o=None, amp=0.002):
    o = px if o is None else o
    return {"open": o, "high": max(o, px) * (1 + amp),
            "low": min(o, px) * (1 - amp), "close": px}


def serie(valeurs, amp=0.002):
    out, prec = [], valeurs[0]
    for v in valeurs:
        out.append(bougie(v, prec, amp))
        prec = v
    return out


def bruit(n=80, graine=0, sigma=0.006):
    rng = random.Random(graine)
    out, px = [], 100.0
    for _ in range(n):
        px *= (1 + rng.gauss(0, sigma))
        o = px * (1 + rng.uniform(-.0015, .0015))
        out.append({"open": o, "high": max(o, px) * (1 + abs(rng.gauss(0, .002))),
                    "low": min(o, px) * (1 - abs(rng.gauss(0, .002))),
                    "close": px})
    return out


# =====================================================================
# LE test : le bruit produit des figures, et le module ne s'y trompe pas
# =====================================================================
def test_le_bruit_pur_produit_des_figures():
    """Ce n'est pas un bug du détecteur, c'est un fait sur les figures.
    Un module qui ne le sait pas fait croire que voir un triangle est une
    information."""
    avec = sum(1 for g in range(200) if fg.detecter(bruit(80, g)))
    assert avec / 200 > 0.6, "un détecteur qui ne trouve rien dans le bruit " \
                             "est trop strict pour trouver quoi que ce soit"


def test_la_reference_de_bruit_est_a_jour():
    """Si les seuils de détection changent, `TAUX_SUR_BRUIT` doit être
    re-mesuré. Une référence périmée ment plus qu'elle n'informe."""
    m = fg.mesurer_bruit(n_essais=400)
    assert abs(m["au_moins_une"] - fg.AU_MOINS_UNE_SUR_BRUIT) < 0.08, \
        f"re-lance mesurer_bruit() : {m['au_moins_une']:.1%} mesuré contre " \
        f"{fg.AU_MOINS_UNE_SUR_BRUIT:.1%} documenté"


def test_le_taux_sur_bruit_est_documente_pour_chaque_figure():
    """Sans cette référence, « j'ai vu une épaule-tête-épaule » n'a pas de
    sens : elle apparaît dans 8 % du bruit."""
    vus = set()
    for g in range(300):
        for f in fg.detecter(bruit(80, g)):
            vus.add(f.code)
    manquants = vus - set(fg.TAUX_SUR_BRUIT)
    assert not manquants, f"figures sans référence de bruit : {manquants}"


def test_sans_poids_mesures_le_biais_est_toujours_neutre():
    """LE garde-fou. Tant qu'aucune figure n'a prouvé qu'elle prédit, le
    module ne donne aucune direction — même avec dix figures à l'écran."""
    for g in range(40):
        b = fg.biais(fg.detecter(bruit(80, g)))
        assert b["sens"] == "neutre" and b["score"] == 0.0


def test_le_poids_par_defaut_est_zero_pas_un():
    """Différence assumée avec avocats.py : la littérature dit « pas
    d'edge », donc une figure part de zéro et doit gagner sa place."""
    assert fg.POIDS_DEFAUT == 0.0


def test_le_biais_dit_combien_de_figures_le_bruit_aurait_donne():
    b = fg.biais([fg.Figure("double_sommet", "retournement", "baissier", 0, 9, 1.0),
                  fg.Figure("doji", "bougie", "indetermine", 9, 9, 1.0)])
    attendu = fg.TAUX_SUR_BRUIT["double_sommet"] + fg.TAUX_SUR_BRUIT["doji"]
    assert b["attendu_sur_bruit"] == pytest.approx(attendu, abs=.01)


def test_ajouter_des_figures_a_AGGRAVE_le_bruit():
    """34 figures voient du motif dans 98 % du hasard, contre 90 % à 17.
    Doubler le catalogue n'a pas doublé la lecture du marché : ça a doublé
    les façons de trouver quelque chose dans du bruit."""
    assert fg.AU_MOINS_UNE_SUR_BRUIT > 0.95
    assert fg.FIGURES_PAR_GRAPHIQUE_BRUIT > 2.5
    assert len(fg.TAUX_SUR_BRUIT) >= 30


def test_les_figures_des_fiches_sont_toutes_detectables():
    """Toutes celles des planches fournies, y compris les rares."""
    for code in ("triple_sommet", "triple_creux", "elargissement",
                 "canal_haussier", "canal_baissier", "arrondi_sommet",
                 "arrondi_creux", "tasse_anse", "etoile_du_matin",
                 "etoile_du_soir", "trois_soldats", "trois_corbeaux",
                 "penetrante", "couverture_nuages", "pendu",
                 "marteau_inverse", "toupie"):
        assert code in fg.TAUX_SUR_BRUIT, f"{code} sans référence de bruit"


def test_l_elargissement_n_a_aucune_direction():
    """Il dit que ça bouge, pas où ça va."""
    for g in range(400):
        for f in fg.detecter(bruit(80, g)):
            if f.code == "elargissement":
                assert f.direction == "indetermine"
                return
    pytest.skip("élargissement non rencontré")


def test_un_poids_mesure_debloque_le_biais():
    figs = [fg.Figure("marteau", "bougie", "haussier", 0, 0, 1.0)]
    assert fg.biais(figs)["sens"] == "neutre"
    assert fg.biais(figs, {"marteau": 1.5})["sens"] == "haussier"


# --- détection : les formes de base ----------------------------------
def test_triangle_ascendant():
    """Résistance plate, creux qui montent."""
    v = []
    for i in range(70):
        plafond, plancher = 110.0, 100 + i * 0.13
        v.append(plafond if i % 10 < 5 else plancher)
    fs = [f.code for f in fg.detecter(serie(v))]
    assert "triangle_ascendant" in fs


def test_triangle_descendant():
    v = []
    for i in range(70):
        plafond, plancher = 110 - i * 0.13, 100.0
        v.append(plafond if i % 10 < 5 else plancher)
    fs = [f.code for f in fg.detecter(serie(v))]
    assert "triangle_descendant" in fs


def test_rectangle():
    v = [110.0 if i % 10 < 5 else 100.0 for i in range(70)]
    fs = [f.code for f in fg.detecter(serie(v))]
    assert "rectangle" in fs


def test_le_triangle_symetrique_n_a_AUCUNE_direction():
    """Les fiches qui circulent affirment « on sait que le prix va sortir ».
    C'est vrai et ça ne dit rien : elles ne disent pas de quel côté."""
    v = []
    for i in range(70):
        c = 105.0
        e = max(0.5, 6 - i * 0.08)
        v.append(c + e if i % 10 < 5 else c - e)
    f = [x for x in fg.detecter(serie(v)) if x.code == "triangle_symetrique"]
    if f:
        assert f[0].direction == "indetermine"


def test_double_sommet_est_baissier_double_creux_haussier():
    for code, sens in (("double_sommet", "baissier"), ("double_creux", "haussier")):
        for g in range(200):
            for f in fg.detecter(bruit(80, g)):
                if f.code == code:
                    assert f.direction == sens
                    return
    pytest.skip(f"{code} non rencontré")


# --- les bougies ------------------------------------------------------
def test_marteau():
    b = [bougie(100 - i * .1) for i in range(20)]
    b.append({"open": 98.0, "high": 98.2, "low": 95.0, "close": 98.1})
    assert "marteau" in [f.code for f in fg.detecter(b)]


def test_etoile_filante():
    b = [bougie(100 + i * .1) for i in range(20)]
    b.append({"open": 102.0, "high": 105.0, "low": 101.9, "close": 102.1})
    assert "etoile_filante" in [f.code for f in fg.detecter(b)]


def test_doji():
    b = [bougie(100 + i * .05) for i in range(20)]
    b.append({"open": 101.0, "high": 101.8, "low": 100.2, "close": 101.01})
    assert "doji" in [f.code for f in fg.detecter(b)]


def test_englobante_haussiere():
    b = [bougie(100 - i * .1) for i in range(20)]
    b.append({"open": 99.0, "high": 99.1, "low": 98.5, "close": 98.6})
    b.append({"open": 98.4, "high": 99.6, "low": 98.3, "close": 99.5})
    assert "englobante_haussiere" in [f.code for f in fg.detecter(b)]


# --- aucune fuite du futur -------------------------------------------
def test_la_detection_ne_regarde_jamais_apres_la_derniere_bougie():
    """Une détection qui lit une bougie de plus produit un backtest
    magnifique et inutilisable en direct."""
    b = bruit(80, 7)
    avant = [f.code for f in fg.detecter(b)]
    suite = b + bruit(20, 999)
    assert [f.code for f in fg.detecter(suite[:len(b)])] == avant


def test_les_indices_restent_dans_la_serie():
    for g in range(30):
        b = bruit(80, g)
        for f in fg.detecter(b):
            assert 0 <= f.debut <= f.fin <= len(b) - 1


# --- robustesse -------------------------------------------------------
def test_une_serie_trop_courte_ne_plante_pas():
    assert fg.detecter([bougie(100) for _ in range(5)]) == []


def test_une_serie_vide_ne_plante_pas():
    assert fg.detecter([]) == []


def test_un_prix_plat_ne_produit_pas_de_figure_fantome():
    assert fg.detecter([bougie(100.0, amp=0) for _ in range(60)]) == []


def test_les_objets_marchent_comme_les_dicts():
    from dataclasses import dataclass

    @dataclass
    class B:
        open: float; high: float; low: float; close: float
    d = bruit(60, 3)
    o = [B(x["open"], x["high"], x["low"], x["close"]) for x in d]
    assert [f.code for f in fg.detecter(o)] == [f.code for f in fg.detecter(d)]


def test_chaque_figure_porte_une_famille_connue():
    for g in range(60):
        for f in fg.detecter(bruit(80, g)):
            assert f.famille in fg.FAMILLES


def test_la_qualite_reste_entre_0_et_1():
    for g in range(60):
        for f in fg.detecter(bruit(80, g)):
            assert 0.0 <= f.qualite <= 1.0


# --- calibration ------------------------------------------------------
def _jeu(n=300, p_avec=0.55, p_sans=0.20, graine=5):
    rng = random.Random(graine)
    out = []
    for i in range(n):
        avec = i % 3 == 0
        decor = i % 4 == 0
        gagne = rng.random() < (p_avec if avec else p_sans)
        figs = ([fg.Figure("marteau", "bougie", "haussier", 0, 0, 1.0)] if avec else []) \
             + ([fg.Figure("doji", "bougie", "indetermine", 0, 0, 1.0)] if decor else [])
        out.append(({"statut": "TP" if gagne else "SL",
                     "r_realise": 2.1 if gagne else -1.0}, figs))
    return out


def test_une_figure_qui_predit_prend_du_poids():
    p = fg.calibrer(_jeu())
    assert p["marteau"].verdict == "discriminante" and p["marteau"].poids > 0.5


def test_une_figure_decorative_reste_a_zero():
    p = fg.calibrer(_jeu())
    assert p["doji"].poids == 0.0


def test_sous_30_observations_une_figure_ne_vote_pas():
    p = fg.calibrer(_jeu(n=45))
    for x in p.values():
        assert x.poids == 0.0 and "non mesurée" in x.verdict


def test_une_figure_inversee_est_signalee_pas_supprimee():
    """Une figure qui précède l'inverse de ce qu'elle annonce porte de
    l'information — à condition de le savoir."""
    p = fg.calibrer(_jeu(p_avec=0.05, p_sans=0.50))
    assert "retourner" in p["marteau"].verdict


def test_calibrer_ignore_les_non_resolus():
    paires = [({"statut": "en_attente", "r_realise": None},
               [fg.Figure("marteau", "bougie", "haussier", 0, 0, 1.0)])
              for _ in range(80)]
    assert fg.calibrer(paires) == {}


def test_calibrer_ne_plante_pas_sans_donnees():
    assert fg.calibrer([]) == {}
    assert isinstance(fg.rapport({}), str)


def test_le_rapport_rappelle_le_taux_sur_bruit():
    r = fg.rapport(fg.calibrer(_jeu()))
    assert "ALÉATOIRES" in r and "%" in r


def test_le_rapport_le_dit_quand_aucune_figure_ne_sert():
    r = fg.rapport(fg.calibrer(_jeu(p_avec=0.20, p_sans=0.20)))
    assert "n'influencent aucune décision" in r
