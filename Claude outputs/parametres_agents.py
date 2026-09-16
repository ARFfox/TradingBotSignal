#!/usr/bin/env python3
"""
AG-00 / NIVEAU 2 — le superviseur règle les paramètres des agents.

    python3 parametres_agents.py          # démonstration

Le superviseur apprend à trois niveaux
---------------------------------------
  NIVEAU 1  les POIDS   — combien écouter chaque agent   (superviseur_apprenant)
  NIVEAU 2  les RÉGLAGES — ce module                      ← ici
  NIVEAU 3  la LOGIQUE  — le code de l'analyse            (Claude Code + toi)

Pourquoi le niveau 2 change tout
---------------------------------
Baisser le poids d'un agent qui se trompe ARRÊTE les dégâts, mais ne crée
aucune valeur : un agent à ×0,1 est un agent qu'on a fait taire. Le rendre
MEILLEUR demande de changer ce qu'il calcule.

Or l'essentiel de ce qu'un agent calcule dépend de quelques nombres : la
période d'une moyenne, le multiple d'ATR d'un stop, un seuil de RSI, la
profondeur d'un pivot. Ces nombres, le superviseur peut les chercher tout
seul dans des bornes déclarées — sans réécrire une ligne de code.

C'est ça, « le superviseur développe les agents ».

LE PIÈGE, et c'est le plus grave du projet
-------------------------------------------
Chercher le meilleur réglage sur les mêmes données qui servent à le juger
trouve TOUJOURS un gagnant, même dans du bruit pur. Sur 288 signaux et
15 valeurs testées, un réglage sortira à +0,4R par pur hasard. On le met
en production, et il perd.

D'où la règle appliquée ici sans exception : on cherche sur le PASSÉ, on
juge sur un FUTUR jamais vu, et on n'accepte le changement que s'il tient
hors échantillon sur plusieurs découpes. La plupart des candidats seront
rejetés. C'est le fonctionnement normal, pas un échec.
"""
from __future__ import annotations

import json
import statistics
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Callable

# --------------------------------------------------------------------------
N_DECOUPES = 4            # découpes chronologiques train/test
PART_TEST = 0.30          # part de chaque découpe réservée au test
N_MIN_TEST = 25           # signaux résolus minimum dans un test
MARGE_BRUIT = 0.05        # gain hors échantillon minimal, en R par signal
PART_DECOUPES_OK = 0.75   # part des découpes qui doivent confirmer le gain
JOURNAL = Path.home() / ".parametres_agents.json"


@dataclass
class Parametre:
    """Un réglage qu'un agent expose au superviseur.

    Les bornes sont des GARDE-FOUS : le superviseur cherche à l'intérieur
    et n'a jamais le droit de les déplacer. Un stop minimum à 1 ATR reste
    à 1 ATR même si une série chanceuse suggère 0,3.
    """
    agent: str
    nom: str
    valeur: float
    mini: float
    maxi: float
    pas: float
    unite: str = ""
    raison_bornes: str = ""

    def candidats(self) -> list[float]:
        out, x = [], self.mini
        while x <= self.maxi + 1e-9:
            out.append(round(x, 6))
            x += self.pas
        return out

    def borner(self, v: float) -> float:
        return max(self.mini, min(self.maxi, v))


@dataclass
class Resultat:
    parametre: str
    agent: str
    ancienne: float
    proposee: float
    gain_hors_echantillon: float      # R par signal
    decoupes_favorables: int
    decoupes_total: int
    n_test_total: int
    accepte: bool
    motif: str

    def ligne(self) -> str:
        fleche = "→" if self.accepte else "✗"
        return (f"  {self.agent} · {self.parametre:<16} "
                f"{self.ancienne:g} {fleche} {self.proposee:g}   "
                f"{self.gain_hors_echantillon:+.3f}R/signal   "
                f"{self.decoupes_favorables}/{self.decoupes_total} découpes   "
                f"{self.motif}")


# --------------------------------------------------------------------------
def decouper(signaux: list, n: int = N_DECOUPES) -> list[tuple[list, list]]:
    """Découpes chronologiques croissantes (walk-forward).

    Découpe 1 : on apprend sur le début, on juge sur la suite.
    Découpe 2 : on apprend sur un passé plus long, on juge sur la suite.
    ...
    Jamais l'inverse : apprendre sur le futur pour juger le passé donne
    des résultats magnifiques et totalement faux.
    """
    s = sorted(signaux, key=lambda x: x.cree_ts)
    total = len(s)
    out = []
    for i in range(1, n + 1):
        fin = int(total * (i / n))
        coupe = int(fin * (1 - PART_TEST))
        train, test = s[:coupe], s[coupe:fin]
        if len(train) >= N_MIN_TEST and len(test) >= N_MIN_TEST:
            out.append((train, test))
    return out


