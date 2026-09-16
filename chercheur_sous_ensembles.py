#!/usr/bin/env python3
"""
CHERCHEUR DE SOUS-ENSEMBLES — existe-t-il un 80 % dans tes données ?

    python3 chercheur_sous_ensembles.py            # démonstration
    python3 chercheur_sous_ensembles.py journal.json

La question posée
-----------------
« Je veux 80 % de TP touchés, SANS rapprocher le TP. »

C'est la bonne façon de poser le problème : on ne triche pas sur la
distance, on sélectionne mieux. Ce module cherche, parmi les signaux déjà
émis, s'il existe un sous-ensemble qui atteint ce taux — et il le fait
avec les garde-fous qui empêchent de se mentir.

La seule référence qui a du sens
---------------------------------
Avec un TP à 2,09R et un SL à 1R, une marche aléatoire touche le TP
**32,3 % du temps** : P = 1/(1+2,09). Ce n'est pas un chiffre arbitraire,
c'est le taux qu'on obtient SANS AUCUNE capacité de prédiction.

Donc :
  · 32,3 %  = aucun edge, on paie juste les frais
  · 23,6 %  = le taux actuel — SOUS le hasard
  · 80,0 %  = il faut une dérive **790 fois** celle du cas sans edge

Comparer un taux à 50 % n'a aucun sens. La seule comparaison honnête est
celle au hasard **à ce R:R précis**, et c'est ce que fait ce module.

Les trois garde-fous
--------------------
1. MAX 2 CONDITIONS combinées. Au-delà, on ne sélectionne plus, on
   mémorise : avec assez de conditions on isole toujours les gagnants.
2. INTERVALLE DE CONFIANCE, corrigé pour le nombre de tests. « 80 % sur
   20 trades » veut dire « entre 59 % et 93 % » — ce n'est pas un système
   à 80 %. C'est la BORNE BASSE qu'on retient pour décider.
3. VÉRIFICATION HORS ÉCHANTILLON. Le sous-ensemble est trouvé sur le
   passé et jugé sur un futur jamais vu.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from itertools import combinations
from typing import Callable

# --------------------------------------------------------------------------
N_MIN = 20                # résolus minimum dans un sous-ensemble
MAX_CONDITIONS = 2        # au-delà, c'est de la mémorisation
PART_TEST = 0.30          # part réservée à la vérification
Z_BASE = 1.96             # 95 % avant correction des tests multiples


# ==========================================================================
def taux_hasard(rr: float) -> float:
    """Taux de réussite d'une marche aléatoire à ce R:R.

    P(toucher +rr avant -1) = 1 / (1 + rr). C'est LA référence : tout
    taux en dessous signifie que le système prédit moins bien qu'une
    pièce — le plus souvent parce que les stops sont dans le bruit.
    """
    return 1.0 / (1.0 + rr) if rr > 0 else 0.0


def wilson(succes: int, n: int, z: float = Z_BASE) -> tuple[float, float]:
    """Intervalle de Wilson. Pas de dépendance, et correct sur petits
    effectifs — contrairement à l'intervalle normal, qui donne des bornes
    au-dessus de 100 % quand le taux est élevé."""
    if n == 0:
        return 0.0, 1.0
    p = succes / n
    d = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    demi = z / d * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return max(0.0, centre - demi), min(1.0, centre + demi)


def z_corrige(n_tests: int) -> float:
    """Correction de Bonferroni. Tester 200 sous-ensembles au seuil de 5 %
    produit ~10 faux positifs. Sans cette correction, le module trouverait
    toujours un « 80 % » et il aurait toujours tort."""
    if n_tests <= 1:
        return Z_BASE
    alpha = 0.05 / n_tests
    # approximation de la quantile normale (Beasley-Springer-Moro simplifié)
    p = 1 - alpha / 2
    t = math.sqrt(-2.0 * math.log(1 - p))
    return t - (2.515517 + 0.802853 * t + 0.010328 * t * t) / \
        (1 + 1.432788 * t + 0.189269 * t * t + 0.001308 * t * t * t)


# ==========================================================================
@dataclass
class Condition:
    nom: str
    test: Callable


@dataclass
class SousEnsemble:
    conditions: list[str]
    n: int
    tp: int
    taux: float
    ic_bas: float
    ic_haut: float
    r_total: float
    esperance: float
    reference: float              # taux d'une marche aléatoire
    n_hors: int = 0
    taux_hors: float | None = None
    verdict: str = ""
    motif: str = ""

    def ligne(self) -> str:
        h = f"{self.taux_hors:.0%}" if self.taux_hors is not None else "—"
        return (f"  {' + '.join(self.conditions):<40} "
                f"n={self.n:<4} {self.taux:>5.0%} "
                f"[{self.ic_bas:.0%}–{self.ic_haut:.0%}]  "
                f"{self.esperance:>+6.2f}R  hors:{h:>4}  {self.verdict}")


# ==========================================================================
def _stats(lot: list, reference: float, z: float) -> dict:
    tp = sum(1 for s in lot if s.statut == "TP")
    n = len(lot)
    r = sum(s.r_realise for s in lot)
    bas, haut = wilson(tp, n, z)
    return {"n": n, "tp": tp, "taux": tp / n, "ic_bas": bas, "ic_haut": haut,
            "r_total": r, "esperance": r / n, "reference": reference}


def chercher(signaux: list, conditions: list[Condition],
             cible: float = 0.80) -> list[SousEnsemble]:
    """Cherche les sous-ensembles qui battent le hasard, et vérifie qu'ils
    tiennent hors échantillon."""
    res = [s for s in signaux if s.resolu]
    if len(res) < N_MIN * 2:
        return []

    res.sort(key=lambda s: s.cree_ts)
    coupe = int(len(res) * (1 - PART_TEST))
    train, test = res[:coupe], res[coupe:]

    rr_moyen = sum(s.rr for s in res) / len(res)
    reference = taux_hasard(rr_moyen)

    # Combinaisons de 1 à MAX_CONDITIONS
    combos = []
    for k in range(1, MAX_CONDITIONS + 1):
        combos += list(combinations(conditions, k))
    z = z_corrige(len(combos))

    out = []
    for combo in combos:
        garde = lambda s: all(c.test(s) for c in combo)
        lot_tr = [s for s in train if garde(s)]
        if len(lot_tr) < N_MIN:
            continue

        st = _stats(lot_tr, reference, z)
        lot_te = [s for s in test if garde(s)]
        taux_hors = (sum(1 for s in lot_te if s.statut == "TP") / len(lot_te)
                     if lot_te else None)

        se = SousEnsemble(conditions=[c.nom for c in combo],
                          n_hors=len(lot_te), taux_hors=taux_hors, **st)

        # --- verdict ------------------------------------------------------
        # Deux preuves de nature différente, et il ne faut pas les confondre :
        #
        #   · l'ÉCHANTILLON D'APPRENTISSAGE sert à TROUVER le motif. C'est là
        #     qu'on teste 43 hypothèses, donc c'est là que la correction de
        #     Bonferroni s'applique — sinon on trouve toujours quelque chose.
        #
        #   · le HORS ÉCHANTILLON sert à le VÉRIFIER. Le motif y arrive déjà
        #     choisi : c'est UN test, pas 43. Lui appliquer la même correction
        #     reviendrait à jeter une preuve indépendante.
        #
        # Première version de ce module : elle classait « HASARD » un motif à
        # 50 % en apprentissage et 67 % hors échantillon. Un module qui rejette
        # ça est aussi inutile qu'un module qui accepte tout.
        assez_hors = len(lot_te) >= max(10, N_MIN // 2)
        bat_train = se.taux > reference
        bat_hors = taux_hors is not None and taux_hors > reference

        if not bat_train:
            se.verdict = "HASARD"
            se.motif = (f"{se.taux:.0%} en apprentissage, sous le hasard "
                        f"({reference:.0%})")
        elif not assez_hors:
            se.verdict = "NON VÉRIFIÉ"
            se.motif = f"seulement {len(lot_te)} signaux hors échantillon"
        elif not bat_hors:
            se.verdict = "NON CONFIRMÉ"
            se.motif = (f"beau sur le passé ({se.taux:.0%}), s'effondre "
                        f"hors échantillon ({taux_hors:.0%})")
        elif se.ic_bas >= cible:
            se.verdict = f"ATTEINT {cible:.0%}"
            se.motif = ("confirmé hors échantillon ET borne basse corrigée "
                        "au-dessus de la cible")
        elif se.ic_bas > reference:
            se.verdict = "EDGE SOLIDE"
            se.motif = (f"confirmé hors échantillon ({taux_hors:.0%}) et borne "
                        f"basse {se.ic_bas:.0%} au-dessus du hasard")
        else:
            se.verdict = "PROMETTEUR"
            se.motif = (f"confirmé hors échantillon ({taux_hors:.0%}) mais "
                        f"l'effectif ne suffit pas encore à le prouver "
                        f"(borne basse {se.ic_bas:.0%})")
        out.append(se)

    rang = {"ATTEINT": 0, "EDGE SOLIDE": 1, "PROMETTEUR": 2,
            "NON CONFIRMÉ": 3, "NON VÉRIFIÉ": 4, "HASARD": 5}
    cle = lambda s: (rang.get(s.verdict.split()[0] if s.verdict.startswith("ATTEINT")
                              else s.verdict, 9), -s.esperance)
    return sorted(out, key=cle)


# ==========================================================================
def conditions_standard() -> list[Condition]:
    """Les découpes qui ont une chance de porter de l'information.

    Toutes sont connues AU MOMENT DE L'ÉMISSION. Une condition qui utilise
    une information postérieure produirait un résultat magnifique et
    totalement inutilisable — c'est la fuite de données la plus courante.
    """
    return [
        Condition("note >= 40 %", lambda s: s.note >= 0.40),
        Condition("note >= 60 %", lambda s: s.note >= 0.60),
        Condition("stop >= 1,5 ATR", lambda s: (s.sl_en_atr or 0) >= 1.5),
        Condition("stop >= 2 ATR", lambda s: (s.sl_en_atr or 0) >= 2.0),
        Condition("R:R >= 2,5", lambda s: s.rr >= 2.5),
        Condition("timeframe H1/H4", lambda s: s.tf in ("H1", "H4")),
        Condition("timeframe M5/M15", lambda s: s.tf in ("M5", "M15")),
        Condition("achat", lambda s: s.sens == "achat"),
        Condition("vente", lambda s: s.sens == "vente"),
        Condition("3+ agents d'accord", lambda s: sum(
            1 for a in s.agents.values()
            if a == ("haussier" if s.sens == "achat" else "baissier")) >= 3),
        Condition("Miroir confirme", lambda s: (
            getattr(s, "intermarche", None) or {}).get("score", 0) > 0.3),
        Condition("marché matières", lambda s: s.marche == "matieres"),
        Condition("marché crypto", lambda s: s.marche == "crypto"),
    ]


def rapport(signaux: list, cible: float = 0.80) -> str:
    res = [s for s in signaux if s.resolu]
    L = "=" * 100
    o = [L, f"  EXISTE-T-IL UN SOUS-ENSEMBLE À {cible:.0%} DANS TES DONNÉES ?", L, ""]

    if len(res) < N_MIN * 2:
        return "\n".join(o + [f"  {len(res)} résolus — il en faut {N_MIN*2}.", ""])

    rr = sum(s.rr for s in res) / len(res)
    ref = taux_hasard(rr)
    tp = sum(1 for s in res if s.statut == "TP")
    o += [f"  Référence : R:R moyen {rr:.2f} → une marche ALÉATOIRE touche "
          f"le TP {ref:.1%} du temps.",
          f"  Taux global actuel : {tp/len(res):.1%} sur {len(res)} résolus.",
          ""]
    if tp / len(res) < ref:
        o += ["  ⚠ Le système est SOUS le hasard. Ce n'est pas « pas encore "
              "assez bon » :",
              "    c'est une capacité de prédiction négative. La cause la plus "
              "probable est",
              "    un stop placé dans le bruit — le prix le touche avant "
              "d'avoir bougé.", ""]

    trouves = chercher(signaux, conditions_standard(), cible)
    if not trouves:
        return "\n".join(o + ["  Aucun sous-ensemble assez fourni pour conclure.", ""])

    o += [f"  {len(trouves)} sous-ensembles testés (correction des tests "
          f"multiples appliquée)", "",
          f"  {'conditions':<40} {'n':<6} {'taux':>5} {'IC 95%':>12}  "
          f"{'espér.':>7}  hors  verdict", "  " + "-" * 96]
    for s in trouves[:15]:
        o.append(s.ligne())

    atteints = [s for s in trouves if s.verdict.startswith("ATTEINT")]
    edges = [s for s in trouves if s.verdict in ("EDGE SOLIDE", "PROMETTEUR")]

    o += ["", "  " + "=" * 96, ""]
    if atteints:
        o += [f"  ✅ {len(atteints)} sous-ensemble(s) atteignent {cible:.0%} "
              f"de façon défendable :", ""]
        for s in atteints:
            o.append(f"     {' + '.join(s.conditions)} — {s.motif}")
    elif edges:
        m = max(edges, key=lambda s: s.ic_bas)
        o += [f"  Aucun sous-ensemble n'atteint {cible:.0%}.",
              f"  Le meilleur edge confirmé : {' + '.join(m.conditions)}",
              f"     {m.taux:.0%} observé, borne basse {m.ic_bas:.0%}, "
              f"espérance {m.esperance:+.2f}R sur {m.n} signaux.", "",
              f"  Une espérance de {m.esperance:+.2f}R est déjà un système "
              f"rentable.",
              "  Le taux affiché compte moins que ce chiffre-là."]
    else:
        o += [f"  Aucun sous-ensemble ne bat le hasard de façon confirmée.",
              "",
              "  Ce n'est pas un problème de sélection : il n'y a rien à",
              "  sélectionner. Le travail est dans les conditions d'entrée",
              "  et dans le placement des stops, pas dans le filtrage."]
    o.append("")
    return "\n".join(o)


# ==========================================================================
if __name__ == "__main__":
    import sys, random, importlib.util
    from pathlib import Path

    spec = importlib.util.spec_from_file_location(
        "sa", Path(__file__).parent / "superviseur_apprenant.py")
    sa = importlib.util.module_from_spec(spec)
    sys.modules["sa"] = sa
    spec.loader.exec_module(sa)

    if len(sys.argv) > 1:
        print(rapport(sa.charger_journal(sys.argv[1])))
        sys.exit(0)

    # Jeu reproduisant ses statistiques, avec UN vrai edge caché :
    # les stops larges sur H1/H4 marchent bien mieux.
    rng = random.Random(7)
    sig = []
    for i in range(548):
        tf = rng.choice(["M5", "M15", "M30", "H1", "H4"])
        atr, e = 10.0, 100.0
        large = rng.random() < 0.35
        risque = atr * (rng.uniform(1.2, 2.2) if large else rng.uniform(0.3, 0.9))
        sens = rng.choice(["achat", "vente"])
        s = sa.Signal(
            id=f"s{i}", instrument=rng.choice(["XAUUSD", "BTCUSD", "CUIVRE"]),
            marche=rng.choice(["matieres", "crypto"]), tf=tf, sens=sens,
            entree=e,
            sl=e - risque if sens == "achat" else e + risque,
            tp=e + 2.09 * risque if sens == "achat" else e - 2.09 * risque,
            note=rng.uniform(0.20, 0.75), cree_ts=1_750_000_000 + i * 3600,
            statut="en_attente", atr=atr,
            agents={f"AG-{c:02d}": rng.choice(["haussier", "baissier", "neutre"])
                    for c in (1, 2, 3, 9, 10)})
        if rng.random() < 0.47:
            s.statut = "en_attente"
        else:
            p = 0.62 if (large and tf in ("H1", "H4")) else 0.20
            s.statut = "TP" if rng.random() < p else "SL"
        sig.append(s)
    print(rapport(sig))
