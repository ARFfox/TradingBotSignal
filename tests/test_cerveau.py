"""Tests de la boucle du cerveau.

Un cerveau qui apprend se casse de deux façons opposées, et les deux ont
l'air normales de l'extérieur : il oscille au rythme du dernier trade, ou
il se fige en affichant une pastille verte. La plupart de ces tests
vérifient qu'il ne fait ni l'un ni l'autre.
"""
from __future__ import annotations

import importlib.util
import json
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


ce = _charger("cerveau")


def journal(n, tp=0.25):
    return [{"statut": "TP" if i % int(1 / tp) == 0 else "SL",
             "r_realise": 2.1 if i % int(1 / tp) == 0 else -1.0}
            for i in range(n)]


def cal(**kw):
    return {"argument": kw}


# =====================================================================
# Ne pas osciller
# =====================================================================
def test_sans_donnees_nouvelles_rien_ne_bouge():
    """Recalibrer sur les mêmes signaux ne crée aucun savoir — et à force
    de re-chercher dans le même journal, on finit par y trouver ce qu'on
    veut."""
    e1 = ce.cycle(journal(100), ce.Etat(), cal(a=1.0))
    e2 = ce.cycle(journal(100), e1, cal(a=2.0))
    assert e2.version == e1.version
    assert e2.poids == e1.poids
    assert "ne crée aucun savoir" in e2.motif_dernier_cycle


def test_il_faut_vingt_resolus_nouveaux():
    e1 = ce.cycle(journal(100), ce.Etat(), cal(a=1.0))
    assert ce.cycle(journal(119), e1, cal(a=2.0)).version == e1.version
    assert ce.cycle(journal(120), e1, cal(a=2.0)).version == e1.version + 1


def test_la_premiere_mesure_s_applique_en_entier():
    """Le lissage protège d'une oscillation entre deux mesures. Sur la
    première, il n'y a aucune croyance antérieure à protéger."""
    e = ce.cycle(journal(100), ce.Etat(), cal(a=1.8))
    assert e.poids["argument"]["a"] == pytest.approx(1.8)
    assert "première mesure" in e.changements[-1]["motif"]


def test_un_poids_ne_saute_jamais_apres_la_premiere_mesure():
    """De 0,1 à 2,0 d'un coup n'est pas de l'apprentissage, c'est une
    réaction au dernier trade."""
    e1 = ce.cycle(journal(100), ce.Etat(), cal(a=0.1))
    e2 = ce.cycle(journal(200), e1, cal(a=2.0))
    assert e2.poids["argument"]["a"] == pytest.approx(0.1 + ce.DELTA_MAX)


def test_le_lissage_marche_dans_les_deux_sens():
    e1 = ce.cycle(journal(100), ce.Etat(), cal(a=1.5))
    assert e1.poids["argument"]["a"] == pytest.approx(1.5)
    e2 = ce.cycle(journal(200), e1, cal(a=0.0))
    assert e2.poids["argument"]["a"] == pytest.approx(1.5 - ce.DELTA_MAX)


def test_un_petit_ajustement_passe_entier():
    e1 = ce.cycle(journal(100), ce.Etat(), cal(a=1.0))
    e2 = ce.cycle(journal(200), e1, cal(a=1.1))
    assert e2.poids["argument"]["a"] == pytest.approx(1.1)


def test_forcer_permet_le_rattrapage_manuel():
    e1 = ce.cycle(journal(100), ce.Etat(), cal(a=1.0))
    assert ce.cycle(journal(105), e1, cal(a=1.2), forcer=True).version > e1.version


# --- ne pas se figer en affichant du vert -----------------------------
def test_un_cerveau_jamais_entraine_le_dit():
    live = ce.etat_live(ce.Etat())
    assert live["statut"] == "jamais entraîné" and live["couleur"] == "gris"


def test_juste_apres_un_cycle_le_statut_dit_qu_il_a_appris():
    """Au sortir d'un cycle, `n_depuis` vaut 0 par construction. Afficher
    « en attente 0/20 » à l'instant où il vient de modifier ses poids donne
    l'inverse de l'information utile."""
    e = ce.cycle(journal(100), ce.Etat(), cal(a=1.0))
    live = ce.etat_live(e)
    assert live["statut"] == "vient d'apprendre" and live["couleur"] == "vert"


def test_un_cycle_sans_changement_ne_dit_pas_qu_il_a_appris():
    e1 = ce.cycle(journal(100), ce.Etat(), cal(a=1.0))
    e2 = ce.cycle(journal(200), e1, cal(a=1.0))     # même poids proposé
    assert e2.n_changements_dernier_cycle == 0
    assert ce.etat_live(e2)["statut"] != "vient d'apprendre"


def test_un_probleme_bloquant_passe_le_statut_au_rouge():
    """Une pastille verte sur un cerveau bridé apprend au lecteur à ne plus
    la regarder."""
    e = ce.cycle(journal(100), ce.Etat(), cal(a=1.0))
    live = ce.etat_live(e, [{"gravite": "bloquant", "quoi": "x",
                             "detail": "l'ATR manque"}])
    assert live["couleur"] == "rouge" and "ATR" in live["phrase"]


def test_le_bandeau_montre_la_proportion_de_poids_mesures():
    e = ce.cycle(journal(100), ce.Etat(), {"argument": {"a": 1.0, "b": 0.0}})
    assert "1/2" in ce.bandeau_texte(ce.etat_live(e))


