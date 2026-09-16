# Chasse aux sous-ensembles

généré le 2026-09-16 15:40 UTC · 626 signaux au journal · 385 résolus

```
====================================================================================================
  EXISTE-T-IL UN SOUS-ENSEMBLE À 80% DANS TES DONNÉES ?
====================================================================================================

  Référence : R:R moyen 2.16 → une marche ALÉATOIRE touche le TP 31.6% du temps.
  Taux global actuel : 21.6% sur 385 résolus.

  ⚠ Le système est SOUS le hasard. Ce n'est pas « pas encore assez bon » :
    c'est une capacité de prédiction négative. La cause la plus probable est
    un stop placé dans le bruit — le prix le touche avant d'avoir bougé.

  26 sous-ensembles testés (correction des tests multiples appliquée)

  conditions                               n       taux       IC 95%   espér.  hors  verdict
  ------------------------------------------------------------------------------------------------
  vente + marché crypto                    n=93     34% [20%–52%]   -0.00R  hors: 42%  PROMETTEUR
  note >= 40 % + R:R >= 2,5                n=42     21% [7%–48%]   -0.04R  hors:  0%  HASARD
  note >= 40 % + vente                     n=44     27% [11%–53%]   -0.10R  hors: 29%  HASARD
  R:R >= 2,5 + vente                       n=56     20% [7%–42%]   -0.11R  hors: 25%  HASARD
  note >= 40 % + marché crypto             n=31     29% [10%–59%]   -0.12R  hors: 40%  HASARD
  R:R >= 2,5 + marché crypto               n=38     18% [6%–46%]   -0.17R  hors: 25%  HASARD
  R:R >= 2,5 + timeframe M5/M15            n=75     19% [8%–38%]   -0.17R  hors: 16%  HASARD
  marché crypto                            n=121    27% [16%–43%]   -0.21R  hors: 34%  HASARD
  R:R >= 2,5                               n=91     18% [8%–35%]   -0.22R  hors: 12%  HASARD
  vente                                    n=176    26% [16%–38%]   -0.23R  hors: 31%  HASARD
  timeframe M5/M15 + vente                 n=138    25% [15%–40%]   -0.24R  hors: 32%  HASARD
  timeframe M5/M15 + marché crypto         n=100    27% [15%–44%]   -0.24R  hors: 33%  HASARD
  note >= 40 % + timeframe M5/M15          n=67     21% [9%–42%]   -0.26R  hors:  0%  HASARD
  timeframe M5/M15                         n=207    23% [15%–35%]   -0.29R  hors: 23%  HASARD
  achat + marché matières                  n=29     21% [6%–53%]   -0.33R  hors: 17%  HASARD

  ================================================================================================

  Aucun sous-ensemble n'atteint 80%.
  Le meilleur edge confirmé : vente + marché crypto
     34% observé, borne basse 20%, espérance -0.00R sur 93 signaux.

  Une espérance de -0.00R est déjà un système rentable.
  Le taux affiché compte moins que ce chiffre-là.

```
