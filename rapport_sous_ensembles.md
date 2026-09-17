# Chasse aux sous-ensembles

généré le 2026-09-17 12:45 UTC · 841 signaux au journal · 577 résolus

```
====================================================================================================
  EXISTE-T-IL UN SOUS-ENSEMBLE À 80% DANS TES DONNÉES ?
====================================================================================================

  Référence : R:R moyen 2.48 → une marche ALÉATOIRE touche le TP 28.8% du temps.
  Taux global actuel : 28.1% sur 577 résolus.

  ⚠ Le système est SOUS le hasard. Ce n'est pas « pas encore assez bon » :
    c'est une capacité de prédiction négative. La cause la plus probable est
    un stop placé dans le bruit — le prix le touche avant d'avoir bougé.

  28 sous-ensembles testés (correction des tests multiples appliquée)

  conditions                               n       taux       IC 95%   espér.  hors  verdict
  ------------------------------------------------------------------------------------------------
  vente + marché crypto                    n=144    41% [28%–55%]   +0.24R  hors: 44%  PROMETTEUR
  note >= 40 % + marché crypto             n=45     38% [18%–63%]   +0.10R  hors: 43%  PROMETTEUR
  marché crypto                            n=181    35% [24%–48%]   +0.06R  hors: 45%  PROMETTEUR
  timeframe M5/M15 + marché crypto         n=132    33% [21%–48%]   +0.02R  hors: 44%  PROMETTEUR
  timeframe M5/M15 + vente                 n=171    30% [19%–43%]   -0.06R  hors: 33%  PROMETTEUR
  vente                                    n=243    30% [21%–41%]   -0.07R  hors: 32%  PROMETTEUR
  note >= 40 % + vente                     n=64     30% [14%–51%]   -0.08R  hors: 31%  PROMETTEUR
  R:R >= 2,5 + marché crypto               n=58     22% [9%–45%]   -0.07R  hors: 41%  HASARD
  R:R >= 2,5 + vente                       n=81     20% [9%–38%]   -0.16R  hors: 26%  HASARD
  timeframe M5/M15                         n=285    26% [18%–36%]   -0.17R  hors: 36%  HASARD
  note >= 40 % + timeframe M5/M15          n=73     23% [11%–43%]   -0.20R  hors: 36%  HASARD
  R:R >= 2,5 + timeframe M5/M15            n=102    19% [9%–35%]   -0.21R  hors: 20%  HASARD
  R:R >= 2,5                               n=138    16% [8%–29%]   -0.32R  hors: 26%  HASARD
  note >= 40 % + R:R >= 2,5                n=60     15% [5%–36%]   -0.33R  hors: 23%  HASARD
  timeframe M5/M15 + achat                 n=114    21% [11%–37%]   -0.33R  hors: 38%  HASARD

  ================================================================================================

  Aucun sous-ensemble n'atteint 80%.
  Le meilleur edge confirmé : vente + marché crypto
     41% observé, borne basse 28%, espérance +0.24R sur 144 signaux.

  Une espérance de +0.24R est déjà un système rentable.
  Le taux affiché compte moins que ce chiffre-là.

```
