# Chasse aux sous-ensembles

généré le 2026-09-16 18:16 UTC · 576 signaux au journal · 400 résolus

```
====================================================================================================
  EXISTE-T-IL UN SOUS-ENSEMBLE À 80% DANS TES DONNÉES ?
====================================================================================================

  Référence : R:R moyen 2.45 → une marche ALÉATOIRE touche le TP 29.0% du temps.
  Taux global actuel : 27.0% sur 400 résolus.

  ⚠ Le système est SOUS le hasard. Ce n'est pas « pas encore assez bon » :
    c'est une capacité de prédiction négative. La cause la plus probable est
    un stop placé dans le bruit — le prix le touche avant d'avoir bougé.

  26 sous-ensembles testés (correction des tests multiples appliquée)

  conditions                               n       taux       IC 95%   espér.  hors  verdict
  ------------------------------------------------------------------------------------------------
  note >= 40 % + marché crypto             n=29     41% [17%–71%]   +0.20R  hors: 58%  PROMETTEUR
  vente + marché crypto                    n=98     37% [22%–54%]   +0.12R  hors: 62%  PROMETTEUR
  note >= 40 % + vente                     n=43     35% [16%–61%]   +0.10R  hors: 43%  PROMETTEUR
  marché crypto                            n=125    30% [18%–45%]   -0.10R  hors: 58%  PROMETTEUR
  note >= 40 % + R:R >= 2,5                n=44     20% [7%–46%]   -0.08R  hors:  0%  HASARD
  vente                                    n=180    27% [17%–40%]   -0.15R  hors: 52%  HASARD
  R:R >= 2,5 + vente                       n=63     19% [8%–40%]   -0.15R  hors: 46%  HASARD
  timeframe M5/M15 + marché crypto         n=102    27% [15%–44%]   -0.16R  hors: 59%  HASARD
  timeframe M5/M15 + vente                 n=141    26% [15%–40%]   -0.18R  hors: 53%  HASARD
  note >= 40 % + timeframe M5/M15          n=66     23% [10%–44%]   -0.20R  hors: 25%  HASARD
  R:R >= 2,5 + marché crypto               n=45     18% [6%–43%]   -0.22R  hors: 58%  HASARD
  timeframe M5/M15                         n=213    24% [15%–35%]   -0.23R  hors: 37%  HASARD
  R:R >= 2,5 + timeframe M5/M15            n=85     18% [8%–36%]   -0.23R  hors: 22%  HASARD
  R:R >= 2,5                               n=103    17% [8%–32%]   -0.27R  hors: 24%  HASARD
  achat + marché matières                  n=34     21% [6%–50%]   -0.29R  hors: 14%  HASARD

  ================================================================================================

  Aucun sous-ensemble n'atteint 80%.
  Le meilleur edge confirmé : vente + marché crypto
     37% observé, borne basse 22%, espérance +0.12R sur 98 signaux.

  Une espérance de +0.12R est déjà un système rentable.
  Le taux affiché compte moins que ce chiffre-là.

```
