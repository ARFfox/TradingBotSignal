# Chasse aux sous-ensembles

généré le 2026-09-16 16:28 UTC · 655 signaux au journal · 405 résolus

```
====================================================================================================
  EXISTE-T-IL UN SOUS-ENSEMBLE À 80% DANS TES DONNÉES ?
====================================================================================================

  Référence : R:R moyen 2.17 → une marche ALÉATOIRE touche le TP 31.5% du temps.
  Taux global actuel : 21.7% sur 405 résolus.

  ⚠ Le système est SOUS le hasard. Ce n'est pas « pas encore assez bon » :
    c'est une capacité de prédiction négative. La cause la plus probable est
    un stop placé dans le bruit — le prix le touche avant d'avoir bougé.

  26 sous-ensembles testés (correction des tests multiples appliquée)

  conditions                               n       taux       IC 95%   espér.  hors  verdict
  ------------------------------------------------------------------------------------------------
  vente + marché crypto                    n=97     35% [21%–53%]   +0.01R  hors: 42%  PROMETTEUR
  note >= 40 % + R:R >= 2,5                n=43     21% [7%–47%]   -0.06R  hors:  0%  HASARD
  note >= 40 % + marché crypto             n=32     31% [12%–61%]   -0.07R  hors: 40%  HASARD
  note >= 40 % + vente                     n=46     28% [12%–54%]   -0.08R  hors: 29%  HASARD
  R:R >= 2,5 + vente                       n=57     19% [7%–42%]   -0.13R  hors: 20%  HASARD
  R:R >= 2,5 + marché crypto               n=38     18% [6%–46%]   -0.17R  hors: 25%  HASARD
  R:R >= 2,5 + timeframe M5/M15            n=77     18% [8%–37%]   -0.20R  hors: 15%  HASARD
  marché crypto                            n=125    28% [17%–43%]   -0.20R  hors: 34%  HASARD
  vente                                    n=184    26% [16%–38%]   -0.23R  hors: 32%  HASARD
  timeframe M5/M15 + marché crypto         n=103    27% [15%–44%]   -0.24R  hors: 34%  HASARD
  timeframe M5/M15 + vente                 n=143    25% [15%–39%]   -0.24R  hors: 35%  HASARD
  R:R >= 2,5                               n=94     17% [8%–34%]   -0.24R  hors: 11%  HASARD
  note >= 40 % + timeframe M5/M15          n=68     21% [9%–41%]   -0.27R  hors: 18%  HASARD
  timeframe M5/M15                         n=215    23% [15%–34%]   -0.29R  hors: 24%  HASARD
  achat + marché matières                  n=32     22% [7%–52%]   -0.31R  hors: 16%  HASARD

  ================================================================================================

  Aucun sous-ensemble n'atteint 80%.
  Le meilleur edge confirmé : vente + marché crypto
     35% observé, borne basse 21%, espérance +0.01R sur 97 signaux.

  Une espérance de +0.01R est déjà un système rentable.
  Le taux affiché compte moins que ce chiffre-là.

```
