"""Tests du graphe d'agents.

Un graphe d'architecture est identique quand le système va bien et quand il
va mal — c'est pour ça qu'il ne sert à rien. Ces tests vérifient l'inverse :
que ce graphe-ci CHANGE avec l'état mesuré.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent


def _charger(nom: str):
    spec = importlib.util.spec_from_file_location(nom, RACINE / f"{nom}.py")
    m = importlib.util.module_from_spec(spec)
    sys.modules[nom] = m
    spec.loader.exec_module(m)
    return m


gr = _charger("graphe_agents")
av = _charger("avocats")


def carte(code, **kw):
    base = {"code": code, "statut": "STREAMING", "conviction": 50,
            "activites": ["—"]}
    base.update(kw)
    return base


# --- le graphe doit refléter l'état, pas le câblage -----------------------
def test_un_agent_sans_carte_ressort_muet():
    """C'est l'information la plus utile du graphe : voir qu'un agent est
    mort. Un graphe qui l'affiche quand même en vert ment."""
    g = gr.construire([carte("AG-01")])
    mort = [n for n in g.noeuds if n.id == "AG-02"][0]
    assert not mort.vivant and mort.statut == "MUET"


def test_la_taille_suit_la_conviction():
    g = gr.construire([carte("AG-01", conviction=100),
                       carte("AG-02", conviction=10)])
    t = {n.id: n.taille for n in g.noeuds}
    assert t["AG-01"] > t["AG-02"]


def test_un_agent_mort_perd_sa_couleur():
    g = gr.construire([carte("AG-01", statut="PANNE")])
    n = [x for x in g.noeuds if x.id == "AG-01"][0]
    assert not n.vivant and n.coul == "#484f58"


# --- les deux avocats ------------------------------------------------------
def test_les_deux_avocats_existent():
    """Un seul avocat, c'est un système qui connaît sa conclusion d'avance."""
    ids = {n.id for n in gr.construire().noeuds}
    assert "AG-16" in ids and "AG-18" in ids


def test_les_deux_avocats_parlent_au_superviseur():
    assert "AG-16" in gr.AGENTS["AG-00"]["ecoute"]
    assert "AG-18" in gr.AGENTS["AG-00"]["ecoute"]


def test_la_defense_produit_un_lien_de_confirmation():
    g = gr.construire([carte("AG-18")], defense={"cible": "AG-03",
                                                 "arguments": ["a", "b"]})
    l = [x for x in g.liens if x.de == "AG-18" and x.type == "confirme"]
    assert l and "2 argument" in l[0].etiquette


def test_un_avocat_muet_ne_produit_aucun_lien():
    """Son silence doit se voir comme un nœud gris, pas se déguiser en
    accord."""
    g = gr.construire([carte("AG-18")], defense={"arguments": []})
    assert not [x for x in g.liens if x.de == "AG-18" and x.type != "alimente"]


# --- positions pour / contre / neutre -------------------------------------
def test_les_trois_positions_sont_lues():
    g = gr.construire([carte("AG-02", position="pour"),
                       carte("AG-04", position="contre"),
                       carte("AG-05", position="neutre")])
    p = {n.id: n.position for n in g.noeuds}
    assert (p["AG-02"], p["AG-04"], p["AG-05"]) == ("pour", "contre", "neutre")


def test_une_position_absente_vaut_neutre_pas_pour():
    """Le défaut doit être l'abstention. Compter un silence comme un accord
    fabriquerait une unanimité qui n'existe pas."""
    g = gr.construire([carte("AG-02")])
    assert [n for n in g.noeuds if n.id == "AG-02"][0].position == "neutre"


def test_la_position_n_est_jamais_deduite_de_la_conviction_seule():
    """Une conviction de 90 % sur « le marché est baissier » est CONTRE un
    achat et POUR une vente. Les confondre afficherait l'inverse du vrai."""
    g = gr.construire([carte("AG-02", conviction=95)])
    assert [n for n in g.noeuds if n.id == "AG-02"][0].position == "neutre"


def test_un_avis_textuel_est_traduit():
    assert gr.position_de({"avis": "contredit"}) == "contre"
    assert gr.position_de({"avis": "confirme"}) == "pour"
    assert gr.position_de({"avis": "je ne sais pas"}) == "neutre"


def test_la_balance_compte_les_trois_camps():
    g = gr.construire([carte("AG-02", position="pour"),
                       carte("AG-04", position="pour"),
                       carte("AG-05", position="contre")])
    b = g.balance()
    assert "2 pour" in b and "1 contre" in b


def test_les_sorties_ne_votent_pas():
    """La notification et toi n'êtes pas des agents : vous ne prenez pas
    position dans le décompte."""
    g = gr.construire([carte("AG-02", position="pour")])
    for n in g.noeuds:
        if n.couche == "sortie":
            assert n.position == "neutre"


# --- le pont avec avocats.py ----------------------------------------------
def test_depuis_verdict_relie_les_deux_modules():
    from dataclasses import dataclass

    @dataclass
    class S:
        id: str = "s"; instrument: str = "CUIVRE"; tf: str = "M5"
        sens: str = "achat"; entree: float = 6.50; sl: float = 6.49
        tp: float = 6.53; note: float = 0.31; statut: str = "en_attente"
        @property
        def rr(self):
            r = abs(self.entree - self.sl)
            return abs(self.tp - self.entree) / r if r else 0.0

    v = av.debat(S(), av.Contexte(atr=0.035, spread=0.003,
                                  score_intermarche=-0.45, base_fiable=True,
                                  regime_marche="baissier"))
    avocat, defense, positions = gr.depuis_verdict(v)
    assert positions["AG-16"] == "contre"
    assert positions["AG-18"] == "neutre", "la défense n'avait rien à plaider"
    assert avocat["bloque"] and not defense

    cartes = [carte("AG-16", position=positions["AG-16"]),
              carte("AG-18", position=positions["AG-18"])]
    g = gr.construire(cartes, avocat=avocat, defense=defense)
    assert [n for n in g.noeuds if n.id == "AG-16"][0].position == "contre"
    assert any(l.type == "bloque" and l.de == "AG-16" for l in g.liens)


# --- robustesse ------------------------------------------------------------
def test_un_graphe_sans_rien_ne_plante_pas():
    g = gr.construire()
    assert g.noeuds and isinstance(g.resume(), str)


def test_le_json_est_serialisable():
    import json
    json.dumps(gr.construire([carte("AG-01")]).json())


def test_une_correlation_faible_ne_cree_pas_de_lien():
    g = gr.construire(inter := None) if False else gr.construire(
        intermarches={"liens": [{"de": "forex", "vers": "crypto",
                                 "corr": 0.05, "meneur": "—", "jours": 0}]})
    assert not [l for l in g.liens if l.type == "correlation"]


def test_un_marche_inconnu_est_ignore_sans_planter():
    g = gr.construire(intermarches={"liens": [
        {"de": "obligations", "vers": "crypto", "corr": 0.8}]})
    assert not [l for l in g.liens if l.type == "correlation"]
