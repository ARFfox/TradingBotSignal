# Rapport du Superviseur apprenant

généré le 2026-09-17 12:45 UTC · 841 signaux au journal · 577 résolus

```
==========================================================================
  SUPERVISEUR — AUTO-DIAGNOSTIC
==========================================================================

  -75.4R sur 577 résolus (841 émis, 264 jamais entrés)
  taux 28.1% · gain moyen +2.1R · équilibre à 32.3%
  ⚠ espérance -0.131R — il manque 4.2% points de réussite pour l'équilibre

  STOPS
    415 stops touchés · 15% par stop trop serré
    stop médian : 1.00 ATR · 45% sous 1.0 ATR
      indetermine          341
      stop_trop_serre      62
      direction_fausse     12

  CALIBRATION DE LA NOTE
    0%–20%     n=45   annoncé 11% → réel 22% · -0.34R
    20%–40%    n=309  annoncé 31% → réel 32% · -0.02R
    40%–60%    n=221  annoncé 45% → réel 24% · -0.23R
    60%–80%    n=2    annoncé 62% → réel 0% · -1.00R  (n trop faible)
    écart moyen 9.3% — exploitable

  AGENTS (poids mesuré, pas choisi)
    AG-01  n=513  poids ×0.10   discr. +0.24   vote quasiment toujours pareil — sans valeur
    AG-10  n=569  poids ×0.10   discr. -0.12   vote quasiment toujours pareil — sans valeur
    AG-05  n=569  poids ×0.59   discr. -0.41   contre-indicateur — inverser son vote

  COUPLES INSTRUMENT × TIMEFRAME
    BTC/USD    M5    n=20   -0.206R  COUPE
    XAU/USD    M5    n=20   -0.562R  COUPE

  SEUIL D'ÉMISSION
    AUCUN seuil ne rend le système positif — le problème n'est pas le filtrage, c'est la stratégie elle-même

    Aucun filtrage ne sauve ce système. Filtrer plus fort ne
    fait que perdre moins vite. Il faut corriger les stops et
    les conditions d'entrée avant de rechercher un seuil.

```
