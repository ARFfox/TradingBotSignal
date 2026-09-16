# Chasse aux sous-ensembles

généré le 2026-09-16 16:39 UTC · 553 signaux au journal · 355 résolus

```
====================================================================================================
  EXISTE-T-IL UN SOUS-ENSEMBLE À 80% DANS TES DONNÉES ?
====================================================================================================

  Référence : R:R moyen 2.49 → une marche ALÉATOIRE touche le TP 28.7% du temps.
  Taux global actuel : 23.7% sur 355 résolus.

  ⚠ Le système est SOUS le hasard. Ce n'est pas « pas encore assez bon » :
    c'est une capacité de prédiction négative. La cause la plus probable est
    un stop placé dans le bruit — le prix le touche avant d'avoir bougé.

  26 sous-ensembles testés (correction des tests multiples appliquée)

  conditions                               n       taux       IC 95%   espér.  hors  verdict
  ------------------------------------------------------------------------------------------------
  vente + marché crypto                    n=80     38% [22%–57%]   +0.15R  hors: 47%  PROMETTEUR
  marché crypto                            n=105    30% [17%–46%]   -0.10R  hors: 42%  PROMETTEUR
  note >= 40 % + marché crypto             n=27     37% [14%–68%]   +0.10R  hors: 50%  NON VÉRIFIÉ
  note >= 40 % + vente                     n=41     32% [13%–58%]   +0.03R  hors: 29%  NON VÉRIFIÉ
  note >= 40 % + R:R >= 2,5                n=43     21% [7%–47%]   -0.06R  hors:  0%  HASARD
  R:R >= 2,5 + vente                       n=57     19% [7%–42%]   -0.13R  hors: 20%  HASARD
  timeframe M5/M15 + marché crypto         n=86     28% [15%–46%]   -0.15R  hors: 43%  HASARD
  vente                                    n=161    27% [17%–40%]   -0.16R  hors: 38%  HASARD
  R:R >= 2,5 + marché crypto               n=38     18% [6%–46%]   -0.17R  hors: 25%  HASARD
  timeframe M5/M15 + vente                 n=126    25% [15%–41%]   -0.19R  hors: 41%  HASARD
  R:R >= 2,5 + timeframe M5/M15            n=77     18% [8%–37%]   -0.20R  hors: 15%  HASARD
  note >= 40 % + timeframe M5/M15          n=62     23% [10%–44%]   -0.20R  hors: 20%  HASARD
  timeframe M5/M15                         n=189    24% [15%–36%]   -0.23R  hors: 29%  HASARD
  R:R >= 2,5                               n=94     17% [8%–34%]   -0.24R  hors: 11%  HASARD
  achat + marché matières                  n=29     21% [6%–53%]   -0.27R  hors: 16%  HASARD

  ================================================================================================

  Aucun sous-ensemble n'atteint 80%.
  Le meilleur edge confirmé : vente + marché crypto
     38% observé, borne basse 22%, espérance +0.15R sur 80 signaux.

  Une espérance de +0.15R est déjà un système rentable.
  Le taux affiché compte moins que ce chiffre-là.

```