def test_un_poids_mesure_a_zero_compte_dans_le_total():
    """Omettre les poids nuls faisait afficher « 3/3 mesurés » alors que
    trois sources avaient été mesurées ET jugées inutiles."""
    e = ce.cycle(journal(100), ce.Etat(), {"argument": {"a": 1.0}})
    e2 = ce.cycle(journal(200), e, {"argument": {"a": 1.0, "b": 0.0}})
    e3 = ce.cycle(journal(300), e2, {"argument": {"a": 1.0, "b": 0.0}})
    assert "b" in e3.poids["argument"] and e3.n_mesures() == 1


# --- le journal des changements ---------------------------------------
def test_chaque_changement_porte_son_avant_apres_et_son_motif():
    e = ce.cycle(journal(100), ce.Etat(), cal(a=1.0))
    c = ce.Changement(**e.changements[-1])
    assert c.avant == 0.0 and c.apres > 0 and c.motif and c.n_base == 100


def test_le_journal_des_changements_est_borne():
    e = ce.Etat()
    for i in range(1, 40):
        e = ce.cycle(journal(100 * i), e,
                     {"argument": {f"a{j}": (i % 3) * 0.5 for j in range(20)}})
    assert len(e.changements) <= ce.N_MAX_CHANGEMENTS


def test_revenir_en_arriere_defait_les_poids():
    """« Tout changement est réversible » n'est une règle que si quelqu'un a
    écrit le retour en arrière."""
    e1 = ce.cycle(journal(100), ce.Etat(), cal(a=1.0))
    e2 = ce.cycle(journal(200), e1, cal(a=0.2))
    assert e2.poids["argument"]["a"] != e1.poids["argument"]["a"]
    retour = ce.revenir_a(e2, e1.version)
    assert retour.poids["argument"]["a"] == pytest.approx(e1.poids["argument"]["a"])


def test_revenir_a_une_version_future_ne_fait_rien():
    e = ce.cycle(journal(100), ce.Etat(), cal(a=1.0))
    assert ce.revenir_a(e, e.version + 5) is e


# --- la santé ---------------------------------------------------------
def test_les_SL_indetermines_sont_signales_bloquants():
    p = ce.sante(ce.Etat(), [], {"sl_indetermines": 314, "sl_total": 317})
    assert any(x["gravite"] == "bloquant" and "stops" in x["quoi"] for x in p)


def test_des_stops_bien_audites_ne_declenchent_rien():
    p = ce.sante(ce.Etat(), [], {"sl_indetermines": 3, "sl_total": 317})
    assert not any("stops" in x["quoi"] for x in p)


def test_la_note_inversee_est_signalee():
    p = ce.sante(ce.Etat(), [], {"calibration_inversee": "17 % contre 25 %"})
    assert any("inversée" in x["quoi"] for x in p)
    assert any("ne PAS filtrer" in x["action"] for x in p)


def test_zero_poids_mesure_est_signale():
    e = ce.cycle(journal(100), ce.Etat(), {"argument": {"a": 1.0}})
    e.poids["argument"]["a"] = 0.0
    assert any("aucun poids mesuré" in x["quoi"] for x in ce.sante(e, []))


def test_chaque_probleme_dit_quoi_faire():
    p = ce.sante(ce.Etat(n_resolus=100, version=1), [],
                 {"sl_indetermines": 314, "sl_total": 317})
    for x in p:
        assert x["action"] and x["pourquoi"] and x["effet"]


# --- persistance ------------------------------------------------------
def test_l_etat_fait_l_aller_retour_sur_disque(tmp_path):
    e = ce.cycle(journal(100), ce.Etat(), cal(a=1.0, b=0.6))
    f = tmp_path / "cerveau.json"
    ce.sauver(e, f)
    relu = ce.charger(f)
    assert relu.version == e.version and relu.poids == e.poids


def test_un_fichier_absent_donne_un_etat_neuf(tmp_path):
    assert ce.charger(tmp_path / "rien.json").version == 0


def test_un_fichier_corrompu_ne_bloque_pas_le_demarrage(tmp_path):
    """Un état illisible ne doit pas empêcher le site de s'ouvrir."""
    f = tmp_path / "casse.json"
    f.write_text("{ ceci n'est pas du json", encoding="utf-8")
    assert ce.charger(f).version == 0


def test_un_fichier_avec_des_champs_inconnus_est_tolere(tmp_path):
    f = tmp_path / "futur.json"
    f.write_text(json.dumps({"version": 3, "champ_du_futur": 42}), encoding="utf-8")
    assert ce.charger(f).version == 3


# --- le rapport -------------------------------------------------------
def test_le_rapport_ne_plante_sur_aucun_etat():
    for e in (ce.Etat(), ce.cycle(journal(100), ce.Etat(), cal(a=1.0))):
        assert isinstance(ce.rapport(e), str)
        assert isinstance(ce.rapport(e, ce.sante(e, [])), str)


def test_le_rapport_liste_ce_qui_a_ete_appris():
    e = ce.cycle(journal(100), ce.Etat(), cal(stop_dans_le_bruit=1.4))
    assert "stop_dans_le_bruit" in ce.rapport(e)


def test_le_rapport_dit_quand_rien_n_a_ete_appris():
    assert "n'a encore rien modifié" in ce.rapport(ce.Etat())


def test_le_rapport_nomme_les_problemes_bloquants():
    e = ce.cycle(journal(100), ce.Etat(), cal(a=1.0))
    r = ce.rapport(e, ce.sante(e, [], {"sl_indetermines": 314, "sl_total": 317}))
    assert "🔴" in r and "étape 1" in r
