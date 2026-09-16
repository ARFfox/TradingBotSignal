#!/usr/bin/env python3
"""
Les quatre outils statistiques dont tout le reste du projet dépend.

Aucune dépendance : ni scipy, ni numpy. Ces fonctions sont appelées par
`chercheur_sous_ensembles`, `parametres_agents` et `avocats`, et les avoir
en trois exemplaires garantissait qu'un jour deux versions divergeraient.

Ce qu'elles protègent contre
----------------------------
Le projet a produit 548 signaux et 288 résolus. À cette échelle, trois
erreurs de raisonnement suffisent à fabriquer une stratégie imaginaire :

  · comparer un taux de réussite à 50 % au lieu du hasard réel  → `taux_hasard`
  · annoncer « 80 % » sans dire sur combien de trades            → `wilson`
  · chercher parmi 43 hypothèses et garder la meilleure          → `z_corrige`
  · confondre un écart de moyenne avec un écart réel             → `marge_bruit`

Ce sont les quatre façons dont un backtest honnête ment sans le vouloir.
"""
from __future__ import annotations

import math

Z_BASE = 1.96        # bilatéral 95 %
Z_UNILATERAL = 1.64  # « meilleur que rien », question à un seul sens


def taux_hasard(rr: float) -> float:
    """Taux de réussite d'une marche aléatoire à ce rapport gain/risque.

    P(toucher +rr avant −1) = 1 / (1 + rr).

    C'est LA référence, et elle est presque toujours absente des discussions
    de trading. À un R:R de 2,09, une pièce lancée touche le TP 32,4 % du
    temps. Un système à 23,6 % ne « manque pas un peu son objectif » : il
    prédit moins bien que le hasard, et le plus souvent parce que ses stops
    sont placés à l'intérieur du bruit.
    """
    return 1.0 / (1.0 + rr) if rr > 0 else 0.0


def wilson(succes: int, n: int, z: float = Z_BASE) -> tuple[float, float]:
    """Intervalle de confiance de Wilson.

    Correct sur petits effectifs, contrairement à l'intervalle normal qui
    produit des bornes au-dessus de 100 % quand le taux est élevé.

    Il existe pour rendre visible une chose simple : 4 réussites sur 5 et
    160 sur 200 sont deux affirmations très différentes, et seule la
    seconde autorise à dire « 80 % ».
    """
    if n <= 0:
        return 0.0, 1.0
    p = succes / n
    d = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    demi = z / d * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return max(0.0, centre - demi), min(1.0, centre + demi)


def z_corrige(n_tests: int, alpha: float = 0.05) -> float:
    """Correction de Bonferroni pour un test répété `n_tests` fois.

    Tester 200 hypothèses au seuil de 5 % produit ~10 faux positifs. Sans
    cette correction, une recherche trouve toujours un gagnant — et il a
    toujours tort.

    ⚠️ Elle s'applique à la RECHERCHE, pas à la VÉRIFICATION. Une fois un
    motif choisi, le tester sur des données jamais vues est UN test, pas
    `n_tests`. Lui appliquer la même correction reviendrait à jeter une
    preuve indépendante.
    """
    if n_tests <= 1:
        return _quantile_normale(1 - alpha / 2)
    return _quantile_normale(1 - alpha / (2 * n_tests))


def marge_bruit(echantillon: list[float], n_tests: int = 1,
                z_min: float | None = None) -> float:
    """L'écart qu'il faut dépasser pour ne pas être du bruit.

    `echantillon` : les écarts mesurés (par exemple le gain hors échantillon
    de chaque découpe). On renvoie `z × erreur-type`, avec `z` corrigé du
    nombre de valeurs essayées pendant la recherche.

    Sans ceci, un balayage sur 9 valeurs accepte du bruit pur environ une
    fois sur cinq : 4 découpes favorables sur 4 arrivent par hasard dans
    6 % des cas, et neuf tentatives suffisent à tomber dessus.
    """
    n = len(echantillon)
    if n < 2:
        return float("inf")     # on ne certifie rien sur une seule mesure
    moyenne = sum(echantillon) / n
    variance = sum((x - moyenne) ** 2 for x in echantillon) / (n - 1)
    erreur = math.sqrt(variance / n)
    z = z_corrige(n_tests) if z_min is None else max(z_corrige(n_tests), z_min)
    return z * erreur


def _quantile_normale(p: float) -> float:
    """Inverse de la loi normale centrée réduite (Abramowitz & Stegun 26.2.23).

    Précision ~4,5e-4, largement suffisante : on s'en sert pour décider
    « significatif / pas significatif », pas pour publier une p-valeur.
    """
    p = min(max(p, 1e-12), 1 - 1e-12)
    if p < 0.5:
        return -_quantile_normale(1 - p)
    t = math.sqrt(-2.0 * math.log(1 - p))
    return t - (2.515517 + 0.802853 * t + 0.010328 * t * t) / \
        (1 + 1.432788 * t + 0.189269 * t * t + 0.001308 * t * t * t)


if __name__ == "__main__":
    print("Taux de réussite d'une marche au hasard :")
    for rr in (1.0, 1.5, 2.0, 2.09, 3.0, 5.0):
        print(f"  R:R {rr:>4.2f}  →  {taux_hasard(rr):>5.1%}")
    print("\n« 80 % de réussite », selon l'effectif :")
    for n in (5, 10, 20, 50, 100, 200, 500):
        b, h = wilson(round(0.8 * n), n)
        print(f"  {round(0.8 * n):>3}/{n:<4} → [{b:>5.1%} – {h:>5.1%}]"
              + ("   ne prouve rien" if b < 0.65 else ""))
    print("\nSeuil z après correction pour n hypothèses testées :")
    for n in (1, 5, 9, 43, 200):
        print(f"  {n:>3} tests → z = {z_corrige(n):.2f}")
