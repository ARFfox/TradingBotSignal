# Chasse aux sous-ensembles

généré le 2026-09-17 10:49 UTC · 804 signaux au journal · 557 résolus

```
====================================================================================================
  EXISTE-T-IL UN SOUS-ENSEMBLE À 80% DANS TES DONNÉES ?
====================================================================================================

  Référence : R:R moyen 2.46 → une marche ALÉATOIRE touche le TP 28.9% du temps.
  Taux global actuel : 28.5% sur 557 résolus.

  ⚠ Le système est SOUS le hasard. Ce n'est pas « pas encore assez bon » :
    c'est une capacité de prédiction négative. La cause la plus probable est
    un stop placé dans le bruit — le prix le touche avant d'avoir bougé.

  27 sous-ensembles testés (correction des tests multiples appliquée)

  conditions                               n       taux       IC 95%   espér.  hors  verdict
  ------------------------------------------------------------------------------------------------
  vente + marché crypto                    n=134    40% [27%–55%]   +0.22R  hors: 57%  PROMETTEUR
  note >= 40 % + marché crypto             n=42     38% [18%–64%]   +0.10R  hors: 43%  PROMETTEUR
  marché crypto                            n=171    34% [23%–47%]   +0.03R  hors: 49%  PROMETTEUR
  timeframe M5/M15 + marché crypto         n=127    32% [20%–48%]   -0.01R  hors: 48%  PROMETTEUR
  timeframe M5/M15 + vente                 n=165    29% [19%–42%]   -0.09R  hors: 40%  PROMETTEUR
  vente                                    n=232    30% [21%–41%]   -0.09R  hors: 40%  PROMETTEUR
  note >= 40 % + vente                     n=61     30% [14%–52%]   -0.09R  hors: 35%  PROMETTEUR
  R:R >= 2,5 + marché crypto               n=54     22% [9%–46%]   -0.07R  hors: 45%  HASARD
  R:R >= 2,5 + vente                       n=77     19% [8%–39%]   -0.16R  hors: 33%  HASARD
  timeframe M5/M15                         n=277    26% [18%–36%]   -0.18R  hors: 38%  HASARD
  note >= 40 % + timeframe M5/M15          n=73     23% [11%–43%]   -0.20R  hors: 35%  HASARD
  R:R >= 2,5 + timeframe M5/M15            n=100    18% [8%–34%]   -0.23R  hors: 24%  HASARD
  note >= 40 % + R:R >= 2,5                n=59     15% [5%–37%]   -0.31R  hors: 17%  HASARD
  timeframe H1/H4                          n=24     25% [7%–60%]   -0.32R  hors: 14%  HASARD
  timeframe M5/M15 + achat                 n=112    21% [11%–37%]   -0.32R  hors: 37%  HASARD

  ================================================================================================

  Aucun sous-ensemble n'atteint 80%.
  Le meilleur edge confirmé : vente + marché crypto
     40% observé, borne basse 27%, espérance +0.22R sur 134 signaux.

  Une espérance de +0.22R est déjà un système rentable.
  Le taux affiché compte moins que ce chiffre-là.

```