def _esperance(signaux: list) -> float | None:
    r = [s.r_realise for s in signaux if s.r_realise is not None]
    return sum(r) / len(r) if r else None


# --------------------------------------------------------------------------
def evaluer_parametre(
    signaux: list,
    param: Parametre,
    rejouer: Callable[[list, float], list],
) -> Resultat:
    """Cherche la meilleure valeur d'un paramètre, et vérifie qu'elle tient.

    `rejouer(signaux, valeur)` est fourni par l'agent : il rejoue les
    signaux historiques comme s'ils avaient été produits avec cette
    valeur, et renvoie la liste avec les statuts recalculés.

    C'est le contrat que chaque agent doit implémenter pour que le
    superviseur puisse le faire progresser. Sans lui, un agent ne peut
    pas être réglé — seulement écouté plus ou moins fort.
    """
    decoupes = decouper(signaux)
    if not decoupes:
        return Resultat(param.nom, param.agent, param.valeur, param.valeur,
                        0.0, 0, 0, 0, False,
                        "pas assez d'historique pour une validation honnête")

    gains, favorables, n_test, choix = [], 0, 0, []

    for train, test in decoupes:
        # --- recherche sur le TRAIN uniquement --------------------------
        meilleur, meilleure_esp = param.valeur, None
        for v in param.candidats():
            e = _esperance(rejouer(train, v))
            if e is not None and (meilleure_esp is None or e > meilleure_esp):
                meilleur, meilleure_esp = v, e
        choix.append(meilleur)

        # --- jugement sur le TEST, jamais vu ----------------------------
        rejoue_ref = rejouer(test, param.valeur)
        rejoue_new = rejouer(test, meilleur)
        e_ref, e_new = _esperance(rejoue_ref), _esperance(rejoue_new)
        if e_ref is None or e_new is None:
            continue
        gains.append(e_new - e_ref)
        # Compter les résolus du REJEU, pas de l'entrée : les signaux
        # d'origine sont encore "en_attente" tant qu'ils n'ont pas été
        # rejoués. Compter les mauvais rendait l'effectif toujours nul,
        # donc tout changement était refusé — un module qui refuse tout
        # est aussi cassé qu'un module qui accepte tout.
        n_test += sum(1 for x in rejoue_new if x.resolu)
        if e_new - e_ref > MARGE_BRUIT:
            favorables += 1

    if not gains:
        return Resultat(param.nom, param.agent, param.valeur, param.valeur,
                        0.0, 0, len(decoupes), 0, False,
                        "aucune découpe exploitable")

    gain = statistics.median(gains)          # médiane : une découpe
    prop = statistics.median(choix)          # exceptionnelle ne décide pas
    prop = param.borner(round(prop / param.pas) * param.pas)

    part = favorables / len(gains)
    if prop == param.valeur:
        ok, motif = False, "la valeur actuelle est déjà la meilleure"
    elif gain <= MARGE_BRUIT:
        ok, motif = False, f"gain sous la marge de bruit ({MARGE_BRUIT}R)"
    elif part < PART_DECOUPES_OK:
        ok, motif = False, (f"ne tient que sur {favorables}/{len(gains)} "
                            f"découpes — probablement du hasard")
    elif n_test < N_MIN_TEST * 2:
        ok, motif = False, f"seulement {n_test} signaux hors échantillon"
    else:
        ok, motif = True, "confirmé hors échantillon"

    return Resultat(param.nom, param.agent, param.valeur, prop,
                    round(gain, 4), favorables, len(gains), n_test, ok, motif)


# --------------------------------------------------------------------------
class Tuner:
    """Le superviseur au niveau 2. Il propose, il journalise, il n'impose pas."""

    def __init__(self, journal: Path | None = JOURNAL):
        self.journal = journal

    def passe(self, signaux: list,
              params: list[Parametre],
              rejoueurs: dict[str, Callable]) -> list[Resultat]:
        """Une passe complète. Un paramètre à la fois — jamais deux ensemble.

        Optimiser deux réglages simultanément multiplie l'espace de
        recherche, donc les faux positifs, et rend impossible de savoir
        lequel des deux a apporté le gain quand il y en a un.
        """
        out = []
        for p in params:
            f = rejoueurs.get(f"{p.agent}.{p.nom}") or rejoueurs.get(p.agent)
            if f is None:
                out.append(Resultat(p.nom, p.agent, p.valeur, p.valeur,
                                    0.0, 0, 0, 0, False,
                                    "aucun rejoueur — l'agent ne sait pas se rejouer"))
                continue
            out.append(evaluer_parametre(signaux, p, f))
        self._journaliser(out)
        return out

    def appliquer(self, params: list[Parametre],
                  resultats: list[Resultat]) -> dict[str, float]:
        """N'applique QUE les résultats acceptés, et réaffirme les bornes."""
        index = {(p.agent, p.nom): p for p in params}
        applique = {}
        for r in resultats:
            if not r.accepte:
                continue
            p = index.get((r.agent, r.parametre))
            if p is None:
                continue
            p.valeur = p.borner(r.proposee)
            applique[f"{r.agent}.{r.parametre}"] = p.valeur
        return applique

    def _journaliser(self, resultats: list[Resultat]) -> None:
        """Tout changement doit être réversible et explicable.

        Un système qui se modifie sans trace est un système qu'on ne peut
        pas déboguer le jour où il se dégrade — et on ne saura même pas
        qu'il s'est dégradé.
        """
        if not self.journal:
            return
        try:
            hist = json.loads(self.journal.read_text()) if self.journal.exists() else []
        except Exception:
            hist = []
        hist.append({"resultats": [asdict(r) for r in resultats]})
        self.journal.write_text(json.dumps(hist[-200:], ensure_ascii=False, indent=1))


