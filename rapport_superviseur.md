# Rapport du Superviseur apprenant

généré le 2026-09-17 10:49 UTC · 804 signaux au journal · 557 résolus

```
==========================================================================
  SUPERVISEUR — AUTO-DIAGNOSTIC
==========================================================================

  -64.6R sur 557 résolus (804 émis, 247 jamais entrés)
  taux 28.5% · gain moyen +2.1R · équilibre à 32.3%
  ⚠ espérance -0.116R — il manque 3.8% points de réussite pour l'équilibre

  STOPS
    398 stops touchés · 14% par stop trop serré
    stop médian : 1.00 ATR · 49% sous 1.0 ATR
      indetermine          332
      stop_trop_serre      57
      direction_fausse     9

  CALIBRATION DE LA NOTE
    0%–20%     n=42   annoncé 11% → réel 24% · -0.29R
    20%–40%    n=298  annoncé 31% → réel 33% · +0.00R
    40%–60%    n=215  annoncé 45% → réel 24% · -0.24R
    60%–80%    n=2    annoncé 62% → réel 0% · -1.00R  (n trop faible)
    écart moyen 10.0% — exploitable

  AGENTS (poids mesuré, pas choisi)
    AG-01  n=494  poids ×0.10   discr. +0.28   vote quasiment toujours pareil — sans valeur
    AG-10  n=549  poids ×0.10   discr. -0.17   vote quasiment toujours pareil — sans valeur
    AG-05  n=549  poids ×0.62   discr. -0.38   contre-indicateur — inverser son vote

  COUPLES INSTRUMENT × TIMEFRAME
    BTC/USD    M5    n=20   -0.206R  COUPE
    XAU/USD    M5    n=20   -0.562R  COUPE

  SEUIL D'ÉMISSION
    AUCUN seuil ne rend le système positif — le problème n'est pas le filtrage, c'est la stratégie elle-même

    Aucun filtrage ne sauve ce système. Filtrer plus fort ne
    fait que perdre moins vite. Il faut corriger les stops et
    les conditions d'entrée avant de rechercher un seuil.

```