# --------------------------------------------------------------------------
# Les paramètres que les agents exposent. Chaque borne a une RAISON.
# --------------------------------------------------------------------------
PARAMETRES_DEFAUT = [
    Parametre("AG-03", "stop_atr", 1.0, 1.0, 3.0, 0.25, "ATR",
              "sous 1 ATR le stop est dans le bruit du timeframe"),
    Parametre("AG-03", "rr_minimum", 1.5, 1.2, 3.0, 0.1, "R",
              "sous 1,2 les coûts mangent l'espérance"),
    Parametre("AG-02", "ema_rapide", 20, 8, 34, 2, "bougies",
              "hors de cette plage ce n'est plus une moyenne courte"),
    Parametre("AG-02", "ema_lente", 50, 34, 200, 8, "bougies", ""),
    Parametre("AG-02", "rsi_periode", 14, 7, 28, 1, "bougies", ""),
    Parametre("AG-04", "pivot_profondeur", 3, 2, 8, 1, "bougies",
              "sous 2 tout devient un pivot"),
    Parametre("AG-00", "confluence_min", 0.65, 0.40, 0.90, 0.05, "",
              "sous 0,40 on émet du bruit ; au-dessus de 0,90 on n'émet plus"),
    Parametre("AG-10", "base_minimale", 1.0, 0.5, 2.5, 0.25, "",
              "en dessous le score intermarché repose sur trop peu"),
]


def rapport(resultats: list[Resultat]) -> str:
    L = "=" * 78
    acc = [r for r in resultats if r.accepte]
    o = [L, "  SUPERVISEUR — RÉGLAGE DES AGENTS (niveau 2)", L, "",
         f"  {len(acc)} changement(s) retenu(s) sur {len(resultats)} testé(s)", ""]
    for r in resultats:
        o.append(r.ligne())
    if not acc:
        o += ["", "  Aucun changement retenu — et c'est le résultat le plus",
              "  fréquent. Un réglage qui ne tient pas hors échantillon est",
              "  du hasard : l'appliquer coûterait de l'argent."]
    o.append("")
    return "\n".join(o)


# --------------------------------------------------------------------------
if __name__ == "__main__":
    import random
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "sa", Path(__file__).parent / "superviseur_apprenant.py")
    sa = importlib.util.module_from_spec(spec)
    import sys as _s
    _s.modules["sa"] = sa
    spec.loader.exec_module(sa)

    rng = random.Random(11)
    base = []
    for i in range(400):
        e, risque = 100.0, 10.0
        base.append(sa.Signal(
            id=f"s{i}", instrument="XAUUSD", marche="matieres", tf="H1",
            sens="achat", entree=e, sl=e - risque, tp=e + 2 * risque,
            note=rng.uniform(0.3, 0.8), cree_ts=1_750_000_000 + i * 3600,
            statut="en_attente", atr=10.0))

    def rejoueur_stop(signaux, valeur):
        """Simulation : un stop plus large est moins souvent touché, mais
        coûte plus cher quand il l'est. L'optimum est au milieu — c'est
        exactement la forme qu'a le vrai problème."""
        out = []
        for s in signaux:
            c = sa.Signal(**{k: getattr(s, k) for k in
                             ("id", "instrument", "marche", "tf", "sens",
                              "entree", "sl", "tp", "note", "cree_ts",
                              "statut", "atr")})
            p_tp = min(0.95, 0.18 + 0.16 * valeur)     # plus large -> survit
            r = random.Random(hash((s.id, round(valeur, 3))) & 0xFFFF).random()
            c.statut = "TP" if r < p_tp else "SL"
            c.sl = c.entree - valeur * c.atr
            c.tp = c.entree + 2.0 * valeur * c.atr * 0.75 / max(valeur, .01)
            out.append(c)
        return out

    res = Tuner(journal=None).passe(
        base, [p for p in PARAMETRES_DEFAUT if p.nom == "stop_atr"],
        {"AG-03": rejoueur_stop})
    print(rapport(res))
